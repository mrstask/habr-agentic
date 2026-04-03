"""
Pipeline node implementations for the Habr Agentic Pipeline.

Each node represents a step in the LangGraph pipeline and handles
a specific task: translation, proofreading, content filtering,
image checking, etc.

Nodes use the translation provider abstractions from app.etl.translation
to perform LLM-based operations.

Usage::

    from app.pipeline.nodes import translation_node, proofreading_node
    from app.etl.translation import create_provider

    provider = create_provider("grok")
    result = await translation_node(article, provider)
"""

import logging
import re
from typing import Any, Optional

from app.core.config import settings
from app.etl.translation import (
    BaseTranslationProvider,
    TranslationRequest,
    TranslationResult as TranslationResult,
    ProofreadingResult as ProofreadingResult,
    TranslationError,
    create_provider,
    create_fallback_provider,
)
from app.etl.translation.prompts import (
    load_content_filter_prompt,
    load_image_check_prompt,
)
from app.models.enums import PipelineStep

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline state
# ---------------------------------------------------------------------------

class PipelineState(dict):
    """
    TypedDict-like state object passed between pipeline nodes.

    Contains all data accumulated during pipeline execution,
    including article data, translation results, and metadata.

    Keys:
        article_id: ID of the article being processed.
        source_title: Original article title.
        source_content: Original article content (Russian).
        target_title: Translated article title.
        target_content: Translated article content (Ukrainian).
        target_excerpt: Translated article excerpt.
        translation_provider: The translation provider instance.
        translation_result: Result from the translation step.
        proofreading_result: Result from the proofreading step.
        content_filter_decision: RELEVANT or IRRELEVANT.
        image_check_decision: APPROVED or REJECTED.
        review_1_score: Score from first review (0-10).
        review_2_score: Score from second review (0-10).
        errors: List of error messages encountered.
        current_step: Current pipeline step name.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize pipeline state with provided values."""
        super().__init__(**kwargs)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from state with a default."""
        return super().get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in state."""
        self[key] = value


# ---------------------------------------------------------------------------
# Translation node
# ---------------------------------------------------------------------------

async def translation_node(
    state: PipelineState,
    provider: Optional[BaseTranslationProvider] = None,
) -> PipelineState:
    """
    Translate article content from Russian to Ukrainian.

    Uses the configured translation provider (Grok or OpenAI) to translate
    the article title and content. Falls back to the secondary provider
    if the primary fails and fallback is enabled.

    Args:
        state: Current pipeline state with article data.
        provider: Optional pre-initialized translation provider.
                  If None, creates one from settings.

    Returns:
        Updated PipelineState with translated title and content.

    Raises:
        TranslationError: If both primary and fallback providers fail.
    """
    state["current_step"] = PipelineStep.translation.value
    logger.info(
        "Translation node started for article %s",
        state.get("article_id"),
    )

    source_title = state.get("source_title", "")
    source_content = state.get("source_content", "")
    article_context = _build_article_context(state)

    # Use provided provider or create from settings
    if provider is None:
        provider = create_provider(
            provider_name=settings.TRANSLATION_PROVIDER,
        )

    # Translate title
    title_request = TranslationRequest(
        source_text=source_title,
        source_language=settings.TRANSLATION_SOURCE_LANG,
        target_language=settings.TRANSLATION_TARGET_LANG,
        context=article_context,
    )

    try:
        title_result = await provider.translate(title_request)
    except TranslationError:
        if settings.TRANSLATION_FALLBACK_ENABLED:
            logger.warning(
                "Primary translation failed for title, trying fallback..."
            )
            fallback = create_fallback_provider(
                primary_name=settings.TRANSLATION_PROVIDER,
            )
            if fallback is not None:
                title_result = await fallback.translate(title_request)
                provider = fallback
            else:
                raise
        else:
            raise

    # Translate content
    content_request = TranslationRequest(
        source_text=source_content,
        source_language=settings.TRANSLATION_SOURCE_LANG,
        target_language=settings.TRANSLATION_TARGET_LANG,
        context=article_context,
    )

    try:
        content_result = await provider.translate(content_request)
    except TranslationError:
        if settings.TRANSLATION_FALLBACK_ENABLED:
            logger.warning(
                "Primary translation failed for content, trying fallback..."
            )
            fallback = create_fallback_provider(
                primary_name=settings.TRANSLATION_PROVIDER,
            )
            if fallback is not None:
                content_result = await fallback.translate(content_request)
                provider = fallback
            else:
                raise
        else:
            raise

    # Update state with results
    state["target_title"] = title_result.translated_text
    state["target_content"] = content_result.translated_text
    state["translation_result"] = content_result
    state["translation_provider"] = provider.name

    logger.info(
        "Translation completed for article %s (provider: %s, model: %s)",
        state.get("article_id"),
        content_result.provider_name,
        content_result.model_name,
    )

    return state


