"""
Voxara AI - Personalized Opportunity Matching Service (Phase 4)

A modular, transparent, rule-based matching and ranking engine that:
1. Category Filtering:
   - Filters opportunities by requested categories (internships, hackathons, fellowships).
2. Domain & Interest Matching:
   - Compares candidate interests, domains, target roles, and skills against
     opportunity titles, descriptions, and tag requirements.
   - Recognizes canonical aliases for Android, Web Development, AI/ML, Generative AI, Systems, etc.
3. Location & Remote Consideration:
   - Evaluates remote availability and preferred geographic locations.
   - Strictly enforces remote-only criteria when specified.
4. Eligibility Evaluation:
   - Assesses candidate eligibility against published opportunity criteria without fabricating eligibility.
   - Explicitly communicates 'unspecified' when source information is missing.
5. Expiry & Deadline Handling:
   - Discards expired opportunities by default; supports rolling deadlines where dates are omitted.
6. Verification Status & Uncertainty Communication:
   - Calibrates match confidence using verification status and communicates uncertainty transparently.
7. Multi-User Isolation:
   - Scopes all preference retrieval and matching evaluations strictly to the individual user.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.db import repository
from app.db.models import (
    OpportunityMatchResult,
    OpportunityModel,
    UserPreferenceRead,
    UserPreferencesModel,
)
from app.db.tables import Opportunity, UserPreference

logger = logging.getLogger("voxara-matching-service")

# Canonical domain synonyms and keyword expansions
DOMAIN_VOCABULARY: Dict[str, List[str]] = {
    "android": [
        "android",
        "kotlin",
        "jetpack compose",
        "android sdk",
        "mobile",
        "java",
    ],
    "web development": [
        "web",
        "web development",
        "frontend",
        "backend",
        "full stack",
        "fullstack",
        "react",
        "next.js",
        "vue",
        "angular",
        "javascript",
        "typescript",
        "node",
        "html/css",
        "css",
        "django",
        "fastapi",
        "express",
    ],
    "ai/ml": [
        "ai",
        "ml",
        "ai/ml",
        "machine learning",
        "deep learning",
        "artificial intelligence",
        "neural",
        "nlp",
        "computer vision",
        "data science",
        "pytorch",
        "tensorflow",
        "scikit-learn",
    ],
    "generative ai": [
        "generative ai",
        "genai",
        "llm",
        "large language model",
        "transformer",
        "diffusion",
        "rag",
        "retrieval-augmented generation",
        "langchain",
        "agentic",
        "agents",
        "prompt engineering",
        "hugging face",
    ],
    "systems": [
        "systems",
        "c++",
        "rust",
        "go",
        "golang",
        "distributed systems",
        "operating systems",
        "networking",
        "linux",
        "concurrency",
        "low level",
    ],
    "cloud / devops": [
        "cloud",
        "aws",
        "gcp",
        "azure",
        "docker",
        "kubernetes",
        "devops",
        "ci/cd",
        "infrastructure",
    ],
}

CATEGORY_ALIASES: Dict[str, str] = {
    "internship": "internship",
    "internships": "internship",
    "hackathon": "hackathon",
    "hackathons": "hackathon",
    "fellowship": "fellowship",
    "fellowships": "fellowship",
    "program": "fellowship",
    "programs": "fellowship",
}

REMOTE_KEYWORDS: Set[str] = {
    "remote",
    "online",
    "virtual",
    "anywhere",
    "worldwide",
    "work from home",
    "wfh",
}


def normalize_category(cat: Optional[str]) -> Optional[str]:
    """Normalizes plural or alias category names to canonical singular type."""
    if not cat:
        return None
    cleaned = cat.strip().lower()
    return CATEGORY_ALIASES.get(cleaned, cleaned)


def is_remote_location(location_str: Optional[str], description: Optional[str] = None) -> bool:
    """Determines if an opportunity supports remote participation."""
    loc_clean = (location_str or "").lower()
    desc_clean = (description or "").lower()

    for kw in REMOTE_KEYWORDS:
        if kw in loc_clean:
            return True
        if f"location: {kw}" in desc_clean or f"mode: {kw}" in desc_clean:
            return True

    return False


class OpportunityMatchingService:
    """
    Reusable matching engine for calculating transparent, rule-based candidate
    fit against internships, hackathons, and fellowship opportunities.
    """

    def _expand_interest_keywords(self, interest: str) -> List[str]:
        """Expands an interest or domain into matching search terms."""
        clean = interest.strip().lower()
        terms = [clean]
        for canonical, synonyms in DOMAIN_VOCABULARY.items():
            if clean == canonical or clean in synonyms or any(s in clean for s in synonyms):
                for s in synonyms:
                    if s not in terms:
                        terms.append(s)
        return terms

    def _evaluate_domain_match(
        self,
        user_domains: List[str],
        user_roles: List[str],
        user_skills: List[str],
        title: str,
        requirements: List[str],
        description: str,
    ) -> Tuple[float, List[str]]:
        """
        Calculates domain and interest overlap between candidate profile and opportunity.
        Returns (score between 0.0 and 1.0, list of human-readable match reasons).
        """
        all_interests = list(dict.fromkeys(user_domains + user_roles + user_skills))
        if not all_interests:
            return 0.5, ["No specific technical interests configured (broad match)"]

        title_lower = title.lower()
        reqs_lower = " ".join(requirements).lower()
        desc_lower = description.lower()

        matched_reasons: List[str] = []
        domain_hits = 0
        total_possible = len(all_interests)

        # Track which distinct interests had hits
        for item in all_interests:
            keywords = self._expand_interest_keywords(item)
            hit_in_title = any(kw in title_lower for kw in keywords)
            hit_in_reqs = any(kw in reqs_lower for kw in keywords)
            hit_in_desc = any(kw in desc_lower for kw in keywords)

            if hit_in_title:
                domain_hits += 1.0
                matched_reasons.append(f"Domain/Skill '{item}' matches title")
            elif hit_in_reqs:
                domain_hits += 0.8
                matched_reasons.append(f"Domain/Skill '{item}' matches requirements")
            elif hit_in_desc:
                domain_hits += 0.5
                matched_reasons.append(f"Domain/Skill '{item}' found in description")

        # Normalized domain score (bounded 0.0 to 1.0)
        raw_ratio = domain_hits / max(1, total_possible)
        # Give higher weight if at least one strong keyword matched title or reqs
        if any("matches title" in r or "matches requirements" in r for r in matched_reasons):
            score = min(1.0, max(0.4, raw_ratio + 0.3))
        elif matched_reasons:
            score = min(1.0, max(0.25, raw_ratio))
        else:
            score = 0.0

        return round(score, 2), matched_reasons

    def _evaluate_location_match(
        self,
        remote_only: bool,
        preferred_locations: List[str],
        opp_location: Optional[str],
        opp_desc: str,
    ) -> Tuple[float, bool, str]:
        """
        Evaluates location and remote status.
        Returns (location_score: float, is_remote: bool, location_explanation: str).
        """
        is_remote = is_remote_location(opp_location, opp_desc)
        loc_str = (opp_location or "").strip()

        # Case 1: Candidate strictly requires remote
        if remote_only:
            if is_remote:
                return 1.0, True, "Matches remote opportunity preference"
            elif not loc_str:
                return 0.3, False, "Location unspecified in source listing; remote status unconfirmed"
            else:
                return 0.0, False, f"On-site listing ({loc_str}); does not meet remote requirement"

        # Case 2: Candidate has specific preferred geographic locations
        if preferred_locations:
            clean_prefs = [p.strip().lower() for p in preferred_locations if p.strip()]
            loc_lower = loc_str.lower()

            if any(p in loc_lower for p in clean_prefs):
                return 1.0, is_remote, f"Location matches preferred: {loc_str}"

            if is_remote and any("remote" in p for p in clean_prefs):
                return 1.0, True, "Remote listing matches preferred remote location"

            if is_remote:
                return 0.85, True, f"Remote opportunity ({loc_str or 'Flexible'})"

            if not loc_str:
                return 0.5, False, "Location unspecified in source listing"

            return 0.2, False, f"Location ({loc_str}) differs from preferred locations"

        # Case 3: No specific location constraints
        if is_remote:
            return 1.0, True, f"Remote opportunity ({loc_str or 'Online'})"
        elif loc_str:
            return 1.0, False, f"Location: {loc_str}"
        else:
            return 0.8, False, "Location not specified by listing"

    def _evaluate_eligibility(
        self,
        opp_eligibility: Optional[str],
        education_level: Optional[str],
        graduation_year: Optional[int],
        eligibility_context: Dict[str, Any],
    ) -> Tuple[str, Optional[str], float]:
        """
        Evaluates eligibility transparently.
        CRITICAL RULE: Never claim candidate is eligible when available info is insufficient.
        Returns: (eligibility_status: 'eligible'|'ineligible'|'unspecified', explanation: str, score_factor: float).
        """
        if not opp_eligibility or not opp_eligibility.strip():
            return (
                "unspecified",
                "Eligibility requirements not published by source listing. Review criteria prior to application.",
                0.85,
            )

        elig_clean = opp_eligibility.strip()
        elig_lower = elig_clean.lower()

        # Check universal open criteria
        open_patterns = [
            "open to all developers",
            "open to all",
            "aged 18+",
            "18+ worldwide",
            "open to anyone",
            "global participation",
        ]
        if any(pat in elig_lower for pat in open_patterns):
            return "eligible", f"Verified open eligibility: {elig_clean}", 1.0

        # Education degree checks
        has_degree_req = any(term in elig_lower for term in ["undergraduate", "bachelor", "master", "phd", "student"])
        if has_degree_req:
            if education_level:
                edu_clean = education_level.strip().lower()
                if "undergraduate" in elig_lower and ("undergrad" in edu_clean or "bachelor" in edu_clean):
                    return "eligible", f"Education profile ({education_level}) aligns with requirement: {elig_clean}", 1.0
                elif "master" in elig_lower and ("master" in edu_clean or "graduate" in edu_clean):
                    return "eligible", f"Education profile ({education_level}) aligns with requirement: {elig_clean}", 1.0
                elif "student" in elig_lower and ("student" in edu_clean or "undergrad" in edu_clean or "master" in edu_clean):
                    return "eligible", f"Student profile ({education_level}) aligns with requirement: {elig_clean}", 1.0
                elif "phd" in elig_lower and ("bachelor" in edu_clean or "high school" in edu_clean):
                    return "ineligible", f"Requires advanced doctoral standing; profile indicates {education_level}.", 0.1
                else:
                    return (
                        "unspecified",
                        f"Listing specifies degree requirements ('{elig_clean}'). Verify individual program standing.",
                        0.75,
                    )
            else:
                return (
                    "unspecified",
                    f"Listing specifies criteria: '{elig_clean}'. Candidate education profile is incomplete.",
                    0.75,
                )

        # Default when eligibility criteria text exists but cannot be proven automatically
        return (
            "unspecified",
            f"Listing specifies eligibility criteria: '{elig_clean}'. Review source requirements before applying.",
            0.80,
        )

    def match_opportunity(
        self,
        opp: Opportunity | OpportunityModel,
        preferences: UserPreference | UserPreferenceRead | UserPreferencesModel | Dict[str, Any],
        category_filter: Optional[str] = None,
        include_expired: bool = False,
    ) -> Optional[OpportunityMatchResult]:
        """
        Evaluates a single opportunity against candidate preferences.
        Returns OpportunityMatchResult or None if filtered out.
        """
        now_utc = datetime.now(timezone.utc)

        # 1. Deadline & Expired check
        opp_deadline = getattr(opp, "deadline", None)
        deadline_dt: Optional[datetime] = None
        if isinstance(opp_deadline, str):
            try:
                deadline_dt = datetime.fromisoformat(opp_deadline.replace("Z", "+00:00"))
            except Exception:
                deadline_dt = None
        elif isinstance(opp_deadline, datetime):
            deadline_dt = opp_deadline

        if deadline_dt is not None and deadline_dt.tzinfo is None:
            deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)

        is_expired = deadline_dt is not None and deadline_dt < now_utc
        if is_expired and not include_expired:
            return None

        # 2. Extract candidate preferences safely
        def _get_pref(key: str, default: Any = None) -> Any:
            if isinstance(preferences, dict):
                return preferences.get(key, default)
            return getattr(preferences, key, default)

        pref_types: List[str] = (
            _get_pref("preferred_types")
            or _get_pref("opportunity_types")
            or ["internship", "hackathon", "fellowship"]
        )
        pref_domains: List[str] = _get_pref("domains") or []
        pref_roles: List[str] = _get_pref("target_roles") or _get_pref("roles") or []
        pref_locations: List[str] = _get_pref("preferred_locations") or []
        remote_only: bool = bool(_get_pref("remote_only", False))
        skills: List[str] = _get_pref("skills") or []
        education_level: Optional[str] = _get_pref("education_level")
        graduation_year: Optional[int] = _get_pref("graduation_year")
        eligibility_context: Dict[str, Any] = _get_pref("eligibility_context") or {}

        # 3. Category matching
        opp_category = normalize_category(opp.type) or "other"
        target_category = normalize_category(category_filter)

        if target_category and target_category != "all":
            if opp_category != target_category:
                return None
        else:
            normalized_allowed = [normalize_category(t) for t in pref_types]
            if opp_category not in normalized_allowed and "all" not in normalized_allowed:
                return None

        # 4. Domain & Interest match
        opp_reqs = getattr(opp, "requirements", []) or []
        domain_score, domain_reasons = self._evaluate_domain_match(
            user_domains=pref_domains,
            user_roles=pref_roles,
            user_skills=skills,
            title=opp.title,
            requirements=opp_reqs,
            description=opp.description or "",
        )

        # 5. Location & Remote match
        opp_location = getattr(opp, "location", None)
        location_score, is_remote, location_explanation = self._evaluate_location_match(
            remote_only=remote_only,
            preferred_locations=pref_locations,
            opp_location=opp_location,
            opp_desc=opp.description or "",
        )

        # If candidate strictly requires remote and listing fails, exclude
        if remote_only and location_score == 0.0:
            return None

        # 6. Eligibility evaluation
        elig_status, elig_notes, elig_factor = self._evaluate_eligibility(
            opp_eligibility=getattr(opp, "eligibility", None),
            education_level=education_level,
            graduation_year=graduation_year,
            eligibility_context=eligibility_context,
        )

        if elig_status == "ineligible":
            return None

        # 7. Verification factor
        opp_verified = getattr(opp, "verified_status", "unverified") or "unverified"
        if opp_verified == "verified":
            verification_multiplier = 1.0
            verif_notice = "Verified listing"
        else:
            verification_multiplier = 0.85
            verif_notice = f"Unverified listing ({opp_verified}); criteria require confirmation"

        # 8. Composite rule-based score calculation
        raw_score = (
            (0.50 * domain_score) + (0.30 * location_score) + (0.20 * elig_factor)
        ) * verification_multiplier

        if is_expired:
            raw_score *= 0.3

        match_score = round(min(1.0, max(0.05, raw_score)), 2)

        # Relevance tier
        if match_score >= 0.75:
            relevance_tier = "High Match"
        elif match_score >= 0.50:
            relevance_tier = "Medium Match"
        else:
            relevance_tier = "Low Match"

        # 9. Concise truthful explanation formulation
        reasons_list: List[str] = []
        if domain_reasons:
            reasons_list.extend(domain_reasons[:2])
        reasons_list.append(location_explanation)
        if elig_notes:
            reasons_list.append(elig_notes)
        reasons_list.append(verif_notice)

        explanation_parts = [
            f"Category: {opp_category.title()}.",
            f"Domain Match: {int(domain_score * 100)}% ({', '.join(domain_reasons[:2]) if domain_reasons else 'General tech alignment'}).",
            location_explanation + ".",
            elig_notes,
            f"Status: {verif_notice}.",
        ]
        match_explanation = " ".join([p for p in explanation_parts if p])

        # Source URL vs Application URL
        source_url = opp.source_url
        app_url = getattr(opp, "application_url", None) or source_url

        # Discovered at timestamp
        disc_at = getattr(opp, "discovered_at", None)
        if isinstance(disc_at, str):
            try:
                disc_dt = datetime.fromisoformat(disc_at.replace("Z", "+00:00"))
            except Exception:
                disc_dt = None
        elif isinstance(disc_at, datetime):
            disc_dt = disc_at
        else:
            disc_dt = None

        return OpportunityMatchResult(
            id=opp.id,
            title=opp.title,
            organization=opp.organization,
            category=opp_category,
            source_url=source_url,
            application_url=app_url,
            source_name=opp.source_name,
            deadline=deadline_dt,
            location=opp_location,
            is_remote=is_remote,
            match_score=match_score,
            relevance_tier=relevance_tier,
            match_reasons=reasons_list,
            match_explanation=match_explanation,
            eligibility_status=elig_status,  # type: ignore[arg-type]
            eligibility_notes=elig_notes,
            verified_status=opp_verified,
            requirements=opp_reqs,
            prize_or_salary=getattr(opp, "prize_or_salary", None),
            discovered_at=disc_dt,
        )

    async def match_user_opportunities(
        self,
        user_id: str,
        category: Optional[str] = None,
        domain_override: Optional[str] = None,
        remote_only: Optional[bool] = None,
        min_score: Optional[float] = None,
        include_expired: bool = False,
        limit: int = 20,
    ) -> List[OpportunityMatchResult]:
        """
        Retrieves stored opportunities and matches them against the specified user's preferences.
        Strict multi-user isolation: User preferences are loaded strictly by user_id.
        """
        # Load user-isolated preferences
        user_pref = await repository.get_user_preferences(user_id=user_id)

        # Build active preference dictionary allowing optional runtime query overrides
        active_prefs: Dict[str, Any] = {
            "preferred_types": user_pref.preferred_types,
            "target_roles": user_pref.target_roles,
            "domains": [domain_override] if domain_override else user_pref.domains,
            "preferred_locations": user_pref.preferred_locations,
            "remote_only": remote_only if remote_only is not None else user_pref.remote_only,
            "skills": user_pref.skills,
            "education_level": user_pref.education_level,
            "graduation_year": user_pref.graduation_year,
            "eligibility_context": user_pref.eligibility_context or {},
            "min_match_score": min_score if min_score is not None else user_pref.min_match_score,
        }

        # Query shared opportunities from PostgreSQL catalog
        target_categories = [category] if category else user_pref.preferred_types
        opportunities = await repository.list_shared_opportunities(
            opp_types=target_categories if not category else None,
            opp_type=category if category else None,
            include_expired=include_expired,
            limit=100,  # evaluate up to 100 candidate opportunities
        )

        matched_results: List[OpportunityMatchResult] = []
        score_threshold = active_prefs.get("min_match_score", 0.0)

        for opp in opportunities:
            res = self.match_opportunity(
                opp=opp,
                preferences=active_prefs,
                category_filter=category,
                include_expired=include_expired,
            )
            if res and res.match_score >= score_threshold:
                matched_results.append(res)

        # Sort descending by match score, then by approaching deadline
        matched_results.sort(
            key=lambda x: (
                x.match_score,
                x.deadline is not None,
                -(x.deadline.timestamp() if x.deadline else 0),
            ),
            reverse=True,
        )

        return matched_results[:limit]


# Global singleton instance
matching_service = OpportunityMatchingService()
