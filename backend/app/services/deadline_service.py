"""
Voxara AI - Deadline Processing & Alert Service

Responsible for:
1. Identifying approaching opportunity deadlines within a configurable window (e.g. 3-7 days).
2. Identifying expired opportunities without fabricating or assuming missing dates.
3. Applying a strict UTC timezone strategy across all datetime operations.
4. Generating persistent, deduplicated alerts in PostgreSQL for user saved applications
   and highly relevant opportunity matches.
5. Preventing duplicate notifications across repeated scheduled runs using deterministic
   content hashing based on (user_id, opportunity_id, deadline_date).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from app.config import settings
from app.db import repository
from app.db.models import NotificationCreate, compute_content_hash
from app.db.tables import Opportunity, SavedOpportunity, User

logger = logging.getLogger("voxara-deadline-service")


class DeadlineProcessingService:
    """
    Evaluates approaching and expired deadlines and issues persistent user notifications.
    """

    def __init__(self, alert_days_threshold: Optional[int] = None):
        self._default_alert_days = alert_days_threshold or settings.deadline_alert_days

    def is_expired(self, deadline: Optional[datetime], now: Optional[datetime] = None) -> bool:
        """
        Determines if an opportunity deadline has passed.
        Returns False if deadline is None (rolling/unspecified). Never fabricates dates.
        """
        if deadline is None:
            return False
        current_time = now or datetime.now(timezone.utc)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return deadline < current_time

    def is_approaching(
        self,
        deadline: Optional[datetime],
        alert_days: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> bool:
        """
        Determines whether a deadline falls between now and now + alert_days.
        Returns False if deadline is missing or already expired.
        """
        if deadline is None:
            return False
        current_time = now or datetime.now(timezone.utc)
        days = alert_days if alert_days is not None else self._default_alert_days
        window_end = current_time + timedelta(days=days)

        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        return current_time <= deadline <= window_end

    async def process_deadlines(
        self,
        alert_days: Optional[int] = None,
        limit_candidates: int = 500,
    ) -> Dict[str, Any]:
        """
        Main execution sweep for deadline processing:
        1. Evaluates all user-saved applications approaching deadline.
        2. Scans catalog opportunities approaching deadline for active users.
        3. Identifies and counts expired opportunities.
        4. Persists deduplicated notifications to PostgreSQL.
        """
        now = datetime.now(timezone.utc)
        effective_alert_days = alert_days if alert_days is not None else self._default_alert_days
        logger.info(
            "Starting deadline processing sweep (window: %d days, UTC reference: %s)...",
            effective_alert_days,
            now.isoformat(),
        )

        notifications_created = 0
        users_notified: Set[str] = set()
        approaching_deadlines_seen = 0
        expired_deadlines_seen = 0

        # -------------------------------------------------------------------
        # Phase 1: Check User-Specific Saved Applications
        # -------------------------------------------------------------------
        saved_items = await repository.list_user_saved_opportunities_with_deadlines(limit=limit_candidates)
        user_saved_opp_ids: Set[tuple[str, str]] = set()

        for saved in saved_items:
            user_saved_opp_ids.add((saved.user_id, saved.opportunity_id))
            opp: Optional[Opportunity] = saved.opportunity
            if not opp or opp.deadline is None:
                continue

            deadline = opp.deadline if opp.deadline.tzinfo else opp.deadline.replace(tzinfo=timezone.utc)

            if deadline < now:
                expired_deadlines_seen += 1
                continue

            if self.is_approaching(deadline, alert_days=effective_alert_days, now=now):
                approaching_deadlines_seen += 1
                days_left = max(0.0, (deadline - now).total_seconds() / 86400.0)
                priority = "urgent" if days_left <= 1.0 else "high"
                date_str = deadline.strftime("%b %d, %Y")
                time_desc = f"{int(days_left)} day(s)" if days_left >= 1.0 else f"{int(days_left * 24)} hour(s)"

                title = f"Deadline Approaching: {opp.title}"
                message = (
                    f"Your tracked application for '{opp.title}' at {opp.organization} "
                    f"has a deadline in {time_desc} ({date_str})."
                )
                spoken = f"Reminder: Your saved application for {opp.title} at {opp.organization} is due in {time_desc}."

                # Deterministic deduplication key strictly bound to (user_id, opp_id, deadline_date)
                deadline_date_key = deadline.strftime("%Y-%m-%d")
                dedup_hash = compute_content_hash(
                    url=f"user:{saved.user_id}:opp:{opp.id}:deadline:{deadline_date_key}",
                    title="deadline_alert",
                )

                notif_dto = NotificationCreate(
                    user_id=saved.user_id,
                    opportunity_id=opp.id,
                    title=title,
                    message=message,
                    spoken_summary=spoken,
                    type="deadline",
                    priority=priority,
                    custom_content_hash=dedup_hash,
                )

                created = await repository.create_user_notification(notif_dto)
                if created:
                    notifications_created += 1
                    users_notified.add(saved.user_id)
                    logger.info(
                        "Created deadline alert for user '%s' on opportunity '%s' (due %s)",
                        saved.user_id,
                        opp.title,
                        date_str,
                    )

        # -------------------------------------------------------------------
        # Phase 2: Check Upcoming Deadlines in General Catalog for Users with Notifications Enabled
        # -------------------------------------------------------------------
        upcoming_catalog_opps = await repository.get_upcoming_shared_deadlines(limit=50)
        active_users = await repository.list_users_with_preferences(limit=100)

        for user in active_users:
            prefs = user.preferences
            if not prefs or not getattr(prefs, "notifications_enabled", True):
                continue

            pref_types = [t.lower() for t in getattr(prefs, "preferred_types", [])]

            for opp in upcoming_catalog_opps:
                if not opp.deadline:
                    continue
                # Skip if already saved and alerted in Phase 1
                if (user.id, opp.id) in user_saved_opp_ids:
                    continue

                deadline = opp.deadline if opp.deadline.tzinfo else opp.deadline.replace(tzinfo=timezone.utc)
                if not self.is_approaching(deadline, alert_days=effective_alert_days, now=now):
                    continue

                # Only notify if opportunity type matches user preference categories
                if pref_types and opp.type.lower() not in pref_types:
                    continue

                days_left = max(0.0, (deadline - now).total_seconds() / 86400.0)
                date_str = deadline.strftime("%b %d, %Y")
                time_desc = f"{int(days_left)} day(s)" if days_left >= 1.0 else f"{int(days_left * 24)} hour(s)"

                title = f"Opportunity Deadline: {opp.title}"
                message = (
                    f"The deadline for {opp.type} '{opp.title}' at {opp.organization} "
                    f"is approaching in {time_desc} ({date_str})."
                )
                spoken = f"The deadline for {opp.title} at {opp.organization} is in {time_desc}."

                deadline_date_key = deadline.strftime("%Y-%m-%d")
                dedup_hash = compute_content_hash(
                    url=f"user:{user.id}:opp:{opp.id}:deadline:{deadline_date_key}",
                    title="deadline_alert",
                )

                notif_dto = NotificationCreate(
                    user_id=user.id,
                    opportunity_id=opp.id,
                    title=title,
                    message=message,
                    spoken_summary=spoken,
                    type="deadline",
                    priority="normal" if days_left > 1.0 else "high",
                    custom_content_hash=dedup_hash,
                )

                created = await repository.create_user_notification(notif_dto)
                if created:
                    notifications_created += 1
                    users_notified.add(user.id)

        result_summary = {
            "status": "completed",
            "checked_at": now.isoformat(),
            "alert_window_days": effective_alert_days,
            "approaching_deadlines_found": approaching_deadlines_seen,
            "expired_deadlines_seen": expired_deadlines_seen,
            "notifications_created": notifications_created,
            "users_notified_count": len(users_notified),
        }
        logger.info(
            "Deadline processing complete: %d alerts created for %d user(s).",
            notifications_created,
            len(users_notified),
        )
        return result_summary


# Global singleton service
deadline_service = DeadlineProcessingService()
