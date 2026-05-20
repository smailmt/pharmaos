"""Router : Endpoints IA basés sur Claude.

3 cas d'usage :
1. interactions : analyse d'interactions médicamenteuses d'une ordonnance
2. order_suggestions : suggérer une commande à partir du stock + ventes
3. pharmabot : agent conversationnel pour le pharmacien
"""
import uuid
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_pharmacy_id
from app.core.config import settings
from app.models.product import Product, ProductLot
from app.models.sale import Sale, SaleItem

router = APIRouter(prefix="/ai", tags=["ai"])


# Lazy import — Anthropic peut ne pas être configurée en dev
def _get_anthropic_client():
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(503, "Service IA non configuré (ANTHROPIC_API_KEY manquant)")
    from anthropic import Anthropic
    return Anthropic(api_key=settings.ANTHROPIC_API_KEY)


# ---------- Interactions médicamenteuses ----------
class InteractionRequest(BaseModel):
    medications: list[str]  # noms ou DCI
    patient_age: int | None = None
    patient_conditions: list[str] | None = None


class InteractionResponse(BaseModel):
    summary: str
    interactions: list[dict]
    warnings: list[str]


@router.post("/interactions", response_model=InteractionResponse)
async def check_interactions(payload: InteractionRequest):
    """Analyse une ordonnance pour détecter interactions et contre-indications."""
    client = _get_anthropic_client()
    meds = ", ".join(payload.medications)
    context = ""
    if payload.patient_age:
        context += f"Âge patient : {payload.patient_age} ans. "
    if payload.patient_conditions:
        context += f"Antécédents : {', '.join(payload.patient_conditions)}. "

    prompt = f"""Tu es pharmacien clinicien. Analyse cette ordonnance pour le marché marocain.

Médicaments : {meds}
{context}

Réponds STRICTEMENT en JSON valide :
{{
  "summary": "résumé en 1 phrase",
  "interactions": [
    {{"drug_a": "...", "drug_b": "...", "severity": "minor|moderate|major", "description": "..."}}
  ],
  "warnings": ["...", "..."]
}}"""

    message = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text.strip()
    # Nettoyer un éventuel code fence
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    import json
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(502, "Réponse IA non parsable")
    return InteractionResponse(**data)


# ---------- Suggestions de commande ----------
class OrderSuggestion(BaseModel):
    product_id: uuid.UUID
    product_name: str
    current_stock: int
    avg_daily_sales: float
    days_of_stock: float
    suggested_quantity: int
    reason: str


