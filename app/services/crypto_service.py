"""
Encryption for the one secret this service has to store: the connection string
of an additional knowledge base.

Everything else stays out of the database on purpose — the primary DSN is read
from the environment on every start, and embedding API keys live in `.env` and
are only ever shown masked. Additional knowledge bases are different: an admin
types their connection details into the UI, so they have to be persisted
somewhere, and that somewhere is a table.

Encrypting them at rest means a dump of the control database does not hand over
working credentials to every other Postgres host the team has registered. The
key lives in SECRET_KEY, outside the database, so the dump alone is not enough.
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Marks a value produced by this module, so a plaintext value written by hand
# is never mistaken for ciphertext.
PREFIX = "enc:v1:"


class SecretsUnavailable(RuntimeError):
    """SECRET_KEY is not configured, so nothing can be encrypted or decrypted."""


def _fernet() -> Fernet:
    raw = (settings.secret_key or "").strip()
    if not raw:
        raise SecretsUnavailable(
            "SECRET_KEY is not set, so connection strings cannot be stored "
            "safely. Generate one and add it to .env:\n"
            '    python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )

    # A proper 32-byte urlsafe-base64 Fernet key is used as-is. Anything else is
    # hashed to that shape, so a hand-written passphrase still works instead of
    # failing with an opaque binascii error.
    try:
        key_bytes = base64.urlsafe_b64decode(raw.encode())
        if len(key_bytes) == 32:
            return Fernet(raw.encode())
    except Exception:
        pass

    derived = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(derived)


def is_available() -> bool:
    """Whether secrets can be encrypted at all, for a clear 400 instead of a 500."""
    try:
        _fernet()
        return True
    except Exception:
        return False


def encrypt(plaintext: str) -> str:
    """Encrypt a value for storage. The result is safe to write to a column."""
    return PREFIX + _fernet().encrypt(plaintext.encode()).decode()


def decrypt(value: str) -> str:
    """
    Decrypt a stored value.

    Raises SecretsUnavailable when SECRET_KEY is missing or has been rotated
    away from the one that encrypted this value — which is a configuration
    problem, not a corrupt row, and the message says so.
    """
    if not value.startswith(PREFIX):
        # Written before encryption existed, or edited in by hand. Accept it so
        # the knowledge base still works, but say so once.
        logger.warning("Found an unencrypted stored secret; re-save it to encrypt it.")
        return value

    try:
        return _fernet().decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken:
        raise SecretsUnavailable(
            "A stored connection string could not be decrypted. SECRET_KEY has "
            "changed since it was saved — restore the old key, or re-enter the "
            "connection details for this knowledge base."
        )
