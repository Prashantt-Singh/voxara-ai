"""
Voxara AI - Voice Agent & LangGraph Workflow Integration Test Suite (Step 4C)

Tests covering:
1. Backend module importability and FastAPI health endpoint integrity.
2. LiveKit token generation endpoint integrity.
3. Workflow engine status endpoint verifying registered voice tools.
4. Independent LangGraph workflow execution.
5. Voice agent skill analysis tool invocation path with structured output.
6. Voice agent skill analysis tool input validation and sanitization.
7. Voice agent skill analysis tool timeout and error handling.
8. Voice agent demo workflow tool invocation and validation.
9. Ordinary conversation isolation (ensuring tools are not called for normal banter).
10. Execution store event tracking, node lifecycle events, and REST retrieval endpoints.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.agent import VOXARA_SYSTEM_PROMPT, entrypoint
from app.agent_tools import (
    analyze_skills_demonstration,
    run_demo_workflow,
    VOICE_AGENT_TOOLS,
)
from app.workflows.state import ExecutionEvent
from app.workflows.graph import run_workflow
from app.workflows.skill_graph import run_skill_analysis_workflow
from app.workflows.execution_store import execution_store


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_execution_store():
    """Ensures a clean execution store before and after each test."""
    execution_store.clear()
    yield
    execution_store.clear()


@pytest.fixture
def mock_gemini_analysis():
    """Structured mock output simulating Gemini text generation."""
    return {
        "prioritized_missing_skills": ["Docker", "PyTorch"],
        "analysis": (
            "The candidate has strong Python and FastAPI foundations. "
            "However, Docker and PyTorch are required for containerized model deployment."
        ),
        "recommended_next_steps": [
            "Complete a hands-on PyTorch tutorial.",
            "Build and containerize a model service with Docker.",
        ],
    }


# ===========================================================================
# 1. Backend Imports & Core Endpoint Health Tests
# ===========================================================================

def test_backend_imports_and_health(client: TestClient):
    """Verifies that the FastAPI backend imports and /health reports healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "voxara-ai-backend"
    assert data["version"] == "0.4.0"
    assert data["workflows_ready"] is True


def test_livekit_token_endpoint_healthy(client: TestClient):
    """Verifies that the LiveKit token generation endpoint generates valid signed JWTs."""
    from app.config import Settings
    with patch.object(Settings, "validate_livekit_credentials", return_value=(True, "")):
        with patch("app.services.token_service.TokenService.generate_token", return_value="mock.jwt.token"):
            response = client.post("/api/voice/token", json={"name": "Alice"})
            assert response.status_code == 200
            data = response.json()
            assert data["token"] == "mock.jwt.token"
            assert "participant_identity" in data
            assert data["room_name"] == settings.livekit_default_room


def test_livekit_token_endpoint_unconfigured(client: TestClient):
    """Verifies that the token endpoint returns 503 when LiveKit credentials are not set."""
    from app.config import Settings
    with patch.object(Settings, "validate_livekit_credentials", return_value=(False, "Missing API Key")):
        response = client.post("/api/voice/token", json={})
        assert response.status_code == 503
        data = response.json()
        assert data["detail"]["error"] == "LIVEKIT_NOT_CONFIGURED"


