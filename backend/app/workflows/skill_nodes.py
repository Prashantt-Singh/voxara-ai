"""
Voxara AI - Skill Analysis Workflow Nodes (Step 4B: Gemini-Powered Skill Analysis)

This module implements discrete, observable workflow nodes for the LangGraph
skill analysis pipeline:
  START -> validate_input -> compare_skills -> analyze_skill_gaps -> validate_analysis -> END

Each node:
1. Emits real start and finish/error execution events with accurate durations.
2. Performs its dedicated responsibility (validation, deterministic comparison,
   Gemini semantic reasoning, or output schema validation).
3. Handles errors gracefully without uncaught exceptions or server crashes.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Set
from app.workflows.state import SkillAnalysisState, create_execution_event
from app.services.gemini_service import generate_skill_gap_analysis, GeminiServiceError

logger = logging.getLogger("voxara-skill-nodes")


def validate_input(state: SkillAnalysisState) -> Dict[str, Any]:
    """
    Node 1: validate_input
    Validates that existing_skills and required_skills are non-empty lists of strings.
    Trims surrounding whitespace and rejects empty or malformed inputs cleanly.
    """
    node_name = "validate_input"
    execution_id = state.get("execution_id", "unknown")
    start_time = time.perf_counter()

    start_event = create_execution_event(
        execution_id=execution_id,
        node_name=node_name,
        event_type="node_start",
        status="started",
        details={"message": "Validating input skills and parameters"},
    )

    try:
        existing = state.get("existing_skills")
        required = state.get("required_skills")

        # Check types
        if not isinstance(existing, list) or not isinstance(required, list):
            err_msg = "Validation error: Both 'existing_skills' and 'required_skills' must be lists."
            elapsed = time.perf_counter() - start_time
            error_event = create_execution_event(
                execution_id=execution_id,
                node_name=node_name,
                event_type="node_error",
                status="failed",
                duration=elapsed,
                details={"error": err_msg},
            )
            return {
                "status": "failed",
                "error": err_msg,
                "events": [start_event, error_event],
            }

        # Normalize and filter whitespace
        cleaned_existing = [s.strip() for s in existing if isinstance(s, str) and s.strip()]
        cleaned_required = [s.strip() for s in required if isinstance(s, str) and s.strip()]

        if not cleaned_existing:
            err_msg = "Validation error: 'existing_skills' cannot be empty or contain only blank items."
            elapsed = time.perf_counter() - start_time
            error_event = create_execution_event(
                execution_id=execution_id,
                node_name=node_name,
                event_type="node_error",
                status="failed",
                duration=elapsed,
                details={"error": err_msg},
            )
            return {
                "status": "failed",
                "error": err_msg,
                "events": [start_event, error_event],
            }

        if not cleaned_required:
            err_msg = "Validation error: 'required_skills' cannot be empty or contain only blank items."
            elapsed = time.perf_counter() - start_time
            error_event = create_execution_event(
                execution_id=execution_id,
                node_name=node_name,
                event_type="node_error",
                status="failed",
                duration=elapsed,
                details={"error": err_msg},
            )
            return {
                "status": "failed",
                "error": err_msg,
                "events": [start_event, error_event],
            }

        elapsed = time.perf_counter() - start_time
        finish_event = create_execution_event(
            execution_id=execution_id,
            node_name=node_name,
            event_type="node_finish",
            status="completed",
            duration=elapsed,
            details={
                "existing_skills_count": len(cleaned_existing),
                "required_skills_count": len(cleaned_required),
            },
        )

        return {
            "status": "running",
            "existing_skills": cleaned_existing,
            "required_skills": cleaned_required,
            "events": [start_event, finish_event],
        }

    except Exception as exc:
        logger.error("Unexpected error in validate_input node: %s", exc, exc_info=True)
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
            "error": f"Input validation failed unexpectedly: {str(exc)}",
            "events": [start_event, error_event],
        }


def compare_skills(state: SkillAnalysisState) -> Dict[str, Any]:
    """
    Node 2: compare_skills
    Deterministic Python comparison of existing skills vs required skills.
    Normalizes case and surrounding whitespace. Identifies matched and missing skills.
    Does NOT rely on Gemini for this deterministic set math.
    """
    node_name = "compare_skills"
    execution_id = state.get("execution_id", "unknown")
    start_time = time.perf_counter()

    start_event = create_execution_event(
        execution_id=execution_id,
        node_name=node_name,
        event_type="node_start",
        status="started",
        details={"message": "Comparing candidate skills with required skills"},
    )

    try:
        # Check if a previous node failed
        if state.get("status") == "failed" or state.get("error"):
            elapsed = time.perf_counter() - start_time
            finish_event = create_execution_event(
                execution_id=execution_id,
                node_name=node_name,
                event_type="node_finish",
                status="skipped",
                duration=elapsed,
                details={"reason": "Skipped due to prior failure"},
            )
            return {"events": [start_event, finish_event]}

        existing = state.get("existing_skills", [])
        required = state.get("required_skills", [])

        # Create lookup map of normalized -> canonical for existing skills
        # Normalization: strip whitespace and lowercase
        normalized_existing: Dict[str, str] = {s.strip().lower(): s.strip() for s in existing}

        matched_skills: List[str] = []
        missing_skills: List[str] = []
        seen_matched_norm: Set[str] = set()
        seen_missing_norm: Set[str] = set()

        for req_skill in required:
            clean_req = req_skill.strip()
            norm_req = clean_req.lower()

            if norm_req in normalized_existing:
                if norm_req not in seen_matched_norm:
                    # Preserve canonical naming from existing skills if possible, or required
                    matched_skills.append(clean_req)
                    seen_matched_norm.add(norm_req)
            else:
                if norm_req not in seen_missing_norm:
                    missing_skills.append(clean_req)
                    seen_missing_norm.add(norm_req)

        elapsed = time.perf_counter() - start_time
        finish_event = create_execution_event(
            execution_id=execution_id,
            node_name=node_name,
            event_type="node_finish",
            status="completed",
            duration=elapsed,
            details={
                "matched_count": len(matched_skills),
                "missing_count": len(missing_skills),
            },
        )

        return {
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "events": [start_event, finish_event],
        }

    except Exception as exc:
        logger.error("Error in compare_skills node: %s", exc, exc_info=True)
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
            "error": f"Skill comparison failed: {str(exc)}",
            "events": [start_event, error_event],
        }


async def analyze_skill_gaps(state: SkillAnalysisState) -> Dict[str, Any]:
    """
    Node 3: analyze_skill_gaps
    Asynchronously invokes Google Gemini to produce semantic gap analysis:
    - Prioritizing missing skills for the internship.
    - Contextual explanation of why missing skills matter.
    - Practical, actionable next steps.
    """
    node_name = "analyze_skill_gaps"
    execution_id = state.get("execution_id", "unknown")
    start_time = time.perf_counter()

    start_event = create_execution_event(
        execution_id=execution_id,
        node_name=node_name,
        event_type="node_start",
        status="started",
        details={"message": "Invoking Gemini model for skill gap analysis"},
    )

    try:
        # Check if a previous node failed
        if state.get("status") == "failed" or state.get("error"):
            elapsed = time.perf_counter() - start_time
            finish_event = create_execution_event(
                execution_id=execution_id,
                node_name=node_name,
                event_type="node_finish",
                status="skipped",
                duration=elapsed,
                details={"reason": "Skipped due to prior failure"},
            )
            return {"events": [start_event, finish_event]}

        matched = state.get("matched_skills", [])
        missing = state.get("missing_skills", [])
        context = state.get("optional_context")

        # Invoke Gemini service
        gemini_result = await generate_skill_gap_analysis(
            matched_skills=matched,
            missing_skills=missing,
            optional_context=context,
        )

        elapsed = time.perf_counter() - start_time
        finish_event = create_execution_event(
            execution_id=execution_id,
            node_name=node_name,
            event_type="node_finish",
            status="completed",
            duration=elapsed,
            details={"message": "Gemini gap analysis generated successfully"},
        )

        return {
            "raw_analysis": gemini_result,
            "events": [start_event, finish_event],
        }

    except GeminiServiceError as exc:
        logger.error("GeminiServiceError in analyze_skill_gaps: %s", exc)
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
            "error": f"Gemini analysis error: {str(exc)}",
            "events": [start_event, error_event],
        }
    except Exception as exc:
        logger.error("Unexpected error in analyze_skill_gaps: %s", exc, exc_info=True)
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
            "error": f"Failed to execute Gemini analysis: {str(exc)}",
            "events": [start_event, error_event],
        }


def validate_analysis(state: SkillAnalysisState) -> Dict[str, Any]:
    """
    Node 4: validate_analysis
    Validates the structure and content of the analysis output before returning:
    - prioritized_missing_skills: must be a list of strings.
    - analysis: must be a non-empty string.
    - recommended_next_steps: must be a list of non-empty strings.
    Catches malformed output and sets status='failed' cleanly.
    """
    node_name = "validate_analysis"
    execution_id = state.get("execution_id", "unknown")
    start_time = time.perf_counter()

    start_event = create_execution_event(
        execution_id=execution_id,
        node_name=node_name,
        event_type="node_start",
        status="started",
        details={"message": "Validating Gemini analysis structure and schema"},
    )

    try:
        # Check if a previous node failed
        if state.get("status") == "failed" or state.get("error"):
            elapsed = time.perf_counter() - start_time
            finish_event = create_execution_event(
                execution_id=execution_id,
                node_name=node_name,
                event_type="node_finish",
                status="skipped",
                duration=elapsed,
                details={"reason": "Skipped due to prior failure"},
            )
            return {"events": [start_event, finish_event]}

        raw = state.get("raw_analysis")
        if not isinstance(raw, dict):
            err_msg = "Validation error: Gemini output is not a structured dictionary."
            elapsed = time.perf_counter() - start_time
            error_event = create_execution_event(
                execution_id=execution_id,
                node_name=node_name,
                event_type="node_error",
                status="failed",
                duration=elapsed,
                details={"error": err_msg},
            )
            return {
                "status": "failed",
                "error": err_msg,
                "events": [start_event, error_event],
            }

        # Check fields
        prioritized = raw.get("prioritized_missing_skills")
        analysis = raw.get("analysis")
        next_steps = raw.get("recommended_next_steps")

        validation_errors: List[str] = []

        if not isinstance(prioritized, list):
            validation_errors.append("'prioritized_missing_skills' must be a list of strings.")
        elif any(not isinstance(s, str) for s in prioritized):
            validation_errors.append("All items in 'prioritized_missing_skills' must be strings.")

        if not isinstance(analysis, str) or not analysis.strip():
            validation_errors.append("'analysis' must be a non-empty string.")

        if not isinstance(next_steps, list) or len(next_steps) == 0:
            validation_errors.append("'recommended_next_steps' must be a non-empty list of actionable steps.")
        elif any(not isinstance(s, str) or not s.strip() for s in next_steps):
            validation_errors.append("All items in 'recommended_next_steps' must be non-empty strings.")

        elapsed = time.perf_counter() - start_time

        if validation_errors:
            full_err = "Output validation failed: " + "; ".join(validation_errors)
            logger.warning("Output validation failed for %s: %s", execution_id, full_err)
            error_event = create_execution_event(
                execution_id=execution_id,
                node_name=node_name,
                event_type="node_error",
                status="failed",
                duration=elapsed,
                details={"error": full_err},
            )
            return {
                "status": "failed",
                "error": full_err,
                "events": [start_event, error_event],
            }

        finish_event = create_execution_event(
            execution_id=execution_id,
            node_name=node_name,
            event_type="node_finish",
            status="completed",
            duration=elapsed,
            details={"message": "Analysis schema validation passed successfully"},
        )

        return {
            "status": "completed",
            "prioritized_missing_skills": [s.strip() for s in prioritized],
            "analysis": analysis.strip(),
            "recommended_next_steps": [s.strip() for s in next_steps],
            "events": [start_event, finish_event],
        }

    except Exception as exc:
        logger.error("Error in validate_analysis node: %s", exc, exc_info=True)
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
            "error": f"Failed to validate analysis structure: {str(exc)}",
            "events": [start_event, error_event],
        }
