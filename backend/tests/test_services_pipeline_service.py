"""
Tests for app.services.pipeline_service — PipelineService business logic.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.pipeline_service import PipelineService
from app.models.pipeline import PipelineRun
from app.models.enums import RunStatus
from app.schemas import (
    PipelineRunResponse,
    PipelineRunListResponse,
    PipelineTriggerResponse,
    PipelineStatusResponse,
)


# ---------------------------------------------------------------------------
# _run_to_response
# ---------------------------------------------------------------------------

def test_run_to_response_maps_fields():
    """_run_to_response correctly maps PipelineRun ORM to PipelineRunResponse."""
    now = datetime.now(timezone.utc)
    run = MagicMock(spec=PipelineRun)
    run.id = 1
    run.article_id = 42
    run.status = RunStatus.running.value
    run.step = "extraction"
    run.started_at = now
    run.completed_at = None
    run.error = None
    run.duration_seconds = None

    service = PipelineService(AsyncMock(spec=AsyncSession))
    result = service._run_to_response(run)

    assert isinstance(result, PipelineRunResponse)
    assert result.id == 1
    assert result.article_id == 42
    assert result.status == RunStatus.running
    assert result.current_step.value == "extraction"
    assert result.started_at == now
    assert result.completed_at is None
    assert result.error_message is None
    assert result.duration_seconds is None


def test_run_to_response_maps_completed_run():
    """_run_to_response correctly maps a completed run with all fields."""
    now = datetime.now(timezone.utc)
    later = datetime.now(timezone.utc)
    run = MagicMock(spec=PipelineRun)
    run.id = 2
    run.article_id = 10
    run.status = RunStatus.completed.value
    run.step = "publish"
    run.started_at = now
    run.completed_at = later
    run.error = None
    run.duration_seconds = 120.5

    service = PipelineService(AsyncMock(spec=AsyncSession))
    result = service._run_to_response(run)

    assert result.status == RunStatus.completed
    assert result.duration_seconds == 120.5
    assert result.error_message is None


# ---------------------------------------------------------------------------
# list_runs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_runs_returns_paginated_response():
    """list_runs returns PipelineRunListResponse with items and metadata."""
    now = datetime.now(timezone.utc)
    run = MagicMock(spec=PipelineRun)
    run.id = 1
    run.article_id = 42
    run.status = RunStatus.running.value
    run.step = "extraction"
    run.started_at = now
    run.completed_at = None
    run.error = None
    run.duration_seconds = None

    mock_session = AsyncMock(spec=AsyncSession)

    count_result = MagicMock()
    count_result.scalar.return_value = 1
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [run]

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return count_result
        return list_result

    mock_session.execute = mock_execute

    service = PipelineService(mock_session)
    result = await service.list_runs(limit=10, offset=0)

    assert isinstance(result, PipelineRunListResponse)
    assert len(result.items) == 1
    assert result.meta.total == 1
    assert result.meta.has_next is False


@pytest.mark.asyncio
async def test_list_runs_filters_by_status():
    """list_runs applies status filter when provided."""
    mock_session = AsyncMock(spec=AsyncSession)

    count_result = MagicMock()
    count_result.scalar.return_value = 0
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return count_result
        return list_result

    mock_session.execute = mock_execute

    service = PipelineService(mock_session)
    await service.list_runs(status_filter=RunStatus.completed, limit=10, offset=0)

    assert call_count == 2


@pytest.mark.asyncio
async def test_list_runs_filters_by_article_id():
    """list_runs applies article_id filter when provided."""
    mock_session = AsyncMock(spec=AsyncSession)

    count_result = MagicMock()
    count_result.scalar.return_value = 0
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return count_result
        return list_result

    mock_session.execute = mock_execute

    service = PipelineService(mock_session)
    await service.list_runs(article_id=42, limit=10, offset=0)

    assert call_count == 2


@pytest.mark.asyncio
async def test_list_runs_has_next_true():
    """list_runs sets has_next=True when more items exist."""
    mock_session = AsyncMock(spec=AsyncSession)

    count_result = MagicMock()
    count_result.scalar.return_value = 200
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return count_result
        return list_result

    mock_session.execute = mock_execute

    service = PipelineService(mock_session)
    result = await service.list_runs(limit=50, offset=0)

    assert result.meta.has_next is True


# ---------------------------------------------------------------------------
# get_run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_run_returns_pipeline_run_response():
    """get_run returns PipelineRunResponse for a valid run ID."""
    now = datetime.now(timezone.utc)
    run = MagicMock(spec=PipelineRun)
    run.id = 1
    run.article_id = 42
    run.status = RunStatus.running.value
    run.step = "extraction"
    run.started_at = now
    run.completed_at = None
    run.error = None
    run.duration_seconds = None

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = run
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = PipelineService(mock_session)
    result = await service.get_run(1)

    assert isinstance(result, PipelineRunResponse)
    assert result.id == 1


@pytest.mark.asyncio
async def test_get_run_raises_404_not_found():
    """get_run raises 404 when run does not exist."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = PipelineService(mock_session)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_run(999)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# trigger_run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_run_creates_new_run():
    """trigger_run creates a new PipelineRun and returns PipelineTriggerResponse."""
    mock_session = AsyncMock(spec=AsyncSession)

    mock_article = MagicMock()
    mock_article.id = 42

    # No existing running pipeline
    mock_no_run = MagicMock()
    mock_no_run.scalar_one_or_none.return_value = None

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none.return_value = mock_article
        else:
            mock_result.scalar_one_or_none.return_value = None
        return mock_result

    mock_session.execute = mock_execute

    async def mock_flush():
        pass

    async def mock_refresh(obj):
        obj.id = 100

    mock_session.flush = mock_flush
    mock_session.refresh = mock_refresh

    # Mock ArticlesSessionLocal at the db.session module level
    with patch("app.db.session.ArticlesSessionLocal") as mock_articles_local:
        mock_articles_session = AsyncMock()
        mock_articles_session.__aenter__ = AsyncMock(return_value=mock_articles_session)
        mock_articles_session.__aexit__ = AsyncMock(return_value=False)
        mock_articles_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_article))
        )
        mock_articles_local.return_value = mock_articles_session

        service = PipelineService(mock_session)
        result = await service.trigger_run(42)

    assert isinstance(result, PipelineTriggerResponse)
    assert result.article_id == 42
    assert result.status == RunStatus.running
    assert "triggered" in result.message.lower()
    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_run_raises_404_article_not_found():
    """trigger_run raises 404 when article does not exist."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = PipelineService(mock_session)

    with pytest.raises(HTTPException) as exc_info:
        await service.trigger_run(999)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_trigger_run_raises_409_already_running():
    """trigger_run raises 409 when article already has a running pipeline."""
    mock_session = AsyncMock(spec=AsyncSession)

    mock_article = MagicMock()
    mock_article.id = 42

    mock_existing_run = MagicMock()
    mock_existing_run.id = 55

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none.return_value = mock_article
        else:
            mock_result.scalar_one_or_none.return_value = mock_existing_run
        return mock_result

    mock_session.execute = mock_execute

    with patch("app.db.session.ArticlesSessionLocal") as mock_articles_local:
        mock_articles_session = AsyncMock()
        mock_articles_session.__aenter__ = AsyncMock(return_value=mock_articles_session)
        mock_articles_session.__aexit__ = AsyncMock(return_value=False)
        mock_articles_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_article))
        )
        mock_articles_local.return_value = mock_articles_session

        service = PipelineService(mock_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.trigger_run(42)

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "already has a running pipeline" in exc_info.value.detail


# ---------------------------------------------------------------------------
# stop_run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_run_succeeds():
    """stop_run updates run status to failed and returns confirmation."""
    now = datetime.now(timezone.utc)
    run = MagicMock(spec=PipelineRun)
    run.id = 1
    run.status = RunStatus.running.value
    run.started_at = now
    run.completed_at = None
    run.error = None
    run.duration_seconds = None

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = run
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = PipelineService(mock_session)
    result = await service.stop_run(1)

    assert run.status == RunStatus.failed.value
    assert "stopped by user" in run.error.lower()
    assert run.completed_at is not None
    assert isinstance(result, dict)
    assert "message" in result
    assert result["run_id"] == 1


@pytest.mark.asyncio
async def test_stop_run_raises_404_not_found():
    """stop_run raises 404 when run does not exist."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = PipelineService(mock_session)

    with pytest.raises(HTTPException) as exc_info:
        await service.stop_run(999)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_stop_run_raises_400_not_running():
    """stop_run raises 400 when run is not in 'running' status."""
    run = MagicMock(spec=PipelineRun)
    run.id = 1
    run.status = RunStatus.completed.value

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = run
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = PipelineService(mock_session)

    with pytest.raises(HTTPException) as exc_info:
        await service.stop_run(1)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Cannot stop" in exc_info.value.detail


