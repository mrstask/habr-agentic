"""Tests for the translation prompt loader."""


from app.etl.translation.prompts.loader import (
    load_content_filter_prompt,
    load_image_check_prompt,
    load_proofreading_prompt,
    load_translation_prompt,
)


class TestLoadTranslationPrompt:
    def test_default_languages(self):
        prompt = load_translation_prompt()
        assert "ru" in prompt
        assert "uk" in prompt
        assert "Translate" in prompt

    def test_custom_languages(self):
        prompt = load_translation_prompt(
            source_language="en", target_language="de"
        )
        assert "en" in prompt
        assert "de" in prompt

    def test_with_context(self):
        prompt = load_translation_prompt(context="Article about Python")
        assert "Article about Python" in prompt

    def test_without_context(self):
        prompt = load_translation_prompt()
        # Default context placeholder should be empty
        assert "context_info" not in prompt or "Article context" not in prompt

    def test_preserves_formatting_instructions(self):
        prompt = load_translation_prompt()
        assert "Markdown" in prompt
        assert "code blocks" in prompt


class TestLoadProofreadingPrompt:
    def test_basic_prompt(self):
        prompt = load_proofreading_prompt()
        assert "Ukrainian" in prompt
        assert "Proofread" in prompt

    def test_with_context(self):
        prompt = load_proofreading_prompt(context="Technical article about ML")
        assert "Technical article about ML" in prompt

    def test_without_context(self):
        prompt = load_proofreading_prompt()
        assert "context_info" not in prompt or "Article context" not in prompt


class TestLoadContentFilterPrompt:
    def test_returns_non_empty_string(self):
        prompt = load_content_filter_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestLoadImageCheckPrompt:
    def test_returns_non_empty_string(self):
        prompt = load_image_check_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
