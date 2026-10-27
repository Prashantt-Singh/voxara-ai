"""
Voxara AI - Supabase Authentication & Cryptographic Security Test Suite

Validates all security requirements:
1. Valid Supabase tokens (HS256 & asymmetric ES256/RS256 via JWKS) are accepted.
2. Invalid or tampered tokens are rejected with HTTP 401.
3. Expired tokens are rejected with HTTP 401.
4. Plain-string Bearer tokens are rejected with HTTP 401.
5. Missing tokens on protected personal-data endpoints return HTTP 401:
   - Preferences: GET /api/preferences, POST /api/preferences, PUT /api/preferences
   - Notifications: GET /api/notifications, POST /api/notifications/{id}/confirm, POST /api/notifications/{id}/read
   - Personalized matches: GET /api/opportunities/matches, POST /api/opportunities/matches
   - Saved opportunities: GET /api/opportunities/saved, POST /api/opportunities/saved
6. User data isolation: User A cannot read or modify User B's personal data.
7. Client-supplied user_id spoofing prevention: Client cannot override verified token identity (HTTP 403).
8. Production safety: Authentication cannot be accidentally disabled in production mode.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.main import app
from app.config import settings
from app.db.database import DatabaseManager
from app.db import repository
from app.db.models import OpportunityCreate
from app.services.auth_service import create_test_token, get_current_user

TEST_SECRET = "voxara-super-secure-test-jwt-secret-key-32-chars"


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch) -> Generator[DatabaseManager, None, None]:
    """Provides an isolated database and sets test Supabase secrets."""
    monkeypatch.setattr(settings, "supabase_jwt_secret", TEST_SECRET)
    monkeypatch.setattr(settings, "supabase_jwt_audience", "authenticated")
    monkeypatch.setattr(settings, "require_auth", True)
    monkeypatch.setattr(settings, "environment", "development")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "auth_security_test.db"
        mgr = DatabaseManager(database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}")
        monkeypatch.setattr("app.db.database.db_manager", mgr)
        monkeypatch.setattr("app.db.repository.db_manager", mgr)
        asyncio.run(mgr.init_db())
        yield mgr
        asyncio.run(mgr.close_db())


def create_auth_headers(user_id: str, email: str = None) -> dict:
    token = create_test_token(user_id=user_id, email=email or f"{user_id}@voxara.ai", secret=TEST_SECRET)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test 1: Valid Supabase Tokens Accepted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_supabase_hs256_token_accepted(client: TestClient):
    """Valid HS256 Supabase JWT is cryptographically verified and grants access."""
    headers = create_auth_headers("user_alice")

    # 1. Access user preferences
    res = client.get("/api/preferences", headers=headers)
    assert res.status_code == 200
    assert "opportunity_types" in res.json()

    # 2. Access notifications
    notif_res = client.get("/api/notifications", headers=headers)
    assert notif_res.status_code == 200

    # 3. Access personalized matches
    match_res = client.get("/api/opportunities/matches", headers=headers)
    assert match_res.status_code == 200
    assert match_res.json()["user_id"] == "user_alice"


@pytest.mark.asyncio
async def test_valid_asymmetric_token_via_jwks_accepted(client: TestClient, monkeypatch):
    """
    Valid asymmetric RS256 token is verified against public key (simulating Supabase JWKS).
    """
    # Generate RSA test key pair
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    # Create mock JWKS client
    mock_jwk_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key
    mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key

    monkeypatch.setattr("app.services.auth_service.get_jwks_client", lambda: mock_jwk_client)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": "user_rsa_verified",
        "aud": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "email": "rsa@voxara.ai",
    }
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    rsa_token = jwt.encode(payload, pem_private, algorithm="RS256", headers={"kid": "test-rsa-kid"})

    headers = {"Authorization": f"Bearer {rsa_token}"}
    res = client.get("/api/preferences", headers=headers)
    assert res.status_code == 200
    assert "opportunity_types" in res.json()

    match_res = client.get("/api/opportunities/matches", headers=headers)
    assert match_res.status_code == 200
    assert match_res.json()["user_id"] == "user_rsa_verified"


# ---------------------------------------------------------------------------
# Test 2: Invalid or Tampered Tokens Rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_or_tampered_token_rejected_with_401(client: TestClient):
    """Tokens with tampered signatures or wrong secrets return HTTP 401."""
    valid_token = create_test_token(user_id="user_alice", secret=TEST_SECRET)
    header_b64, payload_b64, sig_b64 = valid_token.split(".")
    tampered_sig = ("X" if sig_b64[0] != "X" else "Y") + sig_b64[1:]
    tampered_token = f"{header_b64}.{payload_b64}.{tampered_sig}"

    res = client.get("/api/preferences", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res.status_code == 401
    assert "verification failed" in res.json()["detail"].lower()

    # Wrong secret (min 32 chars)
    wrong_secret_token = create_test_token(user_id="user_alice", secret="completely-wrong-secret-32-chars-long")
    res_wrong = client.get("/api/preferences", headers={"Authorization": f"Bearer {wrong_secret_token}"})
    assert res_wrong.status_code == 401
    assert "verification failed" in res_wrong.json()["detail"].lower()


@pytest.mark.asyncio
async def test_plain_string_token_rejected_with_401(client: TestClient):
    """Non-JWT plain string tokens are strictly rejected with HTTP 401."""
    res = client.get("/api/preferences", headers={"Authorization": "Bearer plain_string_token"})
    assert res.status_code == 401
    assert "signed Supabase JWT is required" in res.json()["detail"]


# ---------------------------------------------------------------------------
# Test 3: Expired Tokens Rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expired_token_rejected_with_401(client: TestClient):
    """Expired token returns HTTP 401."""
    expired_token = create_test_token(user_id="user_alice", secret=TEST_SECRET, expires_in=-300)
    res = client.get("/api/preferences", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 4: Missing Tokens Rejected on Protected Personal-Data Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_token_rejected_on_all_protected_endpoints(client: TestClient):
    """All personal data endpoints reject unauthenticated requests with HTTP 401."""
    # Preferences
    assert client.get("/api/preferences").status_code == 401
    assert client.post("/api/preferences", json={}).status_code == 401
    assert client.put("/api/preferences", json={}).status_code == 401

    # Notifications
    assert client.get("/api/notifications").status_code == 401
    assert client.post("/api/notifications/test-notif/confirm", json={"confirmation_token": "abc"}).status_code == 401
    assert client.post("/api/notifications/test-notif/read").status_code == 401

    # Matches
    assert client.get("/api/opportunities/matches").status_code == 401
    assert client.post("/api/opportunities/matches", json={}).status_code == 401

    # Saved opportunities
    assert client.get("/api/opportunities/saved").status_code == 401
    assert client.post("/api/opportunities/saved", json={"opportunity_id": "opp1"}).status_code == 401


# ---------------------------------------------------------------------------
# Test 5: User Isolation - User A cannot access User B's personal data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_data_isolation(client: TestClient):
    """User A and User B personal data remain strictly segregated."""
    alice_headers = create_auth_headers("user_alice")
    bob_headers = create_auth_headers("user_bob")

    # Bob sets preferences
    client.put("/api/preferences", headers=bob_headers, json={"opportunity_types": ["fellowship"], "roles": ["Research Fellow"]})

    # Alice sets different preferences
    client.put("/api/preferences", headers=alice_headers, json={"opportunity_types": ["internship"], "roles": ["Software Engineer"]})

    # Verify Bob reads only Bob's preferences
    bob_pref = client.get("/api/preferences", headers=bob_headers).json()
    assert "fellowship" in bob_pref["opportunity_types"]
    assert "Research Fellow" in bob_pref["roles"]

    # Verify Alice reads only Alice's preferences
    alice_pref = client.get("/api/preferences", headers=alice_headers).json()
    assert "internship" in alice_pref["opportunity_types"]
    assert "Software Engineer" in alice_pref["roles"]

    # Verify Bob matches vs Alice matches
    bob_matches = client.get("/api/opportunities/matches", headers=bob_headers).json()
    alice_matches = client.get("/api/opportunities/matches", headers=alice_headers).json()
    assert bob_matches["user_id"] == "user_bob"
    assert alice_matches["user_id"] == "user_alice"


# ---------------------------------------------------------------------------
# Test 6: Client-Supplied user_id Cannot Override Verified Identity (HTTP 403)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_client_supplied_user_id_mismatch_rejected_with_403(client: TestClient):
    """Client attempting to pass another user's ID in query parameters receives HTTP 403 Forbidden."""
    alice_headers = create_auth_headers("user_alice")

    # Spoofed user_id in preferences
    res1 = client.get("/api/preferences?user_id=user_bob", headers=alice_headers)
    assert res1.status_code == 403
    assert "does not match" in res1.json()["detail"]

    # Spoofed user_id in notifications
    res2 = client.get("/api/notifications?user_id=user_bob", headers=alice_headers)
    assert res2.status_code == 403
    assert "does not match" in res2.json()["detail"]

    # Spoofed user_id in matches
    res3 = client.get("/api/opportunities/matches?user_id=user_bob", headers=alice_headers)
    assert res3.status_code == 403
    assert "does not match" in res3.json()["detail"]

    # Spoofed user_id in saved opportunities
    res4 = client.get("/api/opportunities/saved?user_id=user_bob", headers=alice_headers)
    assert res4.status_code == 403
    assert "does not match" in res4.json()["detail"]


# ---------------------------------------------------------------------------
# Test 7: Production Mode Cannot Accidentally Disable Authentication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_production_mode_guarantees_authentication_enforcement(client: TestClient, monkeypatch):
    """
    Even if REQUIRE_AUTH is falsely set to False, production environment forces auth enforcement.
    """
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "require_auth", False)

    # Protected endpoint must still return 401
    res = client.get("/api/preferences")
    assert res.status_code == 401
    assert "Authentication required" in res.json()["detail"]


# ---------------------------------------------------------------------------
# Test 8: Missing Subject ('sub') Claim in JWT Rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_token_missing_sub_rejected_with_401(client: TestClient):
    """A JWT without 'sub' identity claim is rejected."""
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"aud": "authenticated", "iat": int(now.timestamp()), "exp": int((now + timedelta(hours=1)).timestamp())},
        TEST_SECRET,
        algorithm="HS256",
    )
    res = client.get("/api/preferences", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    detail_lower = res.json()["detail"].lower()
    assert "claim" in detail_lower or "sub" in detail_lower or "missing" in detail_lower
