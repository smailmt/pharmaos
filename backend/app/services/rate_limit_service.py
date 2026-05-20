"""
Rate limiting par clé API — sliding window via Redis (sorted set).

Pour chaque clé API, on maintient un sorted set des timestamps des requêtes
des 60 dernières secondes. Avant chaque appel :
1. ZREMRANGEBYSCORE pour purger les > 60s
2. ZCARD pour compter les restantes
3. Si >= limite : 429
4. Sinon : ZADD avec timestamp, EXPIRE 60s
"""
import time
import uuid
from typing import Optional

try:
    from redis.asyncio import Redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    Redis = None  # type: ignore

from app.core.config import settings


# Limite par défaut si la clé API n'en a pas une spécifique
DEFAULT_RATE_LIMIT_PER_MIN = 120

# Singleton client Redis (lazy)
_redis_client: Optional["Redis"] = None


async def get_redis() -> Optional["Redis"]:
    """Retourne un client Redis async, ou None si Redis n'est pas dispo."""
    global _redis_client
    if not REDIS_AVAILABLE:
        return None
    if _redis_client is None:
        try:
            _redis_client = Redis.from_url(
                settings.REDIS_URL if hasattr(settings, "REDIS_URL") else "redis://localhost:6379/0",
                decode_responses=True,
            )
            # Test ping (non-blocking on first call)
            await _redis_client.ping()
        except Exception:
            _redis_client = None
    return _redis_client


async def check_rate_limit(
    key: str,
    limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MIN,
) -> tuple[bool, int, int]:
    """
    Sliding window check.
    Retourne (allowed, current_count, limit).
    Si Redis n'est pas dispo, autorise toujours (fail-open).
    """
    redis = await get_redis()
    if redis is None:
        return True, 0, limit_per_minute

    now_ms = int(time.time() * 1000)
    window_start = now_ms - 60_000  # 60s glissantes

    try:
        # Pipeline atomique
        async with redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            results = await pipe.execute()
        current = results[1]

        if current >= limit_per_minute:
            return False, current, limit_per_minute

        # Ajouter cette requête
        await redis.zadd(key, {f"{now_ms}-{uuid.uuid4().hex[:8]}": now_ms})
        await redis.expire(key, 65)  # auto-cleanup
        return True, current + 1, limit_per_minute
    except Exception:
        # Si Redis tombe en cours de route, fail-open
        return True, 0, limit_per_minute
