"""
Voxara AI - PostgreSQL Database & Storage Test Suite

Tests:
1. PostgreSQL connection URL normalization and asyncpg driver enforcement.
2. Prevention of silent fallback: missing or empty DATABASE_URL raises ValueError.
3. Explicit rejection of SQLite: SQLite URLs raise ValueError.
4. Rejection of unsupported database schemes (e.g., MySQL, MongoDB).
5. Automatic query parameter normalization (e.g., sslmode=require -> ssl=require).
6. Credential validation helper for PostgreSQL.
7. Database schema creation on PostgreSQL and presence of all 6 multi-user tables.
8. User account creation and automatic default preference seeding.
9. Multi-user preference isolation (User A cannot mutate User B's preferences).
10. Shared opportunity catalog creation, content_hash deduplication, and update semantics.
11. User-specific saved opportunities (application tracking pipeline: saved, applied, interviewing).
12. Multi-user application isolation (User A cannot view, mutate, or delete User B's saved applications).
13. Upcoming shared deadlines query (filtered for future dates and sorted chronologically).
14. User-specific notifications, deduplication, read tracking, and human-in-the-loop confirmation gate.
15. Workflow execution telemetry persistence and retrieval.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
import pytest
from sqlalchemy import select, text

from app.config import Settings, settings
from app.db.database import DatabaseManager
from app.db.base import Base
from app.db.models import (
    UserCreate,
    UserPreferenceUpdate,
    UserPreferencesUpdate,
    OpportunityCreate,
    OpportunityModel,
    SavedOpportunityCreate,
    SavedOpportunityUpdate,
    NotificationCreate,
    NotificationModel,
    compute_content_hash,
)
from app.db.tables import User, UserPreference, Opportunity, SavedOpportunity, Notification
from app.db import repository


# ---------------------------------------------------------------------------
# Section A: Configuration & Security Guardrails Tests (Always Executed)
# ---------------------------------------------------------------------------

def test_postgres_url_normalization():
    """Verifies that postgres:// and postgresql:// are normalized to postgresql+asyncpg://."""
    s1 = Settings(DATABASE_URL="postgres://user:secret@localhost:5432/voxara_ai")
    assert s1.normalized_database_url == "postgresql+asyncpg://user:secret@localhost:5432/voxara_ai"

    s2 = Settings(DATABASE_URL="postgresql://user:secret@localhost:5432/voxara_ai")
    assert s2.normalized_database_url == "postgresql+asyncpg://user:secret@localhost:5432/voxara_ai"

    s3 = Settings(DATABASE_URL="postgresql+asyncpg://user:secret@localhost:5432/voxara_ai")
    assert s3.normalized_database_url == "postgresql+asyncpg://user:secret@localhost:5432/voxara_ai"


def test_missing_database_url_raises_error():
    """Verifies that missing or empty DATABASE_URL raises ValueError without silent SQLite fallback."""
    s = Settings(DATABASE_URL="")
    with pytest.raises(ValueError, match="DATABASE_URL is not configured"):
        _ = s.normalized_database_url


def test_sqlite_database_url_rejected():
    """Verifies that SQLite URLs are explicitly rejected to prevent accidental fallback."""
    s = Settings(DATABASE_URL="sqlite+aiosqlite:///./data/voxara.db")
    with pytest.raises(ValueError, match="SQLite is not supported as the primary database"):
        _ = s.normalized_database_url

    s_plain = Settings(DATABASE_URL="sqlite:///test.db")
    with pytest.raises(ValueError, match="SQLite is not supported as the primary database"):
        _ = s_plain.normalized_database_url


def test_unsupported_database_scheme_rejected():
    """Verifies that non-PostgreSQL URL schemes are rejected."""
    s = Settings(DATABASE_URL="mysql://root:secret@localhost:3306/voxara")
    with pytest.raises(ValueError, match="Unsupported database URL scheme"):
        _ = s.normalized_database_url


def test_ssl_mode_normalization():
    """Verifies that sslmode=require is rewritten to ssl=require for asyncpg compatibility."""
    neon_url = "postgresql://user:pass@ep-sample.us-east-2.aws.neon.tech/neondb?sslmode=require"
    s = Settings(DATABASE_URL=neon_url)
    normalized = s.normalized_database_url
    assert "ssl=require" in normalized
    assert "sslmode=require" not in normalized
    assert normalized.startswith("postgresql+asyncpg://")


