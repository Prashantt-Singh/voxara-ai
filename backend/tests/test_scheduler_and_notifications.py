"""
Targeted Tests for Scheduled Opportunity Discovery, Deadline Processing, and Persistent Notifications
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from typing import Generator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.db.database import DatabaseManager
from app.db import repository
from app.db.models import OpportunityCreate, SavedOpportunityCreate, UserPreferencesUpdate
from app.services.auth_service import create_test_token
from app.services.deadline_service import deadline_service
from app.services.scheduler_service import scheduler
import worker

TEST_SECRET = "voxara-super-secure-test-jwt-secret-key-32-chars"


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch) -> Generator[DatabaseManager, None, None]:
    """Provides an isolated database and test settings."""
    monkeypatch.setattr(settings, "supabase_jwt_secret", TEST_SECRET)
    monkeypatch.setattr(settings, "supabase_jwt_audience", "authenticated")
    monkeypatch.setattr(settings, "require_auth", True)
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "scheduler_enabled", True)
    monkeypatch.setattr(settings, "enable_in_app_scheduler", False)  # manual triggers in tests

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sched_test.db"
        mgr = DatabaseManager(database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}")
        monkeypatch.setattr("app.db.database.db_manager", mgr)
        monkeypatch.setattr("app.db.repository.db_manager", mgr)
        monkeypatch.setattr("worker.db_manager", mgr)
        asyncio.run(mgr.init_db())
        yield mgr
        asyncio.run(mgr.close_db())


def create_auth_headers(user_id: str, email: str = None) -> dict:
    token = create_test_token(user_id=user_id, email=email or f"{user_id}@voxara.ai", secret=TEST_SECRET)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test 1: Deadline Processing Logic & Timezone Handling
# ---------------------------------------------------------------------------

def test_deadline_expired_and_approaching_logic():
    """Validates deadline detection without inventing dates and using strict UTC."""
    now = datetime.now(timezone.utc)

    # 1. Past deadline is expired
    past_dl = now - timedelta(days=2)
    assert deadline_service.is_expired(past_dl, now=now) is True
    assert deadline_service.is_approaching(past_dl, alert_days=3, now=now) is False

    # 2. Approaching deadline within window
    soon_dl = now + timedelta(days=2)
    assert deadline_service.is_expired(soon_dl, now=now) is False
    assert deadline_service.is_approaching(soon_dl, alert_days=3, now=now) is True

    # 3. Distant deadline outside window
    far_dl = now + timedelta(days=10)
    assert deadline_service.is_expired(far_dl, now=now) is False
    assert deadline_service.is_approaching(far_dl, alert_days=3, now=now) is False

    # 4. Missing deadline (None) is never expired and never approaching
    assert deadline_service.is_expired(None, now=now) is False
    assert deadline_service.is_approaching(None, alert_days=3, now=now) is False


# ---------------------------------------------------------------------------
# Test 2: Persistent Deadline Alerts with Deduplication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deadline_alerts_generated_and_deduplicated():
    """
    User saves an application due in 2 days. Deadline processor generates alert once.
    Subsequent sweeps do not create duplicate notifications.
    """
    now = datetime.now(timezone.utc)
    deadline_dt = now + timedelta(days=2)

    # 1. Create opportunity with approaching deadline
    opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="AI Systems Fellowship",
            organization="Anthropic",
            type="fellowship",
            source_url="https://anthropic.com/fellowship",
            source_name="Curated",
            description="6-month AI safety and systems research fellowship.",
            deadline=deadline_dt,
        )
    )

    # 2. Alice saves this opportunity
    await repository.save_user_opportunity(
        user_id="user_alice",
        data=SavedOpportunityCreate(
            opportunity_id=opp.id,
            status="saved",
            notes="Preparing research statement",
        ),
    )

    # 3. Run first deadline sweep
    result1 = await deadline_service.process_deadlines(alert_days=3)
    assert result1["status"] == "completed"
    assert result1["notifications_created"] >= 1
    assert result1["approaching_deadlines_found"] >= 1

    # Verify Alice received the notification
    notifs1 = await repository.list_user_notifications("user_alice")
    assert len(notifs1) == 1
    assert notifs1[0].type == "deadline"
    assert "Anthropic" in notifs1[0].message
    assert notifs1[0].opportunity_id == opp.id

    # 4. Run second deadline sweep immediately
    result2 = await deadline_service.process_deadlines(alert_days=3)
    # Deduplication must prevent any new notification
    assert result2["notifications_created"] == 0

    # Total notifications for Alice must remain exactly 1
    notifs2 = await repository.list_user_notifications("user_alice")
    assert len(notifs2) == 1


# ---------------------------------------------------------------------------
# Test 3: Discovery Cycle, Telemetry, and Matching Notifications
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discovery_cycle_telemetry_and_matching(monkeypatch):
    """
    Executes a discovery cycle:
    - User Bob has preferences for 'internship' and 'Software Engineer'.
    - Discovery inserts a mock internship.
    - Bob receives a 'New Opportunity Match' persistent notification.
    - Execution telemetry is persisted in workflow_executions.
    """
    # 1. Configure Bob's preferences
    bob_headers = create_auth_headers("user_bob")
    await repository.update_user_preferences(
        user_id="user_bob",
        updates=UserPreferencesUpdate(
            roles=["Software Engineer"],
            opportunity_types=["internship"],
            notifications_enabled=True,
            min_match_score=0.5,
        ),
    )

    # 2. Mock opportunity service to return a freshly discovered opportunity
    now = datetime.now(timezone.utc)
    from app.db.models import OpportunityModel

    mock_opp = OpportunityModel(
        id="opp_mock_1",
        title="Software Engineer Intern - Summer 2027",
        organization="Google",
        type="internship",
        source_url="https://google.com/careers/intern",
        source_name="SimplifyJobs",
        content_hash="test_hash_google_swe_intern_1",
        deadline=now + timedelta(days=20),
        description="Software engineering internship working on distributed systems and cloud services.",
        requirements=["Python", "C++", "Data Structures"],
        is_new=True,
    )

    async def mock_discover(*args, **kwargs):
        # Persist mock opp into DB
        saved = await repository.save_opportunity(mock_opp)
        return [saved]

    monkeypatch.setattr("app.services.scheduler_service.opportunity_service.discover_opportunities", mock_discover)

    # 3. Execute discovery cycle
    summary = await scheduler.execute_discovery_cycle(batch_size=10, force=True)
    assert summary["status"] == "success"
    assert summary["discovered_total"] == 1
    assert summary["new_opportunities_inserted"] == 1
    assert summary["opportunity_match_notifications"] >= 1

    # 4. Verify Bob has a persistent notification in PostgreSQL
    bob_notifs = await repository.list_user_notifications("user_bob")
    assert len(bob_notifs) >= 1
    match_notif = next((n for n in bob_notifs if n.type == "opportunity"), None)
    assert match_notif is not None
    assert "Google" in match_notif.message
    assert "Software Engineer" in match_notif.title

    # 5. Verify telemetry record exists in workflow_executions
    executions = await repository.list_workflow_executions(limit=5)
    sched_exec = next((e for e in executions if e["workflow_type"] == "scheduled_opportunity_discovery"), None)
    assert sched_exec is not None
    assert sched_exec["status"] == "completed"
    assert sched_exec["result"]["new_opportunities_inserted"] == 1


# ---------------------------------------------------------------------------
# Test 4: Overlap Prevention Blocks Duplicate Work
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_overlapping_executions_are_prevented():
    """Concurrent discovery invocations are blocked by the execution lock."""
    async with scheduler._execution_lock:
        # With lock acquired by an active task, another call must return skipped
        result = await scheduler.execute_discovery_cycle(force=False)
        assert result["status"] == "skipped"
        assert "still running" in result["reason"].lower()


# ---------------------------------------------------------------------------
# Test 5: Source Fault Tolerance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_individual_source_failure_does_not_abort_cycle(monkeypatch):
    """If Devpost fails, SimplifyJobs and other sources continue successfully."""
    from app.services.opportunity_service import opportunity_service

    async def failing_devpost(*args, **kwargs):
        raise ConnectionError("Devpost endpoint temporarily unavailable (503 Service Unavailable)")

    monkeypatch.setattr(opportunity_service, "fetch_devpost_hackathons", failing_devpost)

    # Calling discover_opportunities should not throw
    results = await opportunity_service.discover_opportunities(limit=5, persist=False)
    # Returns empty or results from other working sources without raising
    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Test 6: Authenticated Notification REST Endpoints & User Isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notification_endpoints_and_user_isolation(client: TestClient):
    """
    - User Alice and Bob receive notifications.
    - Alice cannot see or mark Bob's notifications.
    - Alice can retrieve, mark single as read, and mark all as read.
    """
    alice_headers = create_auth_headers("user_alice")
    bob_headers = create_auth_headers("user_bob")

    # 1. Create notification for Alice
    from app.db.models import NotificationCreate
    notif_alice = await repository.create_user_notification(
        NotificationCreate(
            user_id="user_alice",
            title="Alice Deadline Alert",
            message="Deadline in 2 days",
            type="deadline",
        )
    )

    # 2. Create notification for Bob
    notif_bob = await repository.create_user_notification(
        NotificationCreate(
            user_id="user_bob",
            title="Bob Match Alert",
            message="New match for Bob",
            type="opportunity",
        )
    )

    # 3. Alice retrieves notifications
    res_alice = client.get("/api/notifications", headers=alice_headers)
    assert res_alice.status_code == 200
    alice_data = res_alice.json()
    assert len(alice_data) == 1
    assert alice_data[0]["id"] == notif_alice.id

    # Bob retrieves notifications
    res_bob = client.get("/api/notifications", headers=bob_headers)
    assert res_bob.status_code == 200
    bob_data = res_bob.json()
    assert len(bob_data) == 1
    assert bob_data[0]["id"] == notif_bob.id

    # 4. Alice tries to mark Bob's notification as read (must not affect Bob)
    res_hack = client.post(f"/api/notifications/{notif_bob.id}/read", headers=alice_headers)
    assert res_hack.status_code == 200
    assert res_hack.json()["marked"] is False

    # Verify Bob's notification is still unread
    bob_notifs_after = await repository.list_user_notifications("user_bob", unread_only=True)
    assert len(bob_notifs_after) == 1

    # 5. Alice marks her notification as read
    res_read = client.post(f"/api/notifications/{notif_alice.id}/read", headers=alice_headers)
    assert res_read.status_code == 200
    assert res_read.json()["marked"] is True

    # 6. Alice marks all read
    res_all = client.post("/api/notifications/read-all", headers=alice_headers)
    assert res_all.status_code == 200


# ---------------------------------------------------------------------------
# Test 7: Standalone Worker Execution (--once mode)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_standalone_worker_run_once(monkeypatch):
    """Validates worker.run_once executes cleanly and exits with code 0."""
    async def mock_cycle(*args, **kwargs):
        return {
            "status": "success",
            "discovered_total": 5,
            "new_opportunities_inserted": 2,
            "existing_opportunities_refreshed": 3,
            "deadline_processing": {"notifications_created": 1},
        }

    monkeypatch.setattr("worker.scheduler.execute_discovery_cycle", mock_cycle)

    exit_code = await worker.run_once(batch_size=5)
    assert exit_code == 0


# ---------------------------------------------------------------------------
# Test 8: Scheduler Status Endpoint
# ---------------------------------------------------------------------------

def test_scheduler_status_endpoint(client: TestClient):
    """GET /api/workflows/scheduler/status returns operational metrics."""
    res = client.get("/api/workflows/scheduler/status")
    assert res.status_code == 200
    data = res.json()
    assert "scheduler_enabled" in data
    assert "interval_minutes" in data
    assert "batch_size" in data
    assert "deadline_alert_days" in data
