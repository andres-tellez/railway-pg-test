# src/db/utils/sql_types.py
import os
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID


def is_sqlite():
    db_url = os.getenv("DATABASE_URL", "")
    return db_url.startswith("sqlite")


UUIDType = String if is_sqlite() else UUID(as_uuid=True)
