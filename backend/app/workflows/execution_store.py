"""
Voxara AI - Workflow Execution Store (Step 4C: Observability & Event Tracking)

Provides a lightweight, thread-safe in-memory store for tracking workflow
executions, node lifecycle events, status, durations, and errors.
Enables unified inspection of workflow executions initiated via both
REST API and LiveKit Voice Agent tools.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional

logger = logging.getLogger("voxara-execution-store")


class WorkflowExecutionStore:
    """
    Thread-safe in-memory store holding the most recent workflow execution states.
    Maintains bounded memory usage via an LRU eviction policy.
    """

    def __init__(self, max_records: int = 100):
        self._records: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_records = max_records

    def save_execution(self, record: Dict[str, Any]) -> None:
        """
        Saves or updates a workflow execution record in-memory and in SQLite.
        """
        exec_id = record.get("execution_id")
        if not exec_id:
            logger.warning("Attempted to store execution without an execution_id.")
            return

        with self._lock:
            if exec_id in self._records:
                del self._records[exec_id]
            self._records[exec_id] = record
            if len(self._records) > self._max_records:
                # Evict oldest record
                self._records.popitem(last=False)

        # Asynchronously or synchronously persist to database
        try:
            from app.db.repository import _sync_save_execution
            _sync_save_execution(record)
        except Exception as exc:
            logger.debug("Failed to persist execution %s to DB: %s", exec_id, exc)

    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a workflow execution record by its execution_id from memory or SQLite.
        """
        with self._lock:
            cached = self._records.get(execution_id)
            if cached:
                return cached

        try:
            from app.db.repository import _sync_get_execution
            return _sync_get_execution(execution_id)
        except Exception:
            return None

    def list_executions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Returns recent workflow executions, ordered from most recent to oldest.
        """
        with self._lock:
            items = list(self._records.values())
            items.reverse()
            return items[:limit]

    def clear(self) -> None:
        """Clears all stored execution records (useful for test isolation)."""
        with self._lock:
            self._records.clear()


# Global singleton instance
execution_store = WorkflowExecutionStore()
