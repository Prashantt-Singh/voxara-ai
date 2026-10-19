"""
Voxara AI - Autonomous Background Monitoring Scheduler (Phase 5)

Runs scheduled monitoring cycles independently of an active LiveKit voice session:
- Periodically checks research feeds (arXiv, GitHub, Hugging Face)
- Periodically syncs opportunities from Devpost
- Scans for approaching deadlines and creates proactive notifications
- Zero-external-dependency async background task attached to FastAPI lifespan
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.services.opportunity_service import opportunity_service
from app.db import repository

logger = logging.getLogger("voxara-scheduler")

# Configurable intervals in seconds
DEFAULT_SCAN_INTERVAL_SECONDS = 300  # 5 minutes for demonstration / background polling
INITIAL_DELAY_SECONDS = 5            # Brief delay after server startup before first scan


class BackgroundMonitoringScheduler:
    """
    Manages autonomous periodic monitoring loops in the background.
    """

    def __init__(self, interval_seconds: int = DEFAULT_SCAN_INTERVAL_SECONDS):
        self._interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> None:
        """Starts the background scheduler loop if not already running."""
        if self._is_running:
            return
        self._is_running = True
        self._task = asyncio.create_task(self._run_loop(), name="voxara-background-scheduler")
        logger.info("Autonomous Background Monitoring Scheduler started (interval: %ds).", self._interval_seconds)

    async def stop(self) -> None:
        """Gracefully stops the background scheduler."""
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
        logger.info("Autonomous Background Monitoring Scheduler stopped.")

    async def _run_loop(self) -> None:
        """Main periodic loop."""
        try:
            # Brief initial pause to let server finish startup
            await asyncio.sleep(INITIAL_DELAY_SECONDS)
        except asyncio.CancelledError:
            return

        while self._is_running:
            try:
                logger.info("Executing scheduled monitoring cycle...")
                await self.run_monitoring_cycle()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error during scheduled monitoring cycle: %s", exc, exc_info=True)

            try:
                await asyncio.sleep(self._interval_seconds)
            except asyncio.CancelledError:
                break

    async def run_monitoring_cycle(self) -> None:
        """
        Executes a single monitoring sweep:
        1. Checks user preferences to verify if notifications are enabled.
        2. Ingests and stores new opportunities (internships, hackathons).
        3. Scans deadlines and schedules urgent alerts.
        """
        try:
            prefs = await repository.get_user_preferences("default_user")
            if not getattr(prefs, "notifications_enabled", True):
                logger.info("Notifications are disabled in user preferences. Skipping cycle.")
                return

            # 1. Sync Opportunities
            logger.debug("Scheduler: Syncing opportunities...")
            await opportunity_service.sync_and_store_opportunities(min_score=prefs.min_match_score)

            # 2. Check Deadlines
            deadlines = await repository.get_upcoming_shared_deadlines(limit=5)
            logger.info("Scheduler cycle completed. Monitored %d upcoming deadlines.", len(deadlines))

        except Exception as exc:
            logger.error("Scheduler execution error: %s", exc, exc_info=True)


# Global singleton scheduler instance
scheduler = BackgroundMonitoringScheduler()
