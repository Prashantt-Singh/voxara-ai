"""
Voxara AI - Opportunities REST API Router (Phase 4)

Endpoints:
- POST /api/opportunities/hunt: Runs Opportunity Hunter workflow graph asynchronously.
- GET /api/opportunities: Lists stored opportunities from PostgreSQL with filtering.
- GET /api/opportunities/deadlines: Returns upcoming verified deadlines.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.workflows.opportunity_state import (
    OpportunityHunterRequest,
    OpportunityHunterResponse,
)
from app.workflows.opportunity_graph import run_opportunity_hunter_workflow
from app.workflows.state import ExecutionEventModel
from app.workflows.execution_store import execution_store
from app.services.opportunity_service import opportunity_service
from app.services.matching_service import matching_service
from app.services.auth_service import AuthenticatedUser, get_current_user
from app.db import repository
from app.db.models import (
    OpportunityModel,
    SavedOpportunityRead,
    SavedOpportunityCreate,
    SavedOpportunityUpdate,
    StatusUpdateRequest,
    NotesUpdateRequest,
    OpportunityMatchResult,
    MatchRequest,
    MatchResponse,
)

logger = logging.getLogger("voxara-opportunities-router")

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


class DiscoveryRequest(BaseModel):
    query: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=100)
    persist: bool = Field(default=True, description="Whether to persist results to shared database catalog")


class DiscoveryResponse(BaseModel):
    status: str = "success"
    opportunity_type: str
    count: int
    opportunities: List[OpportunityModel]
    sources_queried: List[str]


# ---------------------------------------------------------------------------
# Opportunity Discovery Endpoints (Phase 2)
# ---------------------------------------------------------------------------

@router.post("/discover/internships", response_model=DiscoveryResponse)
async def discover_internships_endpoint(req: Optional[DiscoveryRequest] = None):
    """
    Discovers tech internships from SimplifyJobs and Arbeitnow.
    Deduplicates and persists discovered records in the central catalog.
    """
    request_data = req or DiscoveryRequest()
    try:
        items = await opportunity_service.discover_internships(
            limit=request_data.limit,
            search_query=request_data.query,
            persist=request_data.persist,
        )
        return DiscoveryResponse(
            status="success",
            opportunity_type="internship",
            count=len(items),
            opportunities=items,
            sources_queried=["SimplifyJobs", "Arbeitnow"],
        )
    except Exception as exc:
        logger.error("Error in discover_internships_endpoint: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internship discovery failed: {str(exc)}")


@router.post("/discover/hackathons", response_model=DiscoveryResponse)
async def discover_hackathons_endpoint(req: Optional[DiscoveryRequest] = None):
    """
    Discovers hackathons from Devpost API.
    Deduplicates and persists discovered records in the central catalog.
    """
    request_data = req or DiscoveryRequest()
    try:
        items = await opportunity_service.discover_hackathons(
            limit=request_data.limit,
            search_query=request_data.query,
            persist=request_data.persist,
        )
        return DiscoveryResponse(
            status="success",
            opportunity_type="hackathon",
            count=len(items),
            opportunities=items,
            sources_queried=["Devpost"],
        )
    except Exception as exc:
        logger.error("Error in discover_hackathons_endpoint: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Hackathon discovery failed: {str(exc)}")


@router.post("/discover/fellowships", response_model=DiscoveryResponse)
async def discover_fellowships_endpoint(req: Optional[DiscoveryRequest] = None):
    """
    Discovers official fellowship and open source programs (GSoC, MLH Fellowship, LFX Mentorship).
    Deduplicates and persists discovered records in the central catalog.
    """
    request_data = req or DiscoveryRequest()
    try:
        items = await opportunity_service.discover_fellowships(
            limit=request_data.limit,
            search_query=request_data.query,
            persist=request_data.persist,
        )
        return DiscoveryResponse(
            status="success",
            opportunity_type="fellowship",
            count=len(items),
            opportunities=items,
            sources_queried=["Google Summer of Code", "Major League Hacking", "Linux Foundation"],
        )
    except Exception as exc:
        logger.error("Error in discover_fellowships_endpoint: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fellowship discovery failed: {str(exc)}")


@router.post("/discover", response_model=DiscoveryResponse)
async def discover_opportunities_endpoint(
    req: Optional[DiscoveryRequest] = None,
    opportunity_type: str = Query(default="all", description="'internship', 'hackathon', 'fellowship', or 'all'"),
):
    """
    Dispatches opportunity discovery for internships, hackathons, fellowships, or all.
    """
    request_data = req or DiscoveryRequest()
    target_type = opportunity_type.lower()
    try:
        items = await opportunity_service.discover_opportunities(
            opportunity_type=target_type,
            limit=request_data.limit,
            search_query=request_data.query,
            persist=request_data.persist,
        )
        if target_type == "hackathon":
            sources = ["Devpost"]
        elif target_type == "internship":
            sources = ["SimplifyJobs", "Arbeitnow"]
        elif target_type in ("fellowship", "program", "fellowships", "programs"):
            sources = ["Google Summer of Code", "Major League Hacking", "Linux Foundation"]
        else:
            sources = [
                "Devpost",
                "SimplifyJobs",
                "Arbeitnow",
                "Google Summer of Code",
                "Major League Hacking",
                "Linux Foundation",
            ]

        return DiscoveryResponse(
            status="success",
            opportunity_type=target_type,
            count=len(items),
            opportunities=items,
            sources_queried=sources,
        )
    except Exception as exc:
        logger.error("Error in discover_opportunities_endpoint: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Opportunity discovery failed: {str(exc)}")


# ---------------------------------------------------------------------------
# Opportunity Hunter LangGraph & Central Catalog Endpoints
# ---------------------------------------------------------------------------


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
    """Returns stored opportunities from PostgreSQL, sorted by match score and recency."""
    return await repository.list_opportunities(opp_type=type, min_score=min_score, limit=limit)


@router.get("/deadlines", response_model=List[OpportunityModel])
async def get_upcoming_deadlines_endpoint(
    limit: int = Query(default=20, ge=1, le=50),
):
    """Returns upcoming verified deadlines ordered chronologically."""
    return await repository.get_upcoming_deadlines(limit=limit)


# ---------------------------------------------------------------------------
# Personalized Opportunity Matching Endpoints (Phase 4)
# ---------------------------------------------------------------------------

@router.get("/matches", response_model=MatchResponse)
async def get_personalized_matches_endpoint(
    current_user: AuthenticatedUser = Depends(get_current_user),
    category: Optional[str] = Query(default=None, description="Filter by category: 'internship', 'hackathon', 'fellowship'"),
    domain: Optional[str] = Query(default=None, description="Optional domain keyword override"),
    remote_only: Optional[bool] = Query(default=None, description="Filter strictly for remote opportunities"),
    min_score: Optional[float] = Query(default=None, ge=0.0, le=1.0, description="Minimum match score threshold"),
    include_expired: bool = Query(default=False, description="Whether to include expired opportunities"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Matches stored opportunities against the authenticated user's preferences.
    Guarantees user-data isolation by reading only the authenticated user's preference record.
    """
    matches = await matching_service.match_user_opportunities(
        user_id=current_user.id,
        category=category,
        domain_override=domain,
        remote_only=remote_only,
        min_score=min_score,
        include_expired=include_expired,
        limit=limit,
    )
    return MatchResponse(
        status="success",
        user_id=current_user.id,
        total_matched=len(matches),
        opportunities=matches,
        criteria_applied={
            "user_id": current_user.id,
            "category": category,
            "domain": domain,
            "remote_only": remote_only,
            "min_score": min_score,
            "include_expired": include_expired,
            "limit": limit,
        },
    )


