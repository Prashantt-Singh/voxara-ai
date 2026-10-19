"""
Voxara AI - Preferences REST API Router (Phase 1 & 5)

Endpoints:
- GET /api/preferences: Retrieves current user preferences.
- PUT /api/preferences: Updates preferences (roles, research topics, opportunity types, threshold).
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Query
from app.db import repository
from app.db.models import UserPreferencesModel, UserPreferencesUpdate

logger = logging.getLogger("voxara-preferences-router")

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("", response_model=UserPreferencesModel)
async def get_preferences_endpoint(
    user_id: str = Query(default="default_user", description="Authenticated user ID"),
):
    """Returns current user preferences."""
    return await repository.get_user_preferences(user_id=user_id)


@router.put("", response_model=UserPreferencesModel)
async def update_preferences_endpoint(
    updates: UserPreferencesUpdate,
    user_id: str = Query(default="default_user", description="Authenticated user ID"),
):
    """Updates user preferences and returns the updated record."""
    return await repository.update_user_preferences(user_id=user_id, updates=updates)
