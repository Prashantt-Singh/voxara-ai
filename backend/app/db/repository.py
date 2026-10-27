"""
Voxara AI - PostgreSQL Database Repositories (SQLAlchemy 2.0 Async)

Enforces:
- Separation of concerns: Database access is strictly decoupled from agent workflows and API routes
- Multi-user isolation: User-specific data (preferences, saved applications, notifications) is scoped by user_id
- Shared opportunities: Internships and hackathons are stored once and referenced across users
- Deduplication: Unique constraints on content_hash prevent duplicate opportunities or alerts
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import and_, delete, desc, func, or_, select, update
from sqlalchemy.orm import selectinload

from app.db.database import db_manager
from app.db.models import (
    UserPreferenceUpdate,
    UserPreferencesUpdate,
    OpportunityCreate,
    OpportunityModel,
    SavedOpportunityCreate,
    SavedOpportunityUpdate,
    NotificationCreate,
    NotificationModel,
    compute_content_hash,
)
from app.db.tables import (
    User,
    UserPreference,
    Opportunity,
    SavedOpportunity,
    Notification,
    WorkflowExecution,
)

logger = logging.getLogger("voxara-repository")


# ---------------------------------------------------------------------------
# User & Preferences Repository
# ---------------------------------------------------------------------------

async def get_or_create_user(
    user_id: str,
    email: Optional[str] = None,
    name: Optional[str] = None,
) -> User:
    """
    Retrieves or creates a user account and initializes default preferences.
    """
    async with db_manager.session() as session:
        result = await session.execute(
            select(User).options(selectinload(User.preferences)).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(id=user_id, email=email, name=name)
            session.add(user)
            await session.flush()

            # Seed default preferences
            pref = UserPreference(
                user_id=user.id,
                preferred_types=["internship", "hackathon", "fellowship"],
                target_roles=["AI Engineer", "Software Engineer"],
                domains=["Artificial Intelligence", "Full Stack", "Systems"],
                preferred_locations=[],
                remote_only=False,
                skills=[],
                education_level=None,
                graduation_year=None,
                eligibility_context={},
                min_match_score=0.6,
                notifications_enabled=True,
            )
            session.add(pref)
            await session.commit()
            await session.refresh(user, attribute_names=["preferences"])
        return user


async def get_user_preferences(user_id: str = "default_user") -> UserPreference:
    """
    Retrieves preferences for a specific user, creating them if not present.
    """
    async with db_manager.session() as session:
        result = await session.execute(
            select(UserPreference).where(UserPreference.user_id == user_id)
        )
        pref = result.scalar_one_or_none()
        if pref is None:
            await get_or_create_user(user_id=user_id)
            result = await session.execute(
                select(UserPreference).where(UserPreference.user_id == user_id)
            )
            pref = result.scalar_one()
        return pref


async def update_user_preferences(
    user_id: Any = None,
    updates: Any = None,
    **kwargs: Any,
) -> UserPreference:
    """
    Updates preferences for the authenticated user ID.
    Supports:
    - update_user_preferences(user_id="user_alice", updates=...)
    - update_user_preferences("user_alice", updates)
    - update_user_preferences(updates)
    """
    if updates is None:
        if isinstance(user_id, str):
            actual_user_id = user_id
            actual_updates = kwargs.get("updates")
        else:
            actual_user_id = "default_user"
            actual_updates = user_id
    else:
        actual_user_id = str(user_id) if user_id is not None else "default_user"
        actual_updates = updates

    user_id = actual_user_id

    async with db_manager.session() as session:
        result = await session.execute(
            select(UserPreference).where(UserPreference.user_id == user_id)
        )
        pref = result.scalar_one_or_none()
        if pref is None:
            await get_or_create_user(user_id=user_id)
            result = await session.execute(
                select(UserPreference).where(UserPreference.user_id == user_id)
            )
            pref = result.scalar_one()

        pref_types = getattr(actual_updates, "preferred_types", None) or getattr(actual_updates, "opportunity_types", None)
        if pref_types is not None:
            pref.preferred_types = pref_types

        roles = getattr(actual_updates, "target_roles", None) or getattr(actual_updates, "roles", None)
        if roles is not None:
            pref.target_roles = roles

        domains = getattr(actual_updates, "domains", None)
        if domains is not None:
            pref.domains = domains

        min_score = getattr(actual_updates, "min_match_score", None)
        if min_score is not None:
            pref.min_match_score = min_score

        notif_enabled = getattr(actual_updates, "notifications_enabled", None)
        if notif_enabled is None:
            notif_enabled = getattr(actual_updates, "auto_monitor_enabled", None)
        if notif_enabled is not None:
            pref.notifications_enabled = notif_enabled

        pref_locations = getattr(actual_updates, "preferred_locations", None)
        if pref_locations is not None:
            pref.preferred_locations = pref_locations

        remote_only = getattr(actual_updates, "remote_only", None)
        if remote_only is not None:
            pref.remote_only = remote_only

        skills = getattr(actual_updates, "skills", None)
        if skills is not None:
            pref.skills = skills

        education_level = getattr(actual_updates, "education_level", None)
        if education_level is not None:
            pref.education_level = education_level

        graduation_year = getattr(actual_updates, "graduation_year", None)
        if graduation_year is not None:
            pref.graduation_year = graduation_year

        eligibility_context = getattr(actual_updates, "eligibility_context", None)
        if eligibility_context is not None:
            pref.eligibility_context = eligibility_context

        await session.commit()
        await session.refresh(pref)
        return pref


# ---------------------------------------------------------------------------
# Shared Opportunity Repository
# ---------------------------------------------------------------------------

async def save_shared_opportunity(data: OpportunityCreate) -> Opportunity:
    """
    Saves a shared internship, hackathon, or fellowship.
    Deduplicates via unique content_hash (SHA-256 of url + title)
    AND normalized (organization, title) to prevent duplicates across different sources.
    """
    content_hash = compute_content_hash(data.source_url, data.title)
    norm_org = data.organization.strip().lower()
    norm_title = data.title.strip().lower()

    async with db_manager.session() as session:
        result = await session.execute(
            select(Opportunity).where(
                or_(
                    Opportunity.content_hash == content_hash,
                    and_(
                        func.lower(Opportunity.organization) == norm_org,
                        func.lower(Opportunity.title) == norm_title,
                    ),
                )
            )
        )
        existing = result.scalars().first()

        if existing:
            # Update mutable fields without creating a duplicate record
            existing.description = data.description or existing.description
            if data.application_url is not None:
                existing.application_url = data.application_url
            if data.location is not None:
                existing.location = data.location
            if data.deadline is not None:
                existing.deadline = data.deadline
            if data.eligibility is not None:
                existing.eligibility = data.eligibility
            if data.requirements:
                merged_reqs = list(dict.fromkeys(existing.requirements + data.requirements))
                existing.requirements = merged_reqs
            if data.prize_or_salary is not None:
                existing.prize_or_salary = data.prize_or_salary
            existing.verified_status = data.verified_status
            if data.verified_at is not None:
                existing.verified_at = data.verified_at
            await session.commit()
            await session.refresh(existing)
            setattr(existing, "_is_new", False)
            return existing

        new_opp = Opportunity(
            title=data.title,
            organization=data.organization,
            type=data.type,
            source_url=data.source_url,
            application_url=data.application_url,
            source_name=data.source_name,
            content_hash=content_hash,
            deadline=data.deadline,
            description=data.description,
            location=data.location,
            eligibility=data.eligibility,
            requirements=data.requirements,
            prize_or_salary=data.prize_or_salary,
            verified_status=data.verified_status,
            verified_at=data.verified_at,
        )
        session.add(new_opp)
        await session.commit()
        await session.refresh(new_opp)
        setattr(new_opp, "_is_new", True)
        return new_opp


async def get_shared_opportunity_by_hash(content_hash: str) -> Optional[Opportunity]:
    async with db_manager.session() as session:
        result = await session.execute(
            select(Opportunity).where(Opportunity.content_hash == content_hash)
        )
        return result.scalar_one_or_none()


async def get_shared_opportunity_by_id(opportunity_id: str) -> Optional[Opportunity]:
    async with db_manager.session() as session:
        result = await session.execute(
            select(Opportunity).where(Opportunity.id == opportunity_id)
        )
        return result.scalar_one_or_none()


async def delete_shared_opportunity(opportunity_id: str) -> bool:
    """
    Deletes a shared opportunity by ID. Returns True if deleted, False if not found.
    """
    async with db_manager.session() as session:
        result = await session.execute(
            select(Opportunity).where(Opportunity.id == opportunity_id)
        )
        opp = result.scalar_one_or_none()
        if opp is None:
            return False
        await session.delete(opp)
        await session.commit()
        return True


async def list_shared_opportunities(
    opp_type: Optional[str] = None,
    opp_types: Optional[List[str]] = None,
    include_expired: bool = True,
    limit: int = 50,
) -> List[Opportunity]:
    """
    Lists shared opportunities from the central catalog.
    Supports filtering by single category, multiple categories, and excluding expired opportunities.
    """
    now = datetime.now(timezone.utc)
    async with db_manager.session() as session:
        query = select(Opportunity)
        if opp_type and opp_type.lower() != "all":
            query = query.where(Opportunity.type == opp_type.lower())
        elif opp_types:
            clean_types = [t.lower().strip() for t in opp_types if t and t.lower().strip() != "all"]
            if clean_types:
                query = query.where(Opportunity.type.in_(clean_types))

        if not include_expired:
            # Exclude opportunities with past deadlines; keep opportunities where deadline is None (rolling/unspecified)
            query = query.where(or_(Opportunity.deadline.is_(None), Opportunity.deadline >= now))

        query = query.order_by(desc(Opportunity.discovered_at)).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())


async def get_upcoming_shared_deadlines(limit: int = 20) -> List[Opportunity]:
    """
    Returns opportunities with deadlines approaching in the future.
    """
    now = datetime.now(timezone.utc)
    async with db_manager.session() as session:
        query = (
            select(Opportunity)
            .where(Opportunity.deadline.is_not(None), Opportunity.deadline >= now)
            .order_by(Opportunity.deadline.asc())
            .limit(limit)
        )
        result = await session.execute(query)
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# User-Specific Saved Opportunities & Application Tracking
# ---------------------------------------------------------------------------

async def save_user_opportunity(
    user_id: str,
    data: SavedOpportunityCreate,
) -> SavedOpportunity:
    """
    Saves an opportunity into the user's personal pipeline.
    Validates that the target opportunity exists.
    If already saved, updates status/notes idempotently.
    """
    # Ensure user exists
    await get_or_create_user(user_id=user_id)

    async with db_manager.session() as session:
        # Verify that the shared opportunity exists
        opp_result = await session.execute(
            select(Opportunity).where(Opportunity.id == data.opportunity_id)
        )
        opp = opp_result.scalar_one_or_none()
        if not opp:
            raise ValueError(f"Opportunity with ID '{data.opportunity_id}' not found.")

        result = await session.execute(
            select(SavedOpportunity)
            .options(selectinload(SavedOpportunity.opportunity))
            .where(
                SavedOpportunity.user_id == user_id,
                SavedOpportunity.opportunity_id == data.opportunity_id,
            )
        )
        existing = result.scalar_one_or_none()

        status_val = data.status.strip().lower() if isinstance(data.status, str) else data.status

        if existing:
            existing.status = status_val
            if data.notes is not None:
                existing.notes = data.notes
            if data.match_score > 0:
                existing.match_score = data.match_score
            if data.match_reason:
                existing.match_reason = data.match_reason
            existing.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(existing, attribute_names=["opportunity"])
            return existing

        saved_item = SavedOpportunity(
            user_id=user_id,
            opportunity_id=data.opportunity_id,
            status=status_val,
            notes=data.notes,
            match_score=data.match_score,
            match_reason=data.match_reason,
            saved_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(saved_item)
        await session.commit()
        await session.refresh(saved_item, attribute_names=["opportunity"])
        return saved_item


async def get_user_saved_opportunity(
    user_id: str,
    saved_id: str,
) -> Optional[SavedOpportunity]:
    """
    Retrieves a single personal saved opportunity by ID for the authenticated user.
    Strictly isolated by user_id for authorization.
    """
    async with db_manager.session() as session:
        result = await session.execute(
            select(SavedOpportunity)
            .options(selectinload(SavedOpportunity.opportunity))
            .where(SavedOpportunity.id == saved_id, SavedOpportunity.user_id == user_id)
        )
        return result.scalar_one_or_none()


async def get_user_saved_opportunity_by_opp_id(
    user_id: str,
    opportunity_id: str,
) -> Optional[SavedOpportunity]:
    """
    Retrieves a personal saved opportunity by opportunity_id for the authenticated user.
    """
    async with db_manager.session() as session:
        result = await session.execute(
            select(SavedOpportunity)
            .options(selectinload(SavedOpportunity.opportunity))
            .where(
                SavedOpportunity.opportunity_id == opportunity_id,
                SavedOpportunity.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()


async def list_user_saved_opportunities(
    user_id: str,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[SavedOpportunity]:
    """
    Retrieves personal saved opportunities for the user, with opportunity relationships.
    Strictly isolated by user_id. Supports case-insensitive status filtering.
    """
    async with db_manager.session() as session:
        query = (
            select(SavedOpportunity)
            .options(selectinload(SavedOpportunity.opportunity))
            .where(SavedOpportunity.user_id == user_id)
        )
        if status:
            clean_status = status.strip().lower()
            query = query.where(func.lower(SavedOpportunity.status) == clean_status)
        query = query.order_by(desc(SavedOpportunity.updated_at)).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())


async def update_user_saved_opportunity(
    user_id: str,
    saved_id: str,
    updates: SavedOpportunityUpdate,
) -> Optional[SavedOpportunity]:
    """
    Updates application status (e.g. 'applied', 'interviewing') and notes.
    Authorization: user can only modify their own saved record.
    """
    async with db_manager.session() as session:
        result = await session.execute(
            select(SavedOpportunity)
            .options(selectinload(SavedOpportunity.opportunity))
            .where(SavedOpportunity.id == saved_id, SavedOpportunity.user_id == user_id)
        )
        saved = result.scalar_one_or_none()
        if not saved:
            return None

        if "status" in updates.model_fields_set and updates.status is not None:
            saved.status = updates.status.strip().lower() if isinstance(updates.status, str) else updates.status
        if "notes" in updates.model_fields_set:
            saved.notes = updates.notes
        if "match_score" in updates.model_fields_set and updates.match_score is not None:
            saved.match_score = updates.match_score
        if "match_reason" in updates.model_fields_set:
            saved.match_reason = updates.match_reason

        saved.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(saved, attribute_names=["opportunity"])
        return saved


async def delete_user_saved_opportunity(user_id: str, saved_id: str) -> bool:
    """
    Removes an opportunity from the user's personal pipeline.
    Authorization: user can only delete their own saved record.
    Preserves the underlying shared opportunity record.
    """
    async with db_manager.session() as session:
        result = await session.execute(
            delete(SavedOpportunity).where(
                SavedOpportunity.id == saved_id,
                SavedOpportunity.user_id == user_id,
            )
        )
        await session.commit()
        return result.rowcount > 0


# ---------------------------------------------------------------------------
# User-Specific Notifications & Confirmation Gates
# ---------------------------------------------------------------------------

async def create_user_notification(data: NotificationCreate) -> Optional[Notification]:
    """
    Creates an alert for an individual user.
    Deduplicates based on content_hash to prevent alert fatigue.
    """
    await get_or_create_user(user_id=data.user_id)
    if getattr(data, "custom_content_hash", None):
        content_hash = data.custom_content_hash
    else:
        content_hash = compute_content_hash(
            url=f"user:{data.user_id}:{data.opportunity_id or 'general'}:{data.type}",
            title=data.title,
        )

    async with db_manager.session() as session:
        # Check duplicate
        result = await session.execute(
            select(Notification).where(Notification.content_hash == content_hash)
        )
        if result.scalar_one_or_none():
            logger.debug("Duplicate notification hash '%s' skipped.", content_hash)
            return None

        notif = Notification(
            user_id=data.user_id,
            opportunity_id=data.opportunity_id,
            title=data.title,
            message=data.message,
            spoken_summary=data.spoken_summary,
            type=data.type,
            priority=data.priority,
            content_hash=content_hash,
            requires_confirmation=data.requires_confirmation,
            confirmation_token=data.confirmation_token,
        )
        try:
            session.add(notif)
            await session.commit()
            await session.refresh(notif)
            return notif
        except Exception as exc:
            logger.debug("Duplicate or race collision for notification hash '%s': %s", content_hash, exc)
            await session.rollback()
            return None


async def list_users_with_preferences(limit: int = 500) -> List[User]:
    """Retrieves all registered users with their preferences preloaded."""
    async with db_manager.session() as session:
        result = await session.execute(
            select(User).options(selectinload(User.preferences)).limit(limit)
        )
        return list(result.scalars().all())


async def list_user_saved_opportunities_with_deadlines(limit: int = 500) -> List[SavedOpportunity]:
    """
    Retrieves all user-saved opportunities that have deadlines approaching in the future.
    """
    now = datetime.now(timezone.utc)
    async with db_manager.session() as session:
        query = (
            select(SavedOpportunity)
            .join(Opportunity, SavedOpportunity.opportunity_id == Opportunity.id)
            .options(selectinload(SavedOpportunity.opportunity))
            .where(Opportunity.deadline.is_not(None), Opportunity.deadline >= now)
            .order_by(Opportunity.deadline.asc())
            .limit(limit)
        )
        result = await session.execute(query)
        return list(result.scalars().all())


async def list_user_notifications(
    user_id: str,
    unread_only: bool = False,
    limit: int = 20,
) -> List[Notification]:
    """
    Retrieves notifications for an individual user.
    """
    async with db_manager.session() as session:
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.is_read.is_(False))
        query = query.order_by(desc(Notification.created_at)).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())


async def mark_notification_read(user_id: str, notification_id: str) -> bool:
    """
    Marks a user's notification as read.
    """
    async with db_manager.session() as session:
        result = await session.execute(
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user_id)
            .values(is_read=True, delivered_at=datetime.now(timezone.utc))
        )
        await session.commit()
        return result.rowcount > 0


async def mark_all_user_notifications_read(user_id: str) -> int:
    """
    Marks all unread notifications for a user as read.
    """
    async with db_manager.session() as session:
        result = await session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True, delivered_at=datetime.now(timezone.utc))
        )
        await session.commit()
        return result.rowcount


async def confirm_user_notification(
    user_id: str,
    notification_id: str,
    confirmation_token: str,
) -> bool:
    """
    Human-in-the-loop confirmation gate:
    Validates token and marks notification confirmed.
    """
    async with db_manager.session() as session:
        result = await session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.confirmation_token == confirmation_token,
            )
        )
        notif = result.scalar_one_or_none()
        if not notif:
            return False

        notif.confirmed_at = datetime.now(timezone.utc)
        notif.is_read = True
        await session.commit()
        return True


# ---------------------------------------------------------------------------
# Workflow Execution Telemetry Repository
# ---------------------------------------------------------------------------

async def save_workflow_execution(
    record: Dict[str, Any],
    user_id: Optional[str] = None,
) -> None:
    """
    Persists LangGraph execution telemetry to the database.
    """
    exec_id = record.get("execution_id")
    if not exec_id:
        return

    status = record.get("status", "unknown")
    task = record.get("task", "")
    workflow_type = record.get("workflow_type", "general")
    created_at = datetime.now(timezone.utc)
    completed_at = datetime.now(timezone.utc) if status in ["completed", "failed"] else None

    async with db_manager.session() as session:
        result = await session.execute(
            select(WorkflowExecution).where(WorkflowExecution.execution_id == exec_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.status = status
            existing.result = record.get("result")
            existing.error = record.get("error")
            existing.events = record.get("events") or []
            existing.completed_at = completed_at
        else:
            item = WorkflowExecution(
                execution_id=exec_id,
                user_id=user_id,
                workflow_type=workflow_type,
                status=status,
                task=task,
                input_data=record.get("input_data"),
                result=record.get("result"),
                error=record.get("error"),
                events=record.get("events") or [],
                created_at=created_at,
                completed_at=completed_at,
            )
            session.add(item)
        await session.commit()


async def get_workflow_execution(execution_id: str) -> Optional[Dict[str, Any]]:
    async with db_manager.session() as session:
        result = await session.execute(
            select(WorkflowExecution).where(WorkflowExecution.execution_id == execution_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            return None
        return {
            "execution_id": item.execution_id,
            "user_id": item.user_id,
            "workflow_type": item.workflow_type,
            "status": item.status,
            "task": item.task,
            "input_data": item.input_data or {},
            "result": item.result,
            "error": item.error,
            "events": item.events or [],
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        }


async def list_workflow_executions(limit: int = 50) -> List[Dict[str, Any]]:
    async with db_manager.session() as session:
        result = await session.execute(
            select(WorkflowExecution).order_by(desc(WorkflowExecution.created_at)).limit(limit)
        )
        items = result.scalars().all()
        return [
            {
                "execution_id": item.execution_id,
                "user_id": item.user_id,
                "workflow_type": item.workflow_type,
                "status": item.status,
                "task": item.task,
                "input_data": item.input_data or {},
                "result": item.result,
                "error": item.error,
                "events": item.events or [],
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            }
            for item in items
        ]


# ---------------------------------------------------------------------------
# Synchronous Bridges for Thread-Safe In-Memory Execution Store
# ---------------------------------------------------------------------------

def _sync_save_execution(record: Dict[str, Any]) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(save_workflow_execution(record))
    except RuntimeError:
        asyncio.run(save_workflow_execution(record))


def _sync_get_execution(execution_id: str) -> Optional[Dict[str, Any]]:
    try:
        loop = asyncio.get_running_loop()
        # If already in running loop, run in a new thread or return None
        return None
    except RuntimeError:
        return asyncio.run(get_workflow_execution(execution_id))


# ---------------------------------------------------------------------------
# Compatibility / Bridge Functions (Phase 1 & 2 Workflow Interop)
# ---------------------------------------------------------------------------

def _opp_to_model(opp: Opportunity) -> OpportunityModel:
    return OpportunityModel(
        id=opp.id,
        title=opp.title,
        organization=opp.organization,
        type=opp.type,
        source_url=opp.source_url,
        application_url=getattr(opp, "application_url", None),
        location=getattr(opp, "location", None),
        source_name=opp.source_name,
        content_hash=opp.content_hash,
        deadline=opp.deadline.isoformat() if opp.deadline else None,
        description=opp.description,
        eligibility=opp.eligibility,
        requirements=opp.requirements or [],
        prize_or_salary=opp.prize_or_salary,
        verified_status=opp.verified_status,
        verified_at=opp.verified_at.isoformat() if opp.verified_at else None,
        discovered_at=opp.discovered_at.isoformat() if opp.discovered_at else current_utc_iso(),
        match_score=0.8,
    )


async def save_opportunity(data: Any) -> OpportunityModel:
    """
    Bridge method: Accepts OpportunityModel or OpportunityCreate,
    persists it into the shared opportunity catalog, and returns OpportunityModel.
    """
    deadline_val = getattr(data, "deadline", None)
    if isinstance(deadline_val, str):
        try:
            deadline_dt = datetime.fromisoformat(deadline_val.replace("Z", "+00:00"))
        except Exception:
            deadline_dt = None
    elif isinstance(deadline_val, datetime):
        deadline_dt = deadline_val
    else:
        deadline_dt = None

    opp_create = OpportunityCreate(
        title=getattr(data, "title", ""),
        organization=getattr(data, "organization", ""),
        type=getattr(data, "type", "hackathon"),
        source_url=getattr(data, "source_url", ""),
        application_url=getattr(data, "application_url", None),
        location=getattr(data, "location", None),
        source_name=getattr(data, "source_name", "Devpost"),
        description=getattr(data, "description", ""),
        deadline=deadline_dt,
        eligibility=getattr(data, "eligibility", None),
        requirements=getattr(data, "requirements", []),
        prize_or_salary=getattr(data, "prize_or_salary", None),
        verified_status=getattr(data, "verified_status", "verified"),
    )
    saved = await save_shared_opportunity(opp_create)
    res = _opp_to_model(saved)
    res.match_score = getattr(data, "match_score", 0.8)
    res.match_reason = getattr(data, "match_reason", None)
    res.is_new = getattr(saved, "_is_new", False)
    return res


async def get_opportunity_by_hash(content_hash: str) -> Optional[OpportunityModel]:
    opp = await get_shared_opportunity_by_hash(content_hash)
    return _opp_to_model(opp) if opp else None


async def list_opportunities(
    opp_type: Optional[str] = None,
    min_score: float = 0.0,
    limit: int = 50,
) -> List[OpportunityModel]:
    items = await list_shared_opportunities(opp_type=opp_type, limit=limit)
    return [_opp_to_model(it) for it in items]


async def get_upcoming_deadlines(limit: int = 20) -> List[OpportunityModel]:
    items = await get_upcoming_shared_deadlines(limit=limit)
    return [_opp_to_model(it) for it in items]


def _notif_to_model(notif: Notification) -> NotificationModel:
    return NotificationModel(
        id=notif.id,
        title=notif.title,
        message=notif.message,
        opportunity_id=notif.opportunity_id,
        spoken_summary=notif.spoken_summary,
        type=notif.type,
        priority=notif.priority,
        is_read=notif.is_read,
        content_hash=notif.content_hash,
        requires_confirmation=notif.requires_confirmation,
        confirmation_token=notif.confirmation_token,
        created_at=notif.created_at.isoformat() if notif.created_at else None,
        delivered_at=notif.delivered_at.isoformat() if notif.delivered_at else None,
    )


async def get_pending_notifications(limit: int = 20) -> List[NotificationModel]:
    items = await list_user_notifications(user_id="default_user", unread_only=True, limit=limit)
    return [_notif_to_model(n) for n in items]


async def confirm_notification(notif_id: str, confirmation_token: str) -> bool:
    return await confirm_user_notification(
        user_id="default_user",
        notification_id=notif_id,
        confirmation_token=confirmation_token,
    )


async def mark_notification_delivered(notif_id: str) -> bool:
    return await mark_notification_read(user_id="default_user", notification_id=notif_id)


async def save_notification(data: Any) -> Optional[NotificationModel]:
    create_dto = NotificationCreate(
        user_id=getattr(data, "user_id", "default_user") or "default_user",
        title=getattr(data, "title", ""),
        message=getattr(data, "message", ""),
        opportunity_id=getattr(data, "opportunity_id", None),
        spoken_summary=getattr(data, "spoken_summary", None),
        type=getattr(data, "type", "opportunity"),
        priority=getattr(data, "priority", "normal"),
        requires_confirmation=getattr(data, "requires_confirmation", False),
        confirmation_token=getattr(data, "confirmation_token", None),
    )
    notif = await create_user_notification(create_dto)
    return _notif_to_model(notif) if notif else None


# Backward-compatible alias for workflows
create_notification = save_notification
