"""
Voxara AI - Workflows API Router (Step 4A & 4B: Agentic Workflows & Skill Analysis)

This module defines FastAPI endpoints for orchestrating LangGraph workflows.
Provides:
  - GET /api/workflows/status: Returns orchestration engine health and metadata.
  - POST /api/workflows/demo: Runs the demonstration workflow graph asynchronously.
  - POST /api/workflows/skill-analysis: Runs the Gemini-powered skill analysis workflow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.workflows.state import (
    WorkflowDemoRequest,
    WorkflowDemoResponse,
    SkillAnalysisRequest,
    SkillAnalysisResponse,
    ExecutionEventModel,
)
from app.workflows.graph import run_workflow
from app.workflows.skill_graph import run_skill_analysis_workflow
from app.workflows.execution_store import execution_store

logger = logging.getLogger("voxara-api")

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class WorkflowEngineStatusResponse(BaseModel):
    status: str = Field(description="Workflow orchestration engine readiness status")
    engine: str = Field(description="Underlying graph orchestration framework")
    graph_nodes: list[str] = Field(description="Registered graph nodes in demonstration pipeline")
    skill_analysis_nodes: list[str] = Field(
        default_factory=lambda: [
            "validate_input",
            "compare_skills",
            "analyze_skill_gaps",
            "validate_analysis",
        ],
        description="Registered graph nodes in the skill analysis pipeline",
    )
    available_workflows: list[str] = Field(
        default_factory=lambda: ["demo", "skill-analysis"],
        description="List of available executable workflows",
    )
    voice_tools_registered: list[str] = Field(
        default_factory=lambda: ["analyze_skills_demonstration", "run_demo_workflow"],
        description="Registered LiveKit voice agent workflow tools",
    )
    details: str = Field(description="Operational status description")


@router.get("/status", response_model=WorkflowEngineStatusResponse)
async def get_workflow_status():
    """
    Returns workflow engine readiness, registered graph metadata, and voice tools.
    """
    return WorkflowEngineStatusResponse(
        status="ready",
        engine="LangGraph StateGraph",
        graph_nodes=["receive_request", "validate_request", "produce_result"],
        skill_analysis_nodes=[
            "validate_input",
            "compare_skills",
            "analyze_skill_gaps",
            "validate_analysis",
        ],
        available_workflows=["demo", "skill-analysis"],
        voice_tools_registered=["analyze_skills_demonstration", "run_demo_workflow"],
        details="LangGraph agentic workflow orchestration engine and voice tools initialized and ready.",
    )


@router.post("/demo", response_model=WorkflowDemoResponse)
async def run_demo_workflow_endpoint(req: WorkflowDemoRequest):
    """
    Executes the demonstration workflow graph asynchronously.

    Accepts:
      - task: Non-empty description of the task.
      - input_data: Optional key-value dictionary of task parameters.

    Returns:
      - execution_id: Unique execution identifier.
      - task: Echoed task description.
      - status: Final execution status (completed, failed).
      - result: Structured execution outcome (if successful).
      - error: Error message (if execution or validation failed).
      - events: Real chronological start and finish events with durations.
    """
    logger.info("Starting workflow demonstration execution for task: '%s'", req.task)

    final_state = await run_workflow(
        task=req.task,
        input_data=req.input_data,
    )

    # Record execution in shared observability store
    execution_store.save_execution(final_state)

    event_models = [
        ExecutionEventModel(
            event_id=evt["event_id"],
            execution_id=evt["execution_id"],
            node_name=evt["node_name"],
            event_type=evt["event_type"],
            timestamp=evt["timestamp"],
            status=evt["status"],
            duration=evt.get("duration"),
            duration_ms=evt.get("duration_ms"),
            details=evt.get("details"),
        )
        for evt in final_state.get("events", [])
    ]

    return WorkflowDemoResponse(
        execution_id=final_state["execution_id"],
        task=final_state.get("task", req.task),
        status=final_state.get("status", "completed"),
        intermediate_results=final_state.get("intermediate_results"),
        result=final_state.get("result"),
        error=final_state.get("error"),
        events=event_models,
    )


@router.post("/skill-analysis", response_model=SkillAnalysisResponse)
async def run_skill_analysis_endpoint(req: SkillAnalysisRequest):
    """
    Executes the Gemini-powered skill gap analysis workflow asynchronously.

    Accepts:
      - existing_skills: List of skills the candidate currently possesses.
      - required_skills: List of skills required for the internship or role.
      - optional_context: Optional context regarding the role or user goals.

    Returns:
      - execution_id: Unique execution identifier.
      - status: Final execution status (completed, failed).
      - matched_skills: Skills present in both sets.
      - missing_skills: Required skills missing from candidate's profile.
      - prioritized_missing_skills: Ranked list of missing skills by urgency.
      - analysis: Semantic gap analysis and contextual explanation.
      - recommended_next_steps: Concrete, actionable learning tasks.
      - events: Real start and finish/error execution events with true durations.
      - error: Error description if workflow or validation failed.
    """
    logger.info(
        "Starting skill analysis workflow: %d existing vs %d required skills",
        len(req.existing_skills),
        len(req.required_skills),
    )

    final_state = await run_skill_analysis_workflow(
        existing_skills=req.existing_skills,
        required_skills=req.required_skills,
        optional_context=req.optional_context,
    )

    # Record execution in shared observability store
    execution_store.save_execution(final_state)

    event_models = [
        ExecutionEventModel(
            event_id=evt["event_id"],
            execution_id=evt["execution_id"],
            node_name=evt["node_name"],
            event_type=evt["event_type"],
            timestamp=evt["timestamp"],
            status=evt["status"],
            duration=evt.get("duration"),
            duration_ms=evt.get("duration_ms"),
            details=evt.get("details"),
        )
        for evt in final_state.get("events", [])
    ]

    return SkillAnalysisResponse(
        execution_id=final_state["execution_id"],
        status=final_state.get("status", "completed"),
        matched_skills=final_state.get("matched_skills", []),
        missing_skills=final_state.get("missing_skills", []),
        prioritized_missing_skills=final_state.get("prioritized_missing_skills", []),
        analysis=final_state.get("analysis", ""),
        recommended_next_steps=final_state.get("recommended_next_steps", []),
        events=event_models,
        error=final_state.get("error"),
    )


@router.get("/executions")
async def list_recent_executions(limit: int = 20):
    """
    Returns recent workflow execution logs across voice and REST calls.
    Ordered from newest to oldest.
    """
    return {
        "count": len(execution_store.list_executions(limit=limit)),
        "executions": execution_store.list_executions(limit=limit),
    }


@router.get("/executions/{execution_id}")
async def get_execution_record(execution_id: str):
    """
    Retrieves full execution state and node event logs for a specific workflow run.
    """
    record = execution_store.get_execution(execution_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Execution with ID '{execution_id}' not found.",
        )
    return record