# ---------------------------------------------------------------------------
# get_pipeline_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_pipeline_status_returns_response():
    """get_pipeline_status returns PipelineStatusResponse with aggregated data."""
    mock_session = AsyncMock(spec=AsyncSession)

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        # Queries through self.session (app DB):
        # 1: active runs count
        # 2: completed today count
        # 3: total finished count
        # 4: success count
        # 5: avg duration
        if call_count == 1:
            mock_result.scalar.return_value = 2  # active runs
        elif call_count == 2:
            mock_result.scalar.return_value = 10  # completed today
        elif call_count == 3:
            mock_result.scalar.return_value = 50  # total finished
        elif call_count == 4:
            mock_result.scalar.return_value = 45  # success count
        else:
            mock_result.scalar.return_value = 60.0  # avg duration
        return mock_result

    mock_session.execute = mock_execute

    with patch("app.db.session.ArticlesSessionLocal") as mock_articles_local:
        mock_articles_session = AsyncMock()
        mock_articles_session.__aenter__ = AsyncMock(return_value=mock_articles_session)
        mock_articles_session.__aexit__ = AsyncMock(return_value=False)
        mock_articles_session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=5))
        )
        mock_articles_local.return_value = mock_articles_session

        with patch("app.services.pipeline_service.settings") as mock_settings:
            mock_settings.AGENT_ENABLED = True
            mock_settings.AGENT_DRY_RUN = False

            service = PipelineService(mock_session)
            result = await service.get_pipeline_status()

    assert isinstance(result, PipelineStatusResponse)
    assert result.active_runs == 2
    assert result.queued_articles == 5
    assert result.total_runs_today == 10
    assert result.success_rate == 90.0  # 45/50 * 100
    assert result.average_duration_seconds == 60.0
    assert result.agent_enabled is True
    assert result.agent_dry_run is False


@pytest.mark.asyncio
async def test_get_pipeline_status_zero_division_safe():
    """get_pipeline_status handles zero finished runs without division error."""
    mock_session = AsyncMock(spec=AsyncSession)

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar.return_value = 0  # active runs
        elif call_count == 3:
            mock_result.scalar.return_value = 0  # completed today
        elif call_count == 4:
            mock_result.scalar.return_value = 0  # total finished
        else:
            mock_result.scalar.return_value = 0.0  # avg duration
        return mock_result

    mock_session.execute = mock_execute

    with patch("app.db.session.ArticlesSessionLocal") as mock_articles_local:
        mock_articles_session = AsyncMock()
        mock_articles_session.__aenter__ = AsyncMock(return_value=mock_articles_session)
        mock_articles_session.__aexit__ = AsyncMock(return_value=False)
        mock_articles_session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0))
        )
        mock_articles_local.return_value = mock_articles_session

        with patch("app.services.pipeline_service.settings") as mock_settings:
            mock_settings.AGENT_ENABLED = False
            mock_settings.AGENT_DRY_RUN = True

            service = PipelineService(mock_session)
            result = await service.get_pipeline_status()

    assert result.success_rate == 0.0
    assert result.average_duration_seconds == 0.0
