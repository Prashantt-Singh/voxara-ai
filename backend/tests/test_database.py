"""
Voxara AI - Multi-User Database & Storage Test Suite (Phase 1)

Tests:
1. Database initialization, schema creation, and SQLite foreign key constraints.
2. User account creation and automatic default preference seeding.
3. Multi-user preference isolation (User A cannot mutate User B's preferences).
4. Shared opportunity catalog creation, content_hash deduplication, and update semantics.
5. User-specific saved opportunities (application tracking pipeline: saved, applied, interviewing).
6. Multi-user application isolation (User A cannot view, mutate, or delete User B's saved applications).
7. Upcoming shared deadlines query (filtered for future dates and sorted chronologically).
8. User-specific notifications, deduplication, read tracking, and human-in-the-loop confirmation gate.
9. Workflow execution telemetry persistence and retrieval.
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from sqlalchemy import select, text

from app.db.database import DatabaseManager
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


@pytest.fixture
def temp_db(monkeypatch):
    """Fixture creating an isolated temporary database for async tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_voxara.db"
        mgr = DatabaseManager(database_url=f"sqlite+aiosqlite:///{db_file.as_posix()}")
        monkeypatch.setattr("app.db.database.db_manager", mgr)
        monkeypatch.setattr("app.db.repository.db_manager", mgr)
        asyncio.run(mgr.init_db())
        yield mgr
        asyncio.run(mgr.close_db())


@pytest.mark.asyncio
async def test_database_initialization_and_foreign_keys(temp_db):
    """Verifies that all 6 multi-user tables are created and SQLite foreign keys are enforced."""
    async with temp_db.session() as session:
        # Check SQLite foreign keys
        result = await session.execute(text("PRAGMA foreign_keys;"))
        fk_status = result.scalar()
        assert fk_status == 1

        # Check table presence
        tables_res = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table';")
        )
        table_names = {row[0] for row in tables_res.fetchall()}
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


@pytest.mark.asyncio
async def test_user_creation_and_default_preferences(temp_db):
    """Verifies user creation and automatic preference seeding."""
    user = await repository.get_or_create_user(
        user_id="user_alice",
        email="alice@example.com",
        name="Alice Smith",
    )
    assert user.id == "user_alice"
    assert user.email == "alice@example.com"
    assert user.name == "Alice Smith"

    # Default preferences should have been seeded
    prefs = await repository.get_user_preferences(user_id="user_alice")
    assert prefs.user_id == "user_alice"
    assert "internship" in prefs.preferred_types
    assert "hackathon" in prefs.preferred_types
    assert "AI Engineer" in prefs.target_roles
    assert prefs.min_match_score == 0.6
    assert prefs.notifications_enabled is True


@pytest.mark.asyncio
async def test_multiuser_preference_isolation(temp_db):
    """Verifies that preferences for User A and User B are strictly isolated."""
    await repository.get_or_create_user(user_id="user_alice")
    await repository.get_or_create_user(user_id="user_bob")

    # Update Alice's preferences
    await repository.update_user_preferences(
        user_id="user_alice",
        updates=UserPreferenceUpdate(
            target_roles=["Robotics Engineer"],
            min_match_score=0.85,
            notifications_enabled=False,
        ),
    )

    # Bob's preferences should remain untouched defaults
    alice_prefs = await repository.get_user_preferences("user_alice")
    bob_prefs = await repository.get_user_preferences("user_bob")

    assert alice_prefs.target_roles == ["Robotics Engineer"]
    assert alice_prefs.min_match_score == 0.85
    assert alice_prefs.notifications_enabled is False

    assert "AI Engineer" in bob_prefs.target_roles
    assert bob_prefs.min_match_score == 0.6
    assert bob_prefs.notifications_enabled is True


@pytest.mark.asyncio
async def test_shared_opportunity_deduplication(temp_db):
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

    # Second insert with updated description must update the record without creating a duplicate
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
    assert saved2.id == first_id  # Same opportunity ID preserved
    assert saved2.description == "Updated description with $50,000 in prizes."
    assert saved2.prize_or_salary == "$50,000"
    assert "PostgreSQL" in saved2.requirements

    # Verify database has exactly 1 row
    all_opps = await repository.list_shared_opportunities()
    assert len(all_opps) == 1


