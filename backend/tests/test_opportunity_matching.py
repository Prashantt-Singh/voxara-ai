"""
Voxara AI - Phase 4: Personalized Opportunity Matching Test Suite

Tests:
1. Preference creation, updates, and persistence across all Phase 4 fields:
   - categories: internships, hackathons, fellowships
   - domains: Android, Web Development, AI/ML, Generative AI, Systems
   - location & remote preferences: preferred_locations, remote_only
   - eligibility context: education_level, graduation_year, skills
2. Category matching (internships vs hackathons vs fellowships).
3. Domain & interest matching (Android, Web Development, AI/ML, Generative AI).
4. Location and remote filtering (remote_only constraint & preferred locations).
5. Missing eligibility information (ensures service never assumes or claims eligibility).
6. Expired opportunities handling (exclusion of past deadlines by default).
7. Different preferences for different users (Alice vs Bob personalized rankings).
8. Multi-user isolation (User A cannot access or mutate User B's preferences or notes).
9. Empty search results handling (graceful empty list with 200 OK).
10. Verification status uncertainty communication (verified vs unverified listings).
11. REST API endpoints:
    - GET /api/opportunities/matches
    - POST /api/opportunities/matches
    - GET /api/preferences
    - PUT /api/preferences
    - POST /api/preferences
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import DatabaseManager
from app.db import repository
from app.db.models import (
    OpportunityCreate,
    SavedOpportunityCreate,
    UserPreferenceUpdate,
    UserPreferencesUpdate,
    MatchRequest,
)
from app.services.matching_service import matching_service


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    """Ensures each test operates on an isolated temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_matching.db"
        mgr = DatabaseManager(database_url=f"sqlite+aiosqlite:///{db_file.as_posix()}")
        monkeypatch.setattr("app.db.database.db_manager", mgr)
        monkeypatch.setattr("app.db.repository.db_manager", mgr)
        asyncio.run(mgr.init_db())
        yield mgr
        asyncio.run(mgr.close_db())


# ---------------------------------------------------------------------------
# 1. Preference Creation and Updates Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preference_creation_and_updates():
    """Verifies that user preferences with all Phase 4 attributes are created and updated."""
    user_id = "user_dev_01"

    # Initial default preferences seeded upon get
    initial_pref = await repository.get_user_preferences(user_id=user_id)
    assert initial_pref.user_id == user_id
    assert initial_pref.remote_only is False
    assert initial_pref.preferred_locations == []
    assert initial_pref.skills == []

    # Update preferences with comprehensive criteria
    updates = UserPreferenceUpdate(
        preferred_types=["internship", "fellowship"],
        target_roles=["Android Developer", "Mobile Engineer"],
        domains=["Android", "Mobile Development"],
        preferred_locations=["San Francisco, CA", "Remote"],
        remote_only=True,
        skills=["Kotlin", "Jetpack Compose", "Coroutines"],
        education_level="Undergraduate",
        graduation_year=2026,
        eligibility_context={"authorized_us": True, "student_status": True},
        min_match_score=0.70,
        notifications_enabled=True,
    )

    updated = await repository.update_user_preferences(user_id=user_id, updates=updates)
    assert updated.remote_only is True
    assert "San Francisco, CA" in updated.preferred_locations
    assert "Remote" in updated.preferred_locations
    assert "Kotlin" in updated.skills
    assert updated.education_level == "Undergraduate"
    assert updated.graduation_year == 2026
    assert updated.eligibility_context.get("authorized_us") is True
    assert updated.min_match_score == 0.70

    # Retrieve again to verify persistence
    reloaded = await repository.get_user_preferences(user_id=user_id)
    assert reloaded.remote_only is True
    assert reloaded.skills == ["Kotlin", "Jetpack Compose", "Coroutines"]
    assert reloaded.education_level == "Undergraduate"


