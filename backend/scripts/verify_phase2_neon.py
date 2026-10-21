"""
Voxara AI - Live Opportunity Discovery & Neon Persistence Verification

Tests real discovery of internships and hackathons, verifies normalization,
checks deduplication in Neon PostgreSQL, and verifies retrieval.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.opportunity_service import opportunity_service
from app.db import repository
from app.db.database import db_manager


async def verify_live_discovery():
    print("=" * 65)
    print("Voxara AI — Phase 2 Live Discovery & Neon Persistence Test")
    print("=" * 65)

    try:
        # 1. Discover Hackathons (Devpost)
        print("\n1. Testing Hackathon Discovery (Devpost Public API)...")
        hackathons = await opportunity_service.discover_hackathons(limit=2, persist=True)
        print(f"   [OK] Discovered and persisted {len(hackathons)} hackathons in Neon:")
        for h in hackathons:
            print(f"      - Title: '{h.title}' | Org: '{h.organization}' | Source: {h.source_name}")
            print(f"        URL: {h.application_url} | Deadline: {h.deadline} | Location: {h.location}")
            assert h.type == "hackathon"
            assert h.content_hash is not None

        # 2. Discover Internships (SimplifyJobs / Arbeitnow / Programs)
        print("\n2. Testing Internship Discovery (SimplifyJobs / Arbeitnow / Programs)...")
        internships = await opportunity_service.discover_internships(limit=2, persist=True)
        print(f"   [OK] Discovered and persisted {len(internships)} internships in Neon:")
        for i in internships:
            print(f"      - Title: '{i.title}' | Org: '{i.organization}' | Source: {i.source_name}")
            print(f"        URL: {i.application_url} | Location: {i.location} | Eligibility: {i.eligibility}")
            assert i.type == "internship"
            assert i.content_hash is not None

        # 3. Test Deduplication in Neon
        print("\n3. Testing Duplicate Prevention on Repeated Search...")
        initial_opps = await repository.list_shared_opportunities(limit=50)
        initial_count = len(initial_opps)

        # Run discovery again with identical search
        _ = await opportunity_service.discover_hackathons(limit=2, persist=True)
        _ = await opportunity_service.discover_internships(limit=2, persist=True)

        recheck_opps = await repository.list_shared_opportunities(limit=50)
        final_count = len(recheck_opps)
        assert final_count == initial_count, f"Duplicate records created! Initial: {initial_count}, Final: {final_count}"
        print(f"   [OK] Duplicate prevention confirmed: {final_count} opportunities in Neon (no duplicates inserted).")

        # 4. Test Catalog Retrieval by Type
        print("\n4. Testing Catalog Filtering by Type from Neon...")
        neon_hackathons = await repository.list_shared_opportunities(opp_type="hackathon", limit=10)
        neon_internships = await repository.list_shared_opportunities(opp_type="internship", limit=10)
        assert all(h.type == "hackathon" for h in neon_hackathons)
        assert all(i.type == "internship" for i in neon_internships)
        print(f"   [OK] Successfully retrieved {len(neon_hackathons)} hackathons and {len(neon_internships)} internships by type filter.")

        print("\n" + "=" * 65)
        print("PHASE 2 VERIFICATION SUCCESSFUL: All Discovery & Neon Integration Tests Passed!")
        print("=" * 65)
        return 0

    except Exception as exc:
        print(f"\n[ERROR] Discovery verification failed: {exc}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        await db_manager.close_db()


if __name__ == "__main__":
    exit_code = asyncio.run(verify_live_discovery())
    sys.exit(exit_code)
