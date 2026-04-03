"""
Pipeline business logic service.

Provides high-level pipeline operations for monitoring, triggering,
and controlling LangGraph pipeline executions.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.models.pipeline import PipelineRun
from app.models.enums import RunStatus, ArticleStatus
from app.schemas import (
    PipelineRunResponse,
    PipelineRunListResponse,
    PipelineTriggerResponse,
    PipelineStatusResponse,
    PaginationMeta,
)


class PipelineService:
    """
    Service layer for pipeline run management and orchestration.

    Coordinates between the pipeline repository and the LangGraph
    pipeline graph for triggering, monitoring, and stopping runs.

    Args:
        session: Async SQLAlchemy session for the App database.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize the PipelineService with a database session.

        Args:
            session: Async SQLAlchemy session for the App database.
        """
        self.session = session

    def _run_to_response(self, run: PipelineRun) -> PipelineRunResponse:
        """Map a PipelineRun ORM model to a PipelineRunResponse schema."""
        return PipelineRunResponse(
            id=run.id,
            article_id=run.article_id,
            status=RunStatus(run.status),
            current_step=run.step,
            started_at=run.started_at,
            completed_at=run.completed_at,
            error_message=run.error,
            duration_seconds=run.duration_seconds,
        )

    async def list_runs(
        self,
        status_filter: Optional[RunStatus] = None,
        article_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PipelineRunListResponse:
        """
        List pipeline runs with optional filtering and pagination.

        Args:
            status_filter: Filter by run status.
            article_id: Filter by specific article ID.
            limit: Maximum number of runs to return.
            offset: Number of runs to skip.

        Returns:
            PipelineRunListResponse: Paginated list of pipeline runs with metadata.
        """
        query = select(PipelineRun)
        count_query = select(func.count(PipelineRun.id))

        if status_filter is not None:
            query = query.where(PipelineRun.status == status_filter.value)
            count_query = count_query.where(PipelineRun.status == status_filter.value)

        if article_id is not None:
            query = query.where(PipelineRun.article_id == article_id)
            count_query = count_query.where(PipelineRun.article_id == article_id)

        # Get total count
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated results
        query = query.order_by(PipelineRun.id.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        runs = result.scalars().all()

        items = [self._run_to_response(r) for r in runs]

        return PipelineRunListResponse(
            items=items,
            meta=PaginationMeta(
                total=total,
                limit=limit,
                offset=offset,
                has_next=offset + limit < total,
            ),
        )

    async def get_run(self, run_id: int) -> PipelineRunResponse:
        """
        Retrieve a single pipeline run by ID.

        Args:
            run_id: The unique identifier of the pipeline run.

        Returns:
            PipelineRunResponse: Pipeline run details including status, duration, and errors.

        Raises:
            HTTPException: 404 Not Found if run does not exist.
        """
        result = await self.session.execute(
            select(PipelineRun).where(PipelineRun.id == run_id)
        )
        run = result.scalar_one_or_none()

        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline run {run_id} not found",
            )

        return self._run_to_response(run)

    async def trigger_run(self, article_id: int) -> PipelineTriggerResponse:
        """
        Manually trigger the pipeline for a specific article.

        Creates a new pipeline run record and launches the LangGraph
        pipeline execution in the background.

        Args:
            article_id: The unique identifier of the article to process.

        Returns:
            PipelineTriggerResponse: Pipeline run ID and status.

        Raises:
            HTTPException: 404 Not Found if article does not exist.
            HTTPException: 409 Conflict if article already has a running pipeline.
        """
        # Verify article exists
        from app.models.article import Article

        result = await self.session.execute(
            select(Article).where(Article.id == article_id)
        )
        article = result.scalar_one_or_none()

        if article is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Article {article_id} not found",
            )

        # Check if article already has a running pipeline
        result = await self.session.execute(
            select(PipelineRun).where(
                PipelineRun.article_id == article_id,
                PipelineRun.status == RunStatus.running.value,
            )
        )
        existing_run = result.scalar_one_or_none()

        if existing_run is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Article {article_id} already has a running pipeline (run {existing_run.id})",
            )

        # Create new PipelineRun record with status='running'
        new_run = PipelineRun(
            article_id=article_id,
            step="extraction",
            status=RunStatus.running.value,
        )
        self.session.add(new_run)
        await self.session.flush()
        await self.session.refresh(new_run)

        # Launch LangGraph pipeline in background (placeholder)
        # In production: asyncio.create_task(self._execute_pipeline(new_run.id))

        return PipelineTriggerResponse(
            run_id=new_run.id,
            article_id=article_id,
            status=RunStatus.running,
            message=f"Pipeline triggered for article {article_id}",
        )

    async def stop_run(self, run_id: int) -> dict:
        """
        Stop a running pipeline execution.

        Signals the LangGraph pipeline to cancel the current run
        and updates the run status to 'failed' with a cancellation message.

        Args:
            run_id: The unique identifier of the pipeline run to stop.

        Returns:
            dict: Confirmation of stop request.

        Raises:
            HTTPException: 404 Not Found if run does not exist.
            HTTPException: 400 Bad Request if run is not in 'running' status.
        """
        # Fetch run by ID
        result = await self.session.execute(
            select(PipelineRun).where(PipelineRun.id == run_id)
        )
        run = result.scalar_one_or_none()

        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline run {run_id} not found",
            )

        # Verify run is in 'running' status
        if run.status != RunStatus.running.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot stop run in '{run.status}' status (must be 'running')",
            )

        # Signal LangGraph to cancel the run (placeholder)
        # In production: graph.interrupt(run_id) or similar

        # Update run status to 'failed' with cancellation message
        run.status = RunStatus.failed.value
        run.error = "Pipeline stopped by user request"
        run.completed_at = datetime.now(timezone.utc)
        if run.started_at:
            run.duration_seconds = (run.completed_at - run.started_at).total_seconds()

        await self.session.flush()

        return {
            "message": f"Pipeline run {run_id} stopped successfully",
            "run_id": run_id,
        }

    async def get_pipeline_status(self) -> PipelineStatusResponse:
        """
        Get overall pipeline status and statistics.

        Aggregates data from active runs, queued articles, and
        historical run data to provide a comprehensive status overview.

        Returns:
            PipelineStatusResponse: Pipeline status including active runs,
                                    queue size, and statistics.
        """
        # Count active (running) pipeline runs
        active_result = await self.session.execute(
            select(func.count(PipelineRun.id)).where(
                PipelineRun.status == RunStatus.running.value
            )
        )
        active_runs = active_result.scalar() or 0

        # Count articles in DISCOVERED status (queued)
        from app.models.article import Article
        from app.db.session import ArticlesSessionLocal

        async with ArticlesSessionLocal() as articles_session:
            queued_result = await articles_session.execute(
                select(func.count(Article.id)).where(
                    Article.status == ArticleStatus.DISCOVERED.value
                )
            )
            queued_articles = queued_result.scalar() or 0

        # Calculate total runs completed today
        # Use strftime for SQLite compatibility
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        completed_result = await self.session.execute(
            select(func.count(PipelineRun.id)).where(
                PipelineRun.status == RunStatus.completed.value,
                func.strftime("%Y-%m-%d", PipelineRun.completed_at) == today_str,
            )
        )
        total_runs_today = completed_result.scalar() or 0

        # Calculate success rate from historical data
        total_completed_result = await self.session.execute(
            select(func.count(PipelineRun.id)).where(
                PipelineRun.status.in_([RunStatus.completed.value, RunStatus.failed.value])
            )
        )
        total_finished = total_completed_result.scalar() or 0

        if total_finished > 0:
            success_result = await self.session.execute(
                select(func.count(PipelineRun.id)).where(
                    PipelineRun.status == RunStatus.completed.value
                )
            )
            success_count = success_result.scalar() or 0
            success_rate = (success_count / total_finished) * 100
        else:
            success_rate = 0.0

        # Calculate average run duration
        avg_result = await self.session.execute(
            select(func.avg(PipelineRun.duration_seconds)).where(
                PipelineRun.duration_seconds.isnot(None)
            )
        )
        avg_duration = avg_result.scalar() or 0.0

        return PipelineStatusResponse(
            agent_enabled=settings.AGENT_ENABLED,
            agent_dry_run=settings.AGENT_DRY_RUN,
            active_runs=active_runs,
            queued_articles=queued_articles,
            total_runs_today=total_runs_today,
            success_rate=round(success_rate, 2),
            average_duration_seconds=round(avg_duration, 2),
        )
