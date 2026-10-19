"""
Voxara AI - Opportunities REST API Router (Phase 4)

Endpoints:
- POST /api/opportunities/hunt: Runs Opportunity Hunter workflow graph asynchronously.
- GET /api/opportunities: Lists stored opportunities from SQLite with filtering.
- GET /api/opportunities/deadlines: Returns upcoming verified deadlines.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.workflows.opportunity_state import (
    OpportunityHunterRequest,
    OpportunityHunterResponse,
)
from app.workflows.opportunity_graph import run_opportunity_hunter_workflow
from app.workflows.state import ExecutionEventModel
from app.workflows.execution_store import execution_store
from app.db import repository
from app.db.models import (
    OpportunityModel,
    SavedOpportunityRead,
    SavedOpportunityCreate,
    SavedOpportunityUpdate,
)

logger = logging.getLogger("voxara-opportunities-router")

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


@router.post("/hunt", response_model=OpportunityHunterResponse)
async def hunt_opportunities_endpoint(req: OpportunityHunterRequest):
    """
    Executes the Opportunity Hunter LangGraph workflow.
    Queries Devpost and tech programs, computes match scores, tracks deadlines,
    and returns verified opportunities.
    """
    logger.info("Triggered Opportunity Hunter workflow via REST: query='%s', type='%s'", req.query, req.opportunity_type)

    final_state = await run_opportunity_hunter_workflow(
        query=req.query,
        opportunity_type=req.opportunity_type,
        min_score=req.min_score,
        limit=req.limit,
    )

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

    return OpportunityHunterResponse(
        execution_id=final_state["execution_id"],
        query=req.query,
        opportunity_type=req.opportunity_type,
        status=final_state.get("status", "completed"),
        found_count=len(final_state.get("opportunities", [])),
        opportunities=final_state.get("opportunities", []),
        urgent_deadlines=final_state.get("urgent_deadlines", []),
        spoken_briefing=final_state.get("spoken_briefing", ""),
        events=event_models,
        error=final_state.get("error"),
    )


@router.get("", response_model=List[OpportunityModel])
async def list_stored_opportunities(
    type: Optional[str] = Query(default=None, description="Filter by opportunity type"),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0, description="Minimum match score"),
    limit: int = Query(default=50, ge=1, le=100),
):
    """Returns stored opportunities from SQLite, sorted by match score and recency."""
    return await repository.list_opportunities(opp_type=type, min_score=min_score, limit=limit)


@router.get("/deadlines", response_model=List[OpportunityModel])
async def get_upcoming_deadlines_endpoint(
    limit: int = Query(default=20, ge=1, le=50),
):
    """Returns upcoming verified deadlines ordered chronologically."""
    return await repository.get_upcoming_deadlines(limit=limit)


# ---------------------------------------------------------------------------
# User Pipeline & Saved Opportunity Endpoints (Multi-User)
# ---------------------------------------------------------------------------

@router.post("/saved", response_model=SavedOpportunityRead)
async def save_opportunity_for_user(
    data: SavedOpportunityCreate,
    user_id: str = Query(default="default_user", description="Authenticated user ID"),
):
    """Saves an opportunity to the user's personal tracking pipeline."""
    return await repository.save_user_opportunity(user_id=user_id, data=data)


@router.get("/saved", response_model=List[SavedOpportunityRead])
async def list_user_saved_opportunities_endpoint(
    user_id: str = Query(default="default_user", description="Authenticated user ID"),
    status: Optional[str] = Query(default=None, description="Filter by status: saved, applied, interviewing, etc."),
    limit: int = Query(default=50, ge=1, le=100),
):
    """Lists saved opportunities in the user's personal pipeline."""
    return await repository.list_user_saved_opportunities(user_id=user_id, status=status, limit=limit)


@router.patch("/saved/{saved_id}", response_model=SavedOpportunityRead)
async def update_user_saved_opportunity_endpoint(
    saved_id: str,
    updates: SavedOpportunityUpdate,
    user_id: str = Query(default="default_user", description="Authenticated user ID"),
):
    """Updates application status (applied, interviewing, etc.) or personal notes."""
    updated = await repository.update_user_saved_opportunity(user_id=user_id, saved_id=saved_id, updates=updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Saved opportunity not found or unauthorized.")
    return updated


@router.delete("/saved/{saved_id}")
async def delete_user_saved_opportunity_endpoint(
    saved_id: str,
    user_id: str = Query(default="default_user", description="Authenticated user ID"),
):
    """Removes an opportunity from the user's personal tracking pipeline."""
    deleted = await repository.delete_user_saved_opportunity(user_id=user_id, saved_id=saved_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved opportunity not found or unauthorized.")
    return {"status": "deleted", "saved_id": saved_id}