@router.get("/order-suggestions", response_model=list[OrderSuggestion])
async def suggest_orders(
    days_history: int = 30,
    days_target: int = 30,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """Suggère les produits à commander basé sur historique de ventes.

    Algorithme simple (sans Claude) : pour chaque produit avec stock faible,
    calcul de la consommation moyenne et de la couverture cible.
    """
    since = date.today() - timedelta(days=days_history)

    # Joindre ventes des X derniers jours par produit
    result = await db.execute(
        select(
            SaleItem.product_id,
            func.sum(SaleItem.quantity).label("total_sold"),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(
            Sale.pharmacy_id == pharmacy_id,
            Sale.status == "completed",
            Sale.sale_date >= since,
        )
        .group_by(SaleItem.product_id)
    )
    sales_by_product = {row[0]: int(row[1]) for row in result.all()}

    # Récupérer produits actifs
    result = await db.execute(
        select(Product).where(
            Product.pharmacy_id == pharmacy_id,
            Product.is_active == True,
        )
    )
    products = list(result.scalars().all())

    suggestions: list[OrderSuggestion] = []
    for p in products:
        sold = sales_by_product.get(p.id, 0)
        avg_daily = sold / days_history if days_history > 0 else 0
        if avg_daily == 0 and p.stock_quantity > p.stock_min:
            continue  # pas de ventes et stock OK
        days_left = (p.stock_quantity / avg_daily) if avg_daily > 0 else 999
        target_qty = int(avg_daily * days_target) - p.stock_quantity
        if target_qty <= 0 and p.stock_quantity > p.stock_min:
            continue
        target_qty = max(target_qty, p.stock_min - p.stock_quantity, 0)
        if target_qty <= 0:
            continue
        reason = (
            f"Stock sous seuil ({p.stock_quantity}/{p.stock_min})"
            if p.stock_quantity <= p.stock_min
            else f"{days_left:.0f}j de stock restant"
        )
        suggestions.append(OrderSuggestion(
            product_id=p.id,
            product_name=p.name,
            current_stock=p.stock_quantity,
            avg_daily_sales=round(avg_daily, 2),
            days_of_stock=round(days_left, 1),
            suggested_quantity=target_qty,
            reason=reason,
        ))

    suggestions.sort(key=lambda s: s.days_of_stock)
    return suggestions[:50]


# ---------- PharmaBot ----------
class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None  # [{"role": "user|assistant", "content": "..."}]


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
async def pharmabot_chat(payload: ChatRequest):
    """Agent conversationnel pour le pharmacien (questions cliniques, posologie, etc.)."""
    client = _get_anthropic_client()

    system = """Tu es PharmaBot, assistant IA d'une pharmacie au Maroc. Tu aides le pharmacien avec :
- Questions cliniques (posologie, contre-indications, effets indésirables)
- Conseil patient (allaitement, grossesse, pédiatrie)
- Pharmacovigilance
- Référence aux DCI marocaines courantes

Réponds en français de manière concise, professionnelle et précise. Précise toujours quand
un avis médical est nécessaire."""

    messages = []
    if payload.history:
        messages.extend(payload.history)
    messages.append({"role": "user", "content": payload.message})

    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    return ChatResponse(reply=response.content[0].text)


# ---------- OCR ordonnance via Claude Vision ----------
class PrescriptionLine(BaseModel):
    medication_name: str
    dci: str | None = None
    dosage: str | None = None  # "500mg", "2cp matin"
    quantity: int | None = None  # boîtes à dispenser
    duration_days: int | None = None
    instructions: str | None = None
    confidence: str = "medium"  # low / medium / high


class PrescriptionOCRRequest(BaseModel):
    image_base64: str  # data URL ou base64 brut
    media_type: str = "image/jpeg"  # image/jpeg, image/png, image/webp


class PrescriptionOCRResponse(BaseModel):
    raw_text: str  # texte brut extrait
    prescriber: str | None = None  # nom médecin si lisible
    prescription_date: str | None = None
    patient_name: str | None = None
    lines: list[PrescriptionLine]
    warnings: list[str]  # ex: "écriture peu lisible", "médicament inconnu"


@router.post("/prescription-ocr", response_model=PrescriptionOCRResponse, tags=["ai"])
async def prescription_ocr(
    payload: PrescriptionOCRRequest,
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyse une photo d'ordonnance (manuscrite ou imprimée) et extrait les médicaments.

    **Workflow** :
    1. Photo de l'ordonnance prise via la caméra du téléphone
    2. Claude Vision extrait le texte et structure les lignes
    3. Cross-check avec le catalogue de la pharmacie pour matcher les produits
    4. Retourne une ordonnance pré-remplie que le pharmacien valide

    C'est le wow effect des démos : photo → caisse pré-remplie en 3 secondes.
    """
    import base64 as b64
    import json as _json

    client = _get_anthropic_client()

    # Nettoyer le base64 (enlever préfixe data:image/...;base64, si présent)
    img_data = payload.image_base64
    if img_data.startswith("data:"):
        img_data = img_data.split(",", 1)[1]

    # Valider que c'est du base64 valide
    try:
        b64.b64decode(img_data, validate=True)
    except Exception:
        raise HTTPException(400, "Image base64 invalide")

    system = (
        "Tu es un expert en pharmacie marocaine spécialisé dans la lecture d'ordonnances médicales. "
        "Ta tâche : extraire de la photo d'ordonnance ci-dessous les médicaments prescrits, "
        "avec leur posologie, quantité et durée. "
        "Réponds UNIQUEMENT en JSON valide selon ce schéma exact (pas de markdown, pas d'explication) : "
        '{"raw_text": str, "prescriber": str|null, "prescription_date": str|null (YYYY-MM-DD), '
        '"patient_name": str|null, "lines": [{"medication_name": str, "dci": str|null, '
        '"dosage": str|null, "quantity": int|null, "duration_days": int|null, '
        '"instructions": str|null, "confidence": "low"|"medium"|"high"}], "warnings": [str]}. '
        "Si l'écriture est peu lisible, marque confidence=low et ajoute un warning. "
        "Ne devine pas un médicament que tu ne reconnais pas — laisse medication_name vide et warn."
    )

    try:
        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=2048,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": payload.media_type,
                                "data": img_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Analyse cette ordonnance et extrait les médicaments en JSON strict. "
                                "Aucun autre texte que le JSON."
                            ),
                        },
                    ],
                }
            ],
        )
        raw = response.content[0].text.strip()
        # Robustesse : enlever des éventuels backticks markdown
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].strip()
        data = _json.loads(raw)
    except _json.JSONDecodeError as e:
        raise HTTPException(502, f"Réponse IA non parsable: {e}")
    except Exception as e:
        raise HTTPException(502, f"Erreur Claude Vision: {e}")

    # Enrichissement : cross-check avec le catalogue local pour proposer
    # un product_id si on a un match exact ou trigram
    enriched_lines = []
    for line in data.get("lines", []):
        med_name = line.get("medication_name") or ""
        dci = line.get("dci") or ""

        # Recherche fuzzy (trigram) dans le catalogue de cette pharmacie
        match_product_id = None
        if med_name or dci:
            search_term = med_name or dci
            result = await db.execute(
                select(Product.id, Product.name, Product.dci)
                .where(
                    Product.pharmacy_id == pharmacy_id,
                    Product.is_active == True,
                )
                .where(
                    (Product.name.ilike(f"%{search_term}%"))
                    | (Product.dci.ilike(f"%{search_term}%"))
                )
                .limit(1)
            )
            row = result.first()
            if row:
                match_product_id = str(row[0])

        line["product_id_match"] = match_product_id
        enriched_lines.append(line)

    return PrescriptionOCRResponse(
        raw_text=data.get("raw_text", ""),
        prescriber=data.get("prescriber"),
        prescription_date=data.get("prescription_date"),
        patient_name=data.get("patient_name"),
        lines=[PrescriptionLine(**{k: v for k, v in l.items() if k != "product_id_match"}) for l in enriched_lines],
        warnings=data.get("warnings", []),
    )


# ---------- Détection anomalies caisse ----------
class AnomalyAlert(BaseModel):
    severity: str  # info / warning / critical
    category: str  # ex: "remise_excessive", "vente_atypique", "stock_negatif", "fréquence"
    title: str
    description: str
    sale_ids: list[str] = []


class AnomalyDetectionResponse(BaseModel):
    period_start: str
    period_end: str
    sales_analyzed: int
    total_revenue: str
    anomalies: list[AnomalyAlert]
    summary: str  # synthèse 2-3 phrases pour le pharmacien


@router.post("/anomaly-detection", response_model=AnomalyDetectionResponse, tags=["ai"])
async def anomaly_detection(
    days: int = 1,
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyse les ventes des N derniers jours avec Claude et signale les patterns suspects.

    Cas détectés (Claude infère) :
    - Remises anormalement élevées
    - Ventes après heures normales
    - Médicaments à ordonnance sans `has_prescription`
    - Annulations en série
    - Écarts de stock vs ventes
    - Patterns de caissiers individuels
    """
    import json as _json
    from datetime import datetime as _dt, timedelta as _td

    client = _get_anthropic_client()

    # Récup les ventes du jour
    period_start = _dt.now() - _td(days=days)
    result = await db.execute(
        select(Sale)
        .where(
            Sale.pharmacy_id == pharmacy_id,
            Sale.sale_date >= period_start,
        )
        .order_by(Sale.sale_date)
        .limit(500)  # cap pour ne pas exploser le contexte
    )
    sales = list(result.scalars().all())

    if not sales:
        return AnomalyDetectionResponse(
            period_start=period_start.isoformat(),
            period_end=_dt.now().isoformat(),
            sales_analyzed=0,
            total_revenue="0",
            anomalies=[],
            summary="Aucune vente sur cette période.",
        )

    # Compacter en CSV-like pour le contexte Claude
    sales_summary = []
    total_rev = 0.0
    for s in sales:
        sales_summary.append({
            "id": str(s.id),
            "n": s.sale_number,
            "t": s.sale_date.strftime("%H:%M") if s.sale_date else "",
            "ttc": float(s.total_ttc or 0),
            "disc": float(s.total_discount or 0),
            "pay": s.payment_method,
            "status": s.status,
            "loy_used": s.loyalty_points_used,
        })
        total_rev += float(s.total_ttc or 0)

    system = (
        "Tu es un expert en audit de caisse pour pharmacies au Maroc. "
        "On te donne un journal de ventes. Identifie les patterns suspects "
        "(remises excessives, horaires inhabituels, annulations en série, montants atypiques, etc.). "
        "Réponds UNIQUEMENT en JSON valide. Soit conservateur : ne signale que ce qui mérite attention. "
        "Schéma : "
        '{"anomalies": [{"severity": "info"|"warning"|"critical", '
        '"category": str, "title": str, "description": str, "sale_ids": [str]}], '
        '"summary": str}'
    )

    user_msg = (
        f"Ventes des {days} dernier(s) jour(s) ({len(sales)} ventes, "
        f"CA total {total_rev:.2f} MAD):\n\n"
        f"{_json.dumps(sales_summary, ensure_ascii=False)}\n\n"
        "Analyse et retourne le JSON."
    )

    try:
        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].strip()
        data = _json.loads(raw)
    except _json.JSONDecodeError as e:
        raise HTTPException(502, f"Réponse IA non parsable: {e}")
    except Exception as e:
        raise HTTPException(502, f"Erreur Claude: {e}")

    return AnomalyDetectionResponse(
        period_start=period_start.isoformat(),
        period_end=_dt.now().isoformat(),
        sales_analyzed=len(sales),
        total_revenue=f"{total_rev:.2f}",
        anomalies=[AnomalyAlert(**a) for a in data.get("anomalies", [])],
        summary=data.get("summary", ""),
    )
