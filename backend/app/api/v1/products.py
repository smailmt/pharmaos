"""Router : Produits (médicaments, parapharmacie) + lots."""
import uuid
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_pharmacy_id
from app.models.product import Product, ProductLot
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductOut,
    ProductLotCreate, ProductLotOut,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductOut, status_code=201)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    product = Product(pharmacy_id=pharmacy_id, **payload.model_dump())
    db.add(product)
    await db.flush()
    return product


@router.get("", response_model=list[ProductOut])
async def list_products(
    q: str | None = Query(None, description="Recherche dans name, dci, barcode"),
    low_stock: bool = Query(False, description="Uniquement produits sous stock_min"),
    expiring_soon: bool = Query(False, description="Produits avec lots qui périment dans 90j"),
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = select(Product).where(Product.pharmacy_id == pharmacy_id, Product.is_active == True)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Product.name.ilike(like),
            Product.dci.ilike(like),
            Product.barcode == q,
            Product.code == q,
        ))
    if low_stock:
        stmt = stmt.where(Product.stock_quantity <= Product.stock_min)
    if expiring_soon:
        soon = date.today() + timedelta(days=90)
        sub = select(ProductLot.product_id).where(
            ProductLot.pharmacy_id == pharmacy_id,
            ProductLot.expiration_date <= soon,
            ProductLot.quantity > 0,
        )
        stmt = stmt.where(Product.id.in_(sub))

    stmt = stmt.order_by(Product.name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    product = await db.get(Product, product_id)
    if not product or product.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Produit introuvable")
    return product


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    product = await db.get(Product, product_id)
    if not product or product.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Produit introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(product, k, v)
    await db.flush()
    return product


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    product = await db.get(Product, product_id)
    if not product or product.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Produit introuvable")
    product.is_active = False  # soft delete


# ---------- Lots ----------
@router.post("/lots", response_model=ProductLotOut, status_code=201)
async def create_lot(
    payload: ProductLotCreate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    product = await db.get(Product, payload.product_id)
    if not product or product.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Produit introuvable")
    lot = ProductLot(pharmacy_id=pharmacy_id, **payload.model_dump())
    db.add(lot)
    product.stock_quantity += payload.quantity
    await db.flush()
    return lot


@router.get("/{product_id}/lots", response_model=list[ProductLotOut])
async def list_product_lots(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    result = await db.execute(
        select(ProductLot)
        .where(
            ProductLot.pharmacy_id == pharmacy_id,
            ProductLot.product_id == product_id,
        )
        .order_by(ProductLot.expiration_date.asc().nullslast())
    )
    return list(result.scalars().all())


@router.get("/alerts/low-stock", response_model=list[ProductOut])
async def low_stock_alerts(
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    result = await db.execute(
        select(Product).where(
            Product.pharmacy_id == pharmacy_id,
            Product.is_active == True,
            Product.stock_quantity <= Product.stock_min,
        )
        .order_by(Product.stock_quantity.asc())
    )
    return list(result.scalars().all())


@router.get("/alerts/expiring", response_model=list[ProductLotOut])
async def expiring_lots(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    cutoff = date.today() + timedelta(days=days)
    result = await db.execute(
        select(ProductLot).where(
            ProductLot.pharmacy_id == pharmacy_id,
            ProductLot.expiration_date <= cutoff,
            ProductLot.quantity > 0,
        )
        .order_by(ProductLot.expiration_date.asc())
    )
    return list(result.scalars().all())
