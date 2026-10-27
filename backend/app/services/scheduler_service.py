"""
Voxara AI - Autonomous Background Monitoring & Discovery Scheduler

Features:
1. Periodic execution of the Opportunity Discovery engine across official sources:
   - Devpost Hackathons API
   - SimplifyJobs Tech Internship repository
   - Arbeitnow Job Board API
   - Curated official fellowship programs
2. Independent fault isolation: Individual source errors do not crash the cycle.
3. Refreshing of existing catalog opportunities and insertion of genuinely new opportunities.
4. User-isolated notification creation:
   - Evaluates newly discovered opportunities against user preferences using the Matching Engine.
   - Evaluates approaching deadlines for saved applications and high-match catalog items.
5. Strict deduplication of notifications via deterministic content hashing.
6. Execution telemetry and logging stored in the PostgreSQL workflow_executions table.
7. Concurrency and overlap prevention using asyncio locks and singleton state guards.
8. Configurable intervals and enable flags driven by environment variables.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings
from app.db import repository
from app.db.models import (
    NotificationCreate,
    OpportunityMatchResult,
    OpportunityModel,
    compute_content_hash,
)
from app.services.deadline_service import deadline_service
from app.services.matching_service import matching_service
from app.services.opportunity_service import opportunity_service

logger = logging.getLogger("voxara-scheduler")


class BackgroundMonitoringScheduler:
    """
    Manages periodic background opportunity discovery and deadline alert cycles.
    """

    def __init__(
        self,
        interval_minutes: Optional[int] = None,
        initial_delay_seconds: Optional[int] = None,
        batch_size: Optional[int] = None,
    ):
        self._interval_minutes = interval_minutes or settings.scheduler_interval_minutes
        self._initial_delay_seconds = (
            initial_delay_seconds
            if initial_delay_seconds is not None
            else settings.scheduler_initial_delay_seconds
        )
        self._batch_size = batch_size or settings.discovery_batch_size
        self._task: Optional[asyncio.Task] = None
        self._is_running = False
        self._execution_lock = asyncio.Lock()
        self._last_execution_summary: Optional[Dict[str, Any]] = None

    @property
    def is_running(self) -> bool:
        """Returns True if the background scheduler loop is active."""
        return self._is_running

    @property
    def interval_seconds(self) -> int:
        """Returns the interval in seconds."""
        return max(10, self._interval_minutes * 60)

    @property
    def last_summary(self) -> Optional[Dict[str, Any]]:
        """Returns the telemetry summary of the most recent execution."""
        return self._last_execution_summary

    def start(self) -> None:
        """
        Starts the background scheduler loop if enabled and not already running.
        Guarantees only one task runs per scheduler instance.
        """
        if not settings.scheduler_enabled or not settings.enable_in_app_scheduler:
            logger.info(
                "Scheduler startup skipped (SCHEDULER_ENABLED=%s, ENABLE_IN_APP_SCHEDULER=%s).",
                settings.scheduler_enabled,
                settings.enable_in_app_scheduler,
            )
            return

        if self._is_running:
            logger.warning("Scheduler start requested, but loop is already running.")
            return

        self._is_running = True
        self._task = asyncio.create_task(self._run_loop(), name="voxara-background-scheduler")
        logger.info(
            "Autonomous Opportunity Scheduler started (interval: %d min, initial delay: %ds, batch: %d).",
            self._interval_minutes,
            self._initial_delay_seconds,
            self._batch_size,
        )

    async def stop(self) -> None:
        """Gracefully stops the background scheduler task."""
        if not self._is_running:
            return
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Autonomous Opportunity Scheduler stopped.")

    async def _run_loop(self) -> None:
        """Main periodic loop."""
        try:
            if self._initial_delay_seconds > 0:
                await asyncio.sleep(self._initial_delay_seconds)
        except asyncio.CancelledError:
            return

        while self._is_running:
            try:
                await self.execute_discovery_cycle()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Unhandled error during discovery cycle: %s", exc, exc_info=True)

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    async def execute_discovery_cycle(
        self,
        batch_size: Optional[int] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes a single end-to-end discovery and deadline processing cycle:
        1. Prevents overlapping executions using an async lock.
        2. Records telemetry in workflow_executions.
        3. Queries Devpost, Simplify, Arbeitnow, and Curated programs.
        4. Distinguishes newly discovered opportunities from refreshed existing ones.
        5. Notifies active users of new matching opportunities based on personal preferences.
        6. Processes approaching deadlines and generates persistent deadline notifications.
        """
        if self._execution_lock.locked() and not force:
            logger.warning("Skipping discovery cycle: Previous execution is still in progress.")
            return {
                "status": "skipped",
                "reason": "Previous cycle is still running. Overlapping executions are blocked.",
            }

        async with self._execution_lock:
            exec_id = f"sched_discovery_{uuid.uuid4().hex[:10]}"
            start_time = time.perf_counter()
            start_dt = datetime.now(timezone.utc)
            limit = batch_size or self._batch_size

            # Record initial execution in database telemetry
            initial_telemetry = {
                "execution_id": exec_id,
                "user_id": None,
                "workflow_type": "scheduled_opportunity_discovery",
                "status": "running",
                "task": "Periodic opportunity discovery, matching, and deadline processing",
                "input_data": {
                    "batch_size": limit,
                    "interval_minutes": self._interval_minutes,
                    "sources": ["Devpost", "SimplifyJobs", "Arbeitnow", "CuratedPrograms"],
                },
                "result": None,
                "error": None,
                "events": [
                    {
                        "event": "cycle_started",
                        "timestamp": start_dt.isoformat(),
                        "message": f"Started scheduled discovery sweep with target batch size {limit}",
                    }
                ],
                "created_at": start_dt,
                "completed_at": None,
            }
            try:
                await repository.save_workflow_execution(initial_telemetry)
            except Exception as exc:
                logger.warning("Failed to save initial execution telemetry: %s", exc)

            logger.info("Starting scheduled opportunity discovery sweep (Exec ID: %s)...", exec_id)

            try:
                # -----------------------------------------------------------
                # Step 1: Run Multi-Source Opportunity Discovery
                # -----------------------------------------------------------
                discovered_items: List[OpportunityModel] = (
                    await opportunity_service.discover_opportunities(
                        opportunity_type="all",
                        limit=limit,
                        persist=True,
                    )
                )

                new_items: List[OpportunityModel] = []
                refreshed_items: List[OpportunityModel] = []

                for item in discovered_items:
                    if getattr(item, "is_new", False):
                        new_items.append(item)
                    else:
                        refreshed_items.append(item)

                logger.info(
                    "Discovery complete: %d opportunities processed (%d genuinely new, %d refreshed).",
                    len(discovered_items),
                    len(new_items),
                    len(refreshed_items),
                )

                # -----------------------------------------------------------
                # Step 2: Notify Users of Newly Discovered Matching Opportunities
                # -----------------------------------------------------------
                match_notifications_count = 0
                active_users = await repository.list_users_with_preferences(limit=100)

                if new_items and active_users:
                    for user in active_users:
                        prefs = user.preferences
                        if not prefs or not getattr(prefs, "notifications_enabled", True):
                            continue

                        # Build preference dictionary for matching engine
                        pref_dict = {
                            "preferred_types": getattr(prefs, "preferred_types", ["internship", "hackathon"]),
                            "target_roles": getattr(prefs, "target_roles", []),
                            "domains": getattr(prefs, "domains", []),
                            "preferred_locations": getattr(prefs, "preferred_locations", []),
                            "remote_only": getattr(prefs, "remote_only", False),
                            "skills": getattr(prefs, "skills", []),
                            "education_level": getattr(prefs, "education_level", None),
                            "graduation_year": getattr(prefs, "graduation_year", None),
                            "eligibility_context": getattr(prefs, "eligibility_context", {}),
                            "min_match_score": getattr(prefs, "min_match_score", 0.6),
                        }

                        for opp in new_items:
                            match_res: Optional[OpportunityMatchResult] = matching_service.match_opportunity(
                                opp=opp,
                                preferences=pref_dict,
                            )
                            if match_res and match_res.match_score >= pref_dict["min_match_score"]:
                                title = f"New Opportunity Match: {opp.title}"
                                score_pct = int(match_res.match_score * 100)
                                message = (
                                    f"{opp.organization} posted a new {opp.type} ({opp.title}) "
                                    f"matching your profile with a {score_pct}% match score."
                                )
                                spoken = (
                                    f"New opportunity found: {opp.title} at {opp.organization} "
                                    f"matches your preferences."
                                )
                                priority = "high" if match_res.match_score >= 0.8 else "normal"

                                dedup_key = compute_content_hash(
                                    url=f"user:{user.id}:opp:{opp.id}:new_match",
                                    title=title,
                                )

                                notif_dto = NotificationCreate(
                                    user_id=user.id,
                                    opportunity_id=opp.id,
                                    title=title,
                                    message=message,
                                    spoken_summary=spoken,
                                    type="opportunity",
                                    priority=priority,
                                    custom_content_hash=dedup_key,
                                )

                                created = await repository.create_user_notification(notif_dto)
                                if created:
                                    match_notifications_count += 1

                # -----------------------------------------------------------
                # Step 3: Run Deadline Processing Sweep
                # -----------------------------------------------------------
                deadline_summary = await deadline_service.process_deadlines()

                elapsed_seconds = round(time.perf_counter() - start_time, 2)
                end_dt = datetime.now(timezone.utc)

                cycle_results = {
                    "status": "success",
                    "execution_id": exec_id,
                    "started_at": start_dt.isoformat(),
                    "completed_at": end_dt.isoformat(),
                    "duration_seconds": elapsed_seconds,
                    "discovered_total": len(discovered_items),
                    "new_opportunities_inserted": len(new_items),
                    "existing_opportunities_refreshed": len(refreshed_items),
                    "opportunity_match_notifications": match_notifications_count,
                    "deadline_processing": deadline_summary,
                }

                # Save successful telemetry record in PostgreSQL
                completed_telemetry = {
                    "execution_id": exec_id,
                    "user_id": None,
                    "workflow_type": "scheduled_opportunity_discovery",
                    "status": "completed",
                    "task": "Periodic opportunity discovery, matching, and deadline processing",
                    "input_data": {"batch_size": limit},
                    "result": cycle_results,
                    "error": None,
                    "events": [
                        {
                            "event": "cycle_finished",
                            "timestamp": end_dt.isoformat(),
                            "duration": elapsed_seconds,
                            "summary": cycle_results,
                        }
                    ],
                    "created_at": start_dt,
                    "completed_at": end_dt,
                }
                try:
                    await repository.save_workflow_execution(completed_telemetry)
                except Exception as exc:
                    logger.warning("Failed to save final execution telemetry: %s", exc)

                self._last_execution_summary = cycle_results
                logger.info(
                    "Scheduled discovery cycle %s finished in %.2fs: %d new opps, %d match alerts, %d deadline alerts.",
                    exec_id,
                    elapsed_seconds,
                    len(new_items),
                    match_notifications_count,
                    deadline_summary.get("notifications_created", 0),
                )
                return cycle_results

            except Exception as exc:
                elapsed_seconds = round(time.perf_counter() - start_time, 2)
                end_dt = datetime.now(timezone.utc)
                error_msg = f"{type(exc).__name__}: {str(exc)}"
                logger.error("Scheduled discovery cycle %s failed: %s", exec_id, error_msg, exc_info=True)

                failed_telemetry = {
                    "execution_id": exec_id,
                    "user_id": None,
                    "workflow_type": "scheduled_opportunity_discovery",
                    "status": "failed",
                    "task": "Periodic opportunity discovery, matching, and deadline processing",
                    "input_data": {"batch_size": limit},
                    "result": None,
                    "error": error_msg,
                    "events": [
                        {
                            "event": "cycle_failed",
                            "timestamp": end_dt.isoformat(),
                            "error": error_msg,
                        }
                    ],
                    "created_at": start_dt,
                    "completed_at": end_dt,
                }
                try:
                    await repository.save_workflow_execution(failed_telemetry)
                except Exception:
                    pass

                self._last_execution_summary = {
                    "status": "failed",
                    "execution_id": exec_id,
                    "error": error_msg,
                    "duration_seconds": elapsed_seconds,
                }
                return self._last_execution_summary


# Global singleton scheduler instance
scheduler = BackgroundMonitoringScheduler()
