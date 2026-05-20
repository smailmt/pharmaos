"""Service de proposition de commande (aide à l'achat).

Deux modes :
- "sales" : basé sur les ventes d'une période. Suggère de racheter ce qui a été
  vendu, en tenant compte du stock actuel.
- "minmax" : basé sur les seuils. Suggère de remonter au stock_max les produits
  sous leur stock_min.

Filtrable par fournisseur (via le catalogue SupplierProduct).
"""
import uuid
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.sale import Sale, SaleItem
from app.models.supplier import SupplierProduct


class PurchaseProposalService:
    def __init__(self, db: AsyncSession, pharmacy_id: uuid.UUID):
        self.db = db
        self.pharmacy_id = pharmacy_id

    async def _catalog_product_ids(self, supplier_id: uuid.UUID) -> set[uuid.UUID]:
        """Produits au catalogue d'un fournisseur."""
        result = await self.db.execute(
            select(SupplierProduct.product_id).where(
                SupplierProduct.pharmacy_id == self.pharmacy_id,
                SupplierProduct.supplier_id == supplier_id,
            )
        )
        return {row[0] for row in result.all()}

    async def _catalog_info(self, supplier_id: uuid.UUID) -> dict[uuid.UUID, dict]:
        """PPH (prix achat) et PPV du catalogue fournisseur, par produit."""
        result = await self.db.execute(
            select(
                SupplierProduct.product_id,
                SupplierProduct.purchase_price_ht,
                SupplierProduct.ppv,
            ).where(
                SupplierProduct.pharmacy_id == self.pharmacy_id,
                SupplierProduct.supplier_id == supplier_id,
            )
        )
        return {
            row.product_id: {"pph": row.purchase_price_ht, "ppv": row.ppv}
            for row in result
        }

    async def propose_by_sales(
        self,
        supplier_id: uuid.UUID | None,
        period_start: date,
        period_end: date,
    ) -> list[dict]:
        """
        Propose les produits vendus sur la période, avec quantité suggérée =
        quantité vendue (pour reconstituer), ajustée du stock disponible.
        """
        start = datetime.combine(period_start, time.min)
        end = datetime.combine(period_end, time.max)

        # Quantités vendues par produit sur la période (ventes complétées)
        sold_stmt = (
            select(
                SaleItem.product_id,
                func.sum(SaleItem.quantity).label("qty_sold"),
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(
                SaleItem.pharmacy_id == self.pharmacy_id,
                Sale.sale_date >= start,
                Sale.sale_date <= end,
                Sale.status == "completed",
            )
            .group_by(SaleItem.product_id)
        )
        sold_result = await self.db.execute(sold_stmt)
        sold_map = {row.product_id: int(row.qty_sold) for row in sold_result}

        if not sold_map:
            return []

        # Filtre catalogue fournisseur si précisé
        catalog_info = {}
        if supplier_id:
            catalog_ids = await self._catalog_product_ids(supplier_id)
            sold_map = {pid: q for pid, q in sold_map.items() if pid in catalog_ids}
            catalog_info = await self._catalog_info(supplier_id)

        if not sold_map:
            return []

        # Charger les produits concernés
        products_result = await self.db.execute(
            select(Product).where(
                Product.pharmacy_id == self.pharmacy_id,
                Product.id.in_(list(sold_map.keys())),
            )
        )
        products = {p.id: p for p in products_result.scalars().all()}

        proposals = []
        for pid, qty_sold in sold_map.items():
            product = products.get(pid)
            if not product:
                continue
            stock = product.stock_quantity or 0
            # Suggestion : racheter ce qui a été vendu, moins ce qui reste en stock
            suggested = max(0, qty_sold - max(0, stock))
            if suggested <= 0 and stock > 0:
                # déjà du stock, mais on propose quand même le réassort minimal
                suggested = max(0, qty_sold - stock)
            info = catalog_info.get(pid, {})
            pph = info.get("pph") if info.get("pph") is not None else product.purchase_price_ht
            ppv = info.get("ppv") if info.get("ppv") is not None else product.sale_price_ttc
            proposals.append({
                "product_id": str(pid),
                "product_name": product.name,
                "product_code": product.code,
                "pph": str(pph or Decimal("0")),
                "ppv": str(ppv or Decimal("0")),
                "qty_sold": qty_sold,
                "current_stock": stock,
                "suggested_quantity": suggested,
            })

        proposals.sort(key=lambda x: x["qty_sold"], reverse=True)
        return proposals

    async def propose_by_minmax(self, supplier_id: uuid.UUID | None) -> list[dict]:
        """
        Propose les produits sous leur stock_min, suggère de remonter à stock_max
        (ou à stock_min+1 si stock_max non défini).
        """
        stmt = select(Product).where(
            Product.pharmacy_id == self.pharmacy_id,
            Product.stock_min > 0,
            Product.stock_quantity <= Product.stock_min,
        )
        result = await self.db.execute(stmt)
        products = list(result.scalars().all())

        catalog_info = {}
        if supplier_id:
            catalog_ids = await self._catalog_product_ids(supplier_id)
            products = [p for p in products if p.id in catalog_ids]
            catalog_info = await self._catalog_info(supplier_id)

        proposals = []
        for product in products:
            stock = product.stock_quantity or 0
            target = product.stock_max if product.stock_max and product.stock_max > product.stock_min else product.stock_min
            suggested = max(0, target - stock)
            if suggested <= 0:
                continue
            info = catalog_info.get(product.id, {})
            pph = info.get("pph") if info.get("pph") is not None else product.purchase_price_ht
            ppv = info.get("ppv") if info.get("ppv") is not None else product.sale_price_ttc
            proposals.append({
                "product_id": str(product.id),
                "product_name": product.name,
                "product_code": product.code,
                "pph": str(pph or Decimal("0")),
                "ppv": str(ppv or Decimal("0")),
                "qty_sold": 0,
                "current_stock": stock,
                "suggested_quantity": suggested,
            })

        proposals.sort(key=lambda x: x["current_stock"])
        return proposals