def test_database_credentials_validation():
    """Verifies Settings.validate_database_credentials() accurately detects invalid states."""
    # Empty
    s_empty = Settings(DATABASE_URL="")
    valid, reason = s_empty.validate_database_credentials()
    assert not valid
    assert "not set" in reason

    # SQLite
    s_sqlite = Settings(DATABASE_URL="sqlite+aiosqlite:///./data/voxara.db")
    valid, reason = s_sqlite.validate_database_credentials()
    assert not valid
    assert "SQLite" in reason

    # Placeholder
    s_placeholder = Settings(DATABASE_URL="postgresql+asyncpg://<username>:<password>@localhost:5432/voxara")
    valid, reason = s_placeholder.validate_database_credentials()
    assert not valid
    assert "placeholder" in reason

    # Valid PostgreSQL URL
    s_valid = Settings(DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/voxara_ai")
    valid, reason = s_valid.validate_database_credentials()
    assert valid
    assert reason == ""


# ---------------------------------------------------------------------------
# Section B: PostgreSQL Integration Tests (Executed when PostgreSQL is live)
# ---------------------------------------------------------------------------

def get_test_postgres_url() -> Optional[str]:
    """
    Returns the PostgreSQL connection string for testing.
    Requires TEST_DATABASE_URL to be set to prevent accidental drops on production databases.
    """
    return os.getenv("TEST_DATABASE_URL")


_POSTGRES_REACHABLE: Optional[bool] = None


def check_postgres_reachable(url: str) -> bool:
    """Synchronously checks if the PostgreSQL server is reachable (cached for test run)."""
    global _POSTGRES_REACHABLE
    if _POSTGRES_REACHABLE is not None:
        return _POSTGRES_REACHABLE

    try:
        mgr = DatabaseManager(database_url=url)
        is_live = asyncio.run(mgr.check_connection())
        asyncio.run(mgr.close_db())
        _POSTGRES_REACHABLE = is_live
    except Exception:
        _POSTGRES_REACHABLE = False
    return _POSTGRES_REACHABLE


@pytest.mark.asyncio
async def test_live_database_schema_presence():
    """
    Non-destructive test: Verifies that the currently configured DATABASE_URL
    has all 6 multi-user tables present and accessible.
    """
    mgr = DatabaseManager()
    is_live = await mgr.check_connection()
    if not is_live:
        pytest.skip("Configured database is not reachable. Skipping live schema check.")

    async with mgr.session() as session:
        result = await session.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        )
        table_names = {row[0] for row in result.fetchall()}
        expected_tables = {
            "users",
            "user_preferences",
            "opportunities",
            "saved_opportunities",
            "notifications",
            "workflow_executions",
        }
        for table in expected_tables:
            assert table in table_names, f"Expected table '{table}' not found in database."

    await mgr.close_db()


@pytest.fixture
def postgres_db(monkeypatch):
    """
    Fixture providing an isolated PostgreSQL database instance for destructive integration tests.
    Requires TEST_DATABASE_URL to be explicitly configured.
    """
    test_url = get_test_postgres_url()
    if not test_url:
        pytest.skip(
            "TEST_DATABASE_URL is not configured. Set TEST_DATABASE_URL to run destructive integration tests."
        )

    if not check_postgres_reachable(test_url):
        server_info = test_url.split("@")[-1] if "@" in test_url else test_url
        pytest.skip(
            f"PostgreSQL test server is unavailable at '{server_info}'."
        )

    mgr = DatabaseManager(database_url=test_url)
    asyncio.run(mgr.init_db())

    monkeypatch.setattr("app.db.database.db_manager", mgr)
    monkeypatch.setattr("app.db.repository.db_manager", mgr)

    yield mgr

    # Clean up tables on dedicated test database
    try:
        async def _cleanup():
            async with mgr.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            await mgr.close_db()
        asyncio.run(_cleanup())
    except Exception:
        pass


@pytest.mark.asyncio
async def test_user_creation_and_default_preferences(postgres_db):
    """Verifies user creation and automatic preference seeding."""
    user = await repository.get_or_create_user(
        user_id="user_alice",
        email="alice@example.com",
        name="Alice Smith",
    )
    assert user.id == "user_alice"
    assert user.email == "alice@example.com"
    assert user.name == "Alice Smith"

    prefs = await repository.get_user_preferences(user_id="user_alice")
    assert prefs.user_id == "user_alice"
    assert "internship" in prefs.preferred_types
    assert "hackathon" in prefs.preferred_types
    assert "AI Engineer" in prefs.target_roles
    assert prefs.min_match_score == 0.6
    assert prefs.notifications_enabled is True


