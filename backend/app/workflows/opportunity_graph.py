"""
Voxara AI - Opportunity Hunter Graph Orchestration (Phase 4: LangGraph)

Constructs and compiles the StateGraph:
  START -> load_hunt_criteria -> ingest_and_score -> track_deadlines_and_briefing -> END
"""

from __future__ import annotations

import logging
from typing import Optional
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from app.workflows.state import generate_execution_id, create_execution_event
from app.workflows.opportunity_state import OpportunityHunterState
from app.workflows.opportunity_nodes import (
    load_hunt_criteria,
    ingest_and_score,
    track_deadlines_and_briefing,
)

logger = logging.getLogger("voxara-opportunity-graph")


def build_opportunity_hunter_graph() -> CompiledStateGraph:
    """Constructs and compiles the StateGraph for Opportunity Hunter."""
    builder = StateGraph(OpportunityHunterState)

    builder.add_node("load_hunt_criteria", load_hunt_criteria)
    builder.add_node("ingest_and_score", ingest_and_score)
    builder.add_node("track_deadlines_and_briefing", track_deadlines_and_briefing)

    builder.add_edge(START, "load_hunt_criteria")
    builder.add_edge("load_hunt_criteria", "ingest_and_score")
    builder.add_edge("ingest_and_score", "track_deadlines_and_briefing")
    builder.add_edge("track_deadlines_and_briefing", END)

    return builder.compile()


# Global compiled graph instance
opportunity_hunter_graph: CompiledStateGraph = build_opportunity_hunter_graph()


async def run_opportunity_hunter_workflow(
    query: str = "all",
    opportunity_type: str = "all",
    min_score: float = 0.5,
    limit: int = 10,
    execution_id: Optional[str] = None,
) -> OpportunityHunterState:
    """
    Executes the compiled Opportunity Hunter graph asynchronously with an isolated state.
    """
    exec_id = execution_id or generate_execution_id()

    initial_state: OpportunityHunterState = {
        "execution_id": exec_id,
        "query": query,
        "opportunity_type": opportunity_type,
        "min_score": min_score,
        "limit": limit,
        "opportunities": [],
        "urgent_deadlines": [],
        "spoken_briefing": "",
        "status": "pending",
        "events": [],
        "error": None,
    }

    try:
        final_state: OpportunityHunterState = await opportunity_hunter_graph.ainvoke(initial_state)
        return final_state
    except Exception as exc:
        logger.error("Opportunity Hunter execution failed for %s: %s", exec_id, exc, exc_info=True)
        fallback_event = create_execution_event(
            execution_id=exec_id,
            node_name="opportunity_hunter_graph",
            event_type="node_error",
            status="failed",
            details={"error": str(exc)},
        )
        return {
            "execution_id": exec_id,
            "query": query,
            "opportunity_type": opportunity_type,
            "min_score": min_score,
            "limit": limit,
            "opportunities": [],
            "urgent_deadlines": [],
            "spoken_briefing": "I encountered an issue while searching for opportunities.",
            "status": "failed",
            "events": [fallback_event],
            "error": f"Unhandled opportunity hunter failure: {str(exc)}",
        }
