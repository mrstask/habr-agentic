"""
Pipeline prompt templates loader.

Loads and formats prompt templates used by LangGraph pipeline nodes
that are not covered by the translation prompts module. This includes
prompts for article review, extraction, vectorization, and publishing.

Each prompt is stored as a .txt template file and loaded via
``pathlib.Path.read_text``. Templates may contain ``{placeholder}``
markers that are substituted at load time.

Usage::

    from app.pipeline.prompts import load_review_prompt
    prompt = load_review_prompt(review_number=1, quality_threshold=5.0)
"""

from pathlib import Path
from typing import Optional


# Base directory for pipeline prompt template files
_PROMPTS_DIR: Path = Path(__file__).parent


def load_review_prompt(
    review_number: int = 1,
    quality_threshold: float = 5.0,
    context: Optional[str] = None,
) -> str:
    """
    Load and format a review system prompt template.

    Reads the appropriate review prompt template (review_1.txt or
    review_2.txt) and substitutes placeholders with the provided
    quality threshold and article context.

    Args:
        review_number: Which review stage (1 or 2).
        quality_threshold: Minimum usefulness score for the article
            to proceed through the pipeline.
        context: Optional article context (title, tags, hubs) to
            include in the prompt for better evaluation.

    Returns:
        Formatted review system prompt string.

    Raises:
        FileNotFoundError: If the template file does not exist.
    """
    template_path = _PROMPTS_DIR / f"review_{review_number}.txt"
    template = template_path.read_text(encoding="utf-8")
    context_info = context if context is not None else ""
    return template.format(
        quality_threshold=quality_threshold,
        context_info=context_info,
    )


def load_extraction_prompt(
    source_language: str = "ru",
    target_language: str = "uk",
) -> str:
    """
    Load the article extraction system prompt template.

    Reads the extraction prompt used by the pipeline's extraction
    node to parse and extract article content from raw HTML or
    RSS feed entries.

    Args:
        source_language: BCP-47 source language code.
        target_language: BCP-47 target language code.

    Returns:
        Extraction system prompt string.

    Raises:
        FileNotFoundError: If the template file does not exist.
    """
    template_path = _PROMPTS_DIR / "extraction.txt"
    template = template_path.read_text(encoding="utf-8")
    return template.format(
        source_language=source_language,
        target_language=target_language,
    )


def load_vectorize_prompt() -> str:
    """
    Load the vectorization system prompt template.

    Reads the prompt used by the pipeline's vectorize node to
    generate a summary or key-points representation of the article
    for embedding and search indexing.

    Returns:
        Vectorization system prompt string.

    Raises:
        FileNotFoundError: If the template file does not exist.
    """
    template_path = _PROMPTS_DIR / "vectorize.txt"
    return template_path.read_text(encoding="utf-8")


def load_publish_prompt() -> str:
    """
    Load the publishing system prompt template.

    Reads the prompt used by the pipeline's publish node to
    format the final article for publication, including SEO
    metadata, excerpt generation, and CMS-ready formatting.

    Returns:
        Publishing system prompt string.

    Raises:
        FileNotFoundError: If the template file does not exist.
    """
    template_path = _PROMPTS_DIR / "publish.txt"
    return template_path.read_text(encoding="utf-8")
