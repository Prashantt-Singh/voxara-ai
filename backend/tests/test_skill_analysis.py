"""
Voxara AI - Skill Analysis Workflow Test Suite (Step 4B: Gemini-Powered Skill Analysis)

Tests covering:
1. Skill comparison with overlapping skills.
2. Skill comparison when there are no matches.
3. Case and whitespace normalization.
4. Invalid or empty input (API 422 validation and Graph node handling).
5. Successful workflow execution end-to-end.
6. Malformed Gemini output handling.
7. Gemini API errors or timeouts handling.
8. Final output schema validation.
9. Execution event ordering, durations, and lifecycle tracking.
10. Optional manual integration test with live Gemini API.
"""

import json
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.workflows.state import SkillAnalysisState
from app.workflows.skill_nodes import (
    validate_input,
    compare_skills,
    analyze_skill_gaps,
    validate_analysis,
)
from app.workflows.skill_graph import (
    skill_analysis_graph,
    run_skill_analysis_workflow,
)
from app.services.gemini_service import (
    generate_skill_gap_analysis,
    build_analysis_prompt,
    GeminiServiceError,
)


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture
def mock_gemini_output():
    """Realistic structured mock output for Gemini skill analysis."""
    return {
        "prioritized_missing_skills": ["PyTorch", "Docker"],
        "analysis": (
            "The candidate has strong backend fundamentals with Python and FastAPI, which aligns "
            "well with service development. However, the internship specifically requires PyTorch "
            "for deep learning experimentation and Docker for containerized model inference pipelines."
        ),
        "recommended_next_steps": [
            "Complete the official PyTorch 60-Minute Blitz tutorial and implement a basic neural net.",
            "Containerize an existing FastAPI model inference service using a multi-stage Dockerfile.",
            "Deploy a toy classification model as a containerized endpoint to demonstrate end-to-end fluency.",
        ],
    }


# ---------------------------------------------------------------------------
# Test 1: Skill comparison with overlapping skills
# ---------------------------------------------------------------------------

def test_compare_skills_overlapping():
    """
    Test deterministic comparison when candidate skills overlap with required skills.
    Matches must be identified; non-matching required skills must be marked missing.
    """
    state: SkillAnalysisState = {
        "execution_id": "wf_test_overlap",
        "existing_skills": ["Python", "FastAPI", "PostgreSQL", "Git"],
        "required_skills": ["Python", "Docker", "PyTorch", "FastAPI"],
        "optional_context": "AI Internship",
        "status": "running",
        "events": [],
        "matched_skills": [],
        "missing_skills": [],
        "prioritized_missing_skills": [],
        "analysis": "",
        "recommended_next_steps": [],
        "raw_analysis": None,
        "error": None,
    }

    result = compare_skills(state)

    assert result["matched_skills"] == ["Python", "FastAPI"]
    assert result["missing_skills"] == ["Docker", "PyTorch"]
    assert len(result["events"]) == 2
    assert result["events"][0]["event_type"] == "node_start"
    assert result["events"][1]["event_type"] == "node_finish"
    assert result["events"][1]["status"] == "completed"
    assert result["events"][1]["details"]["matched_count"] == 2
    assert result["events"][1]["details"]["missing_count"] == 2


# ---------------------------------------------------------------------------
# Test 2: Skill comparison when there are no matches
# ---------------------------------------------------------------------------

def test_compare_skills_no_matches():
    """
    Test deterministic comparison when candidate skills have zero overlap with requirements.
    All required skills must be reported in missing_skills; matched_skills must be empty.
    """
    state: SkillAnalysisState = {
        "execution_id": "wf_test_no_match",
        "existing_skills": ["HTML", "CSS", "Photoshop"],
        "required_skills": ["Rust", "WebAssembly", "LLVM"],
        "optional_context": None,
        "status": "running",
        "events": [],
        "matched_skills": [],
        "missing_skills": [],
        "prioritized_missing_skills": [],
        "analysis": "",
        "recommended_next_steps": [],
        "raw_analysis": None,
        "error": None,
    }

    result = compare_skills(state)

    assert result["matched_skills"] == []
    assert result["missing_skills"] == ["Rust", "WebAssembly", "LLVM"]
    assert result["events"][1]["details"]["matched_count"] == 0
    assert result["events"][1]["details"]["missing_count"] == 3


# ---------------------------------------------------------------------------
# Test 3: Case and whitespace normalization
# ---------------------------------------------------------------------------

