"""
Voxara AI - PostgreSQL Database Tables (SQLAlchemy 2.0 ORM)

Multi-User Architecture:
- User accounts (users)
- User preferences (user_preferences)
- Shared opportunities (opportunities: internships, hackathons)
- User-specific saved opportunities & status (saved_opportunities)
- User-specific notifications & confirmation gates (notifications)
- Workflow execution telemetry (workflow_executions)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


def generate_uuid() -> str:
    """Generates a UUID hex string."""
    return uuid.uuid4().hex


class User(Base):
    """
    Registered user account.
    Personal data, saved opportunities, and notifications are isolated by user_id.
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    preferences: Mapped[Optional["UserPreference"]] = relationship(
        "UserPreference", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    saved_opportunities: Mapped[List["SavedOpportunity"]] = relationship(
        "SavedOpportunity", back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )


class UserPreference(Base):
    """
    User opportunity hunting preferences.
    """
    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    preferred_types: Mapped[List[str]] = mapped_column(
        JSON, default=lambda: ["internship", "hackathon"], nullable=False
    )
    target_roles: Mapped[List[str]] = mapped_column(
        JSON, default=lambda: ["Software Engineer", "AI Engineer"], nullable=False
    )
    domains: Mapped[List[str]] = mapped_column(
        JSON, default=lambda: ["Artificial Intelligence", "Full Stack", "Systems"], nullable=False
    )
    min_match_score: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user: Mapped["User"] = relationship("User", back_populates="preferences")

    @property
    def roles(self) -> List[str]:
        return self.target_roles

    @property
    def opportunity_types(self) -> List[str]:
        return self.preferred_types

    @property
    def auto_monitor_enabled(self) -> bool:
        return self.notifications_enabled


class Opportunity(Base):
    """
    Shared repository of verified internships and hackathons.
    The same opportunity is stored once and referenced by multiple users.
    """
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"opp_{uuid.uuid4().hex[:12]}")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    organization: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # 'internship' | 'hackathon'
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)  # 'Devpost', 'MLH', etc.
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    eligibility: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requirements: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    prize_or_salary: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verified_status: Mapped[str] = mapped_column(String(32), default="unverified", nullable=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    # Relationships
    saved_by_users: Mapped[List["SavedOpportunity"]] = relationship(
        "SavedOpportunity", back_populates="opportunity", cascade="all, delete-orphan"
    )


class SavedOpportunity(Base):
    """
    User-specific saved opportunity and application tracking.
    Enforces authorization and personal data isolation per user.
    """
    __tablename__ = "saved_opportunities"
    __table_args__ = (
        UniqueConstraint("user_id", "opportunity_id", name="uq_user_opportunity"),
        Index("ix_saved_opp_user_status", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"saved_{uuid.uuid4().hex[:12]}")
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opportunity_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="saved", nullable=False
    )  # 'saved' | 'applied' | 'interviewing' | 'offered' | 'rejected' | 'archived'
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    match_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    match_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user: Mapped["User"] = relationship("User", back_populates="saved_opportunities")
    opportunity: Mapped["Opportunity"] = relationship("Opportunity", back_populates="saved_by_users")


class Notification(Base):
    """
    User-specific notifications and human confirmation gates.
    """
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"notif_{uuid.uuid4().hex[:12]}")
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opportunity_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    spoken_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(
        String(64), default="opportunity", nullable=False
    )  # 'opportunity' | 'deadline' | 'application_update' | 'system'
    priority: Mapped[str] = mapped_column(String(32), default="normal", nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmation_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="notifications")
    opportunity: Mapped[Optional["Opportunity"]] = relationship("Opportunity")


class WorkflowExecution(Base):
    """
    Persisted telemetry for LangGraph workflow execution runs.
    """
    __tablename__ = "workflow_executions"

    execution_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    workflow_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    input_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    events: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