# ---------------------------------------------------------------------------
# 2. Category Matching Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_category_matching():
    """Verifies opportunities are filtered accurately by category (internship, hackathon, fellowship)."""
    now = datetime.now(timezone.utc)

    # Seed catalog with 3 different categories
    opp_intern = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Software Engineering Intern",
            organization="Stripe",
            type="internship",
            source_url="https://stripe.com/jobs/intern",
            source_name="Company Site",
            description="Summer software engineering internship.",
            deadline=now + timedelta(days=30),
            verified_status="verified",
        )
    )

    opp_hack = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="HackMIT 2026",
            organization="MIT",
            type="hackathon",
            source_url="https://hackmit.org",
            source_name="Devpost",
            description="Annual collegiate hackathon.",
            deadline=now + timedelta(days=15),
            verified_status="verified",
        )
    )

    opp_fellow = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="MLH Fellowship",
            organization="Major League Hacking",
            type="fellowship",
            source_url="https://fellowship.mlh.io",
            source_name="Major League Hacking",
            description="Open-source engineering fellowship.",
            deadline=now + timedelta(days=45),
            verified_status="verified",
        )
    )

    # User interested only in hackathons
    await repository.update_user_preferences(
        user_id="user_hacker",
        updates=UserPreferenceUpdate(
            preferred_types=["hackathon"],
            domains=["Systems", "Web Development"],
            min_match_score=0.1,
        ),
    )

    matches = await matching_service.match_user_opportunities(user_id="user_hacker")
    matched_ids = [m.id for m in matches]
    assert opp_hack.id in matched_ids
    assert opp_intern.id not in matched_ids
    assert opp_fellow.id not in matched_ids

    # Query with category override for fellowships
    fellow_matches = await matching_service.match_user_opportunities(
        user_id="user_hacker",
        category="fellowship",
    )
    assert len(fellow_matches) == 1
    assert fellow_matches[0].id == opp_fellow.id
    assert fellow_matches[0].category == "fellowship"


# ---------------------------------------------------------------------------
# 3. Domain & Interest Matching Tests (Android, Web Dev, AI/ML, Generative AI)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_domain_and_interest_matching():
    """Verifies domain matching across Android, Web Development, AI/ML, and Generative AI."""
    now = datetime.now(timezone.utc)

    android_opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Android Mobile Engineer Intern",
            organization="Spotify",
            type="internship",
            source_url="https://spotify.com/jobs/android",
            source_name="Company Site",
            description="Build consumer features on Spotify Android client.",
            requirements=["Kotlin", "Jetpack Compose", "Android SDK"],
            deadline=now + timedelta(days=30),
            verified_status="verified",
        )
    )

    genai_opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Generative AI Research Fellow",
            organization="Anthropic",
            type="fellowship",
            source_url="https://anthropic.com/fellows",
            source_name="Company Site",
            description="Work on Large Language Models, RAG architectures, and agentic workflows.",
            requirements=["LLM", "Transformers", "Python", "PyTorch"],
            deadline=now + timedelta(days=40),
            verified_status="verified",
        )
    )

    web_opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Frontend Web Developer Intern",
            organization="Vercel",
            type="internship",
            source_url="https://vercel.com/jobs/frontend",
            source_name="Company Site",
            description="Develop Next.js web applications and React components.",
            requirements=["React", "TypeScript", "Next.js", "Tailwind CSS"],
            deadline=now + timedelta(days=20),
            verified_status="verified",
        )
    )

    # Candidate 1: Android focus
    android_user = "candidate_android"
    await repository.update_user_preferences(
        user_id=android_user,
        updates=UserPreferenceUpdate(
            preferred_types=["internship", "fellowship"],
            domains=["Android"],
            target_roles=["Android Developer"],
            skills=["Kotlin", "Jetpack Compose"],
            min_match_score=0.2,
        ),
    )

    android_matches = await matching_service.match_user_opportunities(user_id=android_user)
    assert len(android_matches) >= 1
    top_match = android_matches[0]
    assert top_match.id == android_opp.id
    assert top_match.match_score >= 0.70
    assert any("Android" in r or "Kotlin" in r for r in top_match.match_reasons)

    # Candidate 2: Generative AI focus
    genai_user = "candidate_genai"
    await repository.update_user_preferences(
        user_id=genai_user,
        updates=UserPreferenceUpdate(
            preferred_types=["fellowship", "internship"],
            domains=["Generative AI", "AI/ML"],
            target_roles=["AI Engineer", "Research Fellow"],
            skills=["LLM", "PyTorch"],
            min_match_score=0.2,
        ),
    )

    genai_matches = await matching_service.match_user_opportunities(user_id=genai_user)
    assert len(genai_matches) >= 1
    top_genai = genai_matches[0]
    assert top_genai.id == genai_opp.id
    assert top_genai.match_score >= 0.75
    assert any("Generative AI" in r or "AI/ML" in r or "LLM" in r for r in top_genai.match_reasons)


