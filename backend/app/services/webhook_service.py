"""
Service Webhooks : émission d'événements signés HMAC-SHA256.

Le pharmacien souscrit ses endpoints (URL + events). Quand un événement
se produit (vente créée, stock bas...), on crée une `WebhookDelivery`
et on POST le payload au endpoint avec signature dans l'en-tête.
"""
import asyncio
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import WebhookEndpoint, WebhookDelivery
from app.services.api_key_service import generate_webhook_secret, hash_key


def sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Signature HMAC-SHA256 du payload."""
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


def verify_signature(payload_bytes: bytes, secret: str, signature: str) -> bool:
    """Vérifie une signature reçue (utile pour les consumers / tests)."""
    expected = sign_payload(payload_bytes, secret)
    return hmac.compare_digest(expected, signature)


class WebhookService:
    def __init__(self, db: AsyncSession, pharmacy_id: uuid.UUID):
        self.db = db
        self.pharmacy_id = pharmacy_id

    async def create_endpoint(
        self,
        url: str,
        events: list[str],
        description: str | None = None,
    ) -> tuple[WebhookEndpoint, str]:
        """Crée un endpoint webhook. Retourne (endpoint, secret en clair à afficher 1 fois)."""
        from app.core.crypto import encrypt
        secret_plaintext, prefix, secret_hash = generate_webhook_secret()
        endpoint = WebhookEndpoint(
            pharmacy_id=self.pharmacy_id,
            url=url,
            description=description,
            secret_hash=secret_hash,
            secret_encrypted=encrypt(secret_plaintext),
            secret_prefix=prefix,
            events=events,
            is_active=True,
        )
        self.db.add(endpoint)
        await self.db.flush()
        return endpoint, secret_plaintext

    async def list_endpoints(self) -> list[WebhookEndpoint]:
        result = await self.db.execute(
            select(WebhookEndpoint)
            .where(WebhookEndpoint.pharmacy_id == self.pharmacy_id)
            .order_by(WebhookEndpoint.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_endpoint(self, endpoint_id: uuid.UUID) -> bool:
        endpoint = await self.db.get(WebhookEndpoint, endpoint_id)
        if not endpoint or endpoint.pharmacy_id != self.pharmacy_id:
            return False
        await self.db.delete(endpoint)
        await self.db.flush()
        return True

    async def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> list[WebhookDelivery]:
        """
        Émet un événement vers tous les endpoints abonnés à ce type.
        Crée les WebhookDelivery (status=pending). La livraison effective
        peut être faite immédiatement ou par un worker.
        """
        # Récup endpoints actifs qui souscrivent à cet event
        result = await self.db.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.pharmacy_id == self.pharmacy_id,
                WebhookEndpoint.is_active == True,
            )
        )
        endpoints = [
            ep for ep in result.scalars().all()
            if event_type in (ep.events or []) or "*" in (ep.events or [])
        ]

        event_id = f"evt_{secrets.token_urlsafe(16).rstrip('=')}"
        enriched_payload = {
            "id": event_id,
            "type": event_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "pharmacy_id": str(self.pharmacy_id),
            "data": payload,
        }

        deliveries = []
        for ep in endpoints:
            delivery = WebhookDelivery(
                pharmacy_id=self.pharmacy_id,
                endpoint_id=ep.id,
                event_type=event_type,
                event_id=event_id,
                payload=enriched_payload,
                status="pending",
                attempt_count=0,
            )
            self.db.add(delivery)
            deliveries.append(delivery)

        await self.db.flush()
        return deliveries


async def deliver_webhook(
    endpoint_url: str,
    payload: dict,
    secret_plaintext: str | None = None,
    timeout: float = 5.0,
) -> tuple[int | None, str | None, str | None]:
    """
    Effectue le POST HTTP vers le endpoint.

    Si secret_plaintext est fourni, ajoute :
        X-PharmaOS-Signature: t=<timestamp>,v1=<hmac>

    Retourne (http_status, response_body, error_message).
    """
    body_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "PharmaOS-Webhooks/1.0",
        "X-PharmaOS-Event": payload.get("type", ""),
        "X-PharmaOS-Delivery": payload.get("id", ""),
    }
    if secret_plaintext:
        timestamp = str(int(time.time()))
        # Signer "{timestamp}.{body}"
        signed_payload = f"{timestamp}.".encode() + body_bytes
        sig = sign_payload(signed_payload, secret_plaintext)
        headers["X-PharmaOS-Signature"] = f"t={timestamp},v1={sig}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint_url, content=body_bytes, headers=headers)
        body_preview = response.text[:1000] if response.text else None
        return response.status_code, body_preview, None
    except httpx.TimeoutException:
        return None, None, "Timeout"
    except httpx.HTTPError as e:
        return None, None, f"HTTP error: {e}"
    except Exception as e:
        return None, None, f"Error: {e}"
