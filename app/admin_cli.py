"""
Manage admin users from the command line.

    python -m app.admin_cli create <username>
    python -m app.admin_cli passwd <username>
    python -m app.admin_cli list
    python -m app.admin_cli disable <username>
    python -m app.admin_cli enable <username>

The password is read from a prompt rather than an argument, so it does not end
up in shell history or in the process list.
"""

import asyncio
import getpass
import sys

from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db.init_db import init_db
from app.db.models import AdminUser
from app.services import auth_service


def _prompt_password(confirm: bool = True) -> str:
    password = getpass.getpass("Password: ")
    if confirm and password != getpass.getpass("Confirm password: "):
        print("Passwords do not match.")
        raise SystemExit(1)
    problem = auth_service.validate_password_strength(password)
    if problem:
        print(problem)
        raise SystemExit(1)
    return password


async def cmd_create(username: str) -> None:
    password = _prompt_password()
    async with AsyncSessionLocal() as session:
        try:
            user = await auth_service.create_user(session, username, password)
            await session.commit()
        except ValueError as e:
            print(f"Error: {e}")
            raise SystemExit(1)
    print(f"Created admin user '{user.username}'.")


async def cmd_passwd(username: str) -> None:
    password = _prompt_password()
    async with AsyncSessionLocal() as session:
        try:
            await auth_service.set_password(session, username, password)
            await session.commit()
        except ValueError as e:
            print(f"Error: {e}")
            raise SystemExit(1)
    print(f"Password updated for '{username}'. All existing sessions were signed out.")


async def cmd_list() -> None:
    async with AsyncSessionLocal() as session:
        users = await auth_service.list_users(session)
    if not users:
        print("No admin users yet. Create one with: python -m app.admin_cli create <username>")
        return
    print(f"{'username':24} {'active':>7}  {'last login':>20}")
    print("-" * 56)
    for u in users:
        last = u.last_login_at.strftime("%Y-%m-%d %H:%M") if u.last_login_at else "never"
        print(f"{u.username:24} {'yes' if u.is_active else 'no':>7}  {last:>20}")


async def _set_active(username: str, active: bool) -> None:
    async with AsyncSessionLocal() as session:
        user = (
            await session.execute(
                select(AdminUser).where(AdminUser.username == username.strip().lower())
            )
        ).scalar_one_or_none()
        if not user:
            print(f"Error: user '{username}' not found.")
            raise SystemExit(1)
        user.is_active = active
        if not active:
            # Disabling must take effect now, not when the session expires
            await auth_service.revoke_all_sessions(session, user.id)
        await session.commit()
    print(f"User '{username}' {'enabled' if active else 'disabled'}.")


async def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        raise SystemExit(1)

    command, rest = args[0], args[1:]

    # Make sure the tables exist before touching them
    await init_db()

    if command == "create" and len(rest) == 1:
        await cmd_create(rest[0])
    elif command == "passwd" and len(rest) == 1:
        await cmd_passwd(rest[0])
    elif command == "list" and not rest:
        await cmd_list()
    elif command == "disable" and len(rest) == 1:
        await _set_active(rest[0], False)
    elif command == "enable" and len(rest) == 1:
        await _set_active(rest[0], True)
    else:
        print(__doc__)
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
