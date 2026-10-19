"""
Voxara AI - Opportunity Hunter & Agentic Workflows Test Suite

Tests:
1. Opportunity Hunter StateGraph direct execution and node events.
2. Opportunity Hunter REST endpoint (POST /api/opportunities/hunt).
3. Opportunities listing and deadlines REST endpoints.
4. User saved opportunities (application tracking pipeline) REST endpoints.
5. Voice Agent tools (hunt_opportunities_tool, demonstration tools).
6. Tool registration in VOICE_AGENT_TOOLS.
7. Preferences and Notifications REST APIs with confirmation gate.
8. Background monitoring scheduler execution.
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import DatabaseManager
from app.db.models import (
    OpportunityModel,
    NotificationModel,
    NotificationCreate,
    SavedOpportunityCreate,
    SavedOpportunityUpdate,
    compute_content_hash,
)
from app.db import repository
from app.workflows.opportunity_graph import run_opportunity_hunter_workflow
from app.agent_tools import (
    hunt_opportunities_tool,
    analyze_skills_demonstration,
    run_demo_workflow,
    VOICE_AGENT_TOOLS,
)
from app.services.scheduler_service import scheduler


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    """Ensures each test operates on an isolated temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_workflows.db"
        mgr = DatabaseManager(database_url=f"sqlite+aiosqlite:///{db_file.as_posix()}")
        monkeypatch.setattr("app.db.database.db_manager", mgr)
        monkeypatch.setattr("app.db.repository.db_manager", mgr)
        asyncio.run(mgr.init_db())
        yield mgr
        asyncio.run(mgr.close_db())


