import pytest
from app.models.enums import ArticleStatus, PipelineStep, RunStatus

def test_article_status_enum_values():
    assert list(ArticleStatus) == [ArticleStatus.DISCOVERED, ArticleStatus.EXTRACTED, ArticleStatus.TRANSLATED, ArticleStatus.PUBLISHED, ArticleStatus.USELESS, ArticleStatus.DRAFT]

def test_pipeline_step_enum_values():
    assert list(PipelineStep) == [PipelineStep.extraction, PipelineStep.content_filter, PipelineStep.translation, PipelineStep.review_1, PipelineStep.proofreading, PipelineStep.review_2, PipelineStep.image_text_check, PipelineStep.image_gen, PipelineStep.vectorize, PipelineStep.publish, PipelineStep.deploy, PipelineStep.mark_useless]

def test_run_status_enum_values():
    assert list(RunStatus) == [RunStatus.running, RunStatus.completed, RunStatus.failed, RunStatus.skipped]