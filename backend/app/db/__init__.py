"""
Voxara AI - Database Package (SQLAlchemy 2.0 Multi-User PostgreSQL & Async SQLite)
"""

from app.db.base import Base
from app.db.database import db_manager, DatabaseManager, get_db
from app.db.tables import (
    User,
    UserPreference,
    Opportunity,
    SavedOpportunity,
    Notification,
    WorkflowExecution,
)
from app.db.models import (
    UserRead,
    UserCreate,
    UserPreferenceRead,
    UserPreferenceUpdate,
    OpportunityRead,
    OpportunityCreate,
    SavedOpportunityRead,
    SavedOpportunityCreate,
    SavedOpportunityUpdate,
    NotificationRead,
    NotificationCreate,
    compute_content_hash,
)
from app.db import repository

__all__ = [
    "Base",
    "db_manager",
    "DatabaseManager",
    "get_db",
    "User",
    "UserPreference",
    "Opportunity",
    "SavedOpportunity",
    "Notification",
    "WorkflowExecution",
    "UserRead",
    "UserCreate",
    "UserPreferenceRead",
    "UserPreferenceUpdate",
    "OpportunityRead",
    "OpportunityCreate",
    "SavedOpportunityRead",
    "SavedOpportunityCreate",
    "SavedOpportunityUpdate",
    "NotificationRead",
    "NotificationCreate",
    "compute_content_hash",
    "repository",
]