def test_compare_skills_case_and_whitespace_normalization():
    """
    Verify that comparison normalizes mixed casing and leading/trailing whitespace.
    E.g. '  pYtHoN  ' matches 'python', 'FASTAPI' matches '  FastAPI  '.
    """
    state: SkillAnalysisState = {
        "execution_id": "wf_test_norm",
        "existing_skills": ["  pYtHoN  ", "FASTAPI ", "  Docker  "],
        "required_skills": ["python", "FastAPI", "docker", "Kubernetes"],
        "optional_context": None,
        "status": "running",
        "events": [],
        "matched_skills": [],
        "missing_skills": [],
        "prioritized_missing_skills": [],
        "analysis": "",
        "recommended_next_steps": [],
        "raw_analysis": None,
        "error": None,
    }

    result = compare_skills(state)

    assert len(result["matched_skills"]) == 3
    # Check that python, FastAPI, and docker were matched regardless of case or spaces
    matched_lower = [s.lower() for s in result["matched_skills"]]
    assert "python" in matched_lower
    assert "fastapi" in matched_lower
    assert "docker" in matched_lower
    assert result["missing_skills"] == ["Kubernetes"]


# ---------------------------------------------------------------------------
# Test 4: Invalid or empty input
# ---------------------------------------------------------------------------

def test_invalid_input_api_empty_lists(client):
    """
    Test that sending empty lists via API returns HTTP 422 Unprocessable Entity.
    """
    # Empty existing_skills
    res1 = client.post(
        "/api/workflows/skill-analysis",
        json={"existing_skills": [], "required_skills": ["Python"]},
    )
    assert res1.status_code == 422

    # Empty required_skills
    res2 = client.post(
        "/api/workflows/skill-analysis",
        json={"existing_skills": ["Python"], "required_skills": []},
    )
    assert res2.status_code == 422


def test_invalid_input_api_whitespace_only(client):
    """
    Test that sending whitespace-only items via API returns HTTP 422.
    """
    res = client.post(
        "/api/workflows/skill-analysis",
        json={"existing_skills": ["   ", ""], "required_skills": ["Python"]},
    )
    assert res.status_code == 422


def test_invalid_input_graph_node_direct():
    """
    Test that supplying invalid or empty input directly to validate_input node
    sets status='failed' and creates a node_error event without crashing.
    """
    state: SkillAnalysisState = {
        "execution_id": "wf_test_invalid",
        "existing_skills": [],
        "required_skills": ["Python"],
        "optional_context": None,
        "status": "pending",
        "events": [],
        "matched_skills": [],
        "missing_skills": [],
        "prioritized_missing_skills": [],
        "analysis": "",
        "recommended_next_steps": [],
        "raw_analysis": None,
        "error": None,
    }

    result = validate_input(state)
    assert result["status"] == "failed"
    assert "Validation error" in result["error"]
    assert len(result["events"]) == 2
    assert result["events"][1]["event_type"] == "node_error"
    assert result["events"][1]["status"] == "failed"


# ---------------------------------------------------------------------------
# Test 5: Successful workflow execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_workflow_execution_graph_direct(mock_gemini_output):
    """
    Test full end-to-end execution of the skill analysis workflow graph
    with Gemini mocked.
    """
    with patch(
        "app.workflows.skill_nodes.generate_skill_gap_analysis",
        new_callable=AsyncMock,
        return_value=mock_gemini_output,
    ) as mock_gemini:
        state = await run_skill_analysis_workflow(
            existing_skills=["Python", "FastAPI"],
            required_skills=["Python", "FastAPI", "PyTorch", "Docker"],
            optional_context="Junior AI Engineer Internship",
        )

        assert state["status"] == "completed"
        assert state["error"] is None
        assert state["matched_skills"] == ["Python", "FastAPI"]
        assert state["missing_skills"] == ["PyTorch", "Docker"]
        assert state["prioritized_missing_skills"] == ["PyTorch", "Docker"]
        assert "FastAPI" in state["analysis"]
        assert len(state["recommended_next_steps"]) == 3
        assert mock_gemini.called


