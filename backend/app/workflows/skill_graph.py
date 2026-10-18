"""
Voxara AI - Skill Analysis Graph Orchestration (Step 4B: Gemini-Powered Skill Analysis)

This module builds, compiles, and runs the LangGraph StateGraph connecting
the skill analysis workflow nodes in sequential order:
  START -> validate_input -> compare_skills -> analyze_skill_gaps -> validate_analysis -> END

Provides a compiled graph object and an async execution helper.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from app.workflows.state import (
    SkillAnalysisState,
    generate_execution_id,
    create_execution_event,
)
from app.workflows.skill_nodes import (
    validate_input,
    compare_skills,
    analyze_skill_gaps,
    validate_analysis,
)

logger = logging.getLogger("voxara-skill-workflows")


def build_skill_analysis_graph() -> CompiledStateGraph:
    """
    Constructs and compiles the StateGraph connecting skill analysis nodes:
      validate_input -> compare_skills -> analyze_skill_gaps -> validate_analysis
    """
    builder = StateGraph(SkillAnalysisState)

    # Register workflow nodes
    builder.add_node("validate_input", validate_input)
    builder.add_node("compare_skills", compare_skills)
    builder.add_node("analyze_skill_gaps", analyze_skill_gaps)
    builder.add_node("validate_analysis", validate_analysis)

    # Define sequential transitions
    builder.add_edge(START, "validate_input")
    builder.add_edge("validate_input", "compare_skills")
    builder.add_edge("compare_skills", "analyze_skill_gaps")
    builder.add_edge("analyze_skill_gaps", "validate_analysis")
    builder.add_edge("validate_analysis", END)

    return builder.compile()


# Global reusable compiled graph instance
skill_analysis_graph: CompiledStateGraph = build_skill_analysis_graph()


async def run_skill_analysis_workflow(
    existing_skills: List[str],
    required_skills: List[str],
    optional_context: Optional[str] = None,
    execution_id: Optional[str] = None,
) -> SkillAnalysisState:
    """
    Runs the compiled skill analysis workflow graph asynchronously with an isolated state.
    Handles any unexpected graph-level errors cleanly without crashing.

    Args:
        existing_skills: List of skills the candidate currently possesses.
        required_skills: List of skills required for the internship or role.
        optional_context: Optional additional details regarding role or goals.
        execution_id: Optional pre-generated execution ID.

    Returns:
        SkillAnalysisState containing execution status, results or error, and events.
    """
    exec_id = execution_id or generate_execution_id()

    # Initialize fresh state to prevent shared mutable state between requests
    initial_state: SkillAnalysisState = {
        "execution_id": exec_id,
        "existing_skills": existing_skills,
        "required_skills": required_skills,
        "optional_context": optional_context,
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

    try:
        final_state: SkillAnalysisState = await skill_analysis_graph.ainvoke(initial_state)
        return final_state
    except Exception as exc:
        logger.error(
            "Skill analysis graph execution failed for %s: %s",
            exec_id,
            exc,
            exc_info=True,
        )
        fallback_event = create_execution_event(
            execution_id=exec_id,
            node_name="skill_analysis_graph",
            event_type="node_error",
            status="failed",
            details={"error": str(exc)},
        )
        return {
            "execution_id": exec_id,
            "existing_skills": existing_skills,
            "required_skills": required_skills,
            "optional_context": optional_context,
            "status": "failed",
            "events": [fallback_event],
            "matched_skills": [],
            "missing_skills": [],
            "prioritized_missing_skills": [],
            "analysis": "",
            "recommended_next_steps": [],
            "raw_analysis": None,
            "error": f"Unhandled skill workflow execution failure: {str(exc)}",
        }
