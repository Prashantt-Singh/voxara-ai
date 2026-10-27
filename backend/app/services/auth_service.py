"""
Voxara AI - Supabase Cryptographic Authentication & Identity Verification Service

Implements verified authentication dependencies and identity validation:
- Cryptographic JWT verification for Supabase access tokens (ES256/RS256 via JWKS and HS256 via secret)
- Validates signature, expiration, audience, issuer, and required subject identity ('sub')
- Enforces strict ownership validation: rejects client-supplied user_id parameters
  that do not match the authenticated identity (HTTP 403 Forbidden)
- Rejects plain-string Bearer tokens (HTTP 401 Unauthorized)
- Rejects expired, tampered, or untrusted tokens (HTTP 401 Unauthorized)
- Guarantees production authentication cannot be disabled accidentally
- Prevents development identity fallbacks in production paths
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, Query, Request
from pydantic import BaseModel
import jwt
from jwt import PyJWKClient, PyJWKClientError, InvalidTokenError, ExpiredSignatureError, InvalidSignatureError

from app.config import settings

logger = logging.getLogger("voxara.auth")

# Module-level cached JWKS client instance
_cached_jwks_client: Optional[PyJWKClient] = None
_cached_jwks_url: Optional[str] = None


class AuthenticatedUser(BaseModel):
    """Represents the cryptographically verified identity of the requesting user."""
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    auth_method: str = "supabase_jwt"


def get_jwks_client() -> Optional[PyJWKClient]:
    """
    Returns a cached PyJWKClient instance pointing to Supabase's JWKS endpoint.
    Caches keys in-memory for 1 hour with automatic refresh on cache miss.
    """
    global _cached_jwks_client, _cached_jwks_url

    jwks_url = (settings.supabase_jwks_url or "").strip()
    if not jwks_url and settings.supabase_url:
        clean_url = settings.supabase_url.strip().rstrip("/")
        jwks_url = f"{clean_url}/auth/v1/.well-known/jwks.json"

    if not jwks_url:
        return None

    if _cached_jwks_client is None or _cached_jwks_url != jwks_url:
        _cached_jwks_client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
        _cached_jwks_url = jwks_url

    return _cached_jwks_client


def verify_supabase_token(token: str) -> AuthenticatedUser:
    """
    Cryptographically verifies a Supabase access token and extracts the authenticated identity.

    Security Validations:
    1. Structure: Must be a well-formed 3-part dot-separated JWT. Plain string tokens are rejected.
    2. Header: Extracts 'alg' and 'kid'. Rejects unsupported or missing algorithms.
    3. Signature:
       - If ES256 / RS256: Resolves the public key from the Supabase JWKS endpoint.
       - If HS256: Verifies against the configured SUPABASE_JWT_SECRET.
    4. Expiration: Rejects expired tokens with HTTP 401.
    5. Audience: Validates audience matches SUPABASE_JWT_AUDIENCE (default: 'authenticated').
    6. Claims: Validates subject ('sub') is present, non-empty, and valid UUID/string.
    """
    cleaned = token.strip()
    if not cleaned:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token: token is empty.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Structure check: Reject plain string identifiers immediately
    parts = cleaned.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token format. A cryptographically signed Supabase JWT is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Extract header without verifying payload yet to determine key resolution
    try:
        header = jwt.get_unverified_header(cleaned)
    except Exception as exc:
        logger.warning("Failed to parse token header: %s", type(exc).__name__)
        raise HTTPException(
            status_code=401,
            detail="Malformed token header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    alg = header.get("alg")
    if not alg or not isinstance(alg, str):
        raise HTTPException(
            status_code=401,
            detail="Malformed token: missing or invalid 'alg' algorithm header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Resolve key according to algorithm
    verification_key: Any = None
    allowed_algorithms = [alg]

    if alg in ("ES256", "RS256"):
        jwk_client = get_jwks_client()
        if jwk_client is not None:
            try:
                signing_key = jwk_client.get_signing_key_from_jwt(cleaned)
                verification_key = signing_key.key
            except Exception as e:
                logger.warning("JWKS key resolution failed: %s", type(e).__name__)
                raise HTTPException(
                    status_code=401,
                    detail="Token verification failed: unable to resolve public key from Supabase JWKS.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        elif settings.supabase_jwt_secret:
            # Fallback for custom RSA/EC public key configured via secret
            verification_key = settings.supabase_jwt_secret
        else:
            raise HTTPException(
                status_code=401,
                detail="Token verification failed: Supabase JWKS or public key is not configured.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    elif alg == "HS256":
        secret = (settings.supabase_jwt_secret or "").strip()
        if not secret:
            raise HTTPException(
                status_code=401,
                detail="Token verification failed: Supabase JWT secret is not configured.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        verification_key = secret

    else:
        raise HTTPException(
            status_code=401,
            detail=f"Unsupported token algorithm '{alg}'. Only ES256, RS256, and HS256 are permitted.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Cryptographic decoding and claims verification
    decode_options: Dict[str, Any] = {
        "require": ["exp", "sub"],
        "verify_signature": True,
        "verify_exp": True,
    }

    audience = settings.supabase_jwt_audience.strip() if settings.supabase_jwt_audience else None
    if not audience:
        decode_options["verify_aud"] = False

    issuer = settings.supabase_jwt_issuer.strip() if settings.supabase_jwt_issuer else None

    try:
        payload = jwt.decode(
            cleaned,
            key=verification_key,
            algorithms=allowed_algorithms,
            options=decode_options,
            audience=audience,
            issuer=issuer,
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Authentication token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token signature: verification failed.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token audience claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidIssuerError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token issuer claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid authentication token: {type(exc).__name__}.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as exc:
        logger.warning("Unexpected error during JWT verification: %s", type(exc).__name__)
        raise HTTPException(
            status_code=401,
            detail="Authentication token verification failed.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 5. Validate subject claim
    user_id = payload.get("sub")
    if not user_id or not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(
            status_code=401,
            detail="Token missing subject identity ('sub') claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_metadata = payload.get("user_metadata") or {}
    name = user_metadata.get("full_name") or user_metadata.get("name") or payload.get("name")

    return AuthenticatedUser(
        id=user_id.strip(),
        email=payload.get("email"),
        name=name,
        role=payload.get("role"),
        auth_method="supabase_jwt",
    )


def create_test_token(
    user_id: str,
    email: Optional[str] = None,
    secret: Optional[str] = None,
    expires_in: int = 3600,
    audience: Optional[str] = "authenticated",
    issuer: Optional[str] = None,
    algorithm: str = "HS256",
) -> str:
    """
    Generates a cryptographically signed test JWT for unit and integration testing.
    Uses the provided secret or settings.supabase_jwt_secret.
    """
    now = datetime.now(timezone.utc)
    signing_secret = secret or settings.supabase_jwt_secret or "voxara-test-secret-key-for-unit-tests"
    payload = {
        "sub": user_id,
        "aud": audience or "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    if email:
        payload["email"] = email
    if issuer:
        payload["iss"] = issuer

    return jwt.encode(payload, signing_secret, algorithm=algorithm)


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    user_id: Optional[str] = Query(default=None, description="Optional client user_id query parameter to validate"),
    x_require_auth: Optional[str] = Header(default=None, alias="X-Require-Auth"),
) -> AuthenticatedUser:
    """
    FastAPI security dependency to resolve and cryptographically validate the authenticated user.

    Security Guarantees:
    1. If an Authorization header is supplied, it MUST use the 'Bearer <token>' scheme.
    2. Validates credentials cryptographically against Supabase keys and resolves the authenticated user ID.
    3. If client also provides a 'user_id' query/body parameter, it MUST MATCH
       the authenticated identity; otherwise HTTP 403 Forbidden is returned.
    4. If no Authorization header is provided:
       - In production, returns HTTP 401 Unauthorized unconditionally.
       - If strict authentication is enabled (settings.is_auth_enforced or X-Require-Auth header),
         returns HTTP 401 Unauthorized.
       - In dev/test when require_auth=False, only non-production environments may use the fallback.
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

        # Cryptographically verify the token
        auth_user = verify_supabase_token(token)

        # Validate that client-supplied user_id matches authenticated identity
        if user_id is not None and user_id.strip() != auth_user.id:
            logger.warning(
                "Security violation: client supplied user_id '%s' does not match authenticated identity '%s'",
                user_id,
                auth_user.id,
            )
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: Client supplied user_id '{user_id}' does not match authenticated identity '{auth_user.id}'.",
            )

        return auth_user

    # No Authorization header present
    is_strict = settings.is_auth_enforced or (
        x_require_auth is not None and x_require_auth.strip().lower() in ("true", "1", "yes")
    )

    if is_strict or settings.is_production:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: No Bearer token provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Insecure development fallback is strictly forbidden in production
    effective_user_id = user_id.strip() if user_id and user_id.strip() else "default_user"
    return AuthenticatedUser(id=effective_user_id, auth_method="dev_fallback")


async def get_current_user_id(
    current_user: AuthenticatedUser = None,
) -> str:
    """Helper dependency returning only the user ID string."""
    return current_user.id
