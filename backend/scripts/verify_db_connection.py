"""
Voxara AI - Database Connection & Health Verification Script

Tests connectivity to PostgreSQL (Neon or local) without exposing secrets.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.config import settings
from app.db.database import db_manager


def sanitize_url(url: str) -> str:
    """Masks password in connection URL for safe logging."""
    return re.sub(r":([^@]+)@", ":***@", url)


async def main() -> int:
    print("=" * 60)
    print("Voxara AI — PostgreSQL Database Verification")
    print("=" * 60)

    # 1. Inspect Environment & Configuration
    try:
        raw_url = settings.database_url
        if not raw_url:
            print("[ERROR] DATABASE_URL is not set in backend/.env")
            return 1

        normalized_url = settings.normalized_database_url
        sanitized = sanitize_url(normalized_url)
        print(f"[OK] DATABASE_URL loaded: {sanitized}")
    except ValueError as err:
        print(f"[ERROR] Configuration error: {err}")
        return 1

    # 2. Check Driver
    if normalized_url.startswith("postgresql+asyncpg://"):
        print("[OK] Driver: SQLAlchemy asyncpg (async PostgreSQL)")
    else:
        print(f"[ERROR] Invalid driver in normalized URL: {sanitized}")
        return 1

    # 3. Test Connection
    print("\nAttempting connection to PostgreSQL server...")
    try:
        async with db_manager.engine.connect() as conn:
            res = await conn.execute(text("SELECT version(), current_database(), current_user;"))
            row = res.fetchone()
            if row:
                version_str = row[0].split()[0:2]
                print(f"[SUCCESS] Connected successfully!")
                print(f" - Server: {' '.join(version_str)}")
                print(f" - Database: {row[1]}")
                print(f" - User: {row[2]}")

            # 4. Check Existing Tables
            tables_res = await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;")
            )
            tables = [r[0] for r in tables_res.fetchall()]
            print(f"\n[INFO] Found {len(tables)} tables in schema 'public':")
            if tables:
                for t in tables:
                    print(f"   - {t}")
            else:
                print("   (No tables found yet. Run migrations to initialize schema.)")

        return 0

    except Exception as exc:
        err_msg = str(exc)
        # Sanitize any accidental password in the exception message
        sanitized_err = sanitize_url(err_msg)
        print(f"[FAILED] Could not connect to database:")
        print(f"Details: {sanitized_err}")
        return 2

    finally:
        await db_manager.close_db()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
