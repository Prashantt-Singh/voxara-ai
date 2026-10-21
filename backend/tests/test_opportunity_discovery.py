"""
Voxara AI - Opportunity Discovery Engine Test Suite (Phase 2)

Tests:
1. Hackathon discovery & normalization (Devpost API).
2. Internship discovery & normalization (SimplifyJobs & Arbeitnow APIs).
3. Missing optional fields handling (ensures unavailable fields are None, never invented).
4. Duplicate prevention across repeated searches.
5. Database persistence and retrieval of discovered opportunities (including application_url & location).
6. Separate discovery paths for internships vs hackathons.
7. API endpoints:
   - POST /api/opportunities/discover/internships
   - POST /api/opportunities/discover/hackathons
   - POST /api/opportunities/discover
   - Error handling & status codes.
8. Live source smoke test for verified endpoints.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import DatabaseManager
from app.db import repository
from app.db.models import OpportunityModel, compute_content_hash
from app.services.opportunity_service import OpportunityDiscoveryService, opportunity_service


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
        db_file = Path(tmpdir) / "test_discovery.db"
        mgr = DatabaseManager(database_url=f"sqlite+aiosqlite:///{db_file.as_posix()}")
        monkeypatch.setattr("app.db.database.db_manager", mgr)
        monkeypatch.setattr("app.db.repository.db_manager", mgr)
        asyncio.run(mgr.init_db())
        yield mgr
        asyncio.run(mgr.close_db())


# ---------------------------------------------------------------------------
# Sample Mock Payloads
# ---------------------------------------------------------------------------

MOCK_DEVPOST_DATA = {
    "hackathons": [
        {
            "id": 1001,
            "title": "Global AI Agent Hackathon 2026",
            "url": "https://aiagents2026.devpost.com",
            "organization_name": "Google Cloud & Anthropic",
            "submission_period_dates": "Aug 15 - Oct 28, 2026",
            "prize_amount": "<span>$50,000</span> in cash prizes",
            "displayed_location": {"location": "Online"},
            "eligibility_requirement": "Open to all developers aged 18+ worldwide.",
            "themes": [{"name": "AI/Machine Learning"}, {"name": "Productivity"}],
        },
        {
            "id": 1002,
            "title": "MIT Hack Reality",
            "url": "https://hackreality.devpost.com",
            "organization_name": "MIT Reality Labs",
            "submission_period_dates": "Nov 12, 2026",
            "prize_amount": "$25,000",
            "displayed_location": {"location": "Cambridge, MA"},
            "eligibility_requirement": None,
            "themes": [{"name": "AR/VR"}, {"name": "Hardware"}],
        },
    ]
}

MOCK_SIMPLIFY_DATA = [
    {
        "source": "Simplify",
        "category": "Software",
        "company_name": "Acme Robotics",
        "title": "Autonomous Systems Software Intern",
        "active": True,
        "terms": ["Summer 2026"],
        "url": "https://jobs.smartrecruiters.com/Acme/12345",
        "company_url": "https://acme.com",
        "locations": ["San Francisco, CA", "Remote"],
        "degrees": ["Bachelor's", "Master's"],
        "sponsorship": "Available",
    },
    {
        "source": "Simplify",
        "category": "Machine Learning",
        "company_name": "DeepData AI",
        "title": "AI Research Engineering Intern",
        "active": True,
        "terms": ["Summer 2026", "Fall 2026"],
        "url": "https://deepdata.greenhouse.io/jobs/67890",
        "company_url": "https://deepdata.ai",
        "locations": ["New York, NY"],
        "degrees": ["Master's", "PhD"],
        "sponsorship": None,
    },
    {
        "source": "Simplify",
        "category": "Hardware",
        "company_name": "Inactive Corp",
        "title": "Closed Internship",
        "active": False,
        "terms": ["Summer 2025"],
        "url": "https://inactive.com/job",
        "locations": ["Boston, MA"],
    },
]

MOCK_ARBEITNOW_DATA = {
    "data": [
        {
            "slug": "ai-developer-intern",
            "company_name": "CloudScale Inc",
            "title": "Junior Python / Backend Intern",
            "description": "<p>Join our <strong>backend team</strong> working on Python APIs and distributed queues.</p>",
            "remote": True,
            "url": "https://arbeitnow.com/view/ai-developer-intern",
            "tags": ["Python", "FastAPI", "PostgreSQL"],
            "location": "Berlin, Germany",
        }
    ]
}


# ---------------------------------------------------------------------------
# Unit & Integration Tests: Source Normalization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discover_hackathons_devpost_normalization():
    """
    Verifies that Devpost hackathons are parsed and accurately normalized
    into the OpportunityModel schema with all fields populated.
    """
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_DEVPOST_DATA

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    service = OpportunityDiscoveryService(client=mock_client)
    hackathons = await service.discover_hackathons(limit=2, persist=False)

    assert len(hackathons) == 2

    # Check Item 1
    h1 = hackathons[0]
    assert h1.title == "Global AI Agent Hackathon 2026"
    assert h1.type == "hackathon"
    assert h1.organization == "Google Cloud & Anthropic"
    assert h1.source_url == "https://aiagents2026.devpost.com"
    assert h1.application_url == "https://aiagents2026.devpost.com"
    assert h1.location == "Online"
    assert h1.source_name == "Devpost"
    assert h1.deadline is not None
    assert "2026-10-28" in h1.deadline
    assert h1.eligibility == "Open to all developers aged 18+ worldwide."
    assert "AI/Machine Learning" in h1.requirements
    assert "$50,000" in h1.prize_or_salary
    assert "<" not in h1.prize_or_salary  # HTML stripped
    assert h1.discovered_at is not None

    # Check Item 2
    h2 = hackathons[1]
    assert h2.title == "MIT Hack Reality"
    assert h2.organization == "MIT Reality Labs"
    assert h2.location == "Cambridge, MA"
    assert "2026-11-12" in h2.deadline


@pytest.mark.asyncio
async def test_discover_internships_simplifyjobs_normalization():
    """
    Verifies that tech internships from SimplifyJobs are parsed,
    filtered for active status, and normalized with direct application URLs.
    """
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_SIMPLIFY_DATA

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    service = OpportunityDiscoveryService(client=mock_client)
    internships = await service.fetch_simplify_internships(limit=5)

    # Inactive item must be filtered out
    assert len(internships) == 2

    i1 = internships[0]
    assert i1.title == "Autonomous Systems Software Intern"
    assert i1.organization == "Acme Robotics"
    assert i1.type == "internship"
    assert i1.application_url == "https://jobs.smartrecruiters.com/Acme/12345"  # Direct company portal
    assert i1.source_url == "https://jobs.smartrecruiters.com/Acme/12345"
    assert i1.location == "San Francisco, CA, Remote"
    assert i1.source_name == "SimplifyJobs"
    assert i1.deadline is None  # Not provided in Simplify; must NOT be fabricated
    assert "Bachelor's" in i1.eligibility
    assert "Summer 2026" in i1.requirements
    assert i1.discovered_at is not None


@pytest.mark.asyncio
async def test_discover_internships_arbeitnow_normalization():
    """
    Verifies that Arbeitnow tech internships are parsed with remote status
    and clean stripped HTML descriptions.
    """
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_ARBEITNOW_DATA

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    service = OpportunityDiscoveryService(client=mock_client)
    internships = await service.fetch_arbeitnow_internships(limit=5)

    assert len(internships) == 1
    job = internships[0]
    assert job.title == "Junior Python / Backend Intern"
    assert job.organization == "CloudScale Inc"
    assert job.type == "internship"
    assert "Remote" in job.location
    assert "<p>" not in job.description  # HTML tags removed
    assert "Python APIs" in job.description
    assert job.source_name == "Arbeitnow"
    assert job.deadline is None
    assert "Python" in job.requirements


@pytest.mark.asyncio
async def test_missing_optional_fields_handling():
    """
    Ensures missing optional fields (deadline, location, eligibility, prizes)
    are preserved as None and never invented or hallucinated.
    """
    minimal_devpost_data = {
        "hackathons": [
            {
                "title": "Minimal Hackathon",
                "url": "https://minimal.devpost.com",
                "organization_name": "Barebones Team",
                # Omit submission_period_dates, displayed_location, eligibility_requirement, prize_amount, themes
            }
        ]
    }

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = minimal_devpost_data

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    service = OpportunityDiscoveryService(client=mock_client)
    items = await service.fetch_devpost_hackathons(limit=1)

    assert len(items) == 1
    opp = items[0]
    assert opp.title == "Minimal Hackathon"
    assert opp.organization == "Barebones Team"
    assert opp.deadline is None  # Accurately None
    assert opp.location is None  # Accurately None
    assert opp.eligibility is None  # Accurately None
    assert opp.prize_or_salary is None  # Accurately None
    assert opp.requirements == []  # Accurately empty


# ---------------------------------------------------------------------------
# Duplicate Prevention & Database Persistence Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_prevention_on_rediscovery(temp_db):
    """
    Verifies that running discovery multiple times does not insert duplicate rows
    into the database, updating mutable fields cleanly instead.
    """
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_DEVPOST_DATA

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    service = OpportunityDiscoveryService(client=mock_client)

    # First discovery run (with persistence)
    first_run = await service.discover_hackathons(limit=2, persist=True)
    assert len(first_run) == 2

    # Check count in DB
    all_opps_1 = await repository.list_opportunities(opp_type="hackathon", limit=50)
    assert len(all_opps_1) == 2

    # Second discovery run with same items
    second_run = await service.discover_hackathons(limit=2, persist=True)
    assert len(second_run) == 2

    # Count in DB MUST STILL BE 2 (no duplicate rows created)
    all_opps_2 = await repository.list_opportunities(opp_type="hackathon", limit=50)
    assert len(all_opps_2) == 2


@pytest.mark.asyncio
async def test_database_persistence_and_retrieval(temp_db):
    """
    Verifies that discovered opportunities are stored in the shared database
    and can be retrieved by type, by content_hash, and with application_url and location intact.
    """
    sample_opp = OpportunityModel(
        id="opp_test_persistence_1",
        title="Software Engineering Intern - Cloud Platforms",
        organization="CloudScale Systems",
        type="internship",
        source_url="https://jobs.smartrecruiters.com/CloudScale/101",
        application_url="https://jobs.smartrecruiters.com/CloudScale/101",
        location="San Francisco, CA & Remote",
        source_name="SimplifyJobs",
        content_hash=compute_content_hash(
            "https://jobs.smartrecruiters.com/CloudScale/101",
            "Software Engineering Intern - Cloud Platforms",
        ),
        deadline="2026-08-31T23:59:59+00:00",
        description="Build distributed cloud control planes.",
        eligibility="Students graduating in 2026-2027",
        requirements=["Go", "Kubernetes", "Linux"],
        prize_or_salary="$55/hr",
        verified_status="verified",
    )

    # Save to database
    saved = await repository.save_opportunity(sample_opp)
    assert saved.id is not None
    assert saved.application_url == "https://jobs.smartrecruiters.com/CloudScale/101"
    assert saved.location == "San Francisco, CA & Remote"

    # Retrieve by hash
    retrieved = await repository.get_opportunity_by_hash(sample_opp.content_hash)
    assert retrieved is not None
    assert retrieved.title == sample_opp.title
    assert retrieved.application_url == sample_opp.application_url
    assert retrieved.location == sample_opp.location
    assert retrieved.type == "internship"
    assert retrieved.requirements == ["Go", "Kubernetes", "Linux"]


@pytest.mark.asyncio
async def test_separate_discovery_paths():
    """
    Verifies that discover_internships() and discover_hackathons()
    execute separate discovery paths and return only their respective types.
    """
    with patch.object(
        OpportunityDiscoveryService,
        "fetch_devpost_hackathons",
        return_value=[
            OpportunityModel(
                id="opp_h1",
                title="AI Hack",
                organization="Devpost",
                type="hackathon",
                source_url="https://devpost.com/h1",
                content_hash="hash_h1",
                source_name="Devpost",
            )
        ],
    ), patch.object(
        OpportunityDiscoveryService,
        "fetch_simplify_internships",
        return_value=[
            OpportunityModel(
                id="opp_i1",
                title="SWE Intern",
                organization="Acme",
                type="internship",
                source_url="https://acme.com/job",
                application_url="https://acme.com/apply",
                content_hash="hash_i1",
                source_name="SimplifyJobs",
            )
        ],
    ), patch.object(
        OpportunityDiscoveryService,
        "fetch_arbeitnow_internships",
        return_value=[],
    ), patch.object(
        OpportunityDiscoveryService,
        "fetch_tech_internships_and_programs",
        return_value=[],
    ):
        service = OpportunityDiscoveryService()

        # Hackathons only
        hackathons = await service.discover_hackathons(persist=False)
        assert len(hackathons) == 1
        assert hackathons[0].type == "hackathon"

        # Internships only
        internships = await service.discover_internships(persist=False)
        assert len(internships) == 1
        assert internships[0].type == "internship"

        # Combined discovery
        all_opps = await service.discover_opportunities(opportunity_type="all", limit=10, persist=False)
        types = {o.type for o in all_opps}
        assert "hackathon" in types
        assert "internship" in types


# ---------------------------------------------------------------------------
# API Endpoint Tests
# ---------------------------------------------------------------------------

def test_api_discover_internships_endpoint(client, monkeypatch):
    """
    Tests POST /api/opportunities/discover/internships endpoint response schema and data.
    """
    mock_internship = OpportunityModel(
        id="opp_mock_int_1",
        title="Robotics Software Intern",
        organization="Boston Dynamic Labs",
        type="internship",
        source_url="https://bdlabs.com",
        application_url="https://smartrecruiters.com/bdlabs/1",
        location="Boston, MA",
        source_name="SimplifyJobs",
        content_hash="hash_mock_int_1",
        requirements=["C++", "ROS"],
    )

    async def mock_discover(*args, **kwargs):
        return [mock_internship]

    monkeypatch.setattr("app.routes.opportunities.opportunity_service.discover_internships", mock_discover)

    response = client.post(
        "/api/opportunities/discover/internships",
        json={"query": "robotics", "limit": 5, "persist": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["opportunity_type"] == "internship"
    assert data["count"] == 1
    assert data["opportunities"][0]["title"] == "Robotics Software Intern"
    assert data["opportunities"][0]["application_url"] == "https://smartrecruiters.com/bdlabs/1"
    assert "SimplifyJobs" in data["sources_queried"]


def test_api_discover_hackathons_endpoint(client, monkeypatch):
    """
    Tests POST /api/opportunities/discover/hackathons endpoint response schema and data.
    """
    mock_hackathon = OpportunityModel(
        id="opp_mock_hack_1",
        title="Agentic AI World Cup",
        organization="OpenAI & Devpost",
        type="hackathon",
        source_url="https://agenticcup.devpost.com",
        application_url="https://agenticcup.devpost.com",
        location="Online",
        source_name="Devpost",
        content_hash="hash_mock_hack_1",
        requirements=["Agentic AI", "Python"],
    )

    async def mock_discover(*args, **kwargs):
        return [mock_hackathon]

    monkeypatch.setattr("app.routes.opportunities.opportunity_service.discover_hackathons", mock_discover)

    response = client.post(
        "/api/opportunities/discover/hackathons",
        json={"limit": 5, "persist": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["opportunity_type"] == "hackathon"
    assert data["count"] == 1
    assert data["opportunities"][0]["title"] == "Agentic AI World Cup"
    assert data["sources_queried"] == ["Devpost"]


def test_api_discover_all_endpoint(client, monkeypatch):
    """
    Tests POST /api/opportunities/discover general endpoint with opportunity_type=all.
    """
    async def mock_discover_all(*args, **kwargs):
        return [
            OpportunityModel(
                id="opp_1",
                title="Internship 1",
                organization="Org 1",
                type="internship",
                source_url="https://org1.com",
                content_hash="hash_1",
                source_name="SimplifyJobs",
            ),
            OpportunityModel(
                id="opp_2",
                title="Hackathon 1",
                organization="Org 2",
                type="hackathon",
                source_url="https://org2.com",
                content_hash="hash_2",
                source_name="Devpost",
            ),
        ]

    monkeypatch.setattr("app.routes.opportunities.opportunity_service.discover_opportunities", mock_discover_all)

    response = client.post(
        "/api/opportunities/discover?opportunity_type=all",
        json={"limit": 10, "persist": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["count"] == 2
    assert len(data["opportunities"]) == 2


def test_api_discovery_error_handling(client, monkeypatch):
    """
    Ensures that unexpected errors during discovery return an HTTP 500 error response
    with informative message without crashing the server.
    """
    async def mock_failure(*args, **kwargs):
        raise RuntimeError("External network connection reset")

    monkeypatch.setattr("app.routes.opportunities.opportunity_service.discover_internships", mock_failure)

    response = client.post(
        "/api/opportunities/discover/internships",
        json={"limit": 5},
    )

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Internship discovery failed" in data["detail"]


# ---------------------------------------------------------------------------
# Additional Phase 2 Rigor Tests: Error Isolation, Deduplication & Fellowships
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_curated_programs_fellowship_categorization():
    """
    Verifies that Google Summer of Code, MLH Fellowship, and Linux Foundation Mentorship
    are strictly categorized as 'fellowship' programs (not ordinary internships),
    with direct application URLs, deadlines, locations, and requirements preserved.
    """
    service = OpportunityDiscoveryService()
    programs = await service.discover_fellowships(limit=10, persist=False)

    assert len(programs) >= 3
    for p in programs:
        assert p.type == "fellowship", f"{p.title} must be categorized as 'fellowship', got {p.type}"
        assert p.application_url is not None
        assert p.source_url is not None
        assert p.location == "Remote"
        assert len(p.requirements) > 0

    titles = [p.title for p in programs]
    assert any("Google Summer of Code" in t for t in titles)
    assert any("MLH" in t for t in titles)
    assert any("Linux Foundation" in t for t in titles)


@pytest.mark.asyncio
async def test_source_level_error_isolation():
    """
    Verifies that if one source fails (e.g. SimplifyJobs raises an unexpected exception or timeout),
    discover_internships isolates the error and still successfully returns results from Arbeitnow.
    """
    with patch.object(
        OpportunityDiscoveryService,
        "fetch_simplify_internships",
        side_effect=RuntimeError("SimplifyJobs repository unreachable"),
    ), patch.object(
        OpportunityDiscoveryService,
        "fetch_arbeitnow_internships",
        return_value=[
            OpportunityModel(
                id="opp_arb_1",
                title="Resilient Backend Intern",
                organization="ResilientCorp",
                type="internship",
                source_url="https://arbeitnow.com/view/resilient-backend",
                application_url="https://arbeitnow.com/view/resilient-backend",
                content_hash="hash_resilient_1",
                source_name="Arbeitnow",
            )
        ],
    ):
        service = OpportunityDiscoveryService()
        items = await service.discover_internships(limit=5, persist=False)
        assert len(items) == 1
        assert items[0].title == "Resilient Backend Intern"
        assert items[0].organization == "ResilientCorp"


@pytest.mark.asyncio
async def test_cross_source_duplicate_prevention_memory_and_db(temp_db):
    """
    Verifies that opportunities discovered across different sources with identical
    (organization, title) but different URLs are deduplicated in memory
    and merged in the shared PostgreSQL database rather than creating duplicate rows.
    """
    with patch.object(
        OpportunityDiscoveryService,
        "fetch_simplify_internships",
        return_value=[
            OpportunityModel(
                id="opp_simp_1",
                title="Software Engineer Intern",
                organization="Acme Systems",
                type="internship",
                source_url="https://jobs.smartrecruiters.com/acme/1",
                application_url="https://jobs.smartrecruiters.com/acme/1",
                content_hash="hash_simplify_acme",
                source_name="SimplifyJobs",
            )
        ],
    ), patch.object(
        OpportunityDiscoveryService,
        "fetch_arbeitnow_internships",
        return_value=[
            OpportunityModel(
                id="opp_arb_dup",
                title="Software Engineer Intern",
                organization="Acme Systems",
                type="internship",
                source_url="https://arbeitnow.com/view/acme-swe",
                application_url="https://arbeitnow.com/view/acme-swe",
                content_hash="hash_arbeitnow_acme",
                source_name="Arbeitnow",
            )
        ],
    ):
        service = OpportunityDiscoveryService()

        # In-memory cross-source deduplication check
        results = await service.discover_internships(limit=10, persist=False)
        assert len(results) == 1
        assert results[0].organization == "Acme Systems"

        # Database deduplication check
        saved_1 = await repository.save_opportunity(results[0])
        assert saved_1.id is not None

        # Try saving the duplicate with different content_hash but identical org & title
        dup_opp = OpportunityModel(
            id="opp_arb_dup_db",
            title="Software Engineer Intern",
            organization="Acme Systems",
            type="internship",
            source_url="https://arbeitnow.com/view/acme-swe",
            application_url="https://arbeitnow.com/view/acme-swe",
            content_hash="hash_arbeitnow_acme",
            source_name="Arbeitnow",
        )
        saved_2 = await repository.save_opportunity(dup_opp)

        # Database must have merged the records into the existing ID, no duplicate row
        all_opps = await repository.list_opportunities(opp_type="internship", limit=10)
        assert len(all_opps) == 1
        assert saved_1.id == saved_2.id


def test_api_discover_fellowships_endpoint(client, monkeypatch):
    """
    Tests POST /api/opportunities/discover/fellowships endpoint response schema and data.
    """
    mock_fellowship = OpportunityModel(
        id="opp_mock_fel_1",
        title="Google Summer of Code (GSoC) 2026",
        organization="Google Open Source",
        type="fellowship",
        source_url="https://summerofcode.withgoogle.com",
        application_url="https://summerofcode.withgoogle.com/get-started",
        location="Remote",
        source_name="Google Open Source",
        content_hash="hash_mock_fel_1",
        requirements=["Open Source", "Python"],
    )

    async def mock_discover(*args, **kwargs):
        return [mock_fellowship]

    monkeypatch.setattr("app.routes.opportunities.opportunity_service.discover_fellowships", mock_discover)

    response = client.post(
        "/api/opportunities/discover/fellowships",
        json={"limit": 5, "persist": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["opportunity_type"] == "fellowship"
    assert data["count"] == 1
    assert data["opportunities"][0]["type"] == "fellowship"
    assert "Google Summer of Code" in data["sources_queried"]


# ---------------------------------------------------------------------------
# Live Verified Sources Smoke Test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_live_sources_smoke_test():
    """
    Smoke tests the actual public endpoints (Devpost & SimplifyJobs) to verify
    real connectivity and expected response schema when network is available.
    """
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        try:
            # 1. Test Devpost
            devpost_resp = await client.get("https://devpost.com/api/hackathons")
            if devpost_resp.status_code == 200:
                data = devpost_resp.json()
                assert "hackathons" in data
                assert isinstance(data["hackathons"], list)

            # 2. Test SimplifyJobs
            simplify_resp = await client.get(
                "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/dev/.github/scripts/listings.json"
            )
            if simplify_resp.status_code == 200:
                data = simplify_resp.json()
                assert isinstance(data, list)
                assert len(data) > 0
                sample = data[0]
                assert "title" in sample
                assert "company_name" in sample
                assert "url" in sample

        except httpx.HTTPError:
            pytest.skip("External network unreachable; skipping live smoke test.")
