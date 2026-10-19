"""
Voxara AI - Database Base (SQLAlchemy 2.0 Declarative Base)
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Naming convention for foreign keys and constraints (PostgreSQL & SQLite compatibility)
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utc_now() -> datetime:
    """Returns the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative Base class for all Voxara AI database entities."""
    metadata = MetaData(naming_convention=convention)
