"""Integration test for the forgotten-password recovery path (User Story 3 / FR-011).

The admin CLI (`medminder-admin user update … --password-stdin`) is a thin wrapper
over ``domain.users.update_user(new_password=…)`` — already covered by the CLI tests.
This test verifies the *composition*: admin-set password → user can sign in → user
re-secures it via the self-service editor → the temporary password no longer works.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.users import create_user, update_user

_INITIAL = "the original forgotten passphrase"
_TEMP = "temporary admin-set passphrase"
_USER_CHOSEN = "the users own private passphrase"


async def test_admin_recovery_then_self_change(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_user(
        session, email="rec@example.com", name="Rec", role="user", password=_INITIAL
    )

    # Admin sets a temporary password (the path the CLI uses).
    await update_user(session, email="rec@example.com", new_password=_TEMP)

    # User signs in with the temporary password.
    login = await client.post(
        "/auth/login", json={"email": "rec@example.com", "password": _TEMP}
    )
    assert login.status_code == 204, login.text
    client.cookies.set("mm_session", login.cookies["mm_session"])

    # User re-secures it via the editor.
    changed = await client.post(
        "/me/password",
        json={"current_password": _TEMP, "new_password": _USER_CHOSEN},
    )
    assert changed.status_code == 204, changed.text

    # The temporary password no longer grants access; the new one does.
    assert (
        await client.post(
            "/auth/login", json={"email": "rec@example.com", "password": _TEMP}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/auth/login",
            json={"email": "rec@example.com", "password": _USER_CHOSEN},
        )
    ).status_code == 204
