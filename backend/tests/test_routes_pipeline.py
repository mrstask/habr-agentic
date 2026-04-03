"""
Tests for app.api.routes.pipeline — Pipeline management API routes.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.pipeline import router as pipeline_router
from app.dependencies import verify_pipeline_enabled
from app.models.enums import RunStatus, PipelineStep
from app.schemas import (
    PipelineRunResponse,
    PipelineRunListResponse,
    PipelineTriggerResponse,
    PipelineStatusResponse,
    PaginationMeta,
)


@pytest.fixture
def app():
    """Create a FastAPI app with the pipeline router."""
    app = FastAPI()
    app.include_router(pipeline_router)
    return app


@pytest.fixture
def client(app):
    """Create a TestClient for the pipeline router."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# list_pipeline_runs
# ---------------------------------------------------------------------------

def test_list_pipeline_runs_returns_200(client):
    """GET /pipeline/runs returns 200 with paginated run list."""
    now = datetime.now(timezone.utc).isoformat()

    mock_response = PipelineRunListResponse(
        items=[
            PipelineRunResponse(
                id=1,
                article_id=42,
                status=RunStatus.running,
                current_step=PipelineStep.extraction,
                started_at=now,
                completed_at=None,
                error_message=None,
                duration_seconds=None,
            )
        ],
        meta=PaginationMeta(total=1, limit=50, offset=0, has_next=False),
    )

    mock_service = MagicMock()
    mock_service.list_runs = AsyncMock(return_value=mock_response)

    with patch("app.api.routes.pipeline.PipelineService", return_value=mock_service):
        response = client.get("/pipeline/runs")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "running"


def test_list_pipeline_runs_with_filters(client):
    """GET /pipeline/runs?status=completed&article_id=42 applies filters."""
    mock_response = PipelineRunListResponse(
        items=[],
        meta=PaginationMeta(total=0, limit=50, offset=0, has_next=False),
    )

    mock_service = MagicMock()
    mock_service.list_runs = AsyncMock(return_value=mock_response)

    with patch("app.api.routes.pipeline.PipelineService", return_value=mock_service):
        response = client.get("/pipeline/runs?status=completed&article_id=42")

    assert response.status_code == 200
    mock_service.list_runs.assert_called_once()


# ---------------------------------------------------------------------------
# get_pipeline_run
# ---------------------------------------------------------------------------

def test_get_pipeline_run_returns_200(client):
    """GET /pipeline/runs/{id} returns 200 with run details."""
    now = datetime.now(timezone.utc).isoformat()

    mock_response = PipelineRunResponse(
        id=1,
        article_id=42,
        status=RunStatus.completed,
        current_step=PipelineStep.publish,
        started_at=now,
        completed_at=now,
        error_message=None,
        duration_seconds=120.5,
    )

    mock_service = MagicMock()
    mock_service.get_run = AsyncMock(return_value=mock_response)

    with patch("app.api.routes.pipeline.PipelineService", return_value=mock_service):
        response = client.get("/pipeline/runs/1")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["status"] == "completed"
    assert data["duration_seconds"] == 120.5


def test_get_pipeline_run_returns_404(client):
    """GET /pipeline/runs/{id} returns 404 when run not found."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.get_run = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline run 999 not found",
        )
    )

    with patch("app.api.routes.pipeline.PipelineService", return_value=mock_service):
        response = client.get("/pipeline/runs/999")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# trigger_pipeline
# ---------------------------------------------------------------------------

def test_trigger_pipeline_returns_200(app, client):
    """POST /pipeline/trigger/{article_id} returns 200 with trigger response."""
    mock_response = PipelineTriggerResponse(
        run_id=100,
        article_id=42,
        status=RunStatus.running,
        message="Pipeline triggered for article 42",
    )

    mock_service = MagicMock()
    mock_service.trigger_run = AsyncMock(return_value=mock_response)

    app.dependency_overrides[verify_pipeline_enabled] = lambda: {"AGENT_ENABLED": "True"}

    with patch("app.api.routes.pipeline.PipelineService", return_value=mock_service):
        response = client.post("/pipeline/trigger/42")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == 100
    assert data["status"] == "running"


def test_trigger_pipeline_returns_404(app, client):
    """POST /pipeline/trigger/{article_id} returns 404 when article not found."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.trigger_run = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article 999 not found",
        )
    )

    app.dependency_overrides[verify_pipeline_enabled] = lambda: {"AGENT_ENABLED": "True"}

    with patch("app.api.routes.pipeline.PipelineService", return_value=mock_service):
        response = client.post("/pipeline/trigger/999")

    app.dependency_overrides.clear()

    assert response.status_code == 404


def test_trigger_pipeline_returns_409_conflict(app, client):
    """POST /pipeline/trigger/{article_id} returns 409 when already running."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.trigger_run = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Article 42 already has a running pipeline",
        )
    )

    app.dependency_overrides[verify_pipeline_enabled] = lambda: {"AGENT_ENABLED": "True"}

    with patch("app.api.routes.pipeline.PipelineService", return_value=mock_service):
        response = client.post("/pipeline/trigger/42")

    app.dependency_overrides.clear()

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# stop_pipeline_run
# ---------------------------------------------------------------------------

def test_stop_pipeline_run_returns_200(client):
    """POST /pipeline/stop/{run_id} returns 200 with confirmation."""
    mock_service = MagicMock()
    mock_service.stop_run = AsyncMock(
        return_value={"message": "Pipeline run 1 stopped successfully", "run_id": 1}
    )

    with patch("app.api.routes.pipeline.PipelineService", return_value=mock_service):
        response = client.post("/pipeline/stop/1")

    assert response.status_code == 200
    data = response.json()
    assert "stopped successfully" in data["message"]


def test_stop_pipeline_run_returns_404(client):
    """POST /pipeline/stop/{run_id} returns 404 when run not found."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.stop_run = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline run 999 not found",
        )
    )

    with patch("app.api.routes.pipeline.PipelineService", return_value=mock_service):
        response = client.post("/pipeline/stop/999")

    assert response.status_code == 404


def test_stop_pipeline_run_returns_400_not_running(client):
    """POST /pipeline/stop/{run_id} returns 400 when run is not running."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.stop_run = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot stop run in 'completed' status",
        )
    )

    with patch("app.api.routes.pipeline.PipelineService", return_value=mock_service):
        response = client.post("/pipeline/stop/1")

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# get_pipeline_status
# ---------------------------------------------------------------------------

def test_get_pipeline_status_returns_200(client):
    """GET /pipeline/status returns 200 with pipeline status."""
    mock_response = PipelineStatusResponse(
        agent_enabled=True,
        agent_dry_run=False,
        active_runs=2,
        queued_articles=5,
        total_runs_today=10,
        success_rate=90.0,
        average_duration_seconds=60.0,
    )

    mock_service = MagicMock()
    mock_service.get_pipeline_status = AsyncMock(return_value=mock_response)

    with patch("app.api.routes.pipeline.PipelineService", return_value=mock_service):
        response = client.get("/pipeline/status")

    assert response.status_code == 200
    data = response.json()
    assert data["active_runs"] == 2
    assert data["success_rate"] == 90.0
    assert data["agent_enabled"] is True
