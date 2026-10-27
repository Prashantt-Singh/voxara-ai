"""
Voxara AI - Phase 5: Saved Opportunities & Application Tracking Test Suite

Comprehensive automated test coverage for Phase 5 requirements:
1. Saving an opportunity (POST /api/opportunities/saved)
2. Viewing saved opportunities (GET /api/opportunities/saved) with opportunity relationships
   (source_name, source_url, application_url, deadline, verified_status)
3. Viewing a single saved opportunity (GET /api/opportunities/saved/{id})
4. Application tracking across all 7 statuses:
   - Saved, Interested, Applied, Interviewing, Offered, Rejected, Withdrawn
5. Private notes management (updating, clearing) scoped strictly to user relationship
6. Removing a saved opportunity (DELETE /api/opportunities/saved/{id}) without deleting the shared opportunity
7. Duplicate save prevention (idempotent upsert & database UniqueConstraint)
8. Multi-user isolation (User A vs User B data segregation)
9. Security & Unauthorized access:
   - Cross-user access denial (HTTP 404)
   - Client user_id spoofing prevention (HTTP 403 Forbidden on identity mismatch)
   - Unauthenticated access rejection when auth is required (HTTP 401 Unauthorized)
   - Malformed Authorization header rejection (HTTP 401 Unauthorized)
10. Database persistence across sessions
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.db.database import DatabaseManager
from app.db.models import (
    OpportunityCreate,
    SavedOpportunityCreate,
    SavedOpportunityUpdate,
    StatusUpdateRequest,
    NotesUpdateRequest,
    compute_content_hash,
)
from app.db.tables import Opportunity, SavedOpportunity
from app.db import repository
from app.config import settings
from app.services.auth_service import create_test_token

TEST_SECRET = "voxara-phase5-test-secret-32-chars-long"


def auth_headers(user_id: str) -> dict:
    """Helper generating Authorization header with cryptographically signed test JWT."""
    token = create_test_token(user_id=user_id, secret=TEST_SECRET)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """TestClient fixture with app."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch) -> Generator[DatabaseManager, None, None]:
    """Provides an isolated database for every test method."""
    monkeypatch.setattr(settings, "supabase_jwt_secret", TEST_SECRET)
    monkeypatch.setattr(settings, "require_auth", True)
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "phase5_test.db"
        mgr = DatabaseManager(database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}")
        monkeypatch.setattr("app.db.database.db_manager", mgr)
        monkeypatch.setattr("app.db.repository.db_manager", mgr)
        asyncio.run(mgr.init_db())
        yield mgr
        asyncio.run(mgr.close_db())


async def seed_test_opportunity(
    title: str = "Google Summer of Code 2026",
    org: str = "Google",
    opp_type: str = "fellowship",
    source_url: str = "https://summerofcode.withgoogle.com",
    app_url: str = "https://summerofcode.withgoogle.com/apply",
    deadline: datetime = None,
    verified_status: str = "verified",
) -> Opportunity:
    """Helper to seed a shared opportunity record."""
    if deadline is None:
        deadline = datetime.now(timezone.utc) + timedelta(days=45)
    return await repository.save_shared_opportunity(
        OpportunityCreate(
            title=title,
            organization=org,
            type=opp_type,
            source_url=source_url,
            application_url=app_url,
            source_name="Google GSoC",
            description="Global mentorship and open-source program.",
            deadline=deadline,
            location="Remote",
            verified_status=verified_status,
        )
    )


