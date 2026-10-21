"""
Voxara AI - Pydantic Data Models (DTOs)

Defines validation and serialization models for:
- User accounts and authentication context
- User preferences (internships, hackathons, roles, domains)
- Shared opportunities (Devpost, MLH, GSoC, etc.)
- User-specific saved opportunities & application tracking
- User-specific notifications & confirmation gates
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


def current_utc_iso() -> str:
    """Returns current UTC timestamp formatted as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def compute_content_hash(url: str, title: str) -> str:
    """Computes a deterministic SHA-256 hash from normalized URL and title for deduplication."""
    norm_url = url.strip().lower().rstrip("/")
    norm_title = title.strip().lower()
    combined = f"{norm_url}::{norm_title}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# User Models
# ---------------------------------------------------------------------------

class UserRead(BaseModel):
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None


# ---------------------------------------------------------------------------
# User Preferences Models
# ---------------------------------------------------------------------------

class UserPreferenceRead(BaseModel):
    id: str
    user_id: str
    preferred_types: List[str] = Field(
        default_factory=lambda: ["internship", "hackathon"],
        description="Categories: 'internship', 'hackathon'",
    )
    target_roles: List[str] = Field(
        default_factory=lambda: ["AI Engineer", "Software Engineer"],
        description="Target job roles or career focus areas",
    )
    domains: List[str] = Field(
        default_factory=lambda: ["Artificial Intelligence", "Full Stack", "Systems"],
        description="Technical domains or focus areas",
    )
    min_match_score: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum match score (0.0 to 1.0) to trigger notifications",
    )
    notifications_enabled: bool = True
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserPreferenceUpdate(BaseModel):
    preferred_types: Optional[List[str]] = None
    target_roles: Optional[List[str]] = None
    domains: Optional[List[str]] = None
    min_match_score: Optional[float] = None
    notifications_enabled: Optional[bool] = None


# ---------------------------------------------------------------------------
# Shared Opportunity Models (Internships & Hackathons)
# ---------------------------------------------------------------------------

class OpportunityRead(BaseModel):
    id: str
    title: str
    organization: str
    type: Literal["internship", "hackathon", "fellowship", "scholarship", "other"]
    source_url: str
    application_url: Optional[str] = None
    source_name: str
    content_hash: str
    deadline: Optional[datetime] = None
    description: str
    location: Optional[str] = None
    eligibility: Optional[str] = None
    requirements: List[str] = Field(default_factory=list)
    prize_or_salary: Optional[str] = None
    verified_status: str
    verified_at: Optional[datetime] = None
    discovered_at: datetime

    model_config = {"from_attributes": True}


class OpportunityCreate(BaseModel):
    title: str
    organization: str
    type: Literal["internship", "hackathon", "fellowship", "scholarship", "other"]
    source_url: str
    application_url: Optional[str] = None
    source_name: str
    description: str
    deadline: Optional[datetime] = None
    location: Optional[str] = None
    eligibility: Optional[str] = None
    requirements: List[str] = Field(default_factory=list)
    prize_or_salary: Optional[str] = None
    verified_status: str = "unverified"
    verified_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# User-Specific Saved Opportunity & Application Tracking Models
# ---------------------------------------------------------------------------

ApplicationStatusType = Literal[
    "saved",
    "applied",
    "interviewing",
    "offered",
    "rejected",
    "archived",
]


class SavedOpportunityRead(BaseModel):
    id: str
    user_id: str
    opportunity_id: str
    status: ApplicationStatusType
    notes: Optional[str] = None
    match_score: float = 0.0
    match_reason: Optional[str] = None
    saved_at: datetime
    updated_at: datetime
    opportunity: Optional[OpportunityRead] = None

    model_config = {"from_attributes": True}


class SavedOpportunityCreate(BaseModel):
    opportunity_id: str
    status: ApplicationStatusType = "saved"
    notes: Optional[str] = None
    match_score: float = 0.0
    match_reason: Optional[str] = None


class SavedOpportunityUpdate(BaseModel):
    status: Optional[ApplicationStatusType] = None
    notes: Optional[str] = None
    match_score: Optional[float] = None
    match_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# User-Specific Notification Models
# ---------------------------------------------------------------------------

class NotificationRead(BaseModel):
    id: str
    user_id: str
    opportunity_id: Optional[str] = None
    title: str
    message: str
    spoken_summary: Optional[str] = None
    type: str
    priority: str
    is_read: bool
    content_hash: str
    requires_confirmation: bool
    confirmation_token: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    delivered_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class NotificationCreate(BaseModel):
    user_id: str
    title: str
    message: str
    opportunity_id: Optional[str] = None
    spoken_summary: Optional[str] = None
    type: str = "opportunity"
    priority: str = "normal"
    requires_confirmation: bool = False
    confirmation_token: Optional[str] = None


# ---------------------------------------------------------------------------
# Compatibility / Bridge Models (Phase 1 & 2 Workflow Interop)
# ---------------------------------------------------------------------------

class UserPreferencesModel(BaseModel):
    id: str = "default"
    roles: List[str] = Field(default_factory=lambda: ["AI Engineer", "Software Engineer"])
    opportunity_types: List[str] = Field(default_factory=lambda: ["internship", "hackathon"])
    domains: List[str] = Field(default_factory=lambda: ["Artificial Intelligence", "Full Stack"])
    min_match_score: float = 0.6
    auto_monitor_enabled: bool = True
    notifications_enabled: bool = True
    updated_at: Any = Field(default_factory=current_utc_iso)

    model_config = {"from_attributes": True}


class UserPreferencesUpdate(BaseModel):
    roles: Optional[List[str]] = None
    opportunity_types: Optional[List[str]] = None
    domains: Optional[List[str]] = None
    min_match_score: Optional[float] = None
    auto_monitor_enabled: Optional[bool] = None
    notifications_enabled: Optional[bool] = None


class OpportunityModel(BaseModel):
    id: str
    title: str
    organization: str
    type: str = "hackathon"
    source_url: str
    application_url: Optional[str] = None
    source_name: str = "Devpost"
    content_hash: str
    deadline: Optional[Any] = None
    description: str = ""
    location: Optional[str] = None
    eligibility: Optional[str] = None
    requirements: List[str] = Field(default_factory=list)
    match_score: float = 0.0
    match_reason: Optional[str] = None
    prize_or_salary: Optional[str] = None
    verified_status: str = "verified"
    verified_at: Optional[Any] = None
    discovered_at: Optional[str] = Field(default_factory=current_utc_iso)

    model_config = {"from_attributes": True}


class NotificationModel(BaseModel):
    id: str
    title: str
    message: str
    opportunity_id: Optional[str] = None
    spoken_summary: Optional[str] = None
    type: str = "opportunity"
    priority: str = "normal"
    is_read: bool = False
    content_hash: str
    requires_confirmation: bool = False
    confirmation_token: Optional[str] = None
    created_at: Optional[Any] = None
    delivered_at: Optional[Any] = None

    model_config = {"from_attributes": True}

