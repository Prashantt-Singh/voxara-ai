"""
Voxara AI - Workflows API Router (Step 4A: Agentic Workflow Foundation)

This module defines FastAPI endpoints for orchestrating LangGraph workflows.
Provides:
  - POST /api/workflows/demo: Runs the demonstration workflow graph asynchronously.
  - GET /api/workflows/status: Returns orchestration engine health and metadata.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.workflows.state import (
    WorkflowDemoRequest,
    WorkflowDemoResponse,
    ExecutionEventModel,
)
from app.workflows.graph import run_workflow

logger = logging.getLogger("voxara-api")

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class WorkflowEngineStatusResponse(BaseModel):
    status: str = Field(description="Workflow orchestration engine readiness status")
    engine: str = Field(description="Underlying graph orchestration framework")
    graph_nodes: list[str] = Field(description="Registered graph nodes in demonstration pipeline")
    details: str = Field(description="Operational status description")


@router.get("/status", response_model=WorkflowEngineStatusResponse)
async def get_workflow_status():
    """
    Returns workflow engine readiness and registered demonstration graph metadata.
    """
    return WorkflowEngineStatusResponse(
        status="ready",
        engine="LangGraph StateGraph",
        graph_nodes=["receive_request", "validate_request", "produce_result"],
        details="LangGraph agentic workflow orchestration engine initialized and ready.",
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

    # Convert event dicts to validated Pydantic models
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
        result=final_state.get("result"),
        error=final_state.get("error"),
        events=event_models,
    )