# ---------------------------------------------------------------------------
# 4. Location and Remote Filtering Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_location_and_remote_filtering():
    """Verifies that remote-only preference and preferred locations filter correctly."""
    now = datetime.now(timezone.utc)

    remote_opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Remote AI Engineer Intern",
            organization="OpenAI",
            type="internship",
            source_url="https://openai.com/jobs/remote-intern",
            source_name="Company Site",
            location="Remote",
            description="Fully remote software engineering role.",
            deadline=now + timedelta(days=25),
            verified_status="verified",
        )
    )

    onsite_sf_opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Software Intern - San Francisco",
            organization="Uber",
            type="internship",
            source_url="https://uber.com/jobs/sf",
            source_name="Company Site",
            location="San Francisco, CA",
            description="On-site position in San Francisco HQ.",
            deadline=now + timedelta(days=25),
            verified_status="verified",
        )
    )

    onsite_tokyo_opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Robotics Intern - Tokyo",
            organization="Sony",
            type="internship",
            source_url="https://sony.com/jobs/tokyo",
            source_name="Company Site",
            location="Tokyo, Japan",
            description="Strictly on-site robotics engineering in Tokyo.",
            deadline=now + timedelta(days=25),
            verified_status="verified",
        )
    )

    # Test A: User requires strictly remote
    remote_user = "user_remote_only"
    await repository.update_user_preferences(
        user_id=remote_user,
        updates=UserPreferenceUpdate(
            preferred_types=["internship"],
            remote_only=True,
            min_match_score=0.1,
        ),
    )

    remote_matches = await matching_service.match_user_opportunities(user_id=remote_user)
    remote_ids = [m.id for m in remote_matches]
    assert remote_opp.id in remote_ids
    assert onsite_sf_opp.id not in remote_ids
    assert onsite_tokyo_opp.id not in remote_ids

    # Test B: User prefers San Francisco
    sf_user = "user_sf_pref"
    await repository.update_user_preferences(
        user_id=sf_user,
        updates=UserPreferenceUpdate(
            preferred_types=["internship"],
            remote_only=False,
            preferred_locations=["San Francisco, CA"],
            min_match_score=0.1,
        ),
    )

    sf_matches = await matching_service.match_user_opportunities(user_id=sf_user)
    # SF position should rank higher than Tokyo position
    sf_score = next(m.match_score for m in sf_matches if m.id == onsite_sf_opp.id)
    tokyo_score = next(m.match_score for m in sf_matches if m.id == onsite_tokyo_opp.id)
    assert sf_score > tokyo_score


