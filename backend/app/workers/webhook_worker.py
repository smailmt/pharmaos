"""
Worker de delivery des webhooks.

Stratégie :
- Cherche les WebhookDelivery `pending` ou `retrying` dont next_retry_at est passé
- POST le payload, met à jour le statut
- Sur échec : reprogramme avec délai exponentiel (1m, 5m, 30m, 2h, 12h) puis abandonne
- Met à jour le compteur d'échecs consécutifs sur l'endpoint, désactive après 10 échecs
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import WebhookEndpoint, WebhookDelivery
from app.services.webhook_service import deliver_webhook


# Délais de retry : 1min, 5min, 30min, 2h, 12h (max 5 retries)
RETRY_DELAYS_SECONDS = [60, 300, 1800, 7200, 43200]
MAX_ATTEMPTS = len(RETRY_DELAYS_SECONDS) + 1
DISABLE_AFTER_CONSECUTIVE_FAILURES = 10


async def process_pending_deliveries(
    db: AsyncSession,
    batch_size: int = 50,
) -> dict:
    """
    Traite un batch de deliveries prêtes à être livrées.
    Retourne {processed, delivered, failed, abandoned}.
    """
    now = datetime.now(timezone.utc)

    # Récup deliveries pending ou retrying dont next_retry_at <= now (ou null)
    stmt = (
        select(WebhookDelivery)
        .where(
            WebhookDelivery.status.in_(["pending", "retrying"]),
        )
        .order_by(WebhookDelivery.created_at)
        .limit(batch_size)
    )
    result = await db.execute(stmt)
    deliveries = list(result.scalars().all())
    # Filtre Python pour les next_retry_at (None ou passé)
    deliveries = [
        d for d in deliveries
        if d.next_retry_at is None or d.next_retry_at <= now
    ]

    stats = {"processed": 0, "delivered": 0, "failed": 0, "abandoned": 0}

    for delivery in deliveries:
        endpoint = await db.get(WebhookEndpoint, delivery.endpoint_id)
        if not endpoint or not endpoint.is_active:
            delivery.status = "failed"
            delivery.error_message = "Endpoint inactif ou supprimé"
            stats["failed"] += 1
            continue

        # Déchiffrer le secret pour signer
        from app.core.crypto import decrypt
        try:
            secret_plaintext = decrypt(endpoint.secret_encrypted)
        except Exception:
            delivery.status = "failed"
            delivery.error_message = "Impossible de déchiffrer le secret (clé maître changée ?)"
            stats["failed"] += 1
            continue

        delivery.attempt_count += 1
        http_status, response_body, error = await deliver_webhook(
            endpoint_url=endpoint.url,
            payload=delivery.payload,
            secret_plaintext=secret_plaintext,
        )

        delivery.http_status = http_status
        delivery.response_body = response_body
        delivery.error_message = error
        stats["processed"] += 1

        # Succès = 2xx
        if http_status and 200 <= http_status < 300:
            delivery.status = "delivered"
            delivery.delivered_at = datetime.now(timezone.utc)
            delivery.next_retry_at = None
            endpoint.last_delivery_at = delivery.delivered_at
            endpoint.last_success_at = delivery.delivered_at
            endpoint.consecutive_failures = 0
            stats["delivered"] += 1
        else:
            # Échec
            endpoint.last_delivery_at = datetime.now(timezone.utc)
            endpoint.consecutive_failures = (endpoint.consecutive_failures or 0) + 1

            # Désactiver si trop d'échecs consécutifs
            if endpoint.consecutive_failures >= DISABLE_AFTER_CONSECUTIVE_FAILURES:
                endpoint.is_active = False

            # Replanifier ou abandonner
            if delivery.attempt_count >= MAX_ATTEMPTS:
                delivery.status = "failed"
                delivery.next_retry_at = None
                stats["abandoned"] += 1
            else:
                delay = RETRY_DELAYS_SECONDS[delivery.attempt_count - 1]
                delivery.status = "retrying"
                delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                stats["failed"] += 1

    await db.commit()
    return stats


async def webhook_worker_loop(
    session_factory,
    interval_seconds: int = 10,
    stop_event: Optional[asyncio.Event] = None,
):
    """
    Boucle infinie pour traiter les webhooks en arrière-plan.
    Lancer comme background task FastAPI.
    """
    while True:
        if stop_event and stop_event.is_set():
            break
        try:
            async with session_factory() as session:
                stats = await process_pending_deliveries(session)
                if stats["processed"] > 0:
                    print(f"[webhook-worker] {stats}")
        except Exception as e:
            print(f"[webhook-worker] Error: {e}")
        await asyncio.sleep(interval_seconds)