def test_successful_workflow_execution_api(client, mock_gemini_output):
    """
    Test POST /api/workflows/skill-analysis endpoint with valid payload and mocked Gemini.
    """
    with patch(
        "app.workflows.skill_nodes.generate_skill_gap_analysis",
        new_callable=AsyncMock,
        return_value=mock_gemini_output,
    ):
        payload = {
            "existing_skills": ["Python", "FastAPI", "Git"],
            "required_skills": ["Python", "Docker", "PyTorch", "FastAPI"],
            "optional_context": "Summer AI Internship at Voxara",
        }

        response = client.post("/api/workflows/skill-analysis", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["execution_id"].startswith("wf_")
        assert data["status"] == "completed"
        assert data["error"] is None
        assert data["matched_skills"] == ["Python", "FastAPI"]
        assert data["missing_skills"] == ["Docker", "PyTorch"]
        assert data["prioritized_missing_skills"] == ["PyTorch", "Docker"]
        assert len(data["recommended_next_steps"]) == 3
        # 4 nodes * 2 events each = 8 events
        assert len(data["events"]) == 8


# ---------------------------------------------------------------------------
# Test 6: Malformed Gemini output
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_malformed_gemini_output_handling():
    """
    Test that when Gemini returns malformed output (missing required keys or wrong types),
    validate_analysis detects it, records a node_error event, and sets status='failed'
    without crashing.
    """
    malformed_output = {
        "prioritized_missing_skills": "Not a list!",  # Invalid type
        "analysis": "",                               # Empty string
        # recommended_next_steps missing entirely
    }

    with patch(
        "app.workflows.skill_nodes.generate_skill_gap_analysis",
        new_callable=AsyncMock,
        return_value=malformed_output,
    ):
        state = await run_skill_analysis_workflow(
            existing_skills=["Python"],
            required_skills=["Python", "Docker"],
            optional_context=None,
        )

        assert state["status"] == "failed"
        assert state["error"] is not None
        assert "Output validation failed" in state["error"]

        # Check that validate_analysis node registered the error event
        error_events = [e for e in state["events"] if e["event_type"] == "node_error"]
        assert len(error_events) >= 1
        assert error_events[0]["node_name"] == "validate_analysis"
        assert error_events[0]["status"] == "failed"


# ---------------------------------------------------------------------------
# Test 7: Gemini API errors or timeouts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gemini_api_error_handling():
    """
    Test that when the Gemini API throws a network error, timeout, or quota error,
    analyze_skill_gaps catches it, records a node_error event, sets status='failed',
    and subsequent nodes skip gracefully.
    """
    with patch(
        "app.workflows.skill_nodes.generate_skill_gap_analysis",
        new_callable=AsyncMock,
        side_effect=GeminiServiceError("Gemini API connection timed out after 30s"),
    ):
        state = await run_skill_analysis_workflow(
            existing_skills=["Python"],
            required_skills=["Python", "Docker"],
        )

        assert state["status"] == "failed"
        assert state["error"] is not None
        assert "Gemini analysis error" in state["error"]
        assert "timed out" in state["error"]

        # Check events
        node_names = [e["node_name"] for e in state["events"]]
        assert "analyze_skill_gaps" in node_names
        assert "validate_analysis" in node_names

        # analyze_skill_gaps should have an error event
        error_events = [
            e for e in state["events"]
            if e["node_name"] == "analyze_skill_gaps" and e["event_type"] == "node_error"
        ]
        assert len(error_events) == 1

        # validate_analysis should be skipped
        validate_finish = [
            e for e in state["events"]
            if e["node_name"] == "validate_analysis" and e["event_type"] == "node_finish"
        ]
        assert len(validate_finish) == 1
        assert validate_finish[0]["status"] == "skipped"


# ---------------------------------------------------------------------------
# Test 8: Final output schema validation
# ---------------------------------------------------------------------------

def test_final_output_schema_validation(client, mock_gemini_output):
    """
    Verify that the API response strictly adheres to the SkillAnalysisResponse schema.
    """
    with patch(
        "app.workflows.skill_nodes.generate_skill_gap_analysis",
        new_callable=AsyncMock,
        return_value=mock_gemini_output,
    ):
        payload = {
            "existing_skills": ["Python", "FastAPI"],
            "required_skills": ["Python", "Docker"],
            "optional_context": "Junior Developer",
        }

        res = client.post("/api/workflows/skill-analysis", json=payload)
        assert res.status_code == 200
        data = res.json()

        # Check all top-level keys
        assert isinstance(data["execution_id"], str) and data["execution_id"].startswith("wf_")
        assert data["status"] in {"completed", "failed", "pending"}
        assert isinstance(data["matched_skills"], list)
        assert isinstance(data["missing_skills"], list)
        assert isinstance(data["prioritized_missing_skills"], list)
        assert isinstance(data["analysis"], str) and len(data["analysis"]) > 0
        assert isinstance(data["recommended_next_steps"], list) and len(data["recommended_next_steps"]) > 0
        assert isinstance(data["events"], list) and len(data["events"]) > 0
        assert data["error"] is None

        # Check individual event fields
        for evt in data["events"]:
            assert evt["event_id"].startswith("evt_")
            assert evt["execution_id"] == data["execution_id"]
            assert evt["node_name"] in {
                "validate_input",
                "compare_skills",
                "analyze_skill_gaps",
                "validate_analysis",
            }
            assert evt["event_type"] in {"node_start", "node_finish", "node_error"}
            assert evt["status"] in {"started", "completed", "failed", "skipped"}
            assert isinstance(evt["timestamp"], str)


# ---------------------------------------------------------------------------
# Test 9: Execution event ordering and durations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execution_event_ordering_and_durations(mock_gemini_output):
    """
    Verify that nodes execute strictly in sequence:
      validate_input -> compare_skills -> analyze_skill_gaps -> validate_analysis
    and that start and finish events are paired, ordered, and include real duration_ms.
    """
    with patch(
        "app.workflows.skill_nodes.generate_skill_gap_analysis",
        new_callable=AsyncMock,
        return_value=mock_gemini_output,
    ):
        state = await run_skill_analysis_workflow(
            existing_skills=["Python", "FastAPI"],
            required_skills=["Python", "Docker", "PyTorch"],
        )

        events = state["events"]
        assert len(events) == 8

        expected_sequence = [
            ("validate_input", "node_start", "started"),
            ("validate_input", "node_finish", "completed"),
            ("compare_skills", "node_start", "started"),
            ("compare_skills", "node_finish", "completed"),
            ("analyze_skill_gaps", "node_start", "started"),
            ("analyze_skill_gaps", "node_finish", "completed"),
            ("validate_analysis", "node_start", "started"),
            ("validate_analysis", "node_finish", "completed"),
        ]

        for idx, (expected_node, expected_type, expected_status) in enumerate(expected_sequence):
            evt = events[idx]
            assert evt["node_name"] == expected_node, f"Mismatch at step {idx}: expected node {expected_node}"
            assert evt["event_type"] == expected_type, f"Mismatch at step {idx}: expected type {expected_type}"
            assert evt["status"] == expected_status, f"Mismatch at step {idx}: expected status {expected_status}"
            assert evt["execution_id"] == state["execution_id"]

            if expected_type == "node_finish":
                assert evt["duration"] is not None
                assert evt["duration"] >= 0.0
                assert evt["duration_ms"] is not None
                assert evt["duration_ms"] >= 0.0


# ---------------------------------------------------------------------------
# Test 10: Status endpoint lists both workflows
# ---------------------------------------------------------------------------

def test_workflow_status_endpoint_includes_skill_analysis(client):
    """
    Verify GET /api/workflows/status reports both demo and skill-analysis workflows.
    """
    response = client.get("/api/workflows/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "demo" in data["available_workflows"]
    assert "skill-analysis" in data["available_workflows"]
    assert "validate_input" in data["skill_analysis_nodes"]
    assert "compare_skills" in data["skill_analysis_nodes"]


# ---------------------------------------------------------------------------
# Test 11: Real Gemini integration test (manual / credential-gated)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_live_gemini_integration():
    """
    Manual integration test using the live Gemini API.
    Only executed when RUN_LIVE_GEMINI_TEST=true is set in the environment,
    ensuring that automated regression runs remain fast, reliable, and consume no API quota.
    """
    import os
    if os.getenv("RUN_LIVE_GEMINI_TEST", "false").lower() not in ("true", "1"):
        pytest.skip(
            "Skipping live Gemini API test. To run this manual test against the real Gemini API, "
            "set RUN_LIVE_GEMINI_TEST=true."
        )

    is_valid, reason = settings.validate_gemini_credentials()
    if not is_valid:
        pytest.skip(f"Live Gemini API key not configured: {reason}")

    try:
        result = await generate_skill_gap_analysis(
            matched_skills=["Python", "FastAPI"],
            missing_skills=["PyTorch", "Docker"],
            optional_context="AI Engineering Internship focusing on ML deployment",
        )
        assert isinstance(result, dict)
        assert "prioritized_missing_skills" in result
        assert isinstance(result["prioritized_missing_skills"], list)
        assert "analysis" in result
        assert isinstance(result["analysis"], str) and len(result["analysis"]) > 0
        assert "recommended_next_steps" in result
        assert isinstance(result["recommended_next_steps"], list) and len(result["recommended_next_steps"]) > 0
    except Exception as exc:
        pytest.fail(f"Live Gemini API invocation failed: {exc}")