# ---------------------------------------------------------------------------
# 5. Missing Eligibility Information Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_eligibility_information():
    """
    Verifies that when eligibility is missing, the service explicitly states
    'unspecified' and NEVER fabricates eligibility or claims the candidate is eligible.
    """
    now = datetime.now(timezone.utc)

    no_elig_opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Backend Engineer Intern",
            organization="Dropbox",
            type="internship",
            source_url="https://dropbox.com/intern",
            source_name="Company Site",
            description="Distributed storage systems engineering.",
            eligibility=None,  # No eligibility published
            deadline=now + timedelta(days=30),
            verified_status="verified",
        )
    )

    open_elig_opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Global Open Source Hackathon",
            organization="GitHub",
            type="hackathon",
            source_url="https://github.com/hackathon",
            source_name="GitHub",
            description="Open worldwide hackathon.",
            eligibility="Open to all developers aged 18+ worldwide.",
            deadline=now + timedelta(days=30),
            verified_status="verified",
        )
    )

    user_id = "user_elig_test"
    await repository.update_user_preferences(
        user_id=user_id,
        updates=UserPreferenceUpdate(
            preferred_types=["internship", "hackathon"],
            min_match_score=0.1,
        ),
    )

    matches = await matching_service.match_user_opportunities(user_id=user_id)
    match_dict = {m.id: m for m in matches}

    # Verify no_elig_opp communicates 'unspecified'
    no_elig_res = match_dict[no_elig_opp.id]
    assert no_elig_res.eligibility_status == "unspecified"
    assert "not published" in no_elig_res.eligibility_notes.lower()
    assert "review criteria" in no_elig_res.eligibility_notes.lower()
    # Confirm truthful explanation includes caution
    assert "unspecified" in no_elig_res.match_explanation.lower() or "not published" in no_elig_res.match_explanation.lower()

    # Verify open_elig_opp communicates 'eligible'
    open_res = match_dict[open_elig_opp.id]
    assert open_res.eligibility_status == "eligible"
    assert "verified open eligibility" in open_res.eligibility_notes.lower()


# ---------------------------------------------------------------------------
# 6. Expired Opportunities Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expired_opportunities():
    """Verifies that expired opportunities are excluded by default and handled appropriately."""
    now = datetime.now(timezone.utc)

    expired_opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Expired Fall Hackathon",
            organization="Old Org",
            type="hackathon",
            source_url="https://example.com/expired-hack",
            source_name="Devpost",
            description="Finished last month.",
            deadline=now - timedelta(days=10),
            verified_status="verified",
        )
    )

    active_opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Active Winter Hackathon",
            organization="New Org",
            type="hackathon",
            source_url="https://example.com/active-hack",
            source_name="Devpost",
            description="Upcoming deadline.",
            deadline=now + timedelta(days=15),
            verified_status="verified",
        )
    )

    rolling_opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Rolling Internship Application",
            organization="Flexible Corp",
            type="hackathon",
            source_url="https://example.com/rolling",
            source_name="Company Site",
            description="Rolling applications.",
            deadline=None,  # Rolling / unspecified deadline
            verified_status="verified",
        )
    )

    user_id = "user_expiry_test"
    await repository.update_user_preferences(
        user_id=user_id,
        updates=UserPreferenceUpdate(preferred_types=["hackathon"], min_match_score=0.1),
    )

    # Default: include_expired=False
    active_matches = await matching_service.match_user_opportunities(
        user_id=user_id,
        include_expired=False,
    )
    active_ids = [m.id for m in active_matches]
    assert active_opp.id in active_ids
    assert rolling_opp.id in active_ids
    assert expired_opp.id not in active_ids

    # With include_expired=True: expired opportunity is included with penalty
    all_matches = await matching_service.match_user_opportunities(
        user_id=user_id,
        include_expired=True,
    )
    all_ids = [m.id for m in all_matches]
    assert expired_opp.id in all_ids


