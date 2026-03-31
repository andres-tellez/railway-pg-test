from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from src.db.db_session import Base


class CoachTool(Base):
    __tablename__ = "coach_tools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    when_to_call = Column(Text)
    parameters_schema = Column(JSONB, nullable=False, server_default="{}")
    returns_description = Column(Text)
    data_source = Column(String)
    is_enabled = Column(Boolean, nullable=False, server_default="true")
    sort_order = Column(Integer, nullable=False, server_default="0")
    call_count = Column(Integer, nullable=False, server_default="0")
    last_called_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
