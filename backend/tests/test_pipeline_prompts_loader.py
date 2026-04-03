"""Tests for the pipeline prompt templates loader.

Covers all loader functions in ``app.pipeline.prompts.loader``:
- ``load_review_prompt`` (review 1 and review 2)
- ``load_extraction_prompt``
- ``load_vectorize_prompt``
- ``load_publish_prompt``
"""

import pytest

from app.pipeline.prompts.loader import (
    load_review_prompt,
    load_extraction_prompt,
    load_vectorize_prompt,
    load_publish_prompt,
)


# ---------------------------------------------------------------------------
# load_review_prompt
# ---------------------------------------------------------------------------

class TestLoadReviewPrompt:
    """Tests for ``load_review_prompt``."""

    def test_review_1_returns_non_empty_string(self) -> None:
        """Review 1 prompt should return a non-empty string."""
        result = load_review_prompt(review_number=1)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_review_2_returns_non_empty_string(self) -> None:
        """Review 2 prompt should return a non-empty string."""
        result = load_review_prompt(review_number=2)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_review_1_contains_quality_threshold(self) -> None:
        """Review 1 prompt should contain the quality threshold value."""
        result = load_review_prompt(review_number=1, quality_threshold=7.5)
        assert "7.5" in result

    def test_review_2_contains_quality_threshold(self) -> None:
        """Review 2 prompt should contain the quality threshold value."""
        result = load_review_prompt(review_number=2, quality_threshold=6.0)
        assert "6.0" in result

    def test_review_1_default_threshold(self) -> None:
        """Review 1 prompt should use default threshold of 5.0."""
        result = load_review_prompt(review_number=1)
        assert "5.0" in result

    def test_review_with_context(self) -> None:
        """Review prompt should include context when provided."""
        result = load_review_prompt(review_number=1, context="Python article")
        assert "Python article" in result

    def test_review_without_context(self) -> None:
        """Review prompt should not contain placeholder when no context."""
        result = load_review_prompt(review_number=1)
        assert "{context_info}" not in result

    def test_invalid_review_number_raises(self) -> None:
        """An invalid review_number should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_review_prompt(review_number=3)

    def test_review_1_mentions_ukrainian(self) -> None:
        """Review 1 prompt should reference Ukrainian audience."""
        result = load_review_prompt(review_number=1)
        assert "Ukrainian" in result

    def test_review_2_mentions_independent(self) -> None:
        """Review 2 prompt should mention it is an independent review."""
        result = load_review_prompt(review_number=2)
        assert "independent" in result.lower()


# ---------------------------------------------------------------------------
# load_extraction_prompt
# ---------------------------------------------------------------------------

class TestLoadExtractionPrompt:
    """Tests for ``load_extraction_prompt``."""

    def test_returns_non_empty_string(self) -> None:
        """Extraction prompt should return a non-empty string."""
        result = load_extraction_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_default_languages(self) -> None:
        """Default languages should be ru -> uk."""
        result = load_extraction_prompt()
        assert "ru" in result
        assert "uk" in result

    def test_custom_languages(self) -> None:
        """Custom language codes should be substituted."""
        result = load_extraction_prompt(source_language="en", target_language="de")
        assert "en" in result
        assert "de" in result

    def test_mentions_extraction_tasks(self) -> None:
        """Prompt should mention extraction-related tasks."""
        result = load_extraction_prompt()
        assert any(
            keyword in result
            for keyword in ("extract", "title", "content", "Markdown")
        )


# ---------------------------------------------------------------------------
# load_vectorize_prompt
# ---------------------------------------------------------------------------

class TestLoadVectorizePrompt:
    """Tests for ``load_vectorize_prompt``."""

    def test_returns_non_empty_string(self) -> None:
        """Vectorize prompt should return a non-empty string."""
        result = load_vectorize_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mentions_summary(self) -> None:
        """Prompt should mention summary generation."""
        result = load_vectorize_prompt()
        assert "summary" in result.lower()

    def test_mentions_key_points(self) -> None:
        """Prompt should mention key points extraction."""
        result = load_vectorize_prompt()
        assert "key" in result.lower()

    def test_mentions_vector_embeddings(self) -> None:
        """Prompt should reference vector embeddings."""
        result = load_vectorize_prompt()
        assert "vector" in result.lower()


# ---------------------------------------------------------------------------
# load_publish_prompt
# ---------------------------------------------------------------------------

class TestLoadPublishPrompt:
    """Tests for ``load_publish_prompt``."""

    def test_returns_non_empty_string(self) -> None:
        """Publish prompt should return a non-empty string."""
        result = load_publish_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mentions_seo(self) -> None:
        """Prompt should mention SEO optimization."""
        result = load_publish_prompt()
        assert "SEO" in result

    def test_mentions_cms(self) -> None:
        """Prompt should reference CMS formatting."""
        result = load_publish_prompt()
        assert "CMS" in result

    def test_mentions_metadata(self) -> None:
        """Prompt should mention metadata fields."""
        result = load_publish_prompt()
        assert "metadata" in result.lower()