# ---------------------------------------------------------------------------
# Opportunity Hunter Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_opportunity_hunter_workflow_direct():
    """Verifies that the Opportunity Hunter StateGraph executes with real node transitions."""
    mock_opps = [
        OpportunityModel(
            id="opp_mock_1",
            title="Global AI Agents Hackathon",
            organization="Devpost",
            type="hackathon",
            source_url="https://example.com/hackathon",
            content_hash=compute_content_hash("https://example.com/hackathon", "Global AI Agents Hackathon"),
            deadline="2026-11-15T23:59:59Z",
            description="Build multi-agent voice systems.",
            match_score=0.95,
            verified_status="verified",
            source_name="Devpost",
        )
    ]

    with patch("app.services.opportunity_service.opportunity_service.sync_and_store_opportunities", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = mock_opps

        state = await run_opportunity_hunter_workflow(query="AI", opportunity_type="hackathon")

        assert state["execution_id"].startswith("wf_")
        assert state["status"] == "completed"
        assert state["error"] is None
        assert len(state["opportunities"]) == 1
        assert "Global AI Agents Hackathon" in state["spoken_briefing"]
        assert len(state["events"]) >= 6  # 3 nodes * (start + finish)


def test_opportunity_hunter_api_endpoint(client: TestClient):
    """Tests POST /api/opportunities/hunt endpoint."""
    response = client.post(
        "/api/opportunities/hunt",
        json={"query": "all", "opportunity_type": "all", "limit": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "opportunities" in data
    assert "urgent_deadlines" in data
    assert "spoken_briefing" in data
    assert len(data["events"]) > 0


def test_opportunities_list_and_deadlines_endpoints(client: TestClient):
    """Tests GET /api/opportunities and GET /api/opportunities/deadlines."""
    resp_opps = client.get("/api/opportunities")
    assert resp_opps.status_code == 200
    assert isinstance(resp_opps.json(), list)

    resp_deadlines = client.get("/api/opportunities/deadlines")
    assert resp_deadlines.status_code == 200
    assert isinstance(resp_deadlines.json(), list)


# ---------------------------------------------------------------------------
# Saved Opportunities (Pipeline) API Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_saved_opportunities_api_endpoints(client: TestClient):
    """Tests POST, GET, PATCH, and DELETE /api/opportunities/saved."""
    # First seed a shared opportunity
    opp = await repository.save_opportunity(
        OpportunityModel(
            id="opp_pipe_1",
            title="Open Source AI Fellowship",
            organization="Hugging Face",
            type="internship",
            source_url="https://huggingface.co/fellowship",
            content_hash=compute_content_hash("https://huggingface.co/fellowship", "Open Source AI Fellowship"),
            description="Contribute to Transformers.",
            source_name="Hugging Face",
        )
    )

    # 1. Save opportunity to user pipeline
    save_res = client.post(
        "/api/opportunities/saved?user_id=user_test_pipe",
        json={
            "opportunity_id": opp.id,
            "status": "saved",
            "notes": "Target for summer 2026",
            "match_score": 0.95,
        },
    )
    assert save_res.status_code == 200
    saved_data = save_res.json()
    saved_id = saved_data["id"]
    assert saved_data["status"] == "saved"
    assert saved_data["notes"] == "Target for summer 2026"

    # 2. List user saved opportunities
    list_res = client.get("/api/opportunities/saved?user_id=user_test_pipe")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 1
    assert items[0]["id"] == saved_id

    # 3. Update application status: saved -> applied
    patch_res = client.patch(
        f"/api/opportunities/saved/{saved_id}?user_id=user_test_pipe",
        json={"status": "applied", "notes": "Submitted application!"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "applied"
    assert patch_res.json()["notes"] == "Submitted application!"

    # 4. Delete saved opportunity
    del_res = client.delete(f"/api/opportunities/saved/{saved_id}?user_id=user_test_pipe")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Verify pipeline is now empty
    empty_list = client.get("/api/opportunities/saved?user_id=user_test_pipe").json()
    assert len(empty_list) == 0


# ---------------------------------------------------------------------------
# Voice Agent Tool Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_voice_agent_hunt_opportunities_tool():
    """Verifies that hunt_opportunities_tool returns voice-friendly payloads."""
    result = await hunt_opportunities_tool(query="AI", opportunity_type="hackathon")
    assert result["status"] == "completed"
    assert "summary_for_voice" in result
    assert isinstance(result["summary_for_voice"], str)
    assert len(result["summary_for_voice"]) > 10


def test_voice_agent_tool_registration():
    """Verifies that registered voice agent workflow tools match current product scope."""
    tool_names = [getattr(t, "__name__", str(t)) for t in VOICE_AGENT_TOOLS]
    assert "hunt_opportunities_tool" in tool_names
    assert "analyze_skills_demonstration" in tool_names
    assert "run_demo_workflow" in tool_names
    # Research Watcher tool must be completely excluded
    assert "check_research_updates_tool" not in tool_names


# ---------------------------------------------------------------------------
# Preferences & Notifications API Tests
# ---------------------------------------------------------------------------

def test_preferences_api_endpoints(client: TestClient):
    """Tests GET and PUT /api/preferences."""
    get_res = client.get("/api/preferences")
    assert get_res.status_code == 200
    data = get_res.json()
    assert "roles" in data

    put_res = client.put(
        "/api/preferences",
        json={"roles": ["Senior AI Engineer"], "min_match_score": 0.8},
    )
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["roles"] == ["Senior AI Engineer"]
    assert updated["min_match_score"] == 0.8


@pytest.mark.asyncio
async def test_notifications_and_confirmation_api(client: TestClient):
    """Tests GET /api/notifications and POST /api/notifications/{id}/confirm."""
    notif = await repository.create_user_notification(
        NotificationCreate(
            user_id="default_user",
            title="Calendar Action",
            message="Add hackathon to calendar",
            requires_confirmation=True,
            confirmation_token="SECRET_KEY_777",
        )
    )
    assert notif is not None

    # Fetch pending
    list_res = client.get("/api/notifications")
    assert list_res.status_code == 200
    notifications = list_res.json()
    assert any(n["id"] == notif.id for n in notifications)

    # Confirm action
    confirm_res = client.post(
        f"/api/notifications/{notif.id}/confirm",
        json={"confirmation_token": "SECRET_KEY_777"},
    )
    assert confirm_res.status_code == 200
    assert confirm_res.json()["status"] == "confirmed"


# ---------------------------------------------------------------------------
# Background Scheduler Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scheduler_monitoring_cycle():
    """Verifies that the background scheduler executes an opportunity monitoring cycle."""
    with patch("app.services.opportunity_service.opportunity_service.sync_and_store_opportunities", new_callable=AsyncMock) as mock_opp:
        mock_opp.return_value = []
        await scheduler.run_monitoring_cycle()
        mock_opp.assert_awaited_once()
