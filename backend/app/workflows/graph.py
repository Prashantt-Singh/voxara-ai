"""
Voxara AI - Workflow Graph Orchestration (Step 4A: Agentic Workflow Foundation)

This module builds and compiles the LangGraph StateGraph connecting
the workflow nodes in sequential order:
  START -> receive_request -> validate_request -> produce_result -> END

Provides a compiled graph object and an async execution helper.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from app.workflows.state import (
    WorkflowState,
    generate_execution_id,
    create_execution_event,
)
from app.workflows.nodes import (
    receive_request,
    validate_request,
    produce_result,
)

logger = logging.getLogger("voxara-workflows")


def build_workflow_graph() -> CompiledStateGraph:
    """
    Constructs and compiles the StateGraph connecting nodes:
      receive_request -> validate_request -> produce_result
    """
    builder = StateGraph(WorkflowState)

    # Register workflow nodes
    builder.add_node("receive_request", receive_request)
    builder.add_node("validate_request", validate_request)
    builder.add_node("produce_result", produce_result)

    # Define sequential transitions
    builder.add_edge(START, "receive_request")
    builder.add_edge("receive_request", "validate_request")
    builder.add_edge("validate_request", "produce_result")
    builder.add_edge("produce_result", END)

    # Compile reusable graph instance
    return builder.compile()


# Global reusable compiled graph instance
workflow_graph: CompiledStateGraph = build_workflow_graph()


async def run_workflow(
    task: str,
    input_data: Optional[Dict[str, Any]] = None,
    execution_id: Optional[str] = None,
) -> WorkflowState:
    """
    Runs the compiled workflow graph asynchronously with an isolated state.
    Handles any unexpected graph-level errors cleanly without crashing.

    Args:
        task: Description of the task to execute.
        input_data: Optional dictionary of parameters/inputs.
        execution_id: Optional pre-generated execution ID.

    Returns:
        WorkflowState containing execution status, result or error, and events.
    """
    exec_id = execution_id or generate_execution_id()
    inputs = input_data if input_data is not None else {}

    # Initialize fresh state to prevent shared mutable state between requests
    initial_state: WorkflowState = {
        "execution_id": exec_id,
        "task": task,
        "input_data": inputs,
        "status": "pending",
        "events": [],
        "intermediate_results": {},
        "result": None,
        "error": None,
    }

    try:
        final_state: WorkflowState = await workflow_graph.ainvoke(initial_state)
        return final_state
    except Exception as exc:
        logger.error("Workflow graph execution failed for %s: %s", exec_id, exc, exc_info=True)
        fallback_event = create_execution_event(
            execution_id=exec_id,
            node_name="workflow_graph",
            event_type="node_error",
            status="failed",
            details={"error": str(exc)},
        )
        return {
            "execution_id": exec_id,
            "task": task,
            "input_data": inputs,
            "status": "failed",
            "events": [fallback_event],
            "intermediate_results": {},
            "result": None,
            "error": f"Unhandled workflow execution failure: {str(exc)}",
        }
