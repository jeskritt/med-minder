"""Contract tests for ``POST /api/doses/{id}/void``."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.users import create_user
from tests.db.factories import make_dose, make_medication

_PASSWORD = "correct horse battery staple"


async def _login(client: AsyncClient, email: str) -> None:
    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": _PASSWORD},
    )
    assert resp.status_code == 204
    cookie = resp.cookies.get("mm_session")
    assert cookie is not None
    client.cookies.set("mm_session", cookie)


async def test_void_204(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session,
        email="v204@example.com",
        name="U",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(session, user=user)
    dose = await make_dose(session, user=user, medication=med)

    await _login(client, "v204@example.com")
    resp = await client.post(f"/api/doses/{dose.id}/void")
    assert resp.status_code == 204


async def test_void_409_double(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session,
        email="v409@example.com",
        name="U",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(session, user=user)
    dose = await make_dose(session, user=user, medication=med)

    await _login(client, "v409@example.com")
    first = await client.post(f"/api/doses/{dose.id}/void")
    assert first.status_code == 204
    second = await client.post(f"/api/doses/{dose.id}/void")
    assert second.status_code == 409


async def test_void_403_cross_user(
    client: AsyncClient, session: AsyncSession
) -> None:
    owner = await create_user(
        session,
        email="vown@example.com",
        name="O",
        role="user",
        password=_PASSWORD,
    )
    await create_user(
        session,
        email="vint@example.com",
        name="I",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(session, user=owner)
    dose = await make_dose(session, user=owner, medication=med)

    await _login(client, "vint@example.com")
    resp = await client.post(f"/api/doses/{dose.id}/void")
    assert resp.status_code == 403


async def test_void_404_missing(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_user(
        session,
        email="v404@example.com",
        name="U",
        role="user",
        password=_PASSWORD,
    )
    await _login(client, "v404@example.com")
    resp = await client.post(f"/api/doses/{uuid.uuid4()}/void")
    assert resp.status_code == 404


async def test_void_401_unauthenticated(client: AsyncClient) -> None:
    resp = await client.post(f"/api/doses/{uuid.uuid4()}/void")
    assert resp.status_code == 401
