"""
Voxara AI - Opportunity Hunter Nodes (Phase 4: LangGraph)

Implements discrete, observable workflow nodes:
1. load_hunt_criteria: Reads query, filters, and user preferences.
2. ingest_and_score: Queries Devpost and verified program sources, storing and scoring matches.
3. track_deadlines_and_briefing: Identifies urgent deadlines and formats a voice-ready briefing.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from app.workflows.state import create_execution_event
from app.workflows.opportunity_state import OpportunityHunterState
from app.services.opportunity_service import opportunity_service
from app.db import repository
from app.db.models import NotificationModel, compute_content_hash

logger = logging.getLogger("voxara-opportunity-nodes")


async def load_hunt_criteria(state: OpportunityHunterState) -> Dict[str, Any]:
    """Node 1: Loads hunt parameters and candidate preferences."""
    node_name = "load_hunt_criteria"
    exec_id = state.get("execution_id", "unknown")
    start_time = time.perf_counter()

    start_event = create_execution_event(
        execution_id=exec_id,
        node_name=node_name,
        event_type="node_start",
        status="started",
        details={"message": "Loading opportunity criteria and user preferences"},
    )

    try:
        raw_query = state.get("query", "all")
        query = raw_query.strip() if isinstance(raw_query, str) and raw_query.strip() else "all"
        opp_type = state.get("opportunity_type", "all").strip().lower()
        min_score = state.get("min_score", 0.5)

        prefs = await repository.get_user_preferences()

        elapsed = time.perf_counter() - start_time
        finish_event = create_execution_event(
            execution_id=exec_id,
            node_name=node_name,
            event_type="node_finish",
            status="completed",
            duration=elapsed,
            details={"query": query, "opp_type": opp_type, "target_roles": prefs.roles},
        )

        return {
            "query": query,
            "opportunity_type": opp_type,
            "min_score": min_score,
            "status": "running",
            "events": [start_event, finish_event],
        }

    except Exception as exc:
        logger.error("Error in load_hunt_criteria: %s", exc, exc_info=True)
        elapsed = time.perf_counter() - start_time
        error_event = create_execution_event(
            execution_id=exec_id,
            node_name=node_name,
            event_type="node_error",
            status="failed",
            duration=elapsed,
            details={"error": str(exc)},
        )
        return {
            "status": "failed",
            "error": f"Failed to load criteria: {str(exc)}",
            "events": [start_event, error_event],
        }


async def ingest_and_score(state: OpportunityHunterState) -> Dict[str, Any]:
    """Node 2: Fetches real opportunities, stores them in SQLite, and filters by criteria."""
    node_name = "ingest_and_score"
    exec_id = state.get("execution_id", "unknown")
    start_time = time.perf_counter()

    start_event = create_execution_event(
        execution_id=exec_id,
        node_name=node_name,
        event_type="node_start",
        status="started",
        details={"message": "Ingesting and scoring real opportunities from Devpost and curated feeds"},
    )

    try:
        if state.get("status") == "failed":
            elapsed = time.perf_counter() - start_time
            finish_event = create_execution_event(
                execution_id=exec_id,
                node_name=node_name,
                event_type="node_finish",
                status="skipped",
                duration=elapsed,
            )
            return {"events": [start_event, finish_event]}

        opp_type = state.get("opportunity_type", "all")
        query = state.get("query", "all").lower()
        min_score = state.get("min_score", 0.5)

        # Ingest and store real opportunities
        items = await opportunity_service.sync_and_store_opportunities(
            opportunity_type=opp_type,
            min_score=min_score,
        )

        # Optional query filter
        filtered_items = []
        for opp in items:
            if query != "all":
                text_to_search = f"{opp.title} {opp.organization} {opp.description} {' '.join(opp.requirements)}".lower()
                if query not in text_to_search:
                    continue
            filtered_items.append(opp.model_dump())

        elapsed = time.perf_counter() - start_time
        finish_event = create_execution_event(
            execution_id=exec_id,
            node_name=node_name,
            event_type="node_finish",
            status="completed",
            duration=elapsed,
            details={"ingested_count": len(filtered_items)},
        )

        return {
            "opportunities": filtered_items,
            "events": [start_event, finish_event],
        }

    except Exception as exc:
        logger.error("Error in ingest_and_score: %s", exc, exc_info=True)
        elapsed = time.perf_counter() - start_time
        error_event = create_execution_event(
            execution_id=exec_id,
            node_name=node_name,
            event_type="node_error",
            status="failed",
            duration=elapsed,
            details={"error": str(exc)},
        )
        return {
            "status": "failed",
            "error": f"Failed to ingest opportunities: {str(exc)}",
            "events": [start_event, error_event],
        }


async def track_deadlines_and_briefing(state: OpportunityHunterState) -> Dict[str, Any]:
    """Node 3: Identifies urgent deadlines, alerts user, and prepares spoken briefing."""
    node_name = "track_deadlines_and_briefing"
    exec_id = state.get("execution_id", "unknown")
    start_time = time.perf_counter()

    start_event = create_execution_event(
        execution_id=exec_id,
        node_name=node_name,
        event_type="node_start",
        status="started",
        details={"message": "Checking deadline dates and preparing voice briefing"},
    )

    try:
        if state.get("status") == "failed":
            elapsed = time.perf_counter() - start_time
            finish_event = create_execution_event(
                execution_id=exec_id,
                node_name=node_name,
                event_type="node_finish",
                status="skipped",
                duration=elapsed,
            )
            return {"events": [start_event, finish_event]}

        opportunities = state.get("opportunities", [])
        deadlines_list = await repository.get_upcoming_deadlines(limit=5)
        urgent_deadlines = [d.model_dump() for d in deadlines_list]

        # Log notification for top verified opportunity
        if opportunities:
            top = opportunities[0]
            notif_hash = compute_content_hash(top.get("source_url", ""), f"opp::{top.get('title', '')}")
            notif = NotificationModel(
                id=f"notif_{top.get('id', 'opp')}",
                item_type="opportunity",
                item_id=top.get("id"),
                title=f"Opportunity Match: {top.get('title')}",
                message=f"{top.get('organization')} — {top.get('description')}",
                spoken_summary=f"Found a matching opportunity: {top.get('title')} hosted by {top.get('organization')}.",
                content_hash=notif_hash,
                priority="normal",
            )
            await repository.create_notification(notif)

        # Format natural speech briefing
        if not opportunities:
            briefing = "I searched available opportunity feeds, but couldn't find matching open applications right now."
        else:
            top_titles = [o.get("title", "") for o in opportunities[:2] if o.get("title")]
            sample = " and ".join(top_titles)
            deadline_note = ""
            if urgent_deadlines:
                closest = urgent_deadlines[0]
                deadline_note = f" Note that {closest.get('title')} has a submission deadline approaching."

            briefing = (
                f"I discovered {len(opportunities)} opportunities matching your criteria, "
                f"including {sample}.{deadline_note} I've saved all details to your dashboard."
            )

        elapsed = time.perf_counter() - start_time
        finish_event = create_execution_event(
            execution_id=exec_id,
            node_name=node_name,
            event_type="node_finish",
            status="completed",
            duration=elapsed,
            details={"opportunities_count": len(opportunities), "deadlines_count": len(urgent_deadlines)},
        )

        return {
            "status": "completed",
            "urgent_deadlines": urgent_deadlines,
            "spoken_briefing": briefing,
            "events": [start_event, finish_event],
        }

    except Exception as exc:
        logger.error("Error in track_deadlines_and_briefing: %s", exc, exc_info=True)
        elapsed = time.perf_counter() - start_time
        error_event = create_execution_event(
            execution_id=exec_id,
            node_name=node_name,
            event_type="node_error",
            status="failed",
            duration=elapsed,
            details={"error": str(exc)},
        )
        return {
            "status": "failed",
            "error": f"Failed to finalize opportunity briefing: {str(exc)}",
            "events": [start_event, error_event],
        }
