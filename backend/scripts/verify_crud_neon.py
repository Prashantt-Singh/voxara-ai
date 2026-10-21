"""
Voxara AI - Neon Database Opportunity CRUD Verification (Task 1)

Verifies creating, retrieving, updating, and deleting an opportunity directly
in the live Neon PostgreSQL database using the existing database layer,
and cleans up test data safely without dropping or resetting any tables.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.database import db_manager
from app.db.models import OpportunityCreate, compute_content_hash
from app.db import repository


async def run_crud_verification() -> int:
    print("=" * 65)
    print("Voxara AI — Neon PostgreSQL CRUD Verification (Task 1)")
    print("=" * 65)

    test_token = uuid.uuid4().hex[:8]
    test_title = f"Test Verification Opportunity {test_token}"
    test_url = f"https://example.com/test-opp-{test_token}"
    test_app_url = f"https://example.com/test-opp-{test_token}/apply"
    content_hash = compute_content_hash(test_url, test_title)

    opp_data = OpportunityCreate(
        title=test_title,
        organization="Voxara Verification Lab",
        type="internship",
        source_url=test_url,
        application_url=test_app_url,
        location="Remote (Global)",
        source_name="VerificationScript",
        description="Initial test description for Neon CRUD verification.",
        deadline=datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        eligibility="Undergraduate & Graduate students",
        requirements=["Python", "FastAPI", "PostgreSQL"],
        prize_or_salary="$5,000/month",
        verified_status="verified",
    )

    created_id = None
    try:
        # Step 1: Create in Neon
        print("\n1. [CREATE] Inserting opportunity into Neon PostgreSQL...")
        created = await repository.save_shared_opportunity(opp_data)
        created_id = created.id
        assert created_id is not None
        assert created.content_hash == content_hash
        print(f"   [OK] Created opportunity ID: {created_id}")
        print(f"   [OK] Title: '{created.title}', Org: '{created.organization}'")

        # Step 2: Retrieve from Neon
        print("\n2. [RETRIEVE] Fetching opportunity by ID and by content hash from Neon...")
        fetched = await repository.get_shared_opportunity_by_id(created_id)
        assert fetched is not None, "Opportunity was not found by ID in Neon!"
        assert fetched.title == test_title
        assert fetched.application_url == test_app_url
        assert fetched.location == "Remote (Global)"
        assert fetched.requirements == ["Python", "FastAPI", "PostgreSQL"]

        fetched_by_hash = await repository.get_shared_opportunity_by_hash(content_hash)
        assert fetched_by_hash is not None, "Opportunity was not found by content_hash in Neon!"
        assert fetched_by_hash.id == created_id
        print("   [OK] Successfully retrieved opportunity and verified all fields match.")

        # Step 3: Update in Neon
        print("\n3. [UPDATE] Updating description, location, and requirements in Neon...")
        updated_data = OpportunityCreate(
            title=test_title,
            organization="Voxara Verification Lab",
            type="internship",
            source_url=test_url,
            application_url=test_app_url,
            location="San Francisco, CA & Remote",
            source_name="VerificationScript",
            description="Updated description with confirmed stipend of $6,000/month.",
            deadline=datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
            eligibility="All developers worldwide",
            requirements=["Python", "FastAPI", "PostgreSQL", "LiveKit"],
            prize_or_salary="$6,000/month",
            verified_status="verified",
        )
        updated = await repository.save_shared_opportunity(updated_data)
        assert updated.id == created_id, "Opportunity ID changed unexpectedly on update!"
        assert updated.description == "Updated description with confirmed stipend of $6,000/month."
        assert updated.location == "San Francisco, CA & Remote"
        assert "LiveKit" in updated.requirements
        assert updated.prize_or_salary == "$6,000/month"
        print("   [OK] Update successfully persisted in Neon.")

        # Step 4: Verify persistence via direct query
        print("\n4. [CONFIRM PERSISTENCE] Querying Neon directly for updated record...")
        re_fetched = await repository.get_shared_opportunity_by_id(created_id)
        assert re_fetched is not None
        assert re_fetched.prize_or_salary == "$6,000/month"
        print(f"   [OK] Verified updated prize/salary in Neon: {re_fetched.prize_or_salary}")

        # Step 5: Delete test opportunity
        print("\n5. [DELETE] Removing test opportunity safely from Neon...")
        deleted = await repository.delete_shared_opportunity(created_id)
        assert deleted is True, f"Failed to delete opportunity {created_id}"

        # Verify deletion
        post_delete = await repository.get_shared_opportunity_by_id(created_id)
        assert post_delete is None, "Opportunity still exists after deletion!"
        print("   [OK] Opportunity successfully deleted. Cleaned up test data safely.")

        print("\n" + "=" * 65)
        print("TASK 1 COMPLETED: Full CRUD cycle on Neon PostgreSQL verified!")
        print("=" * 65)
        return 0

    except Exception as exc:
        print(f"\n[ERROR] CRUD verification failed: {exc}")
        import traceback
        traceback.print_exc()
        # Clean up if partially created
        if created_id:
            try:
                await repository.delete_shared_opportunity(created_id)
            except Exception:
                pass
        return 1

    finally:
        await db_manager.close_db()


if __name__ == "__main__":
    exit_code = asyncio.run(run_crud_verification())
    sys.exit(exit_code)
