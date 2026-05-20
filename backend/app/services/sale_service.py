"""Service : ventes (caisse).

C'est le hub qui orchestre :
- Stock : décrément des lots (FIFO par péremption)
- Crédit client : vente à crédit → CreditEntry + échéancier
- Tiers payant : génération de claim
- Fidélité : points gagnés / utilisés
"""
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sale import Sale, SaleItem
from app.models.product import Product, ProductLot
from app.models.client import Client
from app.services.credit_service import CreditService
from app.services.third_party_service import ThirdPartyService


class SaleService:
    def __init__(self, db: AsyncSession, pharmacy_id: uuid.UUID, cashier_id: uuid.UUID | None = None):
        self.db = db
        self.pharmacy_id = pharmacy_id
        self.cashier_id = cashier_id

    async def _next_sale_number(self) -> str:
        result = await self.db.execute(
            select(func.count(Sale.id)).where(Sale.pharmacy_id == self.pharmacy_id)
        )
        count = result.scalar() or 0
        return f"V-{datetime.now().strftime('%Y%m')}-{count + 1:05d}"

    async def _get_fefo_lot(self, product_id: uuid.UUID) -> ProductLot | None:
        """Retourne le lot FEFO (périme le plus tôt, quantité > 0) d'un produit."""
        result = await self.db.execute(
            select(ProductLot)
            .where(
                ProductLot.pharmacy_id == self.pharmacy_id,
                ProductLot.product_id == product_id,
                ProductLot.quantity > 0,
            )
            .order_by(ProductLot.expiration_date.asc().nullslast())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _decrement_stock(self, product_id: uuid.UUID, quantity: int, lot_id: uuid.UUID | None) -> uuid.UUID | None:
        """Décrémente le stock : lot précisé sinon FIFO sur péremption."""
        if lot_id:
            lot = await self.db.get(ProductLot, lot_id)
            if not lot or lot.quantity < quantity:
                raise HTTPException(400, f"Stock lot insuffisant pour produit {product_id}")
            lot.quantity -= quantity
        else:
            # FIFO : lot le plus proche de la péremption
            result = await self.db.execute(
                select(ProductLot)
                .where(
                    ProductLot.pharmacy_id == self.pharmacy_id,
                    ProductLot.product_id == product_id,
                    ProductLot.quantity > 0,
                )
                .order_by(ProductLot.expiration_date.asc().nullslast())
            )
            lots = list(result.scalars().all())
            remaining = quantity
            for lot in lots:
                if remaining <= 0:
                    break
                take = min(lot.quantity, remaining)
                lot.quantity -= take
                remaining -= take
                if lot_id is None:
                    lot_id = lot.id
            if remaining > 0:
                # Pas assez en lots — on autorise quand même si stock global suffit
                # (compatibilité avec produits sans lot tracé)
                pass

        # Décrémenter stock global
        await self.db.execute(
            update(Product)
            .where(Product.id == product_id)
            .values(stock_quantity=Product.stock_quantity - quantity)
        )
        return lot_id

    async def create_sale(self, data: dict) -> Sale:
        """Création d'une vente complète.

        data attendu (cf schemas.sale.SaleCreate) :
        - items, client_id, third_party_payer_id, paid_cash/card/check, ...
        """
        # 1. Calcul des totaux par item
        items_computed = []
        subtotal_ht = Decimal("0")
        total_vat = Decimal("0")
        total_discount = Decimal("0")

        for it in data["items"]:
            product = await self.db.get(Product, uuid.UUID(str(it["product_id"])))
            if not product:
                raise HTTPException(404, f"Produit {it['product_id']} introuvable")
            if product.pharmacy_id != self.pharmacy_id:
                raise HTTPException(403, "Produit hors tenant")

            qty = int(it["quantity"])
            # Prix de vente : priorité au prix explicite fourni, sinon PPV du lot FEFO,
            # sinon prix de référence du produit. C'est le besoin métier marocain :
            # le PPV est imprimé sur la boîte et peut varier d'un lot à l'autre.
            explicit_price = it.get("unit_price_ttc")
            fefo_lot = None
            if explicit_price is not None:
                unit_ttc = Decimal(str(explicit_price))
            else:
                fefo_lot = await self._get_fefo_lot(product.id)
                if fefo_lot is not None and fefo_lot.sale_price_ttc is not None:
                    unit_ttc = Decimal(str(fefo_lot.sale_price_ttc))
                else:
                    unit_ttc = Decimal(str(product.sale_price_ttc))
            vat = product.vat_rate
            discount = Decimal(str(it.get("discount_rate", 0)))
            unit_ht = unit_ttc / (Decimal("1") + vat)

            line_ttc_gross = unit_ttc * qty
            line_discount = line_ttc_gross * discount
            line_ttc_net = line_ttc_gross - line_discount
            line_ht_net = line_ttc_net / (Decimal("1") + vat)
            line_vat = line_ttc_net - line_ht_net

            items_computed.append({
                "product_id": product.id,
                "lot_id": it.get("lot_id"),
                "quantity": qty,
                "unit_price_ht": unit_ht.quantize(Decimal("0.0001")),
                "unit_price_ttc": unit_ttc.quantize(Decimal("0.0001")),
                "discount_rate": discount,
                "vat_rate": vat,
                "line_total_ttc": line_ttc_net.quantize(Decimal("0.01")),
                "is_reimbursable": it.get("is_reimbursable", product.is_reimbursable),
            })
            subtotal_ht += line_ht_net
            total_vat += line_vat
            total_discount += line_discount

        total_ttc = (subtotal_ht + total_vat).quantize(Decimal("0.01"))

        # 2. Tiers payant : calcul de la répartition
        payer_share = Decimal("0")
        client_share = total_ttc
        coverage_rate = None
        payer_id = data.get("third_party_payer_id")
        if payer_id:
            tp_service = ThirdPartyService(self.db, self.pharmacy_id)
            coverage_rate, payer_share, client_share = await tp_service.compute_coverage(
                uuid.UUID(str(payer_id)),
                total_ttc,
                Decimal(str(data["third_party_coverage_rate"])) if data.get("third_party_coverage_rate") else None,
                items_computed,
            )

        # 3. Vérification crédit si la part client n'est pas entièrement encaissée
        paid_cash = Decimal(str(data.get("paid_cash", 0)))
        paid_card = Decimal(str(data.get("paid_card", 0)))
        paid_check = Decimal(str(data.get("paid_check", 0)))
        paid_immediate = paid_cash + paid_card + paid_check
        paid_credit = client_share - paid_immediate

        client_id = data.get("client_id")
        if paid_credit > 0:
            if not client_id:
                raise HTTPException(400, "Vente à crédit nécessite un client")
            credit_svc = CreditService(self.db, self.pharmacy_id)
            ok, msg = await credit_svc.check_credit_limit(uuid.UUID(str(client_id)), paid_credit)
            if not ok:
                raise HTTPException(400, f"Crédit refusé : {msg}")

        # 4. Création de la vente
        sale = Sale(
            pharmacy_id=self.pharmacy_id,
            sale_number=await self._next_sale_number(),
            sale_date=datetime.utcnow(),
            cashier_id=self.cashier_id,
            client_id=uuid.UUID(str(client_id)) if client_id else None,
            has_prescription=data.get("has_prescription", False),
            prescription_number=data.get("prescription_number"),
            prescriber_name=data.get("prescriber_name"),
            prescriber_inpe=data.get("prescriber_inpe"),
            third_party_payer_id=uuid.UUID(str(payer_id)) if payer_id else None,
            third_party_coverage_rate=coverage_rate,
            subtotal_ht=subtotal_ht.quantize(Decimal("0.01")),
            total_vat=total_vat.quantize(Decimal("0.01")),
            total_discount=total_discount.quantize(Decimal("0.01")),
            total_ttc=total_ttc,
            payer_share=payer_share,
            client_share=client_share,
            paid_cash=paid_cash,
            paid_card=paid_card,
            paid_check=paid_check,
            paid_credit=max(paid_credit, Decimal("0")),
            payment_method=(
                "third_party" if payer_id and paid_credit <= 0 else
                "credit" if paid_credit > 0 else
                "cash" if paid_cash > 0 else
                "card" if paid_card > 0 else
                "check" if paid_check > 0 else "cash"
            ),
            status="completed",
            loyalty_points_used=data.get("loyalty_points_used", 0),
            notes=data.get("notes"),
        )
        self.db.add(sale)
        await self.db.flush()

        # 5. Items + stock
        for it in items_computed:
            lot_id = await self._decrement_stock(it["product_id"], it["quantity"], it.get("lot_id"))
            sale_item = SaleItem(
                pharmacy_id=self.pharmacy_id,
                sale_id=sale.id,
                product_id=it["product_id"],
                lot_id=lot_id,
                quantity=it["quantity"],
                unit_price_ht=it["unit_price_ht"],
                unit_price_ttc=it["unit_price_ttc"],
                discount_rate=it["discount_rate"],
                vat_rate=it["vat_rate"],
                line_total_ttc=it["line_total_ttc"],
                is_reimbursable=it["is_reimbursable"],
            )
            self.db.add(sale_item)

        # 6. Crédit client
        if paid_credit > 0 and client_id:
            credit_svc = CreditService(self.db, self.pharmacy_id)
            client = await self.db.get(Client, uuid.UUID(str(client_id)))
            terms = client.default_payment_terms_days if client else 30
            await credit_svc.record_sale_on_credit(
                client_id=uuid.UUID(str(client_id)),
                sale_id=sale.id,
                amount=paid_credit,
                due_dates=data.get("due_dates"),
                default_terms_days=terms,
            )

        # 7. Tiers payant : claim
        if payer_id and payer_share > 0:
            tp_service = ThirdPartyService(self.db, self.pharmacy_id)
            await tp_service.create_claim_from_sale(
                sale_id=sale.id,
                payer_id=uuid.UUID(str(payer_id)),
                coverage_rate=coverage_rate,
            )

        # 8. Fidélité : 1 point par tranche de 10 MAD payée cash/card/check
        loyalty_earned = int(paid_immediate / 10) if paid_immediate > 0 else 0
        sale.loyalty_points_earned = loyalty_earned
        if client_id and loyalty_earned > 0:
            client = await self.db.get(Client, uuid.UUID(str(client_id)))
            if client:
                client.loyalty_points += loyalty_earned
                if data.get("loyalty_points_used", 0) > 0:
                    client.loyalty_points -= data["loyalty_points_used"]

        await self.db.flush()
        return sale
