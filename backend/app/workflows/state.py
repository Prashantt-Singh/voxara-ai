"""
Voxara AI - Workflow State and Event Definitions (Step 4A: Agentic Workflow Foundation)

This module defines the typed state schemas, execution event structures,
and Pydantic models for LangGraph workflow orchestration.
"""

from __future__ import annotations

import operator
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field, field_validator


def generate_execution_id() -> str:
    """Generates a unique execution identifier prefixed with 'wf_'."""
    return f"wf_{uuid.uuid4().hex[:12]}"


def generate_event_id() -> str:
    """Generates a unique event identifier prefixed with 'evt_'."""
    return f"evt_{uuid.uuid4().hex[:12]}"


def current_utc_iso() -> str:
    """Returns current UTC timestamp formatted as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# TypedDict Definitions for LangGraph StateGraph
# ---------------------------------------------------------------------------

class ExecutionEvent(TypedDict):
    """
    Structured execution event describing a node lifecycle event.
    Designed for real-time tracking, HTTP responses, and future React Flow/DB persistence.
    """
    event_id: str
    execution_id: str
    node_name: str
    event_type: Literal["node_start", "node_finish", "node_error"]
    timestamp: str
    status: Literal["started", "completed", "failed", "skipped"]
    duration: Optional[float]
    duration_ms: Optional[float]
    details: Optional[Dict[str, Any]]


def create_execution_event(
    execution_id: str,
    node_name: str,
    event_type: Literal["node_start", "node_finish", "node_error"],
    status: Literal["started", "completed", "failed", "skipped"],
    duration: Optional[float] = None,
    details: Optional[Dict[str, Any]] = None,
) -> ExecutionEvent:
    """
    Factory helper to create a standardized ExecutionEvent.
    """
    duration_sec = round(duration, 6) if duration is not None else None
    duration_ms = round(duration * 1000.0, 3) if duration is not None else None

    return ExecutionEvent(
        event_id=generate_event_id(),
        execution_id=execution_id,
        node_name=node_name,
        event_type=event_type,
        timestamp=current_utc_iso(),
        status=status,
        duration=duration_sec,
        duration_ms=duration_ms,
        details=details or {},
    )


class WorkflowState(TypedDict):
    """
    Typed state representation passed across LangGraph nodes in a general-purpose workflow.
    Each execution receives an isolated dictionary instance to prevent shared state.
    Events list uses operator.add reducer to append node lifecycle events.
    """
    execution_id: str
    task: str
    input_data: Dict[str, Any]
    status: Literal["pending", "running", "completed", "failed"]
    events: Annotated[List[ExecutionEvent], operator.add]
    intermediate_results: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    error: Optional[str]


# ---------------------------------------------------------------------------
# Pydantic Schemas for FastAPI Validation & Serialization
# ---------------------------------------------------------------------------

class ExecutionEventModel(BaseModel):
    """Pydantic model representing an execution event in API responses."""
    event_id: str = Field(description="Unique event ID")
    execution_id: str = Field(description="Workflow execution ID")
    node_name: str = Field(description="Name of the workflow node")
    event_type: str = Field(description="Lifecycle event type: node_start, node_finish, node_error")
    timestamp: str = Field(description="ISO 8601 timestamp in UTC")
    status: str = Field(description="Status: started, completed, failed, skipped")
    duration: Optional[float] = Field(default=None, description="Elapsed execution duration in seconds")
    duration_ms: Optional[float] = Field(default=None, description="Elapsed execution duration in milliseconds")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata or error details")


class WorkflowDemoRequest(BaseModel):
    """Request payload for initiating a workflow demonstration."""
    task: str = Field(
        ...,
        min_length=1,
        description="Non-empty task description for the workflow to process",
        examples=["Analyze system telemetry"],
    )
    input_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional structured input data for the workflow execution",
    )

    @field_validator("task")
    @classmethod
    def validate_task_non_empty(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Task description cannot be empty or solely whitespace.")
        return trimmed


class WorkflowDemoResponse(BaseModel):
    """Response payload returned by the workflow demonstration endpoint."""
    execution_id: str = Field(description="Unique identifier for this workflow execution")
    task: str = Field(description="Task description")
    status: str = Field(description="Final workflow status: completed, failed, or pending")
    intermediate_results: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Intermediate outcomes generated across workflow stages before finalization",
    )
    result: Optional[Dict[str, Any]] = Field(default=None, description="Final workflow execution result payload")
    error: Optional[str] = Field(default=None, description="Error message if workflow execution failed")
    events: List[ExecutionEventModel] = Field(
        default_factory=list,
        description="Chronological log of real node start and finish execution events",
    )


# ---------------------------------------------------------------------------
# Step 4B: Skill Analysis Workflow State & Schemas
# ---------------------------------------------------------------------------

class SkillAnalysisState(TypedDict):
    """
    Typed state representation passed across LangGraph nodes in the Skill Analysis workflow.
    Each execution receives an isolated dictionary instance to prevent shared state.
    Events list uses operator.add reducer to append node lifecycle events.
    """
    execution_id: str
    existing_skills: List[str]
    required_skills: List[str]
    optional_context: Optional[str]
    status: Literal["pending", "running", "completed", "failed"]
    events: Annotated[List[ExecutionEvent], operator.add]
    matched_skills: List[str]
    missing_skills: List[str]
    prioritized_missing_skills: List[str]
    analysis: str
    recommended_next_steps: List[str]
    raw_analysis: Optional[Dict[str, Any]]
    error: Optional[str]


class SkillAnalysisRequest(BaseModel):
    """Request payload for the Gemini-powered skill gap analysis workflow."""
    existing_skills: List[str] = Field(
        ...,
        description="List of skills currently possessed by the candidate",
        examples=[["Python", "FastAPI", "Git"]],
    )
    required_skills: List[str] = Field(
        ...,
        description="List of skills required for the internship or role",
        examples=[["Python", "Docker", "PyTorch", "FastAPI"]],
    )
    optional_context: Optional[str] = Field(
        default=None,
        description="Optional context describing the internship or candidate's goals",
        examples=["Applying for an AI Engineering internship focusing on backend model deployment."],
    )

    @field_validator("existing_skills", "required_skills")
    @classmethod
    def validate_skills_list(cls, v: List[str], info) -> List[str]:
        field_name = info.field_name
        if not isinstance(v, list) or len(v) == 0:
            raise ValueError(f"'{field_name}' must be a non-empty list of skill names.")
        cleaned: List[str] = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError(f"All items in '{field_name}' must be strings.")
            trimmed = item.strip()
            if trimmed:
                cleaned.append(trimmed)
        if not cleaned:
            raise ValueError(f"'{field_name}' cannot consist solely of empty or whitespace strings.")
        return cleaned


class SkillAnalysisResponse(BaseModel):
    """Response payload returned by the skill analysis workflow endpoint."""
    execution_id: str = Field(description="Unique identifier for this workflow execution")
    status: str = Field(description="Final execution status: completed, failed, or pending")
    matched_skills: List[str] = Field(
        default_factory=list,
        description="Skills present in both candidate skills and role requirements",
    )
    missing_skills: List[str] = Field(
        default_factory=list,
        description="Required skills not currently possessed by the candidate",
    )
    prioritized_missing_skills: List[str] = Field(
        default_factory=list,
        description="Missing skills ranked by learning priority for the specified role",
    )
    analysis: str = Field(
        default="",
        description="Contextual reasoning explaining skill gaps and relevance to the role",
    )
    recommended_next_steps: List[str] = Field(
        default_factory=list,
        description="Concrete, actionable recommendations for closing the identified skill gaps",
    )
    events: List[ExecutionEventModel] = Field(
        default_factory=list,
        description="Chronological log of real node start, finish, and error execution events",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if workflow execution or validation failed",
    )

