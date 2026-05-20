"""Service de clôture caisse fin de journée."""
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operations import DayClosing
from app.models.sale import Sale


class DayClosingService:
    def __init__(self, db: AsyncSession, pharmacy_id: uuid.UUID):
        self.db = db
        self.pharmacy_id = pharmacy_id

    async def is_closed(self, closing_date: date) -> bool:
        """Vérifie si une journée est déjà clôturée."""
        result = await self.db.execute(
            select(DayClosing.id).where(
                DayClosing.pharmacy_id == self.pharmacy_id,
                DayClosing.closing_date == closing_date,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_closing(self, closing_date: date) -> DayClosing | None:
        result = await self.db.execute(
            select(DayClosing).where(
                DayClosing.pharmacy_id == self.pharmacy_id,
                DayClosing.closing_date == closing_date,
            )
        )
        return result.scalar_one_or_none()

    async def list_closings(self, limit: int = 50) -> list[DayClosing]:
        result = await self.db.execute(
            select(DayClosing)
            .where(DayClosing.pharmacy_id == self.pharmacy_id)
            .order_by(DayClosing.closing_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def compute_day_totals(self, target_date: date) -> dict:
        """
        Calcule les totaux pour une journée :
        - revenus par moyen de paiement
        - nombre ventes / annulations
        - cash attendu en caisse
        """
        start = datetime.combine(target_date, time.min)
        end = datetime.combine(target_date, time.max)

        # Totaux ventes complétées
        result = await self.db.execute(
            select(
                func.count(Sale.id).label("count"),
                func.coalesce(func.sum(Sale.total_ttc), 0).label("total"),
                func.coalesce(func.sum(Sale.paid_cash), 0).label("cash"),
                func.coalesce(func.sum(Sale.paid_card), 0).label("card"),
                func.coalesce(func.sum(Sale.paid_check), 0).label("check"),
                func.coalesce(func.sum(Sale.paid_credit), 0).label("credit"),
            ).where(
                Sale.pharmacy_id == self.pharmacy_id,
                Sale.sale_date >= start,
                Sale.sale_date <= end,
                Sale.status == "completed",
            )
        )
        row = result.one()

        # Annulations
        cancelled_result = await self.db.execute(
            select(func.count(Sale.id)).where(
                Sale.pharmacy_id == self.pharmacy_id,
                Sale.sale_date >= start,
                Sale.sale_date <= end,
                Sale.status == "cancelled",
            )
        )
        cancelled_count = cancelled_result.scalar() or 0

        return {
            "sales_count": int(row.count or 0),
            "cancelled_count": int(cancelled_count),
            "total_revenue": Decimal(str(row.total)),
            "total_cash": Decimal(str(row.cash)),
            "total_card": Decimal(str(row.card)),
            "total_check": Decimal(str(row.check)),
            "total_credit": Decimal(str(row.credit)),
            "total_third_party": Decimal("0"),  # à étendre si tiers payants
            "cash_expected": Decimal(str(row.cash)),
        }

    async def close_day(
        self,
        closing_date: date,
        closed_by_user_id: uuid.UUID,
        cash_counted: Decimal = Decimal("0"),
        notes: str | None = None,
    ) -> DayClosing:
        """Clôture la journée. Échoue si déjà clôturée."""
        if await self.is_closed(closing_date):
            raise ValueError(f"La journée du {closing_date} est déjà clôturée.")

        totals = await self.compute_day_totals(closing_date)
        cash_difference = cash_counted - totals["cash_expected"]

        closing = DayClosing(
            pharmacy_id=self.pharmacy_id,
            closing_date=closing_date,
            closed_by_user_id=closed_by_user_id,
            cash_counted=cash_counted,
            cash_difference=cash_difference,
            notes=notes,
            **totals,
        )
        self.db.add(closing)
        await self.db.flush()
        return closing