@pytest.mark.asyncio
async def test_multiuser_preference_isolation(postgres_db):
    """Verifies that preferences for User A and User B are strictly isolated."""
    await repository.get_or_create_user(user_id="user_alice")
    await repository.get_or_create_user(user_id="user_bob")

    await repository.update_user_preferences(
        user_id="user_alice",
        updates=UserPreferenceUpdate(
            target_roles=["Robotics Engineer"],
            min_match_score=0.85,
            notifications_enabled=False,
        ),
    )

    alice_prefs = await repository.get_user_preferences("user_alice")
    bob_prefs = await repository.get_user_preferences("user_bob")

    assert alice_prefs.target_roles == ["Robotics Engineer"]
    assert alice_prefs.min_match_score == 0.85
    assert alice_prefs.notifications_enabled is False

    assert "AI Engineer" in bob_prefs.target_roles
    assert bob_prefs.min_match_score == 0.6
    assert bob_prefs.notifications_enabled is True


@pytest.mark.asyncio
async def test_shared_opportunity_deduplication(postgres_db):
    """Verifies that the same opportunity is stored once and deduplicated via content_hash."""
    url = "https://devpost.com/hackathons/agentic-hackathon-2026"
    title = "Global Agentic AI Hackathon 2026"
    content_hash = compute_content_hash(url, title)

    opp1 = OpportunityCreate(
        title=title,
        organization="Devpost",
        type="hackathon",
        source_url=url,
        source_name="Devpost",
        description="Initial description.",
        requirements=["Python", "LiveKit"],
        verified_status="verified",
    )

    saved1 = await repository.save_shared_opportunity(opp1)
    assert saved1.content_hash == content_hash
    first_id = saved1.id

    opp2 = OpportunityCreate(
        title=title,
        organization="Devpost",
        type="hackathon",
        source_url=url,
        source_name="Devpost",
        description="Updated description with $50,000 in prizes.",
        prize_or_salary="$50,000",
        requirements=["Python", "LiveKit", "PostgreSQL"],
        verified_status="verified",
    )

    saved2 = await repository.save_shared_opportunity(opp2)
    assert saved2.id == first_id
    assert saved2.description == "Updated description with $50,000 in prizes."
    assert saved2.prize_or_salary == "$50,000"
    assert "PostgreSQL" in saved2.requirements

    all_opps = await repository.list_shared_opportunities()
    assert len(all_opps) == 1


@pytest.mark.asyncio
async def test_multiuser_saved_opportunities_and_pipeline(postgres_db):
    """Verifies that multiple users can save the same shared opportunity into their separate pipelines."""
    opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Google Summer of Code 2026",
            organization="Google",
            type="fellowship",
            source_url="https://summerofcode.withgoogle.com",
            source_name="Google",
            description="Open-source mentorship program.",
            deadline=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )

    alice_saved = await repository.save_user_opportunity(
        user_id="user_alice",
        data=SavedOpportunityCreate(
            opportunity_id=opp.id,
            status="saved",
            notes="Need to draft proposal for repository X.",
            match_score=0.92,
        ),
    )
    assert alice_saved.user_id == "user_alice"
    assert alice_saved.status == "saved"

    bob_saved = await repository.save_user_opportunity(
        user_id="user_bob",
        data=SavedOpportunityCreate(
            opportunity_id=opp.id,
            status="applied",
            notes="Proposal submitted on deadline day.",
            match_score=0.88,
        ),
    )
    assert bob_saved.user_id == "user_bob"
    assert bob_saved.status == "applied"

    updated_alice = await repository.update_user_saved_opportunity(
        user_id="user_alice",
        saved_id=alice_saved.id,
        updates=SavedOpportunityUpdate(status="interviewing", notes="Proposal accepted! Starting interview phase."),
    )
    assert updated_alice is not None
    assert updated_alice.status == "interviewing"

    bob_list = await repository.list_user_saved_opportunities(user_id="user_bob")
    assert len(bob_list) == 1
    assert bob_list[0].status == "applied"


@pytest.mark.asyncio
async def test_user_data_isolation_and_authorization(postgres_db):
    """Verifies that User A cannot modify or delete User B's saved opportunities."""
    opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="AI Engineer Internship",
            organization="Tech Corp",
            type="internship",
            source_url="https://techcorp.example/intern",
            source_name="Company Site",
            description="Summer AI Internship.",
        )
    )

    bob_saved = await repository.save_user_opportunity(
        user_id="user_bob",
        data=SavedOpportunityCreate(opportunity_id=opp.id, status="applied", notes="Bob's private note"),
    )

    alice_tamper = await repository.update_user_saved_opportunity(
        user_id="user_alice",
        saved_id=bob_saved.id,
        updates=SavedOpportunityUpdate(notes="Tampered by Alice"),
    )
    assert alice_tamper is None

    alice_delete = await repository.delete_user_saved_opportunity(
        user_id="user_alice",
        saved_id=bob_saved.id,
    )
    assert alice_delete is False

    bob_check = await repository.list_user_saved_opportunities(user_id="user_bob")
    assert len(bob_check) == 1
    assert bob_check[0].notes == "Bob's private note"

    alice_check = await repository.list_user_saved_opportunities(user_id="user_alice")
    assert len(alice_check) == 0


