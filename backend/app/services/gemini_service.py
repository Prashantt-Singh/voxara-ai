"""
Voxara AI - Gemini Text Generation Service (Step 4B: Skill Analysis Workflow)

This service isolates text generation and semantic reasoning powered by
Google's Gemini API (via the official google-genai SDK).
It is strictly distinct from the real-time audio pipeline used by LiveKit Agents.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger("voxara-gemini-service")


class GeminiServiceError(Exception):
    """Custom exception raised when Gemini text generation or parsing fails."""
    pass


def get_gemini_client(api_key: Optional[str] = None) -> genai.Client:
    """
    Instantiates a google.genai Client using the configured GOOGLE_API_KEY.
    Raises GeminiServiceError if the API key is missing or unconfigured.
    """
    key = api_key or settings.google_api_key
    if not key or "your_google" in key:
        raise GeminiServiceError(
            "GOOGLE_API_KEY is not configured in backend/.env. "
            "Please provide a valid Google Gemini API key."
        )
    return genai.Client(api_key=key)


def build_analysis_prompt(
    matched_skills: List[str],
    missing_skills: List[str],
    optional_context: Optional[str] = None,
) -> str:
    """
    Constructs an explicit prompt for Gemini to analyze the candidate's skill gaps.
    Enforces factual adherence to supplied data without hallucinations.
    """
    context_str = optional_context.strip() if optional_context and optional_context.strip() else "None provided"

    prompt = f"""You are an expert AI Career Mentor and Technical Evaluator.
Analyze the candidate's skills against the internship requirements provided below.

SUPPLIED DATA:
- Matched Skills (Candidate already has): {json.dumps(matched_skills)}
- Missing Skills (Candidate needs to learn): {json.dumps(missing_skills)}
- Role / Internship Context: {context_str}

STRICT INSTRUCTIONS:
1. Ground your response ONLY on the supplied skills and context above.
2. DO NOT invent or hallucinate candidate qualifications, job requirements, or past experiences that were not provided.
3. If no missing skills are identified (all requirements met), prioritized_missing_skills should be empty, and your analysis and recommended_next_steps should focus on deepening expertise and portfolio projects.
4. If missing skills are identified, rank them in prioritized_missing_skills from highest to lowest learning priority for this internship.
5. In 'analysis', clearly explain:
   - Which missing skills are most critical.
   - Why they matter for the specified internship.
   - If the supplied context is minimal or insufficient to rank skills reliably, explicitly state that limitation rather than inventing certainty.
6. In 'recommended_next_steps', provide 3 to 5 concrete, actionable learning objectives or practice tasks.
7. Return ONLY a valid JSON object matching this exact schema:
{{
  "prioritized_missing_skills": ["skill_1", "skill_2"],
  "analysis": "Detailed explanation of skill gaps and role relevance...",
  "recommended_next_steps": ["Action item 1", "Action item 2", "Action item 3"]
}}
"""
    return prompt


async def generate_skill_gap_analysis(
    matched_skills: List[str],
    missing_skills: List[str],
    optional_context: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    client: Optional[genai.Client] = None,
) -> Dict[str, Any]:
    """
    Calls Google Gemini asynchronously to generate structured skill gap analysis.

    Args:
        matched_skills: Skills possessed by candidate matching requirements.
        missing_skills: Required skills not possessed by candidate.
        optional_context: Optional additional details about the role or user goals.
        api_key: Optional API key override.
        model: Optional model ID override (defaults to settings.gemini_text_model).
        client: Optional pre-configured genai.Client instance (useful for mocking).

    Returns:
        Dict containing prioritized_missing_skills, analysis, and recommended_next_steps.

    Raises:
        GeminiServiceError: If API call fails, times out, or returns unparseable JSON.
    """
    genai_client = client or get_gemini_client(api_key=api_key)
    target_model = model or settings.gemini_text_model or "gemini-3.7-flash"

    prompt = build_analysis_prompt(
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        optional_context=optional_context,
    )

    logger.info("Calling Gemini (%s) for skill gap analysis...", target_model)

    max_retries = 2
    last_exc = None

    for attempt in range(max_retries):
        try:
            config = types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
            )
            response = await genai_client.aio.models.generate_content(
                model=target_model,
                contents=prompt,
                config=config,
            )

            response_text = response.text
            if not response_text or not response_text.strip():
                raise GeminiServiceError("Gemini returned an empty response.")

            logger.debug("Gemini raw response: %s", response_text)

            # Parse JSON output
            parsed_data = json.loads(response_text)
            if not isinstance(parsed_data, dict):
                raise GeminiServiceError("Gemini response is not a valid JSON object.")

            return parsed_data

        except json.JSONDecodeError as exc:
            logger.error("Failed to parse Gemini JSON output: %s", exc)
            raise GeminiServiceError(f"Malformed JSON returned by Gemini: {str(exc)}") from exc
        except GeminiServiceError:
            raise
        except Exception as exc:
            last_exc = exc
            err_str = str(exc)
            # If server error / 503 spike, wait briefly and retry once
            if "503" in err_str or "UNAVAILABLE" in err_str:
                if attempt < max_retries - 1:
                    logger.warning("Gemini 503 high demand spike encountered. Retrying in 2s...")
                    import asyncio
                    await asyncio.sleep(2.0)
                    continue
            logger.error("Error invoking Gemini text model: %s", exc, exc_info=True)
            raise GeminiServiceError(f"Gemini API invocation failed: {str(exc)}") from exc

    if last_exc:
        raise GeminiServiceError(f"Gemini API invocation failed: {str(last_exc)}") from last_exc

