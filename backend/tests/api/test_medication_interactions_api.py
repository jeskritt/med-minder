"""Phase 6 / US3 — rule-management API (create/list/delete only).

FR-015..FR-020. Validates ownership, the unordered-pair / self-pair /
positive-cooldown invariants, and cross-user isolation.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.users import create_user
from tests.db.factories import make_medication

_PASSWORD = "correct horse battery staple"


async def _login(client: AsyncClient, email: str) -> None:
    resp = await client.post(
        "/auth/login", json={"email": email, "password": _PASSWORD}
    )
    assert resp.status_code == 204
    client.cookies.set("mm_session", resp.cookies["mm_session"])


async def _user_with_two_meds(session: AsyncSession, email: str):
    user = await create_user(
        session, email=email, name="Molly", role="user", password=_PASSWORD
    )
    a = await make_medication(session, user=user, name="A")
    b = await make_medication(session, user=user, name="B")
    await session.flush()
    return user, a, b


async def test_create_list_delete_roundtrip(
    client: AsyncClient, session: AsyncSession
) -> None:
    _u, a, b = await _user_with_two_meds(session, "u-rt@example.com")
    await _login(client, "u-rt@example.com")

    created = await client.post(
        f"/api/v1/medications/{a.id}/interactions",
        json={"other_medication_id": str(b.id), "cooldown_minutes": 120},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["conflicting_medication_id"] == str(b.id)
    assert body["conflicting_medication_name"] == "B"
    assert body["cooldown_minutes"] == 120
    rule_id = body["id"]

    # Symmetric: visible from B's side too, naming A.
    from_b = (
        await client.get(f"/api/v1/medications/{b.id}/interactions")
    ).json()
    assert len(from_b) == 1
    assert from_b[0]["conflicting_medication_name"] == "A"

    deleted = await client.delete(
        f"/api/v1/medications/{a.id}/interactions/{rule_id}"
    )
    assert deleted.status_code == 204
    after = (
        await client.get(f"/api/v1/medications/{a.id}/interactions")
    ).json()
    assert after == []


async def test_duplicate_pair_409(
    client: AsyncClient, session: AsyncSession
) -> None:
    _u, a, b = await _user_with_two_meds(session, "u-dup@example.com")
    await _login(client, "u-dup@example.com")
    first = await client.post(
        f"/api/v1/medications/{a.id}/interactions",
        json={"other_medication_id": str(b.id), "cooldown_minutes": 60},
    )
    assert first.status_code == 201
    # Same unordered pair, created from the other side.
    dup = await client.post(
        f"/api/v1/medications/{b.id}/interactions",
        json={"other_medication_id": str(a.id), "cooldown_minutes": 90},
    )
    assert dup.status_code == 409, dup.text


async def test_self_pair_422(
    client: AsyncClient, session: AsyncSession
) -> None:
    _u, a, _b = await _user_with_two_meds(session, "u-self@example.com")
    await _login(client, "u-self@example.com")
    resp = await client.post(
        f"/api/v1/medications/{a.id}/interactions",
        json={"other_medication_id": str(a.id), "cooldown_minutes": 60},
    )
    assert resp.status_code == 422, resp.text


async def test_non_positive_cooldown_422(
    client: AsyncClient, session: AsyncSession
) -> None:
    _u, a, b = await _user_with_two_meds(session, "u-zero@example.com")
    await _login(client, "u-zero@example.com")
    resp = await client.post(
        f"/api/v1/medications/{a.id}/interactions",
        json={"other_medication_id": str(b.id), "cooldown_minutes": 0},
    )
    assert resp.status_code == 422, resp.text


async def test_cross_user_pairing_and_listing_isolated(
    client: AsyncClient, session: AsyncSession
) -> None:
    _u1, a1, _b1 = await _user_with_two_meds(session, "owner@example.com")
    other = await create_user(
        session,
        email="intruder@example.com",
        name="Intruder",
        role="user",
        password=_PASSWORD,
    )
    other_med = await make_medication(session, user=other, name="X")
    await session.flush()

    await _login(client, "intruder@example.com")
    # Cannot operate on the owner's medication (404, no existence leak).
    assert (
        await client.get(f"/api/v1/medications/{a1.id}/interactions")
    ).status_code == 404
    # Cannot pair own med with the owner's med.
    resp = await client.post(
        f"/api/v1/medications/{other_med.id}/interactions",
        json={"other_medication_id": str(a1.id), "cooldown_minutes": 30},
    )
    assert resp.status_code == 404, resp.text


async def test_delete_nonexistent_rule_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    _u, a, _b = await _user_with_two_meds(session, "u-del404@example.com")
    await _login(client, "u-del404@example.com")
    resp = await client.delete(
        f"/api/v1/medications/{a.id}/interactions/{uuid.uuid4()}"
    )
    assert resp.status_code == 404, resp.text