@pytest.mark.asyncio
async def test_upcoming_shared_deadlines_sorting(postgres_db):
    """Verifies that deadlines are returned in chronological order and past deadlines are excluded."""
    now = datetime.now(timezone.utc)

    await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Past Hackathon",
            organization="Devpost",
            type="hackathon",
            source_url="https://example.com/past",
            source_name="Devpost",
            description="Finished last month.",
            deadline=now - timedelta(days=5),
        )
    )

    await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Late Hackathon",
            organization="Devpost",
            type="hackathon",
            source_url="https://example.com/late",
            source_name="Devpost",
            description="Ends in 20 days.",
            deadline=now + timedelta(days=20),
        )
    )

    await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Urgent Internship",
            organization="Startup",
            type="internship",
            source_url="https://example.com/urgent",
            source_name="Company Site",
            description="Ends in 2 days.",
            deadline=now + timedelta(days=2),
        )
    )

    deadlines = await repository.get_upcoming_shared_deadlines(limit=10)
    assert len(deadlines) == 2
    assert deadlines[0].title == "Urgent Internship"
    assert deadlines[1].title == "Late Hackathon"


@pytest.mark.asyncio
async def test_user_notifications_and_confirmation_gate(postgres_db):
    """Verifies user-scoped notification creation, deduplication, and confirmation gates."""
    notif1 = await repository.create_user_notification(
        NotificationCreate(
            user_id="user_alice",
            title="Deadline Approaching: GSoC 2026",
            message="Your saved application deadline is in 48 hours.",
            requires_confirmation=True,
            confirmation_token="TOKEN_SEC_999",
        )
    )
    assert notif1 is not None
    assert notif1.requires_confirmation is True
    assert notif1.is_read is False

    notif1_dup = await repository.create_user_notification(
        NotificationCreate(
            user_id="user_alice",
            title="Deadline Approaching: GSoC 2026",
            message="Your saved application deadline is in 48 hours.",
        )
    )
    assert notif1_dup is None

    bob_notifs = await repository.list_user_notifications(user_id="user_bob")
    assert len(bob_notifs) == 0

    bob_confirm = await repository.confirm_user_notification(
        user_id="user_bob",
        notification_id=notif1.id,
        confirmation_token="TOKEN_SEC_999",
    )
    assert bob_confirm is False

    wrong_confirm = await repository.confirm_user_notification(
        user_id="user_alice",
        notification_id=notif1.id,
        confirmation_token="WRONG_TOKEN",
    )
    assert wrong_confirm is False

    alice_confirm = await repository.confirm_user_notification(
        user_id="user_alice",
        notification_id=notif1.id,
        confirmation_token="TOKEN_SEC_999",
    )
    assert alice_confirm is True

    alice_notifs = await repository.list_user_notifications(user_id="user_alice", unread_only=True)
    assert len(alice_notifs) == 0


@pytest.mark.asyncio
async def test_workflow_execution_persistence(postgres_db):
    """Verifies that LangGraph execution telemetry is persisted and retrievable."""
    record = {
        "execution_id": "wf_test_12345",
        "workflow_type": "opportunity-hunter",
        "status": "completed",
        "task": "Find ML hackathons",
        "input_data": {"query": "ML", "type": "hackathon"},
        "result": {"found": 3, "best_match": "Global AI Hackathon"},
        "events": [
            {"node_name": "validate", "status": "completed", "duration_ms": 12.5},
            {"node_name": "fetch", "status": "completed", "duration_ms": 250.0},
        ],
    }

    await repository.get_or_create_user(user_id="user_alice")
    await repository.save_workflow_execution(record, user_id="user_alice")

    fetched = await repository.get_workflow_execution("wf_test_12345")
    assert fetched is not None
    assert fetched["execution_id"] == "wf_test_12345"
    assert fetched["status"] == "completed"
    assert fetched["user_id"] == "user_alice"
    assert len(fetched["events"]) == 2

    all_execs = await repository.list_workflow_executions(limit=10)
    assert any(e["execution_id"] == "wf_test_12345" for e in all_execs)