@router.post("/matches", response_model=MatchResponse)
async def query_personalized_matches_endpoint(
    req: MatchRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Personalized matching endpoint supporting explicit request payload criteria and profile overrides.
    """
    user_pref = await repository.get_user_preferences(user_id=current_user.id)

    active_prefs = {
        "preferred_types": [req.category] if req.category else user_pref.preferred_types,
        "target_roles": req.roles if req.roles is not None else user_pref.target_roles,
        "domains": req.domains if req.domains is not None else user_pref.domains,
        "preferred_locations": req.preferred_locations if req.preferred_locations is not None else user_pref.preferred_locations,
        "remote_only": req.remote_only if req.remote_only is not None else user_pref.remote_only,
        "skills": req.skills if req.skills is not None else user_pref.skills,
        "education_level": req.education_level if req.education_level is not None else user_pref.education_level,
        "graduation_year": req.graduation_year if req.graduation_year is not None else user_pref.graduation_year,
        "eligibility_context": user_pref.eligibility_context or {},
        "min_match_score": req.min_score if req.min_score is not None else user_pref.min_match_score,
    }

    opps = await repository.list_shared_opportunities(
        opp_type=req.category,
        opp_types=[req.category] if req.category else active_prefs["preferred_types"],
        include_expired=req.include_expired,
        limit=100,
    )

    matched_results = []
    score_threshold = active_prefs["min_match_score"]
    for opp in opps:
        res = matching_service.match_opportunity(
            opp=opp,
            preferences=active_prefs,
            category_filter=req.category,
            include_expired=req.include_expired,
        )
        if res and res.match_score >= score_threshold:
            matched_results.append(res)

    matched_results.sort(
        key=lambda x: (
            x.match_score,
            x.deadline is not None,
            -(x.deadline.timestamp() if x.deadline else 0),
        ),
        reverse=True,
    )

    final_list = matched_results[:req.limit]
    return MatchResponse(
        status="success",
        user_id=current_user.id,
        total_matched=len(final_list),
        opportunities=final_list,
        criteria_applied=req.model_dump(),
    )


# ---------------------------------------------------------------------------
# User Pipeline & Saved Opportunity Endpoints (Multi-User, Phase 5)
# ---------------------------------------------------------------------------


@router.post("/saved", response_model=SavedOpportunityRead, status_code=200)
async def save_opportunity_for_user(
    data: SavedOpportunityCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Saves an opportunity into the authenticated user's personal pipeline.
    Validates that the target shared opportunity exists (HTTP 404 if missing).
    If already saved, updates status/notes idempotently without creating duplicates.
    """
    try:
        return await repository.save_user_opportunity(user_id=current_user.id, data=data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/saved", response_model=List[SavedOpportunityRead])
async def list_user_saved_opportunities_endpoint(
    status: Optional[str] = Query(default=None, description="Filter by status: saved, interested, applied, interviewing, offered, rejected, withdrawn"),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Lists saved opportunities in the authenticated user's personal pipeline.
    Includes opportunity source, application URL, deadline, and verification status.
    Strictly isolated to the authenticated user identity.
    """
    return await repository.list_user_saved_opportunities(
        user_id=current_user.id,
        status=status,
        limit=limit,
    )


@router.get("/saved/{saved_id}", response_model=SavedOpportunityRead)
async def get_user_saved_opportunity_endpoint(
    saved_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieves a single saved opportunity with source, application URL, deadline,
    and verification status. Verifies user ownership.
    """
    item = await repository.get_user_saved_opportunity(user_id=current_user.id, saved_id=saved_id)
    if not item:
        raise HTTPException(status_code=404, detail="Saved opportunity not found or unauthorized.")
    return item


@router.patch("/saved/{saved_id}", response_model=SavedOpportunityRead)
async def update_user_saved_opportunity_endpoint(
    saved_id: str,
    updates: SavedOpportunityUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Updates application status (saved, interested, applied, interviewing, offered, rejected, withdrawn)
    and/or personal notes. Verifies user ownership.
    """
    updated = await repository.update_user_saved_opportunity(
        user_id=current_user.id,
        saved_id=saved_id,
        updates=updates,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Saved opportunity not found or unauthorized.")
    return updated


@router.patch("/saved/{saved_id}/status", response_model=SavedOpportunityRead)
async def update_user_saved_opportunity_status_endpoint(
    saved_id: str,
    body: StatusUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Updates the application status for an opportunity.
    Accepts: Saved, Interested, Applied, Interviewing, Offered, Rejected, Withdrawn.
    Verifies user ownership.
    """
    updated = await repository.update_user_saved_opportunity(
        user_id=current_user.id,
        saved_id=saved_id,
        updates=SavedOpportunityUpdate(status=body.status),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Saved opportunity not found or unauthorized.")
    return updated


@router.patch("/saved/{saved_id}/notes", response_model=SavedOpportunityRead)
async def update_user_saved_opportunity_notes_endpoint(
    saved_id: str,
    body: NotesUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Updates private notes for an opportunity.
    Notes remain strictly private to the authenticated user.
    Verifies user ownership.
    """
    updated = await repository.update_user_saved_opportunity(
        user_id=current_user.id,
        saved_id=saved_id,
        updates=SavedOpportunityUpdate(notes=body.notes),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Saved opportunity not found or unauthorized.")
    return updated


@router.delete("/saved/{saved_id}")
async def delete_user_saved_opportunity_endpoint(
    saved_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Removes an opportunity from the authenticated user's personal pipeline.
    Verifies user ownership.
    Does NOT delete the shared opportunity record.
    """
    deleted = await repository.delete_user_saved_opportunity(user_id=current_user.id, saved_id=saved_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved opportunity not found or unauthorized.")
    return {"status": "deleted", "saved_id": saved_id}

