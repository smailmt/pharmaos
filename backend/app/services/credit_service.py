"""Service : gestion des crédits clients.

Logique métier :
- Solde courant = somme des CreditEntry signés.
- Paiement = entry négative + allocation FIFO sur les CreditDueDate ouvertes.
- Balance âgée = ventilation par tranches (0-30, 31-60, 61-90, 90+).
- Relances auto : repère les échéances en retard et propose de relancer.
"""
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, CreditEntry, CreditDueDate, CreditReminder
from app.schemas.client import AgingReport, AgingBucket


class CreditService:
    def __init__(self, db: AsyncSession, pharmacy_id: uuid.UUID):
        self.db = db
        self.pharmacy_id = pharmacy_id

    async def get_balance(self, client_id: uuid.UUID) -> Decimal:
        """Solde courant du client (positif = doit à la pharmacie)."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(CreditEntry.amount), 0))
            .where(
                CreditEntry.pharmacy_id == self.pharmacy_id,
                CreditEntry.client_id == client_id,
            )
        )
        return Decimal(str(result.scalar() or 0))

    async def get_overdue_amount(self, client_id: uuid.UUID, as_of: date | None = None) -> Decimal:
        """Montant des échéances en retard."""
        as_of = as_of or date.today()
        result = await self.db.execute(
            select(func.coalesce(func.sum(CreditDueDate.amount_due - CreditDueDate.amount_paid), 0))
            .where(
                CreditDueDate.pharmacy_id == self.pharmacy_id,
                CreditDueDate.client_id == client_id,
                CreditDueDate.due_date < as_of,
                CreditDueDate.status.in_(["pending", "partial"]),
            )
        )
        return Decimal(str(result.scalar() or 0))

    async def check_credit_limit(self, client_id: uuid.UUID, additional_amount: Decimal) -> tuple[bool, str]:
        """Vérifie si le client peut bénéficier d'un crédit supplémentaire.

        Retourne (autorisé, message).
        """
        client = await self.db.get(Client, client_id)
        if not client:
            return False, "Client introuvable"
        if not client.credit_enabled:
            return False, "Crédit non activé pour ce client"

        current = await self.get_balance(client_id)
        future = current + additional_amount
        if client.credit_limit > 0 and future > client.credit_limit:
            return False, (
                f"Plafond dépassé : solde actuel {current} MAD + {additional_amount} MAD "
                f"= {future} MAD > plafond {client.credit_limit} MAD"
            )

        overdue = await self.get_overdue_amount(client_id)
        if overdue > 0:
            return False, f"Client a {overdue} MAD d'échéances en retard"

        return True, "OK"

    async def record_sale_on_credit(
        self,
        client_id: uuid.UUID,
        sale_id: uuid.UUID,
        amount: Decimal,
        due_dates: list[dict] | None = None,
        default_terms_days: int = 30,
    ) -> CreditEntry:
        """Enregistre une vente à crédit : entry + échéancier."""
        entry = CreditEntry(
            pharmacy_id=self.pharmacy_id,
            client_id=client_id,
            entry_type="sale",
            amount=amount,
            entry_date=date.today(),
            sale_id=sale_id,
        )
        self.db.add(entry)

        # Échéancier : explicite OU une seule échéance au terme par défaut
        if due_dates:
            for d in due_dates:
                self.db.add(CreditDueDate(
                    pharmacy_id=self.pharmacy_id,
                    client_id=client_id,
                    sale_id=sale_id,
                    due_date=d["due_date"] if isinstance(d["due_date"], date) else date.fromisoformat(d["due_date"]),
                    amount_due=Decimal(str(d["amount_due"])),
                    status="pending",
                ))
        else:
            self.db.add(CreditDueDate(
                pharmacy_id=self.pharmacy_id,
                client_id=client_id,
                sale_id=sale_id,
                due_date=date.today() + timedelta(days=default_terms_days),
                amount_due=amount,
                status="pending",
            ))

        await self.db.flush()
        return entry

    async def record_payment(
        self,
        client_id: uuid.UUID,
        amount: Decimal,
        payment_method: str = "cash",
        payment_date: date | None = None,
        reference: str | None = None,
        notes: str | None = None,
    ) -> tuple[CreditEntry, list[CreditDueDate]]:
        """Enregistre un paiement et l'alloue FIFO sur les échéances ouvertes.

        Retourne (entry, [due_dates_affectées])
        """
        payment_date = payment_date or date.today()

        # 1. Créer l'entry (négative)
        entry = CreditEntry(
            pharmacy_id=self.pharmacy_id,
            client_id=client_id,
            entry_type="payment",
            amount=-amount,
            entry_date=payment_date,
            payment_method=payment_method,
            reference=reference,
            notes=notes,
        )
        self.db.add(entry)

        # 2. Allocation FIFO sur les échéances ouvertes (plus anciennes d'abord)
        result = await self.db.execute(
            select(CreditDueDate)
            .where(
                CreditDueDate.pharmacy_id == self.pharmacy_id,
                CreditDueDate.client_id == client_id,
                CreditDueDate.status.in_(["pending", "partial"]),
            )
            .order_by(CreditDueDate.due_date.asc())
        )
        open_dues = list(result.scalars().all())

        affected: list[CreditDueDate] = []
        remaining = amount

        for due in open_dues:
            if remaining <= 0:
                break
            due_remaining = due.amount_due - due.amount_paid
            to_apply = min(remaining, due_remaining)
            due.amount_paid += to_apply
            remaining -= to_apply
            if due.amount_paid >= due.amount_due:
                due.status = "paid"
                due.paid_at = datetime.utcnow()
            else:
                due.status = "partial"
            affected.append(due)

        # Si reste un crédit (overpayment), on le laisse en solde négatif (avoir client)
        await self.db.flush()
        return entry, affected

    async def get_overdue_due_dates(self, days_overdue: int = 0) -> list[CreditDueDate]:
        """Liste les échéances en retard (toute la pharmacie)."""
        cutoff = date.today() - timedelta(days=days_overdue)
        result = await self.db.execute(
            select(CreditDueDate)
            .where(
                CreditDueDate.pharmacy_id == self.pharmacy_id,
                CreditDueDate.due_date <= cutoff,
                CreditDueDate.status.in_(["pending", "partial"]),
            )
            .order_by(CreditDueDate.due_date.asc())
        )
        return list(result.scalars().all())

    async def get_due_soon(self, days_ahead: int = 3) -> list[CreditDueDate]:
        """Échéances arrivant à terme dans les X jours."""
        today = date.today()
        end = today + timedelta(days=days_ahead)
        result = await self.db.execute(
            select(CreditDueDate)
            .where(
                CreditDueDate.pharmacy_id == self.pharmacy_id,
                CreditDueDate.due_date >= today,
                CreditDueDate.due_date <= end,
                CreditDueDate.status.in_(["pending", "partial"]),
            )
            .order_by(CreditDueDate.due_date.asc())
        )
        return list(result.scalars().all())

    async def aging_report(self, as_of: date | None = None) -> AgingReport:
        """Balance âgée : ventile les créances par tranches d'ancienneté."""
        as_of = as_of or date.today()

        # Buckets : 0-30, 31-60, 61-90, 90+ jours après date d'échéance
        buckets_def = [
            ("0-30", 0, 30),
            ("31-60", 31, 60),
            ("61-90", 61, 90),
            ("90+", 91, 99999),
        ]

        buckets: list[AgingBucket] = []
        total = Decimal("0")

        for label, min_days, max_days in buckets_def:
            min_date = as_of - timedelta(days=max_days)
            max_date = as_of - timedelta(days=min_days)
            result = await self.db.execute(
                select(
                    func.coalesce(func.sum(CreditDueDate.amount_due - CreditDueDate.amount_paid), 0),
                    func.count(func.distinct(CreditDueDate.client_id)),
                )
                .where(
                    CreditDueDate.pharmacy_id == self.pharmacy_id,
                    CreditDueDate.due_date >= min_date,
                    CreditDueDate.due_date <= max_date,
                    CreditDueDate.status.in_(["pending", "partial"]),
                )
            )
            row = result.one()
            amount = Decimal(str(row[0] or 0))
            count = int(row[1] or 0)
            buckets.append(AgingBucket(bucket=label, amount=amount, clients_count=count))
            total += amount

        return AgingReport(as_of_date=as_of, total_outstanding=total, buckets=buckets)

    async def update_risk_score(self, client_id: uuid.UUID) -> int:
        """Recalcule le score de risque (0-100, plus haut = plus risqué).

        Critères simples :
        - Échéances en retard
        - Montant impayé / plafond
        - Historique de retards
        """
        client = await self.db.get(Client, client_id)
        if not client:
            return 0

        score = 0
        overdue = await self.get_overdue_amount(client_id)
        balance = await self.get_balance(client_id)

        if overdue > 0:
            score += 30
        if client.credit_limit > 0 and balance > 0:
            usage = balance / client.credit_limit
            if usage > Decimal("0.9"):
                score += 25
            elif usage > Decimal("0.7"):
                score += 15

        # Nombre d'échéances historiquement payées en retard
        from sqlalchemy import cast, Date
        result = await self.db.execute(
            select(func.count())
            .where(
                CreditDueDate.pharmacy_id == self.pharmacy_id,
                CreditDueDate.client_id == client_id,
                CreditDueDate.paid_at.isnot(None),
                cast(CreditDueDate.paid_at, Date) > CreditDueDate.due_date,
            )
        )
        late_count = int(result.scalar() or 0)
        score += min(late_count * 5, 30)

        score = min(score, 100)
        client.risk_score = score
        await self.db.flush()
        return score

    async def create_reminder(
        self,
        client_id: uuid.UUID,
        due_date_id: uuid.UUID | None = None,
        channel: str = "manual",
        message: str | None = None,
    ) -> CreditReminder:
        """Trace une relance effectuée."""
        reminder = CreditReminder(
            pharmacy_id=self.pharmacy_id,
            client_id=client_id,
            due_date_id=due_date_id,
            channel=channel,
            message=message,
            sent_at=datetime.utcnow(),
            success=True,
        )
        self.db.add(reminder)
        await self.db.flush()
        return reminder
