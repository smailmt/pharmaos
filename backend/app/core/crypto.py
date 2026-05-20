"""
Chiffrement réversible de secrets (Fernet AES-128-CBC + HMAC).

La clé maître est dérivée du SECRET_KEY de l'app. Si SECRET_KEY change,
les secrets existants deviennent illisibles → c'est délibéré (rotation).
"""
import base64
import hashlib
from cryptography.fernet import Fernet
from app.core.config import settings


def _derive_fernet_key() -> bytes:
    """Dérive une clé Fernet 32-bytes depuis SECRET_KEY."""
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_derive_fernet_key())


def encrypt(plaintext: str) -> str:
    """Chiffre une chaîne, retourne le token base64."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Déchiffre un token Fernet. Lève InvalidToken si la clé a changé."""
    return _fernet.decrypt(token.encode()).decode()
