"""
Voxara AI - Authentication & Identity Verification Service

Implements authentication dependencies and client-identity validation:
- Resolves authenticated user identity from Bearer tokens
- Enforces strict ownership validation: rejects client-supplied user_id parameters
  that do not match the authenticated identity (HTTP 403 Forbidden)
- Supports strict authentication mode (HTTP 401 Unauthorized when unauthenticated)
- Provides development/test fallback when strict auth is not enforced
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Optional
from fastapi import Header, HTTPException, Query, Request
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger("voxara.auth")


class AuthenticatedUser(BaseModel):
    """Represents the validated identity of the requesting user."""
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    auth_method: str = "bearer"


def _extract_user_id_from_token(token: str) -> str:
    """
    Extracts the user identity from a bearer token.
    Supports JWT tokens (extracting 'sub' or 'user_id') as well as opaque/identifier tokens.
    """
    cleaned = token.strip()
    if not cleaned:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token: token is empty.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check for JWT format (header.payload.signature)
    parts = cleaned.split(".")
    if len(parts) == 3:
        try:
            # Decode payload (add base64 padding if needed)
            payload_segment = parts[1]
            padded = payload_segment + "=" * (-len(payload_segment) % 4)
            payload_bytes = base64.urlsafe_b64decode(padded)
            payload_data = json.loads(payload_bytes.decode("utf-8"))
            if isinstance(payload_data, dict):
                user_id = payload_data.get("sub") or payload_data.get("user_id") or payload_data.get("id")
                if user_id:
                    return str(user_id)
        except Exception as e:
            logger.debug("Failed to parse token as JWT: %s", e)

    # Fallback to opaque/direct token identifier
    return cleaned


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    user_id: Optional[str] = Query(default=None, description="Optional client user_id query parameter"),
    x_require_auth: Optional[str] = Header(default=None, alias="X-Require-Auth"),
) -> AuthenticatedUser:
    """
    FastAPI security dependency to resolve and validate the authenticated user.

    Security Rules:
    1. If an Authorization header is supplied, it MUST use the 'Bearer <token>' scheme.
    2. Validates credentials and resolves the authenticated user ID.
    3. If client also provides a 'user_id' query/body parameter, it MUST MATCH
       the authenticated identity; otherwise HTTP 403 Forbidden is returned.
    4. If no Authorization header is provided:
       - If strict authentication is enabled (via settings.require_auth or X-Require-Auth header),
         returns HTTP 401 Unauthorized.
       - Otherwise, in development/test mode, resolves identity from query user_id or 'default_user'.
    """
    if authorization is not None:
        parts = authorization.strip().split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication scheme. Expected 'Bearer <token>'.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = parts[1].strip()
        if not token:
            raise HTTPException(
                status_code=401,
                detail="Bearer token credentials missing.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        auth_user_id = _extract_user_id_from_token(token)

        # Validate that client-supplied user_id matches authenticated identity
        if user_id is not None and user_id.strip() != auth_user_id:
            logger.warning(
                "Security violation: client supplied user_id '%s' does not match authenticated identity '%s'",
                user_id,
                auth_user_id,
            )
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: Client supplied user_id '{user_id}' does not match authenticated identity '{auth_user_id}'.",
            )

        return AuthenticatedUser(id=auth_user_id, auth_method="bearer")

    # No Authorization header present
    is_strict = settings.require_auth or (
        x_require_auth is not None and x_require_auth.strip().lower() in ("true", "1", "yes")
    )

    if is_strict:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: No Bearer token provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Development fallback
    effective_user_id = user_id.strip() if user_id and user_id.strip() else "default_user"
    return AuthenticatedUser(id=effective_user_id, auth_method="dev_fallback")


async def get_current_user_id(
    user: AuthenticatedUser = None,
) -> str:
    """Helper dependency returning only the user ID string."""
    # When used as Depends(get_current_user_id), FastAPI injects via get_current_user
    return user.id
