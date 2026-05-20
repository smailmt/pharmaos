"""Service : fournisseurs.

Logique :
- create_purchase_order : crée un BC avec calcul des totaux.
- receive_delivery : crée un BL et met à jour le stock (lots).
- register_invoice : crée une facture fournisseur (dette).
- pay_invoice : enregistre un paiement et solde la facture.
- get_supplier_balance : calcule la dette nette envers un fournisseur.
"""
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import (
    Supplier, SupplierProduct, PurchaseOrder, PurchaseOrderItem,
    DeliveryNote, DeliveryNoteItem,
    SupplierInvoice, SupplierPayment,
    SupplierReturn, SupplierReturnItem,
)
from app.models.product import Product, ProductLot


class SupplierService:
    def __init__(self, db: AsyncSession, pharmacy_id: uuid.UUID):
        self.db = db
        self.pharmacy_id = pharmacy_id

    async def _next_number(self, model, field: str, prefix: str) -> str:
        """Génère un numéro de document : PREFIX-YYYY-00001."""
        result = await self.db.execute(
            select(func.count(model.id)).where(model.pharmacy_id == self.pharmacy_id)
        )
        count = result.scalar() or 0
        return f"{prefix}-{datetime.now().year}-{count + 1:05d}"

    # ---------- Purchase Orders ----------
    async def create_purchase_order(
        self,
        supplier_id: uuid.UUID,
        items: list[dict],
        order_date: date | None = None,
        expected_delivery_date: date | None = None,
        notes: str | None = None,
    ) -> PurchaseOrder:
        order_number = await self._next_number(PurchaseOrder, "order_number", "BC")

        po = PurchaseOrder(
            pharmacy_id=self.pharmacy_id,
            supplier_id=supplier_id,
            order_number=order_number,
            order_date=order_date or date.today(),
            expected_delivery_date=expected_delivery_date,
            notes=notes,
            status="draft",
        )
        self.db.add(po)
        await self.db.flush()

        total_ht = Decimal("0")
        total_vat = Decimal("0")
        total_discount = Decimal("0")

        for it in items:
            qty = int(it["quantity_ordered"])
            unit_ht = Decimal(str(it["unit_price_ht"]))
            discount = Decimal(str(it.get("discount_rate", 0)))
            vat = Decimal(str(it.get("vat_rate", "0.07")))

            line_ht_gross = unit_ht * qty
            line_discount = line_ht_gross * discount
            line_ht_net = line_ht_gross - line_discount
            line_vat = line_ht_net * vat
            line_ttc = line_ht_net + line_vat

            item = PurchaseOrderItem(
                pharmacy_id=self.pharmacy_id,
                purchase_order_id=po.id,
                product_id=uuid.UUID(str(it["product_id"])),
                quantity_ordered=qty,
                unit_price_ht=unit_ht,
                discount_rate=discount,
                vat_rate=vat,
                line_total_ht=line_ht_net.quantize(Decimal("0.01")),
                line_total_ttc=line_ttc.quantize(Decimal("0.01")),
            )
            self.db.add(item)
            total_ht += line_ht_net
            total_vat += line_vat
            total_discount += line_discount

        po.total_ht = total_ht.quantize(Decimal("0.01"))
        po.total_vat = total_vat.quantize(Decimal("0.01"))
        po.total_discount = total_discount.quantize(Decimal("0.01"))
        po.total_ttc = (total_ht + total_vat).quantize(Decimal("0.01"))

        await self.db.flush()
        return po

    async def send_purchase_order(self, po_id: uuid.UUID) -> PurchaseOrder:
        po = await self.db.get(PurchaseOrder, po_id)
        if not po:
            raise ValueError("Bon de commande introuvable")
        po.status = "sent"
        po.sent_at = datetime.utcnow()
        await self.db.flush()
        return po

    # ---------- Delivery Notes ----------
    async def receive_delivery(
        self,
        supplier_id: uuid.UUID,
        delivery_number: str,
        items: list[dict],
        purchase_order_id: uuid.UUID | None = None,
        delivery_date: date | None = None,
        received_by: uuid.UUID | None = None,
        notes: str | None = None,
    ) -> DeliveryNote:
        """Réception BL : crée lots, incrémente stock, détecte écarts."""
        dn = DeliveryNote(
            pharmacy_id=self.pharmacy_id,
            supplier_id=supplier_id,
            purchase_order_id=purchase_order_id,
            delivery_number=delivery_number,
            delivery_date=delivery_date or date.today(),
            received_by=received_by,
            status="received",
            notes=notes,
        )
        self.db.add(dn)
        await self.db.flush()

        total_ht = Decimal("0")
        total_ttc = Decimal("0")
        has_discrepancies = False

        for it in items:
            qty_received = int(it["quantity_received"])
            qty_ordered = int(it.get("quantity_ordered", 0) or 0)
            unit_ht = Decimal(str(it["unit_price_ht"]))
            discount = Decimal(str(it.get("discount_rate", 0)))
            vat = Decimal(str(it.get("vat_rate", "0.07")))
            line_ht = unit_ht * qty_received * (Decimal("1") - discount)
            line_ttc = line_ht * (Decimal("1") + vat)

            if qty_ordered and qty_ordered != qty_received:
                has_discrepancies = True

            dn_item = DeliveryNoteItem(
                pharmacy_id=self.pharmacy_id,
                delivery_note_id=dn.id,
                product_id=uuid.UUID(str(it["product_id"])),
                lot_number=it.get("lot_number"),
                expiration_date=it.get("expiration_date"),
                quantity_ordered=qty_ordered,
                quantity_received=qty_received,
                unit_price_ht=unit_ht,
                discount_rate=discount,
                vat_rate=vat,
                line_total_ttc=line_ttc.quantize(Decimal("0.01")),
                discrepancy_note=it.get("discrepancy_note"),
            )
            self.db.add(dn_item)
            total_ht += line_ht
            total_ttc += line_ttc

            # Créer le lot et incrémenter le stock du produit
            if it.get("lot_number"):
                # PPV du lot : priorité au PPV saisi, sinon catalogue fournisseur
                lot_ppv = it.get("sale_price_ttc")
                if lot_ppv is None:
                    cat_result = await self.db.execute(
                        select(SupplierProduct.ppv).where(
                            SupplierProduct.pharmacy_id == self.pharmacy_id,
                            SupplierProduct.supplier_id == supplier_id,
                            SupplierProduct.product_id == uuid.UUID(str(it["product_id"])),
                        )
                    )
                    lot_ppv = cat_result.scalar_one_or_none()

                lot = ProductLot(
                    pharmacy_id=self.pharmacy_id,
                    product_id=uuid.UUID(str(it["product_id"])),
                    lot_number=it["lot_number"],
                    quantity=qty_received,
                    expiration_date=it.get("expiration_date"),
                    purchase_price_ht=unit_ht,
                    sale_price_ttc=Decimal(str(lot_ppv)) if lot_ppv is not None else None,
                )
                self.db.add(lot)

            # Incrémenter stock global
            await self.db.execute(
                update(Product)
                .where(Product.id == uuid.UUID(str(it["product_id"])))
                .values(stock_quantity=Product.stock_quantity + qty_received)
            )

            # Mise à jour PO si rattaché
            if purchase_order_id:
                result = await self.db.execute(
                    select(PurchaseOrderItem).where(
                        PurchaseOrderItem.purchase_order_id == purchase_order_id,
                        PurchaseOrderItem.product_id == uuid.UUID(str(it["product_id"])),
                    )
                )
                po_item = result.scalar_one_or_none()
                if po_item:
                    po_item.quantity_received += qty_received

        dn.total_ht = total_ht.quantize(Decimal("0.01"))
        dn.total_ttc = total_ttc.quantize(Decimal("0.01"))
        dn.has_discrepancies = has_discrepancies

        # Mettre à jour le statut du PO si rattaché
        if purchase_order_id:
            po = await self.db.get(PurchaseOrder, purchase_order_id)
            if po:
                result = await self.db.execute(
                    select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == po.id)
                )
                po_items = list(result.scalars().all())
                all_received = all(i.quantity_received >= i.quantity_ordered for i in po_items)
                any_received = any(i.quantity_received > 0 for i in po_items)
                if all_received:
                    po.status = "received"
                elif any_received:
                    po.status = "partially_received"

        await self.db.flush()
        return dn

    # ---------- Invoices ----------
    async def register_invoice(
        self,
        supplier_id: uuid.UUID,
        invoice_number: str,
        invoice_date: date,
        total_ht: Decimal,
        total_vat: Decimal,
        total_ttc: Decimal,
        due_date: date | None = None,
        delivery_note_ids: list[uuid.UUID] | None = None,
        notes: str | None = None,
    ) -> SupplierInvoice:
        supplier = await self.db.get(Supplier, supplier_id)
        if not supplier:
            raise ValueError("Fournisseur introuvable")

        if due_date is None:
            due_date = invoice_date + timedelta(days=supplier.payment_terms_days)

        invoice = SupplierInvoice(
            pharmacy_id=self.pharmacy_id,
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            due_date=due_date,
            received_date=date.today(),
            total_ht=total_ht,
            total_vat=total_vat,
            total_ttc=total_ttc,
            amount_paid=Decimal("0"),
            status="pending",
            delivery_note_ids=[str(i) for i in (delivery_note_ids or [])],
            notes=notes,
        )
        self.db.add(invoice)

        # Marquer les BL comme facturés
        if delivery_note_ids:
            for dn_id in delivery_note_ids:
                dn = await self.db.get(DeliveryNote, dn_id)
                if dn:
                    dn.status = "invoiced"

        await self.db.flush()
        return invoice

    async def pay_invoice(
        self,
        invoice_id: uuid.UUID | None,
        supplier_id: uuid.UUID,
        amount: Decimal,
        payment_method: str = "transfer",
        payment_date: date | None = None,
        reference: str | None = None,
        bank_name: str | None = None,
        check_due_date: date | None = None,
        notes: str | None = None,
    ) -> SupplierPayment:
        """Enregistre un paiement. Si invoice_id fourni, met à jour le statut."""
        payment = SupplierPayment(
            pharmacy_id=self.pharmacy_id,
            supplier_id=supplier_id,
            invoice_id=invoice_id,
            payment_date=payment_date or date.today(),
            amount=amount,
            payment_method=payment_method,
            reference=reference,
            bank_name=bank_name,
            check_due_date=check_due_date,
            notes=notes,
        )
        self.db.add(payment)

        if invoice_id:
            invoice = await self.db.get(SupplierInvoice, invoice_id)
            if invoice:
                invoice.amount_paid += amount
                if invoice.amount_paid >= invoice.total_ttc:
                    invoice.status = "paid"
                elif invoice.amount_paid > 0:
                    invoice.status = "partially_paid"

        await self.db.flush()
        return payment

    # ---------- Balance ----------
    async def get_supplier_balance(self, supplier_id: uuid.UUID) -> Decimal:
        """Dette nette envers un fournisseur = factures impayées - paiements anticipés."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(SupplierInvoice.total_ttc - SupplierInvoice.amount_paid), 0))
            .where(
                SupplierInvoice.pharmacy_id == self.pharmacy_id,
                SupplierInvoice.supplier_id == supplier_id,
                SupplierInvoice.status.in_(["pending", "partially_paid", "overdue"]),
            )
        )
        unpaid = Decimal(str(result.scalar() or 0))

        # Paiements anticipés (sans facture rattachée)
        result = await self.db.execute(
            select(func.coalesce(func.sum(SupplierPayment.amount), 0))
            .where(
                SupplierPayment.pharmacy_id == self.pharmacy_id,
                SupplierPayment.supplier_id == supplier_id,
                SupplierPayment.invoice_id.is_(None),
            )
        )
        on_account = Decimal(str(result.scalar() or 0))

        return unpaid - on_account

    async def get_overdue_amount(self, supplier_id: uuid.UUID) -> Decimal:
        """Montant des factures en retard."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(SupplierInvoice.total_ttc - SupplierInvoice.amount_paid), 0))
            .where(
                SupplierInvoice.pharmacy_id == self.pharmacy_id,
                SupplierInvoice.supplier_id == supplier_id,
                SupplierInvoice.status.in_(["pending", "partially_paid"]),
                SupplierInvoice.due_date < date.today(),
            )
        )
        return Decimal(str(result.scalar() or 0))

    # ---------- Returns ----------
    async def create_return(
        self,
        supplier_id: uuid.UUID,
        items: list[dict],
        reason: str = "expired",
        return_date: date | None = None,
        notes: str | None = None,
    ) -> SupplierReturn:
        return_number = await self._next_number(SupplierReturn, "return_number", "RET")

        ret = SupplierReturn(
            pharmacy_id=self.pharmacy_id,
            supplier_id=supplier_id,
            return_number=return_number,
            return_date=return_date or date.today(),
            reason=reason,
            notes=notes,
            status="pending",
        )
        self.db.add(ret)
        await self.db.flush()

        total = Decimal("0")
        for it in items:
            qty = int(it["quantity"])
            unit = Decimal(str(it["unit_price_ht"]))
            line = unit * qty
            ret_item = SupplierReturnItem(
                pharmacy_id=self.pharmacy_id,
                return_id=ret.id,
                product_id=uuid.UUID(str(it["product_id"])),
                lot_number=it.get("lot_number"),
                quantity=qty,
                unit_price_ht=unit,
                line_total=line.quantize(Decimal("0.01")),
            )
            self.db.add(ret_item)
            total += line

            # Décrémenter le stock
            await self.db.execute(
                update(Product)
                .where(Product.id == uuid.UUID(str(it["product_id"])))
                .values(stock_quantity=Product.stock_quantity - qty)
            )

            # Décrémenter le lot si fourni
            if it.get("lot_number"):
                result = await self.db.execute(
                    select(ProductLot).where(
                        ProductLot.pharmacy_id == self.pharmacy_id,
                        ProductLot.product_id == uuid.UUID(str(it["product_id"])),
                        ProductLot.lot_number == it["lot_number"],
                    )
                )
                lot = result.scalar_one_or_none()
                if lot:
                    lot.quantity = max(0, lot.quantity - qty)

        ret.total_amount = total.quantize(Decimal("0.01"))
        await self.db.flush()
        return ret