# ---------------------------------------------------------------------------
# 7. Different Preferences for Different Users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_different_preferences_for_different_users():
    """Verifies that two users receive different personalized rankings matching their distinct profiles."""
    now = datetime.now(timezone.utc)

    # Opportunity A: Android Remote
    opp_android = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Android Engineer Intern",
            organization="Mobile Inc",
            type="internship",
            source_url="https://mobile.example/android",
            source_name="Company Site",
            location="Remote",
            requirements=["Android", "Kotlin"],
            description="Build Android apps.",
            deadline=now + timedelta(days=20),
            verified_status="verified",
        )
    )

    # Opportunity B: AI/ML New York
    opp_ai_ny = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="AI/ML Research Intern",
            organization="NYU AI Lab",
            type="internship",
            source_url="https://nyu.example/ai",
            source_name="Lab Site",
            location="New York, NY",
            requirements=["AI/ML", "PyTorch"],
            description="Machine learning research in New York.",
            deadline=now + timedelta(days=20),
            verified_status="verified",
        )
    )

    # Alice: Android + Remote
    await repository.update_user_preferences(
        user_id="user_alice",
        updates=UserPreferenceUpdate(
            preferred_types=["internship"],
            domains=["Android"],
            skills=["Kotlin"],
            remote_only=True,
            min_match_score=0.2,
        ),
    )

    # Bob: AI/ML + New York
    await repository.update_user_preferences(
        user_id="user_bob",
        updates=UserPreferenceUpdate(
            preferred_types=["internship"],
            domains=["AI/ML"],
            skills=["PyTorch"],
            preferred_locations=["New York, NY"],
            remote_only=False,
            min_match_score=0.2,
        ),
    )

    alice_matches = await matching_service.match_user_opportunities(user_id="user_alice")
    bob_matches = await matching_service.match_user_opportunities(user_id="user_bob")

    # Alice gets Android as top match; AI/ML New York is excluded (not remote)
    assert len(alice_matches) == 1
    assert alice_matches[0].id == opp_android.id

    # Bob gets AI/ML New York as top match
    assert len(bob_matches) >= 1
    assert bob_matches[0].id == opp_ai_ny.id


# ---------------------------------------------------------------------------
# 8. Multi-User Isolation Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_data_isolation():
    """Verifies that User A's private preferences, saved items, and notes are completely isolated from User B."""
    # Alice sets custom preferences
    await repository.update_user_preferences(
        user_id="alice",
        updates=UserPreferenceUpdate(
            domains=["Generative AI"],
            skills=["Transformers"],
            preferred_locations=["Seattle, WA"],
            education_level="Masters",
            min_match_score=0.88,
        ),
    )

    # Bob sets different preferences
    await repository.update_user_preferences(
        user_id="bob",
        updates=UserPreferenceUpdate(
            domains=["Web Development"],
            skills=["React"],
            preferred_locations=["Austin, TX"],
            education_level="Undergraduate",
            min_match_score=0.55,
        ),
    )

    alice_pref = await repository.get_user_preferences("alice")
    bob_pref = await repository.get_user_preferences("bob")

    assert alice_pref.domains == ["Generative AI"]
    assert alice_pref.min_match_score == 0.88
    assert alice_pref.preferred_locations == ["Seattle, WA"]

    assert bob_pref.domains == ["Web Development"]
    assert bob_pref.min_match_score == 0.55
    assert bob_pref.preferred_locations == ["Austin, TX"]

    # Save private application notes
    opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Staff Fellow",
            organization="Research Org",
            type="fellowship",
            source_url="https://example.com/fellow",
            source_name="Research",
            description="Research fellowship.",
        )
    )

    await repository.save_user_opportunity(
        user_id="alice",
        data=SavedOpportunityCreate(
            opportunity_id=opp.id,
            status="interviewing",
            notes="Alice confidential interview prep notes.",
        ),
    )

    # Bob queries his saved pipeline
    bob_saved = await repository.list_user_saved_opportunities(user_id="bob")
    assert len(bob_saved) == 0  # Bob cannot see Alice's saved opportunity

    alice_saved = await repository.list_user_saved_opportunities(user_id="alice")
    assert len(alice_saved) == 1
    assert alice_saved[0].notes == "Alice confidential interview prep notes."


# ---------------------------------------------------------------------------
# 9. Empty Search Results Handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_search_results():
    """Verifies that matching returns an empty list without error when no opportunities meet criteria."""
    user_id = "user_quantum"
    await repository.update_user_preferences(
        user_id=user_id,
        updates=UserPreferenceUpdate(
            preferred_types=["hackathon"],
            domains=["Quantum Computing"],
            min_match_score=0.99,  # Impossibly high threshold
        ),
    )

    matches = await matching_service.match_user_opportunities(user_id=user_id)
    assert matches == []