# ---------------------------------------------------------------------------
# Section 1: Saved Opportunities - Save, Retrieve, Single View
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_opportunity_success(client: TestClient):
    """Authenticated user saves an opportunity and receives full details."""
    opp = await seed_test_opportunity()

    headers = auth_headers("user_alice")
    res = client.post(
        "/api/opportunities/saved",
        headers=headers,
        json={
            "opportunity_id": opp.id,
            "status": "saved",
            "notes": "Target for summer 2026",
            "match_score": 0.94,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"].startswith("saved_")
    assert data["user_id"] == "user_alice"
    assert data["opportunity_id"] == opp.id
    assert data["status"] == "saved"
    assert data["notes"] == "Target for summer 2026"

    # Verify opportunity projection & relationship
    assert data["source_name"] == "Google GSoC"
    assert data["source_url"] == "https://summerofcode.withgoogle.com"
    assert data["application_url"] == "https://summerofcode.withgoogle.com/apply"
    assert data["verified_status"] == "verified"
    assert data["deadline"] is not None
    assert "opportunity" in data
    assert data["opportunity"]["title"] == "Google Summer of Code 2026"


@pytest.mark.asyncio
async def test_save_nonexistent_opportunity_returns_404(client: TestClient):
    """Attempting to save a non-existent opportunity returns HTTP 404."""
    headers = auth_headers("user_alice")
    res = client.post(
        "/api/opportunities/saved",
        headers=headers,
        json={
            "opportunity_id": "opp_does_not_exist_999",
            "status": "saved",
        },
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_view_saved_opportunities_list(client: TestClient):
    """User can list their saved opportunities with all verification and URL metadata."""
    opp1 = await seed_test_opportunity(title="GSoC 2026", org="Google")
    opp2 = await seed_test_opportunity(
        title="MLH Fellowship Spring 2026",
        org="Major League Hacking",
        source_url="https://fellowship.mlh.io",
        app_url="https://fellowship.mlh.io/apply",
    )

    headers = auth_headers("user_alice")
    client.post("/api/opportunities/saved", headers=headers, json={"opportunity_id": opp1.id, "status": "saved"})
    client.post("/api/opportunities/saved", headers=headers, json={"opportunity_id": opp2.id, "status": "interested"})

    # List all saved opportunities
    res = client.get("/api/opportunities/saved", headers=headers)
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2

    titles = {it["opportunity"]["title"] for it in items}
    assert "GSoC 2026" in titles
    assert "MLH Fellowship Spring 2026" in titles

    # Verify application URL and source URL presence
    for item in items:
        assert item["source_url"] is not None
        assert item["application_url"] is not None
        assert item["verified_status"] is not None


@pytest.mark.asyncio
async def test_view_single_saved_opportunity(client: TestClient):
    """User can view an individual saved opportunity by saved_id."""
    opp = await seed_test_opportunity()
    headers = auth_headers("user_alice")
    save_res = client.post("/api/opportunities/saved", headers=headers, json={"opportunity_id": opp.id, "status": "saved"})
    saved_id = save_res.json()["id"]

    get_res = client.get(f"/api/opportunities/saved/{saved_id}", headers=headers)
    assert get_res.status_code == 200
    single = get_res.json()
    assert single["id"] == saved_id
    assert single["opportunity_id"] == opp.id
    assert single["source_url"] == opp.source_url
    assert single["application_url"] == opp.application_url
    assert single["verified_status"] == opp.verified_status


@pytest.mark.asyncio
async def test_view_unknown_saved_id_returns_404(client: TestClient):
    """Requesting an unknown saved ID returns 404."""
    headers = auth_headers("user_alice")
    res = client.get("/api/opportunities/saved/saved_non_existent", headers=headers)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Section 2: Application Tracking - Statuses & Notes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_seven_tracking_statuses(client: TestClient):
    """
    Verifies that all 7 required progress tracking statuses are supported:
    Saved, Interested, Applied, Interviewing, Offered, Rejected, Withdrawn.
    """
    statuses = [
        "Saved",
        "Interested",
        "Applied",
        "Interviewing",
        "Offered",
        "Rejected",
        "Withdrawn",
    ]

    opp = await seed_test_opportunity()
    headers = auth_headers("user_tracker")

    # Initial save
    save_res = client.post(
        "/api/opportunities/saved",
        headers=headers,
        json={"opportunity_id": opp.id, "status": "Saved"},
    )
    assert save_res.status_code == 200
    saved_id = save_res.json()["id"]

    for status_to_test in statuses:
        # Test status update via dedicated /status endpoint
        patch_res = client.patch(
            f"/api/opportunities/saved/{saved_id}/status",
            headers=headers,
            json={"status": status_to_test},
        )
        assert patch_res.status_code == 200
        # Canonical lowercase in DB
        assert patch_res.json()["status"] == status_to_test.lower()

        # Test filtering by status case-insensitively
        filter_res = client.get(f"/api/opportunities/saved?status={status_to_test}", headers=headers)
        assert filter_res.status_code == 200
        matched = filter_res.json()
        assert len(matched) == 1
        assert matched[0]["status"] == status_to_test.lower()


@pytest.mark.asyncio
async def test_invalid_status_rejected_with_422(client: TestClient):
    """Submitting an invalid status returns HTTP 422 Unprocessable Entity."""
    opp = await seed_test_opportunity()
    headers = auth_headers("user_tracker")
    save_res = client.post("/api/opportunities/saved", headers=headers, json={"opportunity_id": opp.id, "status": "saved"})
    saved_id = save_res.json()["id"]

    bad_res = client.patch(
        f"/api/opportunities/saved/{saved_id}/status",
        headers=headers,
        json={"status": "invalid_status_type"},
    )
    assert bad_res.status_code == 422


@pytest.mark.asyncio
async def test_update_private_notes(client: TestClient):
    """User can add, update, and clear private notes on their saved opportunity."""
    opp = await seed_test_opportunity()
    headers = auth_headers("user_alice")
    save_res = client.post("/api/opportunities/saved", headers=headers, json={"opportunity_id": opp.id, "status": "saved"})
    saved_id = save_res.json()["id"]

    # 1. Update notes via /notes endpoint
    res1 = client.patch(
        f"/api/opportunities/saved/{saved_id}/notes",
        headers=headers,
        json={"notes": "First interview scheduled for next Thursday."},
    )
    assert res1.status_code == 200
    assert res1.json()["notes"] == "First interview scheduled for next Thursday."

    # 2. Update status and notes simultaneously via PATCH /saved/{id}
    res2 = client.patch(
        f"/api/opportunities/saved/{saved_id}",
        headers=headers,
        json={"status": "interviewing", "notes": "Interview went well, awaiting coding test."},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "interviewing"
    assert res2.json()["notes"] == "Interview went well, awaiting coding test."

    # 3. Clear notes
    res3 = client.patch(
        f"/api/opportunities/saved/{saved_id}/notes",
        headers=headers,
        json={"notes": None},
    )
    assert res3.status_code == 200
    assert res3.json()["notes"] is None


# ---------------------------------------------------------------------------
# Section 3: Removal & Opportunity Preservation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remove_saved_opportunity_preserves_shared_opportunity(client: TestClient, isolated_db: DatabaseManager):
    """
    Removing a saved opportunity removes the user's relationship record,
    but DOES NOT delete the underlying shared opportunity record.
    """
    opp = await seed_test_opportunity()
    headers = auth_headers("user_alice")

    save_res = client.post("/api/opportunities/saved", headers=headers, json={"opportunity_id": opp.id, "status": "saved"})
    saved_id = save_res.json()["id"]

    # Delete the saved opportunity
    del_res = client.delete(f"/api/opportunities/saved/{saved_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json() == {"status": "deleted", "saved_id": saved_id}

    # Verify pipeline is now empty for user
    list_res = client.get("/api/opportunities/saved", headers=headers)
    assert len(list_res.json()) == 0

    # CRITICAL: Verify shared opportunity record STILL EXISTS in the database
    async with isolated_db.session() as session:
        result = await session.execute(select(Opportunity).where(Opportunity.id == opp.id))
        still_present = result.scalar_one_or_none()
        assert still_present is not None, "Shared opportunity was improperly deleted!"
        assert still_present.title == opp.title


# ---------------------------------------------------------------------------
# Section 4: Duplicate Saves Prevention
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_save_idempotency(client: TestClient, isolated_db: DatabaseManager):
    """
    Saving the same opportunity twice for the same user updates status/notes
    idempotently without creating duplicate database rows.
    """
    opp = await seed_test_opportunity()
    headers = auth_headers("user_alice")

    # First save: saved
    res1 = client.post(
        "/api/opportunities/saved",
        headers=headers,
        json={"opportunity_id": opp.id, "status": "saved", "notes": "Initial interest"},
    )
    assert res1.status_code == 200
    saved_id = res1.json()["id"]

    # Second save: applied with updated notes
    res2 = client.post(
        "/api/opportunities/saved",
        headers=headers,
        json={"opportunity_id": opp.id, "status": "applied", "notes": "Submitted today!"},
    )
    assert res2.status_code == 200
    assert res2.json()["id"] == saved_id  # Same record ID
    assert res2.json()["status"] == "applied"
    assert res2.json()["notes"] == "Submitted today!"

    # Verify database has exactly 1 record for this user and opportunity
    async with isolated_db.session() as session:
        result = await session.execute(
            select(SavedOpportunity).where(
                SavedOpportunity.user_id == "user_alice",
                SavedOpportunity.opportunity_id == opp.id,
            )
        )
        records = result.scalars().all()
        assert len(records) == 1


@pytest.mark.asyncio
async def test_database_unique_constraint_enforced(isolated_db: DatabaseManager):
    """
    Direct database test: UniqueConstraint('user_id', 'opportunity_id')
    strictly prevents duplicate rows.
    """
    opp = await seed_test_opportunity()
    await repository.get_or_create_user("user_alice")

    async with isolated_db.session() as session:
        row1 = SavedOpportunity(user_id="user_alice", opportunity_id=opp.id, status="saved")
        session.add(row1)
        await session.commit()

    # Attempting to insert a duplicate must raise IntegrityError
    with pytest.raises(IntegrityError):
        async with isolated_db.session() as session:
            row2 = SavedOpportunity(user_id="user_alice", opportunity_id=opp.id, status="applied")
            session.add(row2)
            await session.commit()


# ---------------------------------------------------------------------------
# Section 5: Multi-User Isolation & Separate Users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiuser_isolation_and_independence(client: TestClient):
    """
    Multiple users can save the same shared opportunity. Each user maintains
    completely independent tracking statuses and private notes.
    """
    opp = await seed_test_opportunity(title="Anthropic AI Fellow", org="Anthropic")

    alice_headers = auth_headers("user_alice")
    bob_headers = auth_headers("user_bob")

    # Alice saves as interviewing with Alice's note
    res_a = client.post(
        "/api/opportunities/saved",
        headers=alice_headers,
        json={"opportunity_id": opp.id, "status": "interviewing", "notes": "Alice: Prep systems round"},
    )
    assert res_a.status_code == 200
    alice_saved_id = res_a.json()["id"]

    # Bob saves as offered with Bob's note
    res_b = client.post(
        "/api/opportunities/saved",
        headers=bob_headers,
        json={"opportunity_id": opp.id, "status": "offered", "notes": "Bob: Received offer letter!"},
    )
    assert res_b.status_code == 200
    bob_saved_id = res_b.json()["id"]

    assert alice_saved_id != bob_saved_id

    # Alice views her list
    alice_list = client.get("/api/opportunities/saved", headers=alice_headers).json()
    assert len(alice_list) == 1
    assert alice_list[0]["status"] == "interviewing"
    assert alice_list[0]["notes"] == "Alice: Prep systems round"

    # Bob views his list
    bob_list = client.get("/api/opportunities/saved", headers=bob_headers).json()
    assert len(bob_list) == 1
    assert bob_list[0]["status"] == "offered"
    assert bob_list[0]["notes"] == "Bob: Received offer letter!"

    # Alice removes her opportunity
    del_res = client.delete(f"/api/opportunities/saved/{alice_saved_id}", headers=alice_headers)
    assert del_res.status_code == 200

    # Bob's opportunity is completely unaffected
    bob_check = client.get("/api/opportunities/saved", headers=bob_headers).json()
    assert len(bob_check) == 1
    assert bob_check[0]["id"] == bob_saved_id
    assert bob_check[0]["status"] == "offered"


# ---------------------------------------------------------------------------
# Section 6: Security & Unauthorized Access
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthorized_cross_user_access_blocked(client: TestClient):
    """
    User A cannot view, update, or delete User B's saved opportunities.
    All cross-user attempts return HTTP 404 (Not Found or Unauthorized).
    """
    opp = await seed_test_opportunity()

    bob_headers = auth_headers("user_bob")
    alice_headers = auth_headers("user_alice")

    # Bob creates a saved opportunity
    save_res = client.post(
        "/api/opportunities/saved",
        headers=bob_headers,
        json={"opportunity_id": opp.id, "status": "applied", "notes": "Bob private note"},
    )
    bob_saved_id = save_res.json()["id"]

    # 1. Alice tries to view Bob's saved opportunity -> 404
    get_res = client.get(f"/api/opportunities/saved/{bob_saved_id}", headers=alice_headers)
    assert get_res.status_code == 404

    # 2. Alice tries to update Bob's saved opportunity -> 404
    patch_res = client.patch(
        f"/api/opportunities/saved/{bob_saved_id}",
        headers=alice_headers,
        json={"status": "rejected", "notes": "Tampered by Alice"},
    )
    assert patch_res.status_code == 404

    # 3. Alice tries to update Bob's status -> 404
    status_res = client.patch(
        f"/api/opportunities/saved/{bob_saved_id}/status",
        headers=alice_headers,
        json={"status": "withdrawn"},
    )
    assert status_res.status_code == 404

    # 4. Alice tries to update Bob's notes -> 404
    notes_res = client.patch(
        f"/api/opportunities/saved/{bob_saved_id}/notes",
        headers=alice_headers,
        json={"notes": "Tampered note"},
    )
    assert notes_res.status_code == 404

    # 5. Alice tries to delete Bob's saved opportunity -> 404
    del_res = client.delete(f"/api/opportunities/saved/{bob_saved_id}", headers=alice_headers)
    assert del_res.status_code == 404

    # Verify Bob's record was completely untouched
    bob_get = client.get(f"/api/opportunities/saved/{bob_saved_id}", headers=bob_headers)
    assert bob_get.status_code == 200
    assert bob_get.json()["status"] == "applied"
    assert bob_get.json()["notes"] == "Bob private note"


@pytest.mark.asyncio
async def test_client_supplied_user_id_mismatch_rejected_with_403(client: TestClient):
    """
    Security requirement: Never trust a user ID supplied by the client without
    validating it against the authenticated identity.
    If authenticated as Alice, passing ?user_id=bob returns HTTP 403 Forbidden.
    """
    opp = await seed_test_opportunity()
    alice_headers = auth_headers("user_alice")

    # Attempt to save with spoofed user_id query parameter
    res = client.post(
        f"/api/opportunities/saved?user_id=user_bob",
        headers=alice_headers,
        json={"opportunity_id": opp.id, "status": "saved"},
    )
    assert res.status_code == 403
    assert "does not match" in res.json()["detail"]

    # Attempt to list with spoofed user_id query parameter
    list_res = client.get(
        "/api/opportunities/saved?user_id=user_bob",
        headers=alice_headers,
    )
    assert list_res.status_code == 403
    assert "does not match" in list_res.json()["detail"]


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected_when_strict_auth_enabled(client: TestClient):
    """
    Security requirement: When strict authentication is enabled,
    requests without Bearer tokens return HTTP 401 Unauthorized.
    """
    opp = await seed_test_opportunity()

    # Pass X-Require-Auth header to activate strict authentication check
    headers = {"X-Require-Auth": "true"}

    res = client.post(
        "/api/opportunities/saved",
        headers=headers,
        json={"opportunity_id": opp.id, "status": "saved"},
    )
    assert res.status_code == 401
    assert "Authentication required" in res.json()["detail"]


@pytest.mark.asyncio
async def test_malformed_auth_header_rejected_with_401(client: TestClient):
    """Supplying malformed, invalid, or tampered Authorization headers returns HTTP 401."""
    opp = await seed_test_opportunity()

    # 1. Scheme other than Bearer (e.g. Basic)
    res1 = client.post(
        "/api/opportunities/saved",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
        json={"opportunity_id": opp.id, "status": "saved"},
    )
    assert res1.status_code == 401
    assert "Expected 'Bearer <token>'" in res1.json()["detail"]

    # 2. Empty Bearer token
    res2 = client.post(
        "/api/opportunities/saved",
        headers={"Authorization": "Bearer  "},
        json={"opportunity_id": opp.id, "status": "saved"},
    )
    assert res2.status_code == 401

    # 3. Plain string (not a valid JWT)
    res3 = client.post(
        "/api/opportunities/saved",
        headers={"Authorization": "Bearer user_alice_plain_string"},
        json={"opportunity_id": opp.id, "status": "saved"},
    )
    assert res3.status_code == 401
    assert "signed Supabase JWT is required" in res3.json()["detail"]

    # 4. Tampered JWT signature
    valid_token = create_test_token(user_id="user_alice", secret=TEST_SECRET)
    header_b64, payload_b64, sig_b64 = valid_token.split(".")
    tampered_sig = ("A" if sig_b64[0] != "A" else "B") + sig_b64[1:]
    tampered_token = f"{header_b64}.{payload_b64}.{tampered_sig}"
    res4 = client.post(
        "/api/opportunities/saved",
        headers={"Authorization": f"Bearer {tampered_token}"},
        json={"opportunity_id": opp.id, "status": "saved"},
    )
    assert res4.status_code == 401
    assert "verification failed" in res4.json()["detail"].lower()

    # 5. Expired token
    expired_token = create_test_token(user_id="user_alice", secret=TEST_SECRET, expires_in=-100)
    res5 = client.post(
        "/api/opportunities/saved",
        headers={"Authorization": f"Bearer {expired_token}"},
        json={"opportunity_id": opp.id, "status": "saved"},
    )
    assert res5.status_code == 401
    assert "expired" in res5.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Section 7: Database Persistence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_saved_opportunity_persistence_across_sessions(isolated_db: DatabaseManager):
    """
    Verifies that saved opportunity records and updates persist across database sessions.
    """
    opp = await seed_test_opportunity(title="Persisted Fellowship", org="OpenAI")
    await repository.get_or_create_user("user_persistent")

    # Session 1: Create
    saved_id: str
    async with isolated_db.session() as session1:
        item = SavedOpportunity(
            user_id="user_persistent",
            opportunity_id=opp.id,
            status="applied",
            notes="Session 1 note",
        )
        session1.add(item)
        await session1.commit()
        await session1.refresh(item)
        saved_id = item.id

    # Session 2: Read & Update
    async with isolated_db.session() as session2:
        result = await session2.execute(
            select(SavedOpportunity).where(SavedOpportunity.id == saved_id)
        )
        loaded = result.scalar_one_or_none()
        assert loaded is not None
        assert loaded.status == "applied"
        assert loaded.notes == "Session 1 note"

        loaded.status = "interviewing"
        loaded.notes = "Session 2 note"
        await session2.commit()

    # Session 3: Verify Persistence
    async with isolated_db.session() as session3:
        result = await session3.execute(
            select(SavedOpportunity).where(SavedOpportunity.id == saved_id)
        )
        final_check = result.scalar_one_or_none()
        assert final_check is not None
        assert final_check.status == "interviewing"
        assert final_check.notes == "Session 2 note"