# ---------------------------------------------------------------------------
# Proofreading node
# ---------------------------------------------------------------------------

async def proofreading_node(
    state: PipelineState,
    provider: Optional[BaseTranslationProvider] = None,
) -> PipelineState:
    """
    Proofread and correct the translated Ukrainian text.

    Uses the translation provider to review the translated content
    for grammar, style, and fluency issues.

    Args:
        state: Current pipeline state with translated content.
        provider: Optional pre-initialized translation provider.

    Returns:
        Updated PipelineState with proofread content.

    Raises:
        TranslationError: If proofreading fails after all retries.
    """
    state["current_step"] = PipelineStep.proofreading.value
    logger.info(
        "Proofreading node started for article %s",
        state.get("article_id"),
    )

    target_content = state.get("target_content", "")
    article_context = _build_article_context(state)

    if provider is None:
        provider = create_provider(
            provider_name=settings.TRANSLATION_PROVIDER,
        )

    try:
        result = await provider.proofread(
            text=target_content,
            context=article_context,
        )
    except TranslationError:
        if settings.TRANSLATION_FALLBACK_ENABLED:
            logger.warning(
                "Primary proofreading failed, trying fallback..."
            )
            fallback = create_fallback_provider(
                primary_name=settings.TRANSLATION_PROVIDER,
            )
            if fallback is not None:
                result = await fallback.proofread(
                    text=target_content,
                    context=article_context,
                )
                provider = fallback
            else:
                raise
        else:
            raise

    state["target_content"] = result.corrected_text
    state["proofreading_result"] = result

    logger.info(
        "Proofreading completed for article %s (%d corrections)",
        state.get("article_id"),
        result.corrections_made,
    )

    return state


# ---------------------------------------------------------------------------
# Content filter node
# ---------------------------------------------------------------------------

async def content_filter_node(
    state: PipelineState,
    provider: Optional[BaseTranslationProvider] = None,
) -> PipelineState:
    """
    Determine if the article is relevant for the Ukrainian audience.

    Uses an LLM to analyze the article content and decide whether
    it should proceed through the pipeline or be marked as useless.

    Args:
        state: Current pipeline state with article data.
        provider: Optional pre-initialized translation provider.

    Returns:
        Updated PipelineState with content filter decision.
    """
    state["current_step"] = PipelineStep.content_filter.value
    logger.info(
        "Content filter node started for article %s",
        state.get("article_id"),
    )

    if not settings.CONTENT_FILTER_ENABLED:
        logger.info("Content filtering disabled, article passes through")
        state["content_filter_decision"] = "RELEVANT"
        return state

    source_content = state.get("source_content", "")
    source_title = state.get("source_title", "")

    system_prompt = load_content_filter_prompt()
    user_content = f"Title: {source_title}\n\nContent:\n{source_content}"

    if provider is None:
        provider = create_provider(
            provider_name=settings.CONTENT_FILTER_PROVIDER,
        )

    request = TranslationRequest(
        source_text=user_content,
        system_prompt=system_prompt,
    )

    try:
        result = await provider.translate(request)
    except TranslationError:
        logger.warning(
            "Content filter failed for article %s, defaulting to RELEVANT",
            state.get("article_id"),
        )
        state["content_filter_decision"] = "RELEVANT"
        return state

    decision = result.translated_text.strip().upper()

    if "IRRELEVANT" in decision:
        state["content_filter_decision"] = "IRRELEVANT"
        logger.info(
            "Article %s marked as IRRELEVANT by content filter",
            state.get("article_id"),
        )
    else:
        state["content_filter_decision"] = "RELEVANT"
        logger.info(
            "Article %s marked as RELEVANT by content filter",
            state.get("article_id"),
        )

    return state


