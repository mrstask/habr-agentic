import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.pipeline import PipelineRun, AgentConfig
from app.db.base import AppBase
def test_pipeline_run_table_creation():
    assert hasattr(PipelineRun, '__tablename__') and PipelineRun.__tablename__ == 'pipeline_runs'

def test_agent_config_table_creation():
    assert hasattr(AgentConfig, '__tablename__') and AgentConfig.__tablename__ == 'agent_configs'