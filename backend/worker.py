"""
Voxara AI - Standalone Opportunity Discovery & Deadline Processing Worker

Entry point for running scheduled discovery and persistent user notification sweeps
independently of the FastAPI web server process.

Usage:
  # Run a single sweep and exit (recommended for external Cron, GitHub Actions, Render Cron):
  python worker.py --once

  # Run a continuous periodic loop in the background:
  python worker.py --loop

  # Specify custom batch size:
  python worker.py --once --batch-size 50
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from typing import Optional

from app.config import settings
from app.db.database import db_manager
from app.services.scheduler_service import scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [voxara-worker] %(message)s",
)
logger = logging.getLogger("voxara-worker")


async def run_once(batch_size: Optional[int] = None) -> int:
    """Runs a single discovery and deadline processing cycle and returns exit code."""
    logger.info("Initializing Voxara AI worker for a single execution cycle...")

    is_db_ok = await db_manager.check_connection()
    if not is_db_ok:
        logger.error("Database connection failed. Ensure DATABASE_URL is valid and accessible.")
        return 1

    try:
        summary = await scheduler.execute_discovery_cycle(batch_size=batch_size, force=True)
        status = summary.get("status")
        if status == "success":
            logger.info("Single worker cycle completed successfully: %s", summary)
            return 0
        elif status == "skipped":
            logger.warning("Worker cycle was skipped: %s", summary.get("reason"))
            return 0
        else:
            logger.error("Worker cycle reported error: %s", summary.get("error"))
            return 1
    except Exception as exc:
        logger.error("Worker execution threw an unhandled exception: %s", exc, exc_info=True)
        return 1
    finally:
        await db_manager.close_db()


async def run_loop(interval_minutes: Optional[int] = None, batch_size: Optional[int] = None) -> None:
    """Runs a continuous periodic loop until interrupted by SIGINT/SIGTERM."""
    interval_min = interval_minutes or settings.scheduler_interval_minutes
    interval_sec = max(10, interval_min * 60)
    logger.info(
        "Starting Voxara AI continuous worker loop (interval: %d minutes / %ds, batch: %s)...",
        interval_min,
        interval_sec,
        batch_size or settings.discovery_batch_size,
    )

    is_db_ok = await db_manager.check_connection()
    if not is_db_ok:
        logger.error("Database connection failed on startup. Exiting.")
        return

    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Termination signal received. Stopping worker loop gracefully...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Signal handlers not implemented on Windows event loop for non-main thread
            pass

    try:
        while not stop_event.is_set():
            logger.info("Worker: Starting scheduled sweep...")
            await scheduler.execute_discovery_cycle(batch_size=batch_size)

            try:
                # Sleep in small slices to respond promptly to shutdown signals
                for _ in range(interval_sec):
                    if stop_event.is_set():
                        break
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user (KeyboardInterrupt).")
    finally:
        await db_manager.close_db()
        logger.info("Voxara AI worker shutdown cleanly.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Voxara AI Opportunity Discovery & Persistent Notification Worker"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--once",
        action="store_true",
        help="Run a single discovery and deadline cycle then exit immediately",
    )
    group.add_argument(
        "--loop",
        action="store_true",
        default=False,
        help="Run continuously in a periodic loop",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Maximum opportunities to fetch per sweep",
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=None,
        help="Minutes between sweeps when running in --loop mode",
    )

    args = parser.parse_args()

    # Default to --loop if neither flag is passed
    if args.once:
        exit_code = asyncio.run(run_once(batch_size=args.batch_size))
        sys.exit(exit_code)
    else:
        asyncio.run(run_loop(interval_minutes=args.interval_minutes, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
