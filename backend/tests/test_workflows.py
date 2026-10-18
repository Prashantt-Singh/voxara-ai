"""
Voxara AI - Workflow Orchestration Test Suite (Step 4A: Agentic Workflow Foundation)

Tests covering:
1. A valid demonstration request (API and Graph).
2. A missing or invalid task description (API 422 and Graph error handling).
3. Correct graph node execution order and lifecycle events.
4. Execution error handling without server crashes.
5. Workflow endpoint response structure and event telemetry schema.
6. Existing health and voice endpoints backward compatibility.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.workflows.graph import run_workflow, workflow_graph


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: Valid demonstration request
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_demonstration_workflow_direct():
    """
    Test direct asynchronous execution of the compiled StateGraph with valid task and input.
    """
    task = "Process system logs for anomalous spikes"
    input_data = {"threshold": 95, "timeframe": "1h"}

    state = await run_workflow(task=task, input_data=input_data)

    assert state["execution_id"].startswith("wf_")
    assert state["task"] == task
    assert state["status"] == "completed"
    assert state["error"] is None
    assert "intermediate_results" in state
    assert state["intermediate_results"]["validation_status"] == "passed"
    assert state["result"] is not None
    assert state["result"]["task"] == task
    assert state["result"]["received_input"] == input_data
    assert "execution_steps" in state["result"]
    assert state["result"]["execution_steps"] == ["receive_request", "validate_request", "produce_result"]


def test_valid_demonstration_workflow_api(client):
    """
    Test POST /api/workflows/demo endpoint with a valid request payload.
    """
    payload = {
        "task": "Summarize user telemetry events",
        "input_data": {"device": "desktop", "locale": "en-US"},
    }

    response = client.post("/api/workflows/demo", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["execution_id"].startswith("wf_")
    assert data["task"] == payload["task"]
    assert data["status"] == "completed"
    assert data["error"] is None
    assert "intermediate_results" in data
    assert data["intermediate_results"]["validation_status"] == "passed"
    assert data["result"] is not None
    assert data["result"]["summary"].startswith("Completed workflow demonstration")
    assert len(data["events"]) == 6


# ---------------------------------------------------------------------------
# Test 2: Missing or invalid task description
# ---------------------------------------------------------------------------

def test_missing_task_description_api(client):
    """
    Test that omitting the required 'task' property yields HTTP 422 Unprocessable Entity.
    """
    response = client.post("/api/workflows/demo", json={"input_data": {"foo": "bar"}})
    assert response.status_code == 422
    errors = response.json().get("detail", [])
    assert any("task" in err["loc"] for err in errors)


def test_empty_task_description_api(client):
    """
    Test that an empty or whitespace-only task description is rejected with HTTP 422.
    """
    response = client.post("/api/workflows/demo", json={"task": "   "})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_task_description_graph_direct():
    """
    Test that invalid/empty task descriptions supplied directly to the graph
    are caught by validate_request, resulting in status='failed' without server crash.
    """
    state = await run_workflow(task="")

    assert state["status"] == "failed"
    assert state["error"] is not None
    assert "Task description cannot be missing or empty" in state["error"]
    assert state["result"] is None

    # Verify that produce_result was skipped due to validation failure
    node_names = [e["node_name"] for e in state["events"]]
    assert "validate_request" in node_names
    assert "produce_result" in node_names

    # Check that produce_result event recorded 'skipped' status
    produce_finish_events = [
        e for e in state["events"]
        if e["node_name"] == "produce_result" and e["event_type"] == "node_finish"
    ]
    assert len(produce_finish_events) == 1
    assert produce_finish_events[0]["status"] == "skipped"


# ---------------------------------------------------------------------------
# Test 3: Correct graph node execution order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_correct_graph_node_execution_order():
    """
    Test that workflow nodes execute strictly in the order:
    receive_request -> validate_request -> produce_result
    and that lifecycle events (start -> finish) are properly paired and ordered.
    """
    task = "Verify graph execution order"
    state = await run_workflow(task=task)

    events = state["events"]
    assert len(events) == 6

    expected_sequence = [
        ("receive_request", "node_start", "started"),
        ("receive_request", "node_finish", "completed"),
        ("validate_request", "node_start", "started"),
        ("validate_request", "node_finish", "completed"),
        ("produce_result", "node_start", "started"),
        ("produce_result", "node_finish", "completed"),
    ]

    for idx, (expected_node, expected_type, expected_status) in enumerate(expected_sequence):
        evt = events[idx]
        assert evt["node_name"] == expected_node, f"Mismatch at step {idx}: expected node {expected_node}"
        assert evt["event_type"] == expected_type, f"Mismatch at step {idx}: expected event_type {expected_type}"
        assert evt["status"] == expected_status, f"Mismatch at step {idx}: expected status {expected_status}"
        assert evt["execution_id"] == state["execution_id"]
        assert evt["timestamp"] is not None

        # Verify real duration on finish events (must be >= 0.0)
        if expected_type == "node_finish":
            assert evt["duration"] is not None
            assert evt["duration"] >= 0.0
            assert evt["duration_ms"] is not None
            assert evt["duration_ms"] >= 0.0


# ---------------------------------------------------------------------------
# Test 4: Execution error handling
# ---------------------------------------------------------------------------

def test_workflow_execution_error_handling(client):
    """
    Test that an execution error in produce_result is caught gracefully,
    records node_error event, sets status to 'failed', and does not crash the server.
    """
    payload = {
        "task": "simulate_execution_error",
        "input_data": {"simulate_error": True},
    }

    response = client.post("/api/workflows/demo", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "failed"
    assert data["result"] is None
    assert data["error"] is not None
    assert "Simulated node failure in produce_result" in data["error"]

    # Verify that an error event was recorded
    error_events = [e for e in data["events"] if e["event_type"] == "node_error"]
    assert len(error_events) >= 1
    assert error_events[0]["node_name"] == "produce_result"
    assert error_events[0]["status"] == "failed"


# ---------------------------------------------------------------------------
# Test 5: Workflow endpoint response structure
# ---------------------------------------------------------------------------

def test_workflow_endpoint_response_structure(client):
    """
    Verify the full schema and field types of the /api/workflows/demo response.
    """
    response = client.post(
        "/api/workflows/demo",
        json={"task": "Inspect payload structure", "input_data": {"mode": "test"}},
    )
    assert response.status_code == 200
    data = response.json()

    # Top-level keys
    assert "execution_id" in data and isinstance(data["execution_id"], str)
    assert "task" in data and data["task"] == "Inspect payload structure"
    assert "status" in data and data["status"] == "completed"
    assert "intermediate_results" in data and isinstance(data["intermediate_results"], dict)
    assert "result" in data and isinstance(data["result"], dict)
    assert "error" in data and data["error"] is None
    assert "events" in data and isinstance(data["events"], list)

    # Event schema verification
    for event in data["events"]:
        assert "event_id" in event and event["event_id"].startswith("evt_")
        assert "execution_id" in event and event["execution_id"] == data["execution_id"]
        assert "node_name" in event and event["node_name"] in {"receive_request", "validate_request", "produce_result"}
        assert "event_type" in event and event["event_type"] in {"node_start", "node_finish", "node_error"}
        assert "timestamp" in event and isinstance(event["timestamp"], str)
        assert "status" in event and event["status"] in {"started", "completed", "failed", "skipped"}
        if event["event_type"] == "node_finish":
            assert isinstance(event["duration"], (int, float))
            assert isinstance(event["duration_ms"], (int, float))


# ---------------------------------------------------------------------------
# Test 6: Workflow engine status endpoint
# ---------------------------------------------------------------------------

def test_workflow_status_endpoint(client):
    """
    Verify GET /api/workflows/status returns readiness info.
    """
    response = client.get("/api/workflows/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "LangGraph" in data["engine"]
    assert data["graph_nodes"] == ["receive_request", "validate_request", "produce_result"]


# ---------------------------------------------------------------------------
# Test 7: Backward compatibility - Existing Health & Voice Endpoints
# ---------------------------------------------------------------------------

def test_existing_health_endpoint(client):
    """
    Verify GET /health retains its previous structure and reports workflows_ready.
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "voxara-ai-backend"
    assert "livekit_configured" in data
    assert "gemini_configured" in data
    assert data["workflows_ready"] is True


def test_existing_voice_status_endpoint(client):
    """
    Verify GET /api/voice/status remains functional and unaffected.
    """
    response = client.get("/api/voice/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "livekit_configured" in data
    assert "gemini_configured" in data


def test_existing_voice_token_endpoint(client):
    """
    Verify POST /api/voice/token behaves properly according to configuration
    (returns 200 with JWT if configured, or 503 if credentials need configuration).
    """
    response = client.post("/api/voice/token", json={"name": "test_user"})
    # Endpoint should respond with either 200 or 503, never an unhandled 500
    assert response.status_code in {200, 503}

