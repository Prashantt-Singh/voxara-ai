"""
Voxara AI - Voice Agent Workflow Tools (Step 4C: LangGraph Voice Integration)

This module defines callable LiveKit Agent tools that connect the real-time
voice agent (Gemini Live) to compiled LangGraph workflows.

Key Architectural Decisions:
1. Tool-Based Invocation (Approach A): Preserves Gemini Live's sub-second audio duplex
   and interruption handling for ordinary conversation, while providing a clean,
   asynchronous bridge to LangGraph for multi-step task execution.
2. Demonstration Scope: The skill-analysis and demo workflows are explicitly marked
   as demonstration tools. Voxara is a general-purpose voice assistant and is NOT
   hardcoded solely for internship or skill analysis.
3. Reliability & Safety: All tools enforce strict input validation, timeouts,
   isolated workflow states, and error handling so that failures return clear spoken
   feedback without crashing the real-time audio session.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from livekit.agents import llm

from app.workflows.graph import run_workflow
from app.workflows.skill_graph import run_skill_analysis_workflow
from app.workflows.opportunity_graph import run_opportunity_hunter_workflow
from app.workflows.execution_store import execution_store

logger = logging.getLogger("voxara-agent-tools")

# Execution timeout in seconds to prevent blocking the voice agent
WORKFLOW_TIMEOUT_SECONDS = 30.0


@llm.function_tool(
    description=(
        "Demonstration task: Analyzes and compares a candidate's existing skills against "
        "the skills required for an internship or job role using the Gemini-powered LangGraph workflow. "
        "Use this tool ONLY when the user explicitly asks to evaluate, compare, or analyze skills "
        "or identify learning gaps. Do NOT call this tool for normal conversation, greetings, or questions "
        "unrelated to skill gap analysis."
    )
)
async def analyze_skills_demonstration(
    existing_skills: list[str],
    required_skills: list[str],
    optional_context: str = "",
) -> dict[str, Any]:
    """
    Executes the Gemini-powered skill analysis LangGraph workflow on behalf of the voice agent.

    Args:
        existing_skills: List of skills the candidate currently possesses.
        required_skills: List of skills required for the internship or role.
        optional_context: Optional context describing the role, goals, or domain.

    Returns:
        Structured dictionary containing status, matched skills, prioritized missing skills,
        next steps, and a spoken summary designed for natural voice synthesis.
    """
    logger.info(
        "Voice agent invoked 'analyze_skills_demonstration' with %d existing skills and %d required skills.",
        len(existing_skills) if isinstance(existing_skills, list) else 0,
        len(required_skills) if isinstance(required_skills, list) else 0,
    )

    # 1. Input Validation
    if not isinstance(existing_skills, list) or not existing_skills:
        return {
            "status": "failed",
            "error": "Existing skills must be provided as a non-empty list of skill names.",
            "summary_for_voice": (
                "I couldn't run the skill analysis because no existing skills were provided. "
                "Please tell me what skills you currently have, as well as the required skills."
            ),
        }

    if not isinstance(required_skills, list) or not required_skills:
        return {
            "status": "failed",
            "error": "Required skills must be provided as a non-empty list of skill names.",
            "summary_for_voice": (
                "I couldn't run the skill analysis because no required skills were specified. "
                "Please mention the skills needed for the role or internship."
            ),
        }

    # Clean and sanitize skill strings
    cleaned_existing = [s.strip() for s in existing_skills if isinstance(s, str) and s.strip()]
    cleaned_required = [s.strip() for s in required_skills if isinstance(s, str) and s.strip()]

    if not cleaned_existing or not cleaned_required:
        return {
            "status": "failed",
            "error": "Skill lists must contain valid, non-empty names.",
            "summary_for_voice": (
                "The skills provided were empty or unclear. Could you please repeat the skills?"
            ),
        }

    # 2. Asynchronous Execution with Timeout
    context_str = optional_context.strip() if optional_context else None

    try:
        final_state = await asyncio.wait_for(
            run_skill_analysis_workflow(
                existing_skills=cleaned_existing,
                required_skills=cleaned_required,
                optional_context=context_str,
            ),
            timeout=WORKFLOW_TIMEOUT_SECONDS,
        )

        # Record execution in shared observability store
        execution_store.save_execution(final_state)

        exec_id = final_state.get("execution_id", "unknown")
        status = final_state.get("status", "completed")

        if status == "failed":
            error_msg = final_state.get("error", "Unknown workflow failure")
            logger.warning("Skill analysis workflow failed for %s: %s", exec_id, error_msg)
            return {
                "status": "failed",
                "execution_id": exec_id,
                "error": error_msg,
                "summary_for_voice": (
                    "The skill analysis workflow encountered an issue while processing your skills. "
                    "Please verify your inputs and try again in a moment."
                ),
            }

        # 3. Format Structured Voice-Friendly Summary
        matched = final_state.get("matched_skills", [])
        missing = final_state.get("missing_skills", [])
        prioritized = final_state.get("prioritized_missing_skills", [])
        recommendations = final_state.get("recommended_next_steps", [])

        # Build a natural spoken summary
        voice_summary_parts = []
        if matched:
            voice_summary_parts.append(
                f"You already match on {len(matched)} skills: {', '.join(matched[:4])}."
            )
        else:
            voice_summary_parts.append("You don't currently match any of the required skills.")

        if missing:
            top_priority = prioritized[:2] if prioritized else missing[:2]
            voice_summary_parts.append(
                f"There are {len(missing)} missing skills to focus on, especially {', '.join(top_priority)}."
            )
        else:
            voice_summary_parts.append("Great job! You have all the required skills for this role.")

        if recommendations:
            voice_summary_parts.append(f"Recommended next step: {recommendations[0]}")

        summary_for_voice = " ".join(voice_summary_parts)

        return {
            "status": "completed",
            "execution_id": exec_id,
            "matched_skills": matched,
            "missing_skills": missing,
            "prioritized_missing_skills": prioritized,
            "recommended_next_steps": recommendations,
            "summary_for_voice": summary_for_voice,
            "analysis": final_state.get("analysis", ""),
        }

    except asyncio.TimeoutError:
        logger.error("Skill analysis workflow timed out after %.1fs", WORKFLOW_TIMEOUT_SECONDS)
        return {
            "status": "failed",
            "error": f"Workflow timed out after {WORKFLOW_TIMEOUT_SECONDS} seconds.",
            "summary_for_voice": (
                "The skill analysis workflow timed out while reasoning about the skills. "
                "Please try again or simplify the request."
            ),
        }
    except Exception as exc:
        logger.error("Unexpected error executing skill analysis workflow: %s", exc, exc_info=True)
        return {
            "status": "failed",
            "error": "Internal workflow execution error.",
            "summary_for_voice": (
                "I encountered an unexpected error while executing the skill analysis. "
                "Please try again shortly."
            ),
        }


@llm.function_tool(
    description=(
        "Demonstration task: Executes the general-purpose demonstration LangGraph workflow "
        "through sequential state transitions (receive_request -> validate_request -> produce_result). "
        "Use this tool ONLY when the user explicitly asks to run a workflow demonstration, "
        "test graph execution, or verify background task processing."
    )
)
async def run_demo_workflow(
    task: str,
    parameters_json: str = "{}",
) -> dict[str, Any]:
    """
    Executes the general demonstration LangGraph workflow on behalf of the voice agent.

    Args:
        task: Non-empty description of the task to process.
        parameters_json: Optional JSON string of task parameters.

    Returns:
        Structured dictionary containing status, result, and spoken summary.
    """
    logger.info("Voice agent invoked 'run_demo_workflow' with task: '%s'", task)

    # 1. Input Validation
    if not isinstance(task, str) or not task.strip():
        return {
            "status": "failed",
            "error": "Task description cannot be empty.",
            "summary_for_voice": "I couldn't run the demo workflow because no task was specified.",
        }

    cleaned_task = task.strip()
    parsed_inputs: Dict[str, Any] = {}
    if parameters_json and parameters_json.strip():
        try:
            parsed = json.loads(parameters_json)
            if isinstance(parsed, dict):
                parsed_inputs = parsed
        except Exception:
            logger.debug("parameters_json could not be parsed as JSON, passing as raw text parameter.")
            parsed_inputs = {"raw_parameters": parameters_json}

    # 2. Asynchronous Execution with Timeout
    try:
        final_state = await asyncio.wait_for(
            run_workflow(task=cleaned_task, input_data=parsed_inputs),
            timeout=WORKFLOW_TIMEOUT_SECONDS,
        )

        # Record execution in shared observability store
        execution_store.save_execution(final_state)

        exec_id = final_state.get("execution_id", "unknown")
        status = final_state.get("status", "completed")

        if status == "failed":
            error_msg = final_state.get("error", "Unknown demo workflow failure")
            return {
                "status": "failed",
                "execution_id": exec_id,
                "error": error_msg,
                "summary_for_voice": f"The demo workflow failed: {error_msg}.",
            }

        result = final_state.get("result", {})
        summary = (
            f"Demonstration workflow completed successfully. "
            f"Execution ID is {exec_id}. Result: {result.get('summary', 'Task finalized')}."
        )

        return {
            "status": "completed",
            "execution_id": exec_id,
            "task": cleaned_task,
            "result": result,
            "summary_for_voice": summary,
        }

    except asyncio.TimeoutError:
        logger.error("Demo workflow timed out after %.1fs", WORKFLOW_TIMEOUT_SECONDS)
        return {
            "status": "failed",
            "error": f"Workflow timed out after {WORKFLOW_TIMEOUT_SECONDS} seconds.",
            "summary_for_voice": "The demo workflow timed out before completing.",
        }
    except Exception as exc:
        logger.error("Unexpected error executing demo workflow: %s", exc, exc_info=True)
        return {
            "status": "failed",
            "error": "Internal workflow execution error.",
            "summary_for_voice": "I ran into an unexpected error running the demo workflow.",
        }


@llm.function_tool(
    description=(
        "Discovers verified internships, hackathons, and technology programs matching "
        "user preferences. Tracks submission deadlines and provides real opportunities. "
        "Use this tool when the user asks to find hackathons, internships, scholarships, "
        "or deadline reminders."
    )
)
async def hunt_opportunities_tool(
    query: str = "all",
    opportunity_type: str = "all",
) -> dict[str, Any]:
    """
    Executes the Opportunity Hunter LangGraph workflow on behalf of the voice agent.
    """
    logger.info("Voice agent invoked 'hunt_opportunities_tool' with query='%s', type='%s'", query, opportunity_type)

    try:
        final_state = await asyncio.wait_for(
            run_opportunity_hunter_workflow(
                query=query,
                opportunity_type=opportunity_type,
            ),
            timeout=WORKFLOW_TIMEOUT_SECONDS,
        )

        execution_store.save_execution(final_state)
        status = final_state.get("status", "completed")
        briefing = final_state.get("spoken_briefing") or "I completed the opportunity search."

        return {
            "status": status,
            "execution_id": final_state.get("execution_id"),
            "found_count": len(final_state.get("opportunities", [])),
            "opportunities": final_state.get("opportunities", [])[:3],
            "urgent_deadlines": final_state.get("urgent_deadlines", [])[:2],
            "summary_for_voice": briefing,
        }
    except asyncio.TimeoutError:
        logger.error("Opportunity Hunter workflow timed out.")
        return {
            "status": "failed",
            "error": "Workflow timed out.",
            "summary_for_voice": "The opportunity search timed out. Please try again with a narrower query.",
        }
    except Exception as exc:
        logger.error("Error executing Opportunity Hunter: %s", exc, exc_info=True)
        return {
            "status": "failed",
            "error": str(exc),
            "summary_for_voice": "I encountered an error while searching for opportunities.",
        }


# List of tools to register with the LiveKit voice agent
VOICE_AGENT_TOOLS = [
    hunt_opportunities_tool,
    analyze_skills_demonstration,
    run_demo_workflow,
]
