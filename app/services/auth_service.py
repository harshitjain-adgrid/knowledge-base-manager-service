"""
Admin authentication: users, passwords and sessions.

Kept deliberately small. Passwords are bcrypt-hashed, sessions are rows in the
database rather than JWTs so that signing out revokes access immediately, and
only a hash of each session token is stored so a database dump cannot be
replayed as a live login.
"""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import AdminSession, AdminUser

logger = logging.getLogger(__name__)
settings = get_settings()

MIN_PASSWORD_LENGTH = 8
TOKEN_BYTES = 32


# ── Passwords ──

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Check a password. Never raises on a malformed hash — it just fails."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        logger.warning("Stored password hash is unreadable; treating login as failed.")
        return False


def validate_password_strength(password: str) -> str | None:
    """Return an error message, or None if the password is acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return None


# ── Tokens ──

def _hash_token(token: str) -> str:
    """
    SHA-256 is right here, unlike for passwords.

    A session token is 32 bytes of entropy, so it cannot be brute-forced or
    guessed from a dictionary; the slow hashing that protects human-chosen
    passwords would only add latency to every request.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ── Users ──

async def create_user(db: AsyncSession, username: str, password: str) -> AdminUser:
    """Create an admin user. Raises ValueError on bad input or a duplicate name."""
    username = username.strip().lower()
    if not username:
        raise ValueError("Username cannot be empty.")
    if len(username) > 64:
        raise ValueError("Username must be 64 characters or fewer.")

    problem = validate_password_strength(password)
    if problem:
        raise ValueError(problem)

    existing = (
        await db.execute(select(AdminUser).where(AdminUser.username == username))
    ).scalar_one_or_none()
    if existing:
        raise ValueError(f"User '{username}' already exists.")

    user = AdminUser(username=username, password_hash=hash_password(password))
    db.add(user)
    await db.flush()
    logger.info(f"Created admin user '{username}'.")
    return user


async def set_password(db: AsyncSession, username: str, password: str) -> AdminUser:
    """Change a user's password and sign out all of their sessions."""
    problem = validate_password_strength(password)
    if problem:
        raise ValueError(problem)

    user = (
        await db.execute(
            select(AdminUser).where(AdminUser.username == username.strip().lower())
        )
    ).scalar_one_or_none()
    if not user:
        raise ValueError(f"User '{username}' not found.")

    user.password_hash = hash_password(password)
    # A password change must not leave old sessions usable
    await db.execute(delete(AdminSession).where(AdminSession.user_id == user.id))
    logger.info(f"Password changed for '{user.username}'; existing sessions revoked.")
    return user


async def count_users(db: AsyncSession) -> int:
    from sqlalchemy import func

    return (await db.execute(select(func.count(AdminUser.id)))).scalar() or 0


async def list_users(db: AsyncSession) -> list[AdminUser]:
    return list(
        (await db.execute(select(AdminUser).order_by(AdminUser.username))).scalars().all()
    )


# ── Sign in / out ──

async def authenticate(
    db: AsyncSession, username: str, password: str
) -> tuple[str, AdminUser] | None:
    """
    Verify credentials and open a session.

    Returns (token, user), or None if the credentials are wrong. The caller must
    not tell the client which half was wrong.
    """
    username = (username or "").strip().lower()
    user = (
        await db.execute(select(AdminUser).where(AdminUser.username == username))
    ).scalar_one_or_none()

    if user is None:
        # Hash anyway so a missing user and a wrong password take the same time,
        # which stops an attacker enumerating valid usernames by timing.
        verify_password(password or "", hash_password("timing-equaliser"))
        return None

    if not user.is_active:
        logger.warning(f"Sign-in attempt for disabled account '{username}'.")
        return None

    if not verify_password(password or "", user.password_hash):
        return None

    token = secrets.token_urlsafe(TOKEN_BYTES)
    db.add(
        AdminSession(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=settings.session_ttl_hours),
        )
    )
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info(f"'{user.username}' signed in.")
    return token, user


async def resolve_session(db: AsyncSession, token: str) -> AdminUser | None:
    """Return the user for a live session token, or None."""
    if not token:
        return None

    session = (
        await db.execute(
            select(AdminSession).where(AdminSession.token_hash == _hash_token(token))
        )
    ).scalar_one_or_none()

    if session is None:
        return None

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return None

    user = session.user
    if user is None or not user.is_active:
        return None
    return user


async def revoke_session(db: AsyncSession, token: str) -> bool:
    result = await db.execute(
        delete(AdminSession).where(AdminSession.token_hash == _hash_token(token))
    )
    return bool(result.rowcount)


async def revoke_all_sessions(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(delete(AdminSession).where(AdminSession.user_id == user_id))
    return result.rowcount or 0


async def purge_expired_sessions(db: AsyncSession) -> int:
    """Delete sessions that have already expired. Called at startup."""
    result = await db.execute(
        delete(AdminSession).where(AdminSession.expires_at <= datetime.now(timezone.utc))
    )
    return result.rowcount or 0
