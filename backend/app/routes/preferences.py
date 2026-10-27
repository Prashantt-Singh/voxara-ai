"""
Voxara AI - Preferences REST API Router (Phase 1 & 5)

Endpoints:
- GET /api/preferences: Retrieves current authenticated user preferences.
- PUT /api/preferences: Updates preferences (roles, research topics, opportunity types, threshold).
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends
from app.db import repository
from app.db.models import UserPreferencesModel, UserPreferencesUpdate
from app.services.auth_service import AuthenticatedUser, get_current_user

logger = logging.getLogger("voxara-preferences-router")

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("", response_model=UserPreferencesModel)
async def get_preferences_endpoint(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Returns current user preferences strictly scoped to authenticated user."""
    return await repository.get_user_preferences(user_id=current_user.id)


@router.post("", response_model=UserPreferencesModel)
async def create_preferences_endpoint(
    preferences: UserPreferencesUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Initializes or sets user preferences with provided criteria."""
    return await repository.update_user_preferences(user_id=current_user.id, updates=preferences)


@router.put("", response_model=UserPreferencesModel)
async def update_preferences_endpoint(
    updates: UserPreferencesUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Updates user preferences and returns the updated record."""
    return await repository.update_user_preferences(user_id=current_user.id, updates=updates)
