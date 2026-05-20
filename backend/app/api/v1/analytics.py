"""
Router /analytics : dashboards avancés (CA, top produits, séries temporelles).

Endpoints :
- /revenue-summary : CA jour/semaine/mois/an + comparaison vs période précédente
- /sales-timeseries : courbe CA sur N derniers jours
- /top-products : produits les plus vendus (CA et quantité)
- /payment-methods-breakdown : répartition espèces/carte/chèque/crédit
- /hourly-distribution : ventes par heure de la journée (heat map)
"""
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_pharmacy_id
from app.models.sale import Sale, SaleItem
from app.models.product import Product

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ============ Schemas ============
class RevenueComparison(BaseModel):
    today: str
    yesterday: str
    this_week: str
    last_week: str
    this_month: str
    last_month: str
    delta_week_pct: float | None = None
    delta_month_pct: float | None = None


class SalesTimeSeriesPoint(BaseModel):
    date: date
    revenue: str
    sales_count: int


class TopProduct(BaseModel):
    product_id: uuid.UUID
    code: str
    name: str
    quantity_sold: int
    revenue: str


class PaymentBreakdown(BaseModel):
    method: str
    amount: str
    percentage: float


class HourlyDistribution(BaseModel):
    hour: int  # 0..23
    sales_count: int
    revenue: str


# ============ Helpers ============
def _start_of_day(d: date) -> datetime:
    return datetime.combine(d, time.min)


def _end_of_day(d: date) -> datetime:
    return datetime.combine(d, time.max)


def _pct_change(current: Decimal, previous: Decimal) -> float | None:
    if previous == 0:
        return None
    return float((current - previous) / previous * 100)


async def _sum_sales_in_period(
    db: AsyncSession, pharmacy_id: uuid.UUID, start: datetime, end: datetime
) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(Sale.total_ttc), 0))
        .where(
            Sale.pharmacy_id == pharmacy_id,
            Sale.status == "completed",
            Sale.sale_date >= start,
            Sale.sale_date <= end,
        )
    )
    return result.scalar() or Decimal("0")


