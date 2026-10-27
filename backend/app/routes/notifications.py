"""
Voxara AI - Notifications & Confirmation Gate REST API Router (Phase 5)

Endpoints:
- GET /api/notifications: Retrieves pending or recent notifications for the authenticated user.
- POST /api/notifications/{id}/confirm: Confirms a consequential action using confirmation token.
- POST /api/notifications/{id}/read: Marks a notification as read or dismissed.
"""

from __future__ import annotations

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import repository
from app.db.models import NotificationModel, NotificationRead
from app.services.auth_service import AuthenticatedUser, get_current_user

logger = logging.getLogger("voxara-notifications-router")

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class ConfirmationRequest(BaseModel):
    confirmation_token: str = Field(..., description="Confirmation token issued for human verification")


@router.get("", response_model=List[NotificationModel])
async def list_notifications_endpoint(
    unread_only: bool = Query(default=False, description="Filter unread notifications only"),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Returns notifications strictly scoped to the authenticated user."""
    items = await repository.list_user_notifications(user_id=current_user.id, unread_only=unread_only, limit=limit)
    return [repository._notif_to_model(n) for n in items]


@router.post("/read-all")
async def mark_all_read_endpoint(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Marks all notifications as read for the authenticated user."""
    count = await repository.mark_all_user_notifications_read(user_id=current_user.id)
    return {"status": "success", "marked_count": count}


@router.post("/{notification_id}/confirm")
async def confirm_notification_endpoint(
    notification_id: str,
    req: ConfirmationRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Human-in-the-loop confirmation gate:
    Validates confirmation token and commits the consequential action for authenticated user.
    """
    success = await repository.confirm_user_notification(
        user_id=current_user.id,
        notification_id=notification_id,
        confirmation_token=req.confirmation_token,
    )
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Confirmation failed. Invalid notification ID or mismatched confirmation token.",
        )
    return {"status": "confirmed", "notification_id": notification_id}


@router.post("/{notification_id}/read")
@router.patch("/{notification_id}/read")
async def mark_read_endpoint(
    notification_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Marks a notification as delivered/read for the authenticated user."""
    success = await repository.mark_notification_read(user_id=current_user.id, notification_id=notification_id)
    return {"status": "success", "marked": success}
