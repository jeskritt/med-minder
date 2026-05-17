"""Contract tests for ``GET /api/v1/medications/{medication_id}`` (Phase 5 US3).

The three 404 paths (unknown id / other-user / soft-deleted) MUST be
observably indistinguishable — no existence leak (FR-014, security
checklist).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.domain.users import create_user
from tests.db.factories import make_medication

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


async def test_detail_200_own_medication(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await create_user(
        session,
        email="billy@example.com",
        name="Billy",
        role="user",
        password=_PASSWORD,
    )
    med = await make_medication(
        session,
        user=user,
        name="Tylenol 3",
        timer_preference="multi_sub_dose",
        window_duration_minutes=360,
    )
    await session.flush()

    await _login(client, "billy@example.com")
    resp = await client.get(f"/api/v1/medications/{med.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(med.id)
    assert body["name"] == "Tylenol 3"
    assert body["timer_preference"] == "multi_sub_dose"
    assert "timer_state" in body
    assert body["timer_state"]["mode"] == "multi_sub_dose"


async def test_detail_404_paths_are_indistinguishable(
    client: AsyncClient, session: AsyncSession
) -> None:
    owner = await create_user(
        session,
        email="owner-d@example.com",
        name="O",
        role="user",
        password=_PASSWORD,
    )
    other = await create_user(
        session,
        email="other-d@example.com",
        name="X",
        role="user",
        password=_PASSWORD,
    )
    owned = await make_medication(session, user=owner, name="Owned")
    foreign = await make_medication(session, user=other, name="Foreign")
    deleted = await make_medication(session, user=owner, name="Deleted")
    deleted.deleted_at = datetime.now(UTC)
    await session.flush()

    await _login(client, "owner-d@example.com")

    unknown_resp = await client.get(f"/api/v1/medications/{uuid.uuid4()}")
    foreign_resp = await client.get(f"/api/v1/medications/{foreign.id}")
    deleted_resp = await client.get(f"/api/v1/medications/{deleted.id}")

    for resp in (unknown_resp, foreign_resp, deleted_resp):
        assert resp.status_code == 404

    # Bodies must be byte-identical — no field that reveals which case hit.
    assert unknown_resp.json() == foreign_resp.json() == deleted_resp.json()
    assert set(unknown_resp.json().keys()) == {"detail"}

    # Sanity: the owned med is still reachable (control).
    ok = await client.get(f"/api/v1/medications/{owned.id}")
    assert ok.status_code == 200


async def test_detail_401_unauthenticated(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/medications/{uuid.uuid4()}")
    assert resp.status_code == 401