# ---------------------------------------------------------------------------
# Image text check node
# ---------------------------------------------------------------------------

async def image_text_check_node(
    state: PipelineState,
    provider: Optional[BaseTranslationProvider] = None,
) -> PipelineState:
    """
    Check if images contain appropriate text content.

    Uses an LLM to analyze image text (if available) and determine
    whether images are suitable for the article.

    Args:
        state: Current pipeline state with article data.
        provider: Optional pre-initialized translation provider.

    Returns:
        Updated PipelineState with image check decision.
    """
    state["current_step"] = PipelineStep.image_text_check.value
    logger.info(
        "Image text check node started for article %s",
        state.get("article_id"),
    )

    # If no image data, approve by default
    image_text = state.get("image_text", "")
    if not image_text:
        state["image_check_decision"] = "APPROVED"
        logger.info("No image text to check, defaulting to APPROVED")
        return state

    system_prompt = load_image_check_prompt()
    user_content = f"Image text content:\n{image_text}"

    if provider is None:
        provider = create_provider(
            provider_name=settings.CONTENT_FILTER_PROVIDER,
        )

    request = TranslationRequest(
        source_text=user_content,
        system_prompt=system_prompt,
    )

    try:
        result = await provider.translate(request)
    except TranslationError:
        logger.warning(
            "Image text check failed for article %s, defaulting to APPROVED",
            state.get("article_id"),
        )
        state["image_check_decision"] = "APPROVED"
        return state

    decision = result.translated_text.strip().upper()

    if "REJECTED" in decision:
        state["image_check_decision"] = "REJECTED"
        logger.info(
            "Image text REJECTED for article %s",
            state.get("article_id"),
        )
    else:
        state["image_check_decision"] = "APPROVED"
        logger.info(
            "Image text APPROVED for article %s",
            state.get("article_id"),
        )

    return state


# ---------------------------------------------------------------------------
# Review nodes
# ---------------------------------------------------------------------------

async def review_1_node(
    state: PipelineState,
    provider: Optional[BaseTranslationProvider] = None,
) -> PipelineState:
    """
    First review of the translated and proofread article.

    Evaluates the article quality and usefulness on a scale of 0-10.

    Args:
        state: Current pipeline state with translated content.
        provider: Optional pre-initialized translation provider.

    Returns:
        Updated PipelineState with review score.
    """
    state["current_step"] = PipelineStep.review_1.value
    logger.info(
        "Review 1 node started for article %s",
        state.get("article_id"),
    )

    target_content = state.get("target_content", "")
    target_title = state.get("target_title", "")

    system_prompt = (
        "You are a technical article reviewer. Evaluate the following "
        "Ukrainian article and rate its usefulness for a Ukrainian tech audience "
        "on a scale from 0 to 10. Respond with ONLY a number (0-10), nothing else."
    )

    user_content = f"Title: {target_title}\n\nContent:\n{target_content}"

    if provider is None:
        provider = create_provider(
            provider_name=settings.TRANSLATION_PROVIDER,
        )

    request = TranslationRequest(
        source_text=user_content,
        system_prompt=system_prompt,
    )

    try:
        result = await provider.translate(request)
        score_text = result.translated_text.strip()
        # Extract numeric score
        score = _extract_score(score_text)
    except TranslationError:
        logger.warning(
            "Review 1 failed for article %s, defaulting to score 5",
            state.get("article_id"),
        )
        score = 5.0

    state["review_1_score"] = score
    logger.info(
        "Review 1 completed for article %s: score %.1f",
        state.get("article_id"),
        score,
    )

    return state


