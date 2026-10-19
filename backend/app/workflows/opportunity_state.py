"""
Voxara AI - Opportunity Hunter State Definitions (Phase 4)

Defines the typed state representation for the LangGraph Opportunity Hunter pipeline:
  START -> load_hunt_criteria -> ingest_and_score -> track_deadlines_and_briefing -> END
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

from app.workflows.state import ExecutionEvent, ExecutionEventModel


class OpportunityHunterState(TypedDict):
    """
    Typed state passed across nodes in the Opportunity Hunter LangGraph workflow.
    Uses operator.add reducer for appending real node lifecycle events.
    """
    execution_id: str
    query: str
    opportunity_type: str
    min_score: float
    limit: int
    opportunities: List[Dict[str, Any]]
    urgent_deadlines: List[Dict[str, Any]]
    spoken_briefing: str
    status: Literal["pending", "running", "completed", "failed"]
    events: Annotated[List[ExecutionEvent], operator.add]
    error: Optional[str]


class OpportunityHunterRequest(BaseModel):
    """Payload for invoking the Opportunity Hunter workflow via REST."""
    query: str = Field(default="all", description="Query or domain filter (e.g. 'AI', 'hackathon')")
    opportunity_type: str = Field(
        default="all",
        description="Filter by type: 'hackathon', 'internship', 'scholarship', or 'all'",
    )
    min_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum match score")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum opportunities to return")


class OpportunityHunterResponse(BaseModel):
    """Payload returned by the Opportunity Hunter endpoint."""
    execution_id: str
    query: str
    opportunity_type: str
    status: str
    found_count: int
    opportunities: List[Dict[str, Any]]
    urgent_deadlines: List[Dict[str, Any]]
    spoken_briefing: str
    events: List[ExecutionEventModel]
    error: Optional[str] = None
