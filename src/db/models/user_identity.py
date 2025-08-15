# src/db/models/user_identity.py
from sqlalchemy import Table, Column, String, Boolean, DateTime, MetaData
from datetime import datetime

metadata = MetaData()

user_identity = Table(
    "user_identity",
    metadata,
    Column("user_id", String, primary_key=True),
    Column("email", String, nullable=True),
    Column("email_verified", Boolean, nullable=True),
    Column("name", String, nullable=True),
    Column("picture", String, nullable=True),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
)

__all__ = ["user_identity", "metadata"]
