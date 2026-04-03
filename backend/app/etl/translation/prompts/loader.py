"""
Translation prompt templates.

Contains prompt templates for translation and proofreading operations.
Prompts are loaded as text resources and can be parameterized with
language codes, context, and other variables.

Usage::

    from app.etl.translation.prompts import load_translation_prompt
    prompt = load_translation_prompt(source_lang="ru", target_lang="uk")
"""

from pathlib import Path
from typing import Optional


# Base directory for prompt template files
_PROMPTS_DIR: Path = Path(__file__).parent


def load_translation_prompt(
    source_language: str = "ru",
    target_language: str = "uk",
    context: Optional[str] = None,
) -> str:
    """
    Load and format the translation system prompt template.

    Reads the translation prompt template file and substitutes
    placeholders with the provided language codes and context.

    Args:
        source_language: BCP-47 source language code.
        target_language: BCP-47 target language code.
        context: Optional article context (title, tags, hubs).

    Returns:
        Formatted translation system prompt string.
    """
    template_path = _PROMPTS_DIR / "translation.txt"
    template = template_path.read_text(encoding="utf-8")

    # Build context info line
    if context:
        context_info = f"\nArticle context: {context}"
    else:
        context_info = ""

    return template.format(
        source_language=source_language,
        target_language=target_language,
        context_info=context_info,
    )


def load_proofreading_prompt(
    context: Optional[str] = None,
) -> str:
    """
    Load and format the proofreading system prompt template.

    Reads the proofreading prompt template file and substitutes
    placeholders with the provided context.

    Args:
        context: Optional article context for better proofreading.

    Returns:
        Formatted proofreading system prompt string.
    """
    template_path = _PROMPTS_DIR / "proofreading.txt"
    template = template_path.read_text(encoding="utf-8")

    # Build context info line
    if context:
        context_info = f"\nArticle context: {context}"
    else:
        context_info = ""

    return template.format(context_info=context_info)


def load_content_filter_prompt() -> str:
    """
    Load the content filter system prompt template.

    Reads the content filter prompt used by the pipeline's content_filter
    node to determine if an article is relevant for the Ukrainian audience.

    Returns:
        Content filter system prompt string.
    """
    template_path = _PROMPTS_DIR / "content_filter.txt"
    return template_path.read_text(encoding="utf-8")


def load_image_check_prompt() -> str:
    """
    Load the image text check system prompt template.

    Reads the prompt used by the pipeline's image_text_check node
    to verify that images contain appropriate text content.

    Returns:
        Image text check system prompt string.
    """
    template_path = _PROMPTS_DIR / "image_check.txt"
    return template_path.read_text(encoding="utf-8")
