"""Service de gestion des clés API : génération, vérification, révocation."""
import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey


def hash_key(plaintext_key: str) -> str:
    """SHA-256 d'une clé en clair (irréversible)."""
    return hashlib.sha256(plaintext_key.encode()).hexdigest()


def generate_api_key(env: str = "live") -> tuple[str, str, str]:
    """
    Génère une nouvelle clé API.
    Retourne (clé_complète, préfixe_visible, hash).

    Format : pk_<env>_<32 caractères url-safe>
    """
    suffix = secrets.token_urlsafe(24).rstrip("=")  # ~32 chars
    plaintext = f"pk_{env}_{suffix}"
    # Préfixe visible : 12 premiers caractères (pk_live_xxxx ou pk_test_xxxx)
    prefix = plaintext[:16]
    return plaintext, prefix, hash_key(plaintext)


def generate_webhook_secret() -> tuple[str, str, str]:
    """
    Génère un secret HMAC pour webhook.
    Retourne (secret_complet, préfixe_visible, hash).

    Format : whsec_<40 caractères>
    """
    suffix = secrets.token_urlsafe(30).rstrip("=")
    plaintext = f"whsec_{suffix}"
    prefix = plaintext[:14]
    return plaintext, prefix, hash_key(plaintext)


class ApiKeyService:
    def __init__(self, db: AsyncSession, pharmacy_id: uuid.UUID):
        self.db = db
        self.pharmacy_id = pharmacy_id

    async def create(
        self,
        name: str,
        description: str | None = None,
        scopes: str | None = None,
        rate_limit_per_min: int | None = None,
        created_by_user_id: uuid.UUID | None = None,
        env: str = "live",
    ) -> tuple[ApiKey, str]:
        """Crée une nouvelle clé. Retourne (objet ApiKey, clé en clair à montrer une fois)."""
        plaintext, prefix, key_hash = generate_api_key(env)

        api_key = ApiKey(
            pharmacy_id=self.pharmacy_id,
            name=name,
            description=description,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=scopes,
            rate_limit_per_min=rate_limit_per_min,
            created_by_user_id=created_by_user_id,
            is_active=True,
        )
        self.db.add(api_key)
        await self.db.flush()
        return api_key, plaintext

    async def verify(self, plaintext_key: str) -> ApiKey | None:
        """
        Vérifie une clé en clair. Retourne l'ApiKey si valide et active.
        Met à jour last_used_at + usage_count si valide.
        """
        if not plaintext_key or not plaintext_key.startswith("pk_"):
            return None
        key_hash = hash_key(plaintext_key)

        result = await self.db.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True,
            )
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            return None
        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            return None

        # Update stats (best-effort, ne pas bloquer)
        api_key.last_used_at = datetime.now(timezone.utc)
        api_key.usage_count = (api_key.usage_count or 0) + 1
        return api_key

    async def list(self) -> list[ApiKey]:
        result = await self.db.execute(
            select(ApiKey)
            .where(ApiKey.pharmacy_id == self.pharmacy_id)
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke(self, api_key_id: uuid.UUID) -> ApiKey | None:
        api_key = await self.db.get(ApiKey, api_key_id)
        if not api_key or api_key.pharmacy_id != self.pharmacy_id:
            return None
        api_key.is_active = False
        api_key.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()
        return api_key