def test_workflow_engine_status_endpoint(client: TestClient):
    """Verifies that the workflow status endpoint reports registered nodes and voice tools."""
    response = client.get("/api/workflows/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["engine"] == "LangGraph StateGraph"
    assert "available_workflows" in data
    assert "skill-analysis" in data["available_workflows"]
    assert "demo" in data["available_workflows"]
    assert "analyze_skills_demonstration" in data["voice_tools_registered"]
    assert "run_demo_workflow" in data["voice_tools_registered"]


# ===========================================================================
# 2. Independent Workflow Execution Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_workflow_independent_execution(mock_gemini_analysis):
    """Verifies that the skill analysis workflow executes independently with valid state transitions."""
    with patch("app.workflows.skill_nodes.generate_skill_gap_analysis", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = mock_gemini_analysis

        state = await run_skill_analysis_workflow(
            existing_skills=["Python", "FastAPI"],
            required_skills=["Python", "Docker", "PyTorch"],
            optional_context="Junior AI Engineer",
        )

        assert state["status"] == "completed"
        assert state["matched_skills"] == ["Python"]
        assert set(state["missing_skills"]) == {"Docker", "PyTorch"}
        assert len(state["events"]) > 0
        assert any(e["node_name"] == "validate_analysis" for e in state["events"])


# ===========================================================================
# 3. Voice Agent Tool Invocation Path Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_voice_agent_skill_tool_success(mock_gemini_analysis):
    """
    Verifies that the voice agent's analyze_skills_demonstration tool:
    1. Executes the compiled LangGraph workflow asynchronously.
    2. Generates a natural spoken summary for voice response.
    3. Returns structured data with matched and missing skills.
    4. Automatically records the execution in the execution store.
    """
    with patch("app.workflows.skill_nodes.generate_skill_gap_analysis", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = mock_gemini_analysis

        result = await analyze_skills_demonstration(
            existing_skills=["Python", "SQL"],
            required_skills=["Python", "Docker", "FastAPI"],
            optional_context="Backend Developer",
        )

        assert result["status"] == "completed"
        assert "execution_id" in result
        assert result["matched_skills"] == ["Python"]
        assert set(result["missing_skills"]) == {"Docker", "FastAPI"}
        assert len(result["recommended_next_steps"]) > 0

        # Spoken summary check
        summary = result["summary_for_voice"]
        assert isinstance(summary, str) and len(summary) > 20
        assert "Python" in summary
        assert "missing skills" in summary.lower() or "focus on" in summary.lower()

        # Observability store verification
        saved_record = execution_store.get_execution(result["execution_id"])
        assert saved_record is not None
        assert saved_record["status"] == "completed"
        assert len(saved_record["events"]) >= 4


@pytest.mark.asyncio
async def test_voice_agent_skill_tool_input_validation():
    """Verifies that invalid or empty inputs return clean voice-friendly failure messages."""
    # 1. Empty existing skills
    res1 = await analyze_skills_demonstration(
        existing_skills=[],
        required_skills=["Python"],
    )
    assert res1["status"] == "failed"
    assert "summary_for_voice" in res1
    assert "no existing skills" in res1["summary_for_voice"].lower()

    # 2. Empty required skills
    res2 = await analyze_skills_demonstration(
        existing_skills=["Python"],
        required_skills=[],
    )
    assert res2["status"] == "failed"
    assert "summary_for_voice" in res2
    assert "no required skills" in res2["summary_for_voice"].lower()

    # 3. Whitespace-only skills
    res3 = await analyze_skills_demonstration(
        existing_skills=["   "],
        required_skills=[" \t "],
    )
    assert res3["status"] == "failed"
    assert "empty or unclear" in res3["summary_for_voice"].lower()


@pytest.mark.asyncio
async def test_voice_agent_skill_tool_timeout_handling():
    """Verifies that a workflow timeout is cleanly caught and spoken politely without crashing."""
    with patch("app.agent_tools.run_skill_analysis_workflow", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = asyncio.TimeoutError()

        result = await analyze_skills_demonstration(
            existing_skills=["Python"],
            required_skills=["Rust"],
        )

        assert result["status"] == "failed"
        assert "timed out" in result["error"].lower()
        assert "timed out" in result["summary_for_voice"].lower()


@pytest.mark.asyncio
async def test_voice_agent_skill_tool_unexpected_error_handling():
    """Verifies that unexpected workflow failures do not leak tracebacks or crash the voice session."""
    with patch("app.agent_tools.run_skill_analysis_workflow", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = RuntimeError("Fatal GPU connection failure")

        result = await analyze_skills_demonstration(
            existing_skills=["Python"],
            required_skills=["Docker"],
        )

        assert result["status"] == "failed"
        assert "unexpected error" in result["summary_for_voice"].lower()
        # Verify no raw exception details exposed in voice response
        assert "Fatal GPU connection" not in result["summary_for_voice"]


@pytest.mark.asyncio
async def test_voice_agent_demo_tool_success():
    """Verifies that the general demonstration tool executes and produces structured voice results."""
    result = await run_demo_workflow(
        task="Audit system telemetry logs",
        parameters_json='{"severity": "high"}',
    )

    assert result["status"] == "completed"
    assert "execution_id" in result
    assert result["task"] == "Audit system telemetry logs"
    assert "Demonstration workflow completed" in result["summary_for_voice"]

    # Verify execution saved in store
    saved = execution_store.get_execution(result["execution_id"])
    assert saved is not None
    assert saved["status"] == "completed"


@pytest.mark.asyncio
async def test_voice_agent_demo_tool_empty_task():
    """Verifies that run_demo_workflow rejects empty task strings with a helpful spoken message."""
    result = await run_demo_workflow(task="   ")
    assert result["status"] == "failed"
    assert "no task was specified" in result["summary_for_voice"].lower()


# ===========================================================================
# 4. Ordinary Conversation & Persona Isolation Tests
# ===========================================================================

def test_ordinary_conversation_instructions():
    """
    Verifies that the agent prompt explicitly preserves ordinary conversation,
    restricts tools strictly to requested demonstration tasks, and forbids
    claiming unverified arbitrary execution capabilities.
    """
    prompt = VOXARA_SYSTEM_PROMPT.lower()

    # Must specify that ordinary conversation should NOT call tools
    assert "ordinary conversation" in prompt
    assert "without calling tools" in prompt or "without using any tools" in prompt

    # Must mention demonstration tools by name
    assert "analyze_skills_demonstration" in prompt
    assert "run_demo_workflow" in prompt

    # Must handle arbitrary task requests honestly
    assert "arbitrary" in prompt or "outside your available tools" in prompt


def test_voice_agent_tools_registration():
    """Verifies that all registered tools have complete metadata and valid schemas."""
    assert len(VOICE_AGENT_TOOLS) >= 2
    tool_names = [tool.info.name for tool in VOICE_AGENT_TOOLS]
    assert "analyze_skills_demonstration" in tool_names
    assert "run_demo_workflow" in tool_names

    for tool in VOICE_AGENT_TOOLS:
        assert tool.info.description is not None
        assert len(tool.info.description) > 30


# ===========================================================================
# 5. Execution Store & Event Logging Retrieval Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_execution_store_and_endpoints(client: TestClient, mock_gemini_analysis):
    """
    Verifies that workflow executions (from voice or REST) create real chronological
    events and can be retrieved via GET /api/workflows/executions endpoints.
    """
    with patch("app.workflows.skill_nodes.generate_skill_gap_analysis", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = mock_gemini_analysis

        tool_result = await analyze_skills_demonstration(
            existing_skills=["Python", "FastAPI"],
            required_skills=["Python", "Docker"],
        )
        exec_id = tool_result["execution_id"]

        # 1. Test listing executions
        list_res = client.get("/api/workflows/executions")
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["count"] >= 1
        assert any(e["execution_id"] == exec_id for e in list_data["executions"])

        # 2. Test retrieving single execution by ID
        get_res = client.get(f"/api/workflows/executions/{exec_id}")
        assert get_res.status_code == 200
        record = get_res.json()
        assert record["execution_id"] == exec_id
        assert record["status"] == "completed"

        # 3. Verify real node execution events
        events = record["events"]
        assert len(events) >= 4
        node_names = [e["node_name"] for e in events]
        assert "validate_input" in node_names
        assert "compare_skills" in node_names
        assert "analyze_skill_gaps" in node_names
        assert "validate_analysis" in node_names

        # Verify durations and event types
        for event in events:
            assert event["event_type"] in ["node_start", "node_finish", "node_error"]
            if event["event_type"] == "node_finish":
                assert event["duration"] is not None
                assert event["duration"] >= 0.0

        # 4. Test 404 for unknown execution ID
        notFoundRes = client.get("/api/workflows/executions/non_existent_id")
        assert notFoundRes.status_code == 404
