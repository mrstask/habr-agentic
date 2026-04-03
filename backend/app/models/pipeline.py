from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.enums import RunStatus


class PipelineRun(Base):
    __tablename__ = 'pipeline_runs'

    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, index=True)
    step = Column(String, nullable=False)
    status = Column(String, default=RunStatus.running.value)
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)


class AgentConfig(Base):
    __tablename__ = 'agent_configs'

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
