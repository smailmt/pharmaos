"""Service : tiers payants.

Logique :
- compute_coverage : à partir d'une vente et d'un organisme, calcule part payeur / part client.
- create_claim_from_sale : génère la claim quand on encaisse une vente avec tiers payant.
- generate_bordereau : agrège les claims pending d'une période en un bordereau.
- record_payment : impute le règlement de l'organisme, marque claims payées, gère les refus.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.third_party import (
    ThirdPartyPayer, ThirdPartyClaim, ThirdPartyBordereau, ThirdPartyPayment,
)
from app.models.sale import Sale, SaleItem


class ThirdPartyService:
    def __init__(self, db: AsyncSession, pharmacy_id: uuid.UUID):
        self.db = db
        self.pharmacy_id = pharmacy_id

    async def compute_coverage(
        self,
        payer_id: uuid.UUID,
        total_amount: Decimal,
        coverage_rate: Decimal | None = None,
        items: list[dict] | None = None,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Calcule (taux_effectif, part_payeur, part_client).

        Applique :
        - rules.excluded_categories : produits non couverts
        - max_coverage_per_claim : plafond
        - rate explicite ou rate par défaut de l'organisme
        """
        payer = await self.db.get(ThirdPartyPayer, payer_id)
        if not payer:
            raise ValueError("Organisme introuvable")

        effective_rate = coverage_rate if coverage_rate is not None else payer.default_coverage_rate
        rules = payer.rules or {}

        # Si items fournis, retirer les exclusions
        reimbursable_amount = total_amount
        if items:
            excluded_cats = set(rules.get("excluded_categories", []))
            non_reimb_only = rules.get("reimbursable_products_only", False)
            reimbursable_amount = Decimal("0")
            for it in items:
                if non_reimb_only and not it.get("is_reimbursable", True):
                    continue
                if excluded_cats and it.get("category") in excluded_cats:
                    continue
                reimbursable_amount += Decimal(str(it.get("line_total_ttc", 0)))

        payer_share = (reimbursable_amount * effective_rate).quantize(Decimal("0.01"))

        # Plafond
        if payer.max_coverage_per_claim and payer_share > payer.max_coverage_per_claim:
            payer_share = payer.max_coverage_per_claim

        # Minimum
        min_amount = Decimal(str(rules.get("min_amount", 0)))
        if reimbursable_amount < min_amount:
            payer_share = Decimal("0")

        client_share = total_amount - payer_share
        return effective_rate, payer_share, client_share

    async def create_claim_from_sale(
        self,
        sale_id: uuid.UUID,
        payer_id: uuid.UUID,
        coverage_rate: Decimal | None = None,
    ) -> ThirdPartyClaim:
        """Génère une claim à partir d'une vente."""
        sale = await self.db.get(Sale, sale_id)
        if not sale:
            raise ValueError("Vente introuvable")

        # Récupérer items pour calcul fin
        result = await self.db.execute(
            select(SaleItem).where(SaleItem.sale_id == sale_id)
        )
        items_orm = list(result.scalars().all())
        items_data = [
            {
                "line_total_ttc": it.line_total_ttc,
                "is_reimbursable": it.is_reimbursable,
            }
            for it in items_orm
        ]

        rate, payer_share, client_share = await self.compute_coverage(
            payer_id, sale.total_ttc, coverage_rate, items_data,
        )

        claim = ThirdPartyClaim(
            pharmacy_id=self.pharmacy_id,
            payer_id=payer_id,
            client_id=sale.client_id,
            sale_id=sale_id,
            claim_date=date.today(),
            prescription_number=sale.prescription_number,
            prescriber_name=sale.prescriber_name,
            prescriber_inpe=sale.prescriber_inpe,
            total_amount=sale.total_ttc,
            coverage_rate=rate,
            payer_share=payer_share,
            client_share=client_share,
            status="pending",
        )
        self.db.add(claim)
        await self.db.flush()
        return claim

    async def generate_bordereau(
        self,
        payer_id: uuid.UUID,
        period_start: date,
        period_end: date,
        claim_ids: list[uuid.UUID] | None = None,
    ) -> ThirdPartyBordereau:
        """Crée un bordereau qui regroupe les claims pending d'une période.

        Si claim_ids fourni : utilise exactement ces claims.
        Sinon : prend toutes les claims 'pending' du payer sur la période.
        """
        # Compter les bordereaux existants pour générer le numéro
        result = await self.db.execute(
            select(func.count(ThirdPartyBordereau.id))
            .where(ThirdPartyBordereau.pharmacy_id == self.pharmacy_id)
        )
        count = result.scalar() or 0
        bordereau_number = f"BORD-{datetime.now().year}-{count + 1:05d}"

        bordereau = ThirdPartyBordereau(
            pharmacy_id=self.pharmacy_id,
            payer_id=payer_id,
            bordereau_number=bordereau_number,
            period_start=period_start,
            period_end=period_end,
            status="draft",
            total_amount=Decimal("0"),
        )
        self.db.add(bordereau)
        await self.db.flush()

        # Sélectionner les claims
        if claim_ids:
            q = select(ThirdPartyClaim).where(
                ThirdPartyClaim.pharmacy_id == self.pharmacy_id,
                ThirdPartyClaim.id.in_(claim_ids),
                ThirdPartyClaim.status == "pending",
            )
        else:
            q = select(ThirdPartyClaim).where(
                ThirdPartyClaim.pharmacy_id == self.pharmacy_id,
                ThirdPartyClaim.payer_id == payer_id,
                ThirdPartyClaim.status == "pending",
                ThirdPartyClaim.claim_date >= period_start,
                ThirdPartyClaim.claim_date <= period_end,
            )

        result = await self.db.execute(q)
        claims = list(result.scalars().all())

        total = Decimal("0")
        for claim in claims:
            claim.bordereau_id = bordereau.id
            claim.status = "bordereau_pending"
            total += claim.payer_share

        bordereau.total_amount = total
        await self.db.flush()
        return bordereau

    async def submit_bordereau(self, bordereau_id: uuid.UUID) -> ThirdPartyBordereau:
        """Marque le bordereau comme envoyé à l'organisme."""
        bordereau = await self.db.get(ThirdPartyBordereau, bordereau_id)
        if not bordereau:
            raise ValueError("Bordereau introuvable")
        bordereau.status = "submitted"
        bordereau.submitted_at = datetime.utcnow()

        # Marquer toutes les claims du bordereau comme submitted
        result = await self.db.execute(
            select(ThirdPartyClaim).where(ThirdPartyClaim.bordereau_id == bordereau_id)
        )
        for claim in result.scalars().all():
            claim.status = "submitted"

        await self.db.flush()
        return bordereau

    async def record_bordereau_payment(
        self,
        bordereau_id: uuid.UUID,
        amount: Decimal,
        payment_date: date | None = None,
        payment_method: str = "transfer",
        reference: str | None = None,
        rejected_claim_ids: list[uuid.UUID] | None = None,
        rejection_reasons: dict | None = None,
        notes: str | None = None,
    ) -> ThirdPartyPayment:
        """Enregistre un règlement de l'organisme.

        - Marque les claims non-refusées comme payées (proportionnellement si paiement < total).
        - Marque les claims refusées avec motif.
        """
        bordereau = await self.db.get(ThirdPartyBordereau, bordereau_id)
        if not bordereau:
            raise ValueError("Bordereau introuvable")

        payment = ThirdPartyPayment(
            pharmacy_id=self.pharmacy_id,
            bordereau_id=bordereau_id,
            payment_date=payment_date or date.today(),
            amount=amount,
            payment_method=payment_method,
            reference=reference,
            notes=notes,
        )
        self.db.add(payment)

        # Récupérer toutes les claims du bordereau
        result = await self.db.execute(
            select(ThirdPartyClaim).where(ThirdPartyClaim.bordereau_id == bordereau_id)
        )
        claims = list(result.scalars().all())

        rejected_ids = set(rejected_claim_ids or [])
        reasons = rejection_reasons or {}

        # Traiter rejets
        for claim in claims:
            if claim.id in rejected_ids:
                claim.status = "rejected"
                claim.rejection_reason = reasons.get(str(claim.id), "Non précisé")

        # Distribuer le paiement sur les claims non-rejetées (proportionnel)
        accepted = [c for c in claims if c.id not in rejected_ids]
        total_accepted = sum((c.payer_share for c in accepted), Decimal("0"))

        if total_accepted > 0 and amount > 0:
            ratio = min(amount / total_accepted, Decimal("1"))
            distributed = Decimal("0")
            for c in accepted:
                share = (c.payer_share * ratio).quantize(Decimal("0.01"))
                c.amount_paid = share
                if share >= c.payer_share:
                    c.status = "paid"
                else:
                    c.status = "partially_paid"
                distributed += share

        # Mettre à jour le bordereau
        bordereau.amount_paid += amount
        if bordereau.amount_paid >= bordereau.total_amount:
            bordereau.status = "paid"
        elif bordereau.amount_paid > 0:
            bordereau.status = "partially_paid"

        await self.db.flush()
        return payment
