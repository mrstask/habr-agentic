"""
Pipeline management API routes.

Provides endpoints for monitoring and controlling the LangGraph
pipeline execution, including run status, logs, and manual triggers.

All endpoints use the PipelineService for business logic and the
centralized database session dependency from app.dependencies.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_app_session, verify_pipeline_enabled
from app.models.enums import RunStatus
from app.schemas import (
    PipelineRunResponse,
    PipelineRunListResponse,
    PipelineTriggerResponse,
    PipelineStatusResponse,
)
from app.services.pipeline_service import PipelineService

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get(
    "/runs",
    response_model=PipelineRunListResponse,
    summary="List pipeline runs",
)
async def list_pipeline_runs(
    status_filter: Optional[RunStatus] = Query(
        None, alias="status", description="Filter by run status"
    ),
    article_id: Optional[int] = Query(None, description="Filter by article ID"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of runs to return"),
    offset: int = Query(0, ge=0, description="Number of runs to skip"),
    session: AsyncSession = Depends(get_app_session),
) -> PipelineRunListResponse:
    """
    List pipeline runs with optional filtering and pagination.

    Args:
        status_filter: Filter by run status (running, completed, failed, skipped).
        article_id: Filter by specific article ID.
        limit: Maximum number of runs to return (1-200).
        offset: Number of runs to skip for pagination.
        session: Async database session.

    Returns:
        PipelineRunListResponse: Paginated list of pipeline runs with metadata.
    """
    service = PipelineService(session)
    return await service.list_runs(
        status=status_filter,
        article_id=article_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/runs/{run_id}",
    response_model=PipelineRunResponse,
    summary="Get pipeline run by ID",
)
async def get_pipeline_run(
    run_id: int,
    session: AsyncSession = Depends(get_app_session),
) -> PipelineRunResponse:
    """
    Retrieve a single pipeline run by ID.

    Args:
        run_id: The unique identifier of the pipeline run.
        session: Async database session.

    Returns:
        PipelineRunResponse: Pipeline run details including status, duration, and errors.

    Raises:
        HTTPException: 404 Not Found if run does not exist.
    """
    service = PipelineService(session)
    return await service.get_run(run_id)


@router.post(
    "/trigger/{article_id}",
    response_model=PipelineTriggerResponse,
    summary="Manually trigger pipeline for an article",
)
async def trigger_pipeline(
    article_id: int,
    session: AsyncSession = Depends(get_app_session),
    _config: dict = Depends(verify_pipeline_enabled),
) -> PipelineTriggerResponse:
    """
    Manually trigger the pipeline for a specific article.

    Args:
        article_id: The unique identifier of the article to process.
        session: Async database session.
        _config: Pipeline configuration (from verify_pipeline_enabled dependency).

    Returns:
        PipelineTriggerResponse: Pipeline run ID and status.

    Raises:
        HTTPException: 400 Bad Request if pipeline is disabled.
        HTTPException: 404 Not Found if article does not exist.
        HTTPException: 409 Conflict if article already has a running pipeline.
    """
    service = PipelineService(session)
    return await service.trigger_run(article_id)


@router.post(
    "/stop/{run_id}",
    summary="Stop a running pipeline execution",
)
async def stop_pipeline_run(
    run_id: int,
    session: AsyncSession = Depends(get_app_session),
) -> dict:
    """
    Stop a running pipeline execution.

    Args:
        run_id: The unique identifier of the pipeline run to stop.
        session: Async database session.

    Returns:
        dict: Confirmation of stop request.

    Raises:
        HTTPException: 404 Not Found if run does not exist.
        HTTPException: 400 Bad Request if run is not in 'running' status.
    """
    service = PipelineService(session)
    return await service.stop_run(run_id)


@router.get(
    "/status",
    response_model=PipelineStatusResponse,
    summary="Get overall pipeline status",
)
async def get_pipeline_status(
    session: AsyncSession = Depends(get_app_session),
) -> PipelineStatusResponse:
    """
    Get overall pipeline status and statistics.

    Args:
        session: Async database session.

    Returns:
        PipelineStatusResponse: Pipeline status including active runs,
                                queue size, and statistics.
    """
    service = PipelineService(session)
    return await service.get_pipeline_status()