# ============ Endpoints ============
@router.get("/revenue-summary", response_model=RevenueComparison)
async def revenue_summary(
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """CA des principales périodes + comparaison période précédente."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    # Semaine = lundi → aujourd'hui
    week_start = today - timedelta(days=today.weekday())
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start - timedelta(days=1)
    month_start = today.replace(day=1)
    # Mois précédent : reculer 1 jour depuis month_start et prendre le 1er
    if month_start.month == 1:
        last_month_start = month_start.replace(year=month_start.year - 1, month=12)
    else:
        last_month_start = month_start.replace(month=month_start.month - 1)
    last_month_end = month_start - timedelta(days=1)

    today_rev = await _sum_sales_in_period(db, pharmacy_id, _start_of_day(today), _end_of_day(today))
    yesterday_rev = await _sum_sales_in_period(db, pharmacy_id, _start_of_day(yesterday), _end_of_day(yesterday))
    this_week_rev = await _sum_sales_in_period(db, pharmacy_id, _start_of_day(week_start), _end_of_day(today))
    last_week_rev = await _sum_sales_in_period(db, pharmacy_id, _start_of_day(last_week_start), _end_of_day(last_week_end))
    this_month_rev = await _sum_sales_in_period(db, pharmacy_id, _start_of_day(month_start), _end_of_day(today))
    last_month_rev = await _sum_sales_in_period(db, pharmacy_id, _start_of_day(last_month_start), _end_of_day(last_month_end))

    return RevenueComparison(
        today=str(today_rev),
        yesterday=str(yesterday_rev),
        this_week=str(this_week_rev),
        last_week=str(last_week_rev),
        this_month=str(this_month_rev),
        last_month=str(last_month_rev),
        delta_week_pct=_pct_change(this_week_rev, last_week_rev),
        delta_month_pct=_pct_change(this_month_rev, last_month_rev),
    )


@router.get("/sales-timeseries", response_model=list[SalesTimeSeriesPoint])
async def sales_timeseries(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """CA quotidien sur les N derniers jours."""
    end = date.today()
    start = end - timedelta(days=days - 1)

    result = await db.execute(
        select(
            cast(Sale.sale_date, Date).label("d"),
            func.sum(Sale.total_ttc).label("revenue"),
            func.count(Sale.id).label("sales_count"),
        )
        .where(
            Sale.pharmacy_id == pharmacy_id,
            Sale.status == "completed",
            Sale.sale_date >= _start_of_day(start),
            Sale.sale_date <= _end_of_day(end),
        )
        .group_by(cast(Sale.sale_date, Date))
        .order_by(cast(Sale.sale_date, Date))
    )

    rows = {row.d: row for row in result}

    # Remplir les jours sans ventes avec 0
    output = []
    cur = start
    while cur <= end:
        row = rows.get(cur)
        output.append(
            SalesTimeSeriesPoint(
                date=cur,
                revenue=str(row.revenue) if row else "0",
                sales_count=int(row.sales_count) if row else 0,
            )
        )
        cur += timedelta(days=1)
    return output


@router.get("/top-products", response_model=list[TopProduct])
async def top_products(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    sort_by: str = Query("revenue", regex="^(revenue|quantity)$"),
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """Top produits par CA ou quantité vendue sur les N derniers jours."""
    end = date.today()
    start = end - timedelta(days=days - 1)

    qty_col = func.sum(SaleItem.quantity).label("qty")
    rev_col = func.sum(SaleItem.line_total_ttc).label("rev")

    stmt = (
        select(
            SaleItem.product_id,
            Product.code,
            Product.name,
            qty_col,
            rev_col,
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .join(Product, Product.id == SaleItem.product_id)
        .where(
            SaleItem.pharmacy_id == pharmacy_id,
            Sale.status == "completed",
            Sale.sale_date >= _start_of_day(start),
            Sale.sale_date <= _end_of_day(end),
        )
        .group_by(SaleItem.product_id, Product.code, Product.name)
    )
    if sort_by == "revenue":
        stmt = stmt.order_by(rev_col.desc())
    else:
        stmt = stmt.order_by(qty_col.desc())
    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    return [
        TopProduct(
            product_id=row.product_id,
            code=row.code,
            name=row.name,
            quantity_sold=int(row.qty or 0),
            revenue=str(row.rev or "0"),
        )
        for row in result
    ]


@router.get("/payment-methods-breakdown", response_model=list[PaymentBreakdown])
async def payment_methods_breakdown(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """Répartition espèces / carte / chèque / crédit sur les N derniers jours."""
    end = date.today()
    start = end - timedelta(days=days - 1)

    result = await db.execute(
        select(
            func.coalesce(func.sum(Sale.paid_cash), 0).label("cash"),
            func.coalesce(func.sum(Sale.paid_card), 0).label("card"),
            func.coalesce(func.sum(Sale.paid_check), 0).label("check"),
            func.coalesce(func.sum(Sale.paid_credit), 0).label("credit"),
        )
        .where(
            Sale.pharmacy_id == pharmacy_id,
            Sale.status == "completed",
            Sale.sale_date >= _start_of_day(start),
            Sale.sale_date <= _end_of_day(end),
        )
    )
    row = result.one()
    cash, card, check, credit = (
        Decimal(row.cash or 0),
        Decimal(row.card or 0),
        Decimal(row.check or 0),
        Decimal(row.credit or 0),
    )
    total = cash + card + check + credit
    if total == 0:
        return []

    return [
        PaymentBreakdown(method="cash", amount=str(cash), percentage=float(cash / total * 100)),
        PaymentBreakdown(method="card", amount=str(card), percentage=float(card / total * 100)),
        PaymentBreakdown(method="check", amount=str(check), percentage=float(check / total * 100)),
        PaymentBreakdown(method="credit", amount=str(credit), percentage=float(credit / total * 100)),
    ]


@router.get("/hourly-distribution", response_model=list[HourlyDistribution])
async def hourly_distribution(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """Distribution des ventes par heure (utile pour staffing)."""
    end = date.today()
    start = end - timedelta(days=days - 1)

    result = await db.execute(
        select(
            func.extract("hour", Sale.sale_date).label("h"),
            func.count(Sale.id).label("cnt"),
            func.coalesce(func.sum(Sale.total_ttc), 0).label("rev"),
        )
        .where(
            Sale.pharmacy_id == pharmacy_id,
            Sale.status == "completed",
            Sale.sale_date >= _start_of_day(start),
            Sale.sale_date <= _end_of_day(end),
        )
        .group_by(func.extract("hour", Sale.sale_date))
    )
    rows = {int(r.h): r for r in result}

    # Remplir 0-23
    output = []
    for h in range(24):
        r = rows.get(h)
        output.append(HourlyDistribution(
            hour=h,
            sales_count=int(r.cnt) if r else 0,
            revenue=str(r.rev) if r else "0",
        ))
    return output