async def review_2_node(
    state: PipelineState,
    provider: Optional[BaseTranslationProvider] = None,
) -> PipelineState:
    """
    Second review of the translated and proofread article.

    Provides an independent quality evaluation to cross-validate
    the first review score.

    Args:
        state: Current pipeline state with translated content and review 1 score.
        provider: Optional pre-initialized translation provider.

    Returns:
        Updated PipelineState with review 2 score.
    """
    state["current_step"] = PipelineStep.review_2.value
    logger.info(
        "Review 2 node started for article %s",
        state.get("article_id"),
    )

    target_content = state.get("target_content", "")
    target_title = state.get("target_title", "")

    system_prompt = (
        "You are an independent technical article reviewer. Evaluate the following "
        "Ukrainian article and rate its usefulness for a Ukrainian tech audience "
        "on a scale from 0 to 10. Consider technical accuracy, clarity, and relevance. "
        "Respond with ONLY a number (0-10), nothing else."
    )

    user_content = f"Title: {target_title}\n\nContent:\n{target_content}"

    if provider is None:
        provider = create_provider(
            provider_name=settings.TRANSLATION_PROVIDER,
        )

    request = TranslationRequest(
        source_text=user_content,
        system_prompt=system_prompt,
    )

    try:
        result = await provider.translate(request)
        score_text = result.translated_text.strip()
        score = _extract_score(score_text)
    except TranslationError:
        logger.warning(
            "Review 2 failed for article %s, defaulting to score 5",
            state.get("article_id"),
        )
        score = 5.0

    state["review_2_score"] = score
    logger.info(
        "Review 2 completed for article %s: score %.1f",
        state.get("article_id"),
        score,
    )

    return state


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _build_article_context(state: PipelineState) -> str:
    """
    Build article context string from pipeline state.

    Combines title, tags, and hubs into a context string
    for use in translation and proofreading prompts.

    Args:
        state: Current pipeline state.

    Returns:
        Formatted context string.
    """
    parts = []

    title = state.get("source_title")
    if title:
        parts.append(f"Title: {title}")

    tags = state.get("tags")
    if tags:
        if isinstance(tags, list):
            parts.append(f"Tags: {', '.join(tags)}")
        else:
            parts.append(f"Tags: {tags}")

    hubs = state.get("hubs")
    if hubs:
        if isinstance(hubs, list):
            parts.append(f"Hubs: {', '.join(hubs)}")
        else:
            parts.append(f"Hubs: {hubs}")

    return "\n".join(parts) if parts else ""


def _extract_score(text: str) -> float:
    """
    Extract a numeric score from LLM response text.

    Parses the response to find a number between 0 and 10.

    Args:
        text: LLM response text.

    Returns:
        Extracted score as float, or 5.0 if parsing fails.
    """
    # Try to find a number (int or float) in the text
    match = re.search(r"(\d+\.?\d*)", text)
    if match:
        score = float(match.group(1))
        # Clamp to valid range
        return max(0.0, min(10.0, score))

    return 5.0  # Default fallback


def should_proceed_to_publish(state: PipelineState) -> bool:
    """
    Determine if the article should proceed to publishing.

    Checks if the average review score meets the quality threshold
    and all previous steps completed successfully.

    Args:
        state: Current pipeline state.

    Returns:
        True if the article meets quality requirements for publishing.
    """
    review_1 = state.get("review_1_score", 0)
    review_2 = state.get("review_2_score", 0)
    avg_score = (review_1 + review_2) / 2

    threshold = settings.AGENT_QUALITY_THRESHOLD
    return avg_score >= threshold


def should_mark_useless(state: PipelineState) -> bool:
    """
    Determine if the article should be marked as useless.

    Checks if the content filter rejected the article or
    review scores are below threshold.

    Args:
        state: Current pipeline state.

    Returns:
        True if the article should be marked as useless.
    """
    content_decision = state.get("content_filter_decision", "RELEVANT")
    if content_decision == "IRRELEVANT":
        return True

    review_1 = state.get("review_1_score", 0)
    review_2 = state.get("review_2_score", 0)
    avg_score = (review_1 + review_2) / 2

    threshold = settings.AGENT_QUALITY_THRESHOLD
    return avg_score < threshold
