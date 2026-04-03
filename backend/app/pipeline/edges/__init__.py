"""
Pipeline edge functions for the Habr Agentic Pipeline.

Edge functions determine the routing between pipeline nodes
based on the current state. They implement the conditional
logic that controls the flow of the LangGraph pipeline.

Usage::

    from app.pipeline.edges import route_after_content_filter
    next_node = route_after_content_filter(state)
"""

import logging
from typing import Literal

from app.core.config import settings

logger = logging.getLogger(__name__)


def route_after_content_filter(
    state: dict,
) -> Literal["translation", "mark_useless"]:
    """
    Route after the content filter node.

    If the content filter marks the article as IRRELEVANT,
    route to mark_useless. Otherwise, proceed to translation.

    Args:
        state: Current pipeline state.

    Returns:
        Next node name: 'translation' or 'mark_useless'.
    """
    decision = state.get("content_filter_decision", "RELEVANT")

    if decision == "IRRELEVANT":
        logger.info(
            "Routing article %s to mark_useless (content filter: IRRELEVANT)",
            state.get("article_id"),
        )
        return "mark_useless"

    logger.info(
        "Routing article %s to translation (content filter: RELEVANT)",
        state.get("article_id"),
    )
    return "translation"


def route_after_review_1(
    state: dict,
) -> Literal["review_2", "mark_useless"]:
    """
    Route after the first review node.

    If the first review score is very low (below half the threshold),
    skip the second review and mark as useless. Otherwise, proceed
    to the second review.

    Args:
        state: Current pipeline state.

    Returns:
        Next node name: 'review_2' or 'mark_useless'.
    """
    score = state.get("review_1_score", 0)
    threshold = settings.AGENT_QUALITY_THRESHOLD

    # If score is very low, skip second review
    if score < threshold / 2:
        logger.info(
            "Routing article %s to mark_useless (review 1 score: %.1f)",
            state.get("article_id"),
            score,
        )
        return "mark_useless"

    logger.info(
        "Routing article %s to review_2 (review 1 score: %.1f)",
        state.get("article_id"),
        score,
    )
    return "review_2"


def route_after_review_2(
    state: dict,
) -> Literal["image_text_check", "mark_useless"]:
    """
    Route after the second review node.

    If the average review score is below the quality threshold,
    mark as useless. Otherwise, proceed to image text check.

    Args:
        state: Current pipeline state.

    Returns:
        Next node name: 'image_text_check' or 'mark_useless'.
    """
    review_1 = state.get("review_1_score", 0)
    review_2 = state.get("review_2_score", 0)
    avg_score = (review_1 + review_2) / 2

    threshold = settings.AGENT_QUALITY_THRESHOLD

    if avg_score < threshold:
        logger.info(
            "Routing article %s to mark_useless (avg review score: %.1f < %.1f)",
            state.get("article_id"),
            avg_score,
            threshold,
        )
        return "mark_useless"

    logger.info(
        "Routing article %s to image_text_check (avg review score: %.1f)",
        state.get("article_id"),
        avg_score,
    )
    return "image_text_check"


def route_after_image_check(
    state: dict,
) -> Literal["image_gen", "publish"]:
    """
    Route after the image text check node.

    If image check is REJECTED, still proceed to image generation
    (to generate a replacement). Otherwise, proceed to publishing.

    Args:
        state: Current pipeline state.

    Returns:
        Next node name: 'image_gen' or 'publish'.
    """
    decision = state.get("image_check_decision", "APPROVED")

    if decision == "REJECTED":
        logger.info(
            "Routing article %s to image_gen (image check: REJECTED)",
            state.get("article_id"),
        )
        return "image_gen"

    if settings.IMAGE_GENERATION_ENABLED:
        logger.info(
            "Routing article %s to image_gen (image generation enabled)",
            state.get("article_id"),
        )
        return "image_gen"

    logger.info(
        "Routing article %s to publish (image check: APPROVED)",
        state.get("article_id"),
    )
    return "publish"


def route_after_image_gen(
    state: dict,
) -> Literal["publish", "deploy"]:
    """
    Route after the image generation node.

    If auto-publish is enabled, proceed to publish.
    Otherwise, route to deploy for manual review.

    Args:
        state: Current pipeline state.

    Returns:
        Next node name: 'publish' or 'deploy'.
    """
    if settings.AGENT_AUTO_PUBLISH:
        logger.info(
            "Routing article %s to publish (auto-publish enabled)",
            state.get("article_id"),
        )
        return "publish"

    logger.info(
        "Routing article %s to deploy (manual review required)",
        state.get("article_id"),
    )
    return "deploy"


def route_after_translation(
    state: dict,
) -> Literal["proofreading", "mark_useless"]:
    """
    Route after the translation node.

    If translation succeeded, proceed to proofreading.
    If translation failed, mark as useless.

    Args:
        state: Current pipeline state.

    Returns:
        Next node name: 'proofreading' or 'mark_useless'.
    """
    if state.get("target_content"):
        logger.info(
            "Routing article %s to proofreading (translation succeeded)",
            state.get("article_id"),
        )
        return "proofreading"

    logger.warning(
        "Routing article %s to mark_useless (translation failed)",
        state.get("article_id"),
    )
    return "mark_useless"


def route_after_proofreading(
    state: dict,
) -> Literal["review_1", "mark_useless"]:
    """
    Route after the proofreading node.

    If proofreading succeeded, proceed to the first review.
    If proofreading failed, mark as useless.

    Args:
        state: Current pipeline state.

    Returns:
        Next node name: 'review_1' or 'mark_useless'.
    """
    if state.get("target_content"):
        logger.info(
            "Routing article %s to review_1 (proofreading succeeded)",
            state.get("article_id"),
        )
        return "review_1"

    logger.warning(
        "Routing article %s to mark_useless (proofreading failed)",
        state.get("article_id"),
    )
    return "mark_useless"