@pytest.mark.asyncio
async def test_multiuser_saved_opportunities_and_pipeline(temp_db):
    """Verifies that multiple users can save the same shared opportunity into their separate pipelines."""
    # Create shared opportunity
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

    # User Alice saves the opportunity
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
    assert alice_saved.notes == "Need to draft proposal for repository X."

    # User Bob applies to the same opportunity
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
    assert bob_saved.notes == "Proposal submitted on deadline day."

    # Alice transitions her pipeline: saved -> interviewing
    updated_alice = await repository.update_user_saved_opportunity(
        user_id="user_alice",
        saved_id=alice_saved.id,
        updates=SavedOpportunityUpdate(status="interviewing", notes="Proposal accepted! Starting interview phase."),
    )
    assert updated_alice is not None
    assert updated_alice.status == "interviewing"

    # Bob's status must remain 'applied'
    bob_list = await repository.list_user_saved_opportunities(user_id="user_bob")
    assert len(bob_list) == 1
    assert bob_list[0].status == "applied"
    assert bob_list[0].notes == "Proposal submitted on deadline day."


@pytest.mark.asyncio
async def test_user_data_isolation_and_authorization(temp_db):
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

    # Alice tries to mutate Bob's saved opportunity -> must return None (unauthorized)
    alice_tamper = await repository.update_user_saved_opportunity(
        user_id="user_alice",
        saved_id=bob_saved.id,
        updates=SavedOpportunityUpdate(notes="Tampered by Alice"),
    )
    assert alice_tamper is None

    # Alice tries to delete Bob's saved opportunity -> must return False (unauthorized)
    alice_delete = await repository.delete_user_saved_opportunity(
        user_id="user_alice",
        saved_id=bob_saved.id,
    )
    assert alice_delete is False

    # Bob's record remains intact
    bob_check = await repository.list_user_saved_opportunities(user_id="user_bob")
    assert len(bob_check) == 1
    assert bob_check[0].notes == "Bob's private note"

    # Alice's pipeline is completely empty
    alice_check = await repository.list_user_saved_opportunities(user_id="user_alice")
    assert len(alice_check) == 0


@pytest.mark.asyncio
async def test_upcoming_shared_deadlines_sorting(temp_db):
    """Verifies that deadlines are returned in chronological order and past deadlines are excluded."""
    now = datetime.now(timezone.utc)

    # Past deadline
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

    # Distant deadline (20 days)
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

    # Urgent deadline (2 days)
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
async def test_user_notifications_and_confirmation_gate(temp_db):
    """Verifies user-scoped notification creation, deduplication, and confirmation gates."""
    # Create confirmation notification for Alice
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

    # Duplicate alert for Alice should be deduplicated
    notif1_dup = await repository.create_user_notification(
        NotificationCreate(
            user_id="user_alice",
            title="Deadline Approaching: GSoC 2026",
            message="Your saved application deadline is in 48 hours.",
        )
    )
    assert notif1_dup is None  # Skipped duplicate

    # Bob's notification list should NOT include Alice's alert
    bob_notifs = await repository.list_user_notifications(user_id="user_bob")
    assert len(bob_notifs) == 0

    # Bob attempts to confirm Alice's notification -> fails
    bob_confirm = await repository.confirm_user_notification(
        user_id="user_bob",
        notification_id=notif1.id,
        confirmation_token="TOKEN_SEC_999",
    )
    assert bob_confirm is False

    # Alice confirms with wrong token -> fails
    wrong_confirm = await repository.confirm_user_notification(
        user_id="user_alice",
        notification_id=notif1.id,
        confirmation_token="WRONG_TOKEN",
    )
    assert wrong_confirm is False

    # Alice confirms with correct token -> succeeds
    alice_confirm = await repository.confirm_user_notification(
        user_id="user_alice",
        notification_id=notif1.id,
        confirmation_token="TOKEN_SEC_999",
    )
    assert alice_confirm is True

    # Alice marks read
    alice_notifs = await repository.list_user_notifications(user_id="user_alice", unread_only=True)
    assert len(alice_notifs) == 0  # Marked confirmed & read


@pytest.mark.asyncio
async def test_workflow_execution_persistence(temp_db):
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