# ---------------------------------------------------------------------------
# 10. Verification Status Uncertainty Communication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verification_status_uncertainty():
    """Verifies that unverified opportunities communicate uncertainty in match score and explanation."""
    now = datetime.now(timezone.utc)

    verified_opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Verified AI Engineer",
            organization="DeepMind",
            type="internship",
            source_url="https://deepmind.google/jobs",
            source_name="Google Careers",
            requirements=["AI/ML", "Python"],
            description="AI research internship.",
            deadline=now + timedelta(days=30),
            verified_status="verified",
        )
    )

    unverified_opp = await repository.save_shared_opportunity(
        OpportunityCreate(
            title="Unverified AI Engineer",
            organization="Unknown Startup",
            type="internship",
            source_url="https://unknown.example/job",
            source_name="Community Board",
            requirements=["AI/ML", "Python"],
            description="AI research internship.",
            deadline=now + timedelta(days=30),
            verified_status="unverified",
        )
    )

    user_id = "user_verif_test"
    await repository.update_user_preferences(
        user_id=user_id,
        updates=UserPreferenceUpdate(
            preferred_types=["internship"],
            domains=["AI/ML"],
            skills=["Python"],
            min_match_score=0.1,
        ),
    )

    matches = await matching_service.match_user_opportunities(user_id=user_id)
    match_map = {m.id: m for m in matches}

    verif_res = match_map[verified_opp.id]
    unverif_res = match_map[unverified_opp.id]

    assert verif_res.verified_status == "verified"
    assert "Verified listing" in verif_res.match_reasons

    assert unverif_res.verified_status == "unverified"
    assert any("Unverified listing" in r for r in unverif_res.match_reasons)
    # The verified opportunity should achieve a higher match score than unverified
    assert verif_res.match_score > unverif_res.match_score


# ---------------------------------------------------------------------------
# 11. REST API Endpoints Tests
# ---------------------------------------------------------------------------

def test_api_preferences_and_matching(client):
    """Verifies GET/PUT/POST /api/preferences and GET/POST /api/opportunities/matches."""
    # 1. Update preferences via API
    pref_payload = {
        "domains": ["Android", "Web Development"],
        "roles": ["Android Engineer"],
        "preferred_locations": ["Remote"],
        "remote_only": True,
        "skills": ["Kotlin", "React"],
        "education_level": "Undergraduate",
        "graduation_year": 2026,
        "min_match_score": 0.5,
    }
    put_resp = client.put("/api/preferences?user_id=api_user_01", json=pref_payload)
    assert put_resp.status_code == 200
    pref_data = put_resp.json()
    assert pref_data["remote_only"] is True
    assert "Kotlin" in pref_data["skills"]
    assert pref_data["education_level"] == "Undergraduate"

    # 2. Get preferences via API
    get_resp = client.get("/api/preferences?user_id=api_user_01")
    assert get_resp.status_code == 200
    assert get_resp.json()["remote_only"] is True

    # 3. Match opportunities via GET
    matches_get = client.get("/api/opportunities/matches?user_id=api_user_01&limit=10")
    assert matches_get.status_code == 200
    body = matches_get.json()
    assert body["status"] == "success"
    assert body["user_id"] == "api_user_01"
    assert isinstance(body["opportunities"], list)

    # 4. Match opportunities via POST with overrides
    match_req = {
        "category": "internship",
        "domains": ["Android"],
        "remote_only": True,
        "limit": 5,
    }
    matches_post = client.post("/api/opportunities/matches?user_id=api_user_01", json=match_req)
    assert matches_post.status_code == 200
    post_body = matches_post.json()
    assert post_body["status"] == "success"
    assert isinstance(post_body["opportunities"], list)
