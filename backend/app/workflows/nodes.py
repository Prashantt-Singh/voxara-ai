"""
Voxara AI - Workflow Nodes (Step 4A: Agentic Workflow Foundation)

This module implements focused, discrete workflow nodes for LangGraph.
Nodes execute real logic, generate concrete start and finish events with
real durations, and handle validation or execution errors without crashing.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.workflows.state import WorkflowState, create_execution_event

logger = logging.getLogger("voxara-workflows")


def receive_request(state: WorkflowState) -> Dict[str, Any]:
    """
    Node 1: receive_request
    Captures incoming task parameters, initializes execution context,
    and logs start/finish events.
    """
    node_name = "receive_request"
    execution_id = state.get("execution_id", "unknown")
    start_time = time.perf_counter()

    start_event = create_execution_event(
        execution_id=execution_id,
        node_name=node_name,
        event_type="node_start",
        status="started",
        details={"message": "Received workflow execution request"},
    )

    try:
        raw_task = state.get("task", "")
        task = raw_task.strip() if isinstance(raw_task, str) else str(raw_task)
        input_data = state.get("input_data")
        if not isinstance(input_data, dict):
            input_data = {}

        elapsed = time.perf_counter() - start_time
        finish_event = create_execution_event(
            execution_id=execution_id,
            node_name=node_name,
            event_type="node_finish",
            status="completed",
            duration=elapsed,
            details={"task_length": len(task), "input_keys": list(input_data.keys())},
        )

        return {
            "task": task,
            "input_data": input_data,
            "status": "running",
            "events": [start_event, finish_event],
        }

    except Exception as exc:
        logger.error("Error in receive_request node: %s", exc, exc_info=True)
        elapsed = time.perf_counter() - start_time
        error_event = create_execution_event(
            execution_id=execution_id,
            node_name=node_name,
            event_type="node_error",
            status="failed",
            duration=elapsed,
            details={"error": str(exc)},
        )
        return {
            "status": "failed",
            "error": f"Failed to receive request: {str(exc)}",
            "events": [start_event, error_event],
        }


def validate_request(state: WorkflowState) -> Dict[str, Any]:
    """
    Node 2: validate_request
    Validates task description and input data structure.
    Catches invalid or missing parameters, setting error state cleanly.
    """
    node_name = "validate_request"
    execution_id = state.get("execution_id", "unknown")
    start_time = time.perf_counter()

    start_event = create_execution_event(
        execution_id=execution_id,
        node_name=node_name,
        event_type="node_start",
        status="started",
        details={"message": "Validating request parameters"},
    )

    try:
        task = state.get("task", "")
        input_data = state.get("input_data", {})

        # Validation rules:
        validation_error: str | None = None

        if not task or not task.strip():
            validation_error = "Validation error: Task description cannot be missing or empty."
        elif not isinstance(input_data, dict):
            validation_error = "Validation error: Input data must be a valid key-value mapping."
        elif task == "simulate_validation_error" or input_data.get("simulate_validation_error"):
            validation_error = "Validation error: Simulated validation failure requested."

        elapsed = time.perf_counter() - start_time

        if validation_error:
            logger.warning("Workflow validation failed for %s: %s", execution_id, validation_error)
            error_event = create_execution_event(
                execution_id=execution_id,
                node_name=node_name,
                event_type="node_error",
                status="failed",
                duration=elapsed,
                details={"error": validation_error},
            )
            return {
                "status": "failed",
                "error": validation_error,
                "events": [start_event, error_event],
            }

        finish_event = create_execution_event(
            execution_id=execution_id,
            node_name=node_name,
            event_type="node_finish",
            status="completed",
            duration=elapsed,
            details={"message": "Request validation passed successfully"},
        )

        return {
            "events": [start_event, finish_event],
        }

    except Exception as exc:
        logger.error("Error in validate_request node: %s", exc, exc_info=True)
        elapsed = time.perf_counter() - start_time
        error_event = create_execution_event(
            execution_id=execution_id,
            node_name=node_name,
            event_type="node_error",
            status="failed",
            duration=elapsed,
            details={"error": str(exc)},
        )
        return {
            "status": "failed",
            "error": f"Unexpected error during validation: {str(exc)}",
            "events": [start_event, error_event],
        }


def produce_result(state: WorkflowState) -> Dict[str, Any]:
    """
    Node 3: produce_result
    Produces the structured workflow outcome or handles prior errors gracefully.
    Demonstrates actual graph execution output without mock delays.
    """
    node_name = "produce_result"
    execution_id = state.get("execution_id", "unknown")
    start_time = time.perf_counter()

    start_event = create_execution_event(
        execution_id=execution_id,
        node_name=node_name,
        event_type="node_start",
        status="started",
        details={"message": "Producing workflow demonstration result"},
    )

    try:
        # Check if a prior node already flagged an error
        if state.get("status") == "failed" or state.get("error"):
            elapsed = time.perf_counter() - start_time
            finish_event = create_execution_event(
                execution_id=execution_id,
                node_name=node_name,
                event_type="node_finish",
                status="skipped",
                duration=elapsed,
                details={"reason": "Skipped result production due to prior validation error"},
            )
            return {
                "events": [start_event, finish_event],
            }

        task = state.get("task", "")
        input_data = state.get("input_data", {})

        # Check for simulated execution error hook
        if task == "simulate_execution_error" or input_data.get("simulate_error"):
            elapsed = time.perf_counter() - start_time
            error_message = "Workflow execution error: Simulated node failure in produce_result."
            error_event = create_execution_event(
                execution_id=execution_id,
                node_name=node_name,
                event_type="node_error",
                status="failed",
                duration=elapsed,
                details={"error": error_message},
            )
            return {
                "status": "failed",
                "error": error_message,
                "events": [start_event, error_event],
            }

        # Produce real demonstration result
        result_payload = {
            "execution_id": execution_id,
            "task": task,
            "summary": f"Completed workflow demonstration for task: '{task}'",
            "received_input": input_data,
            "execution_steps": ["receive_request", "validate_request", "produce_result"],
            "step_count": 3,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        elapsed = time.perf_counter() - start_time
        finish_event = create_execution_event(
            execution_id=execution_id,
            node_name=node_name,
            event_type="node_finish",
            status="completed",
            duration=elapsed,
            details={"step_count": 3},
        )

        return {
            "status": "completed",
            "result": result_payload,
            "events": [start_event, finish_event],
        }

    except Exception as exc:
        logger.error("Error in produce_result node: %s", exc, exc_info=True)
        elapsed = time.perf_counter() - start_time
        error_event = create_execution_event(
            execution_id=execution_id,
            node_name=node_name,
            event_type="node_error",
            status="failed",
            duration=elapsed,
            details={"error": str(exc)},
        )
        return {
            "status": "failed",
            "error": f"Failed to produce workflow result: {str(exc)}",
            "events": [start_event, error_event],
        }
