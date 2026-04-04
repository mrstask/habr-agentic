# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

Habr Agentic Pipeline — a fully autonomous content pipeline that discovers, filters, translates, reviews, and publishes Habr articles to a Ukrainian tech blog (potik.dev). Built on LangGraph for workflow orchestration with a Kanban-style ops dashboard.

- **Backend**: FastAPI + SQLAlchemy (async) + LangGraph
- **Frontend**: React + TypeScript + Vite
- **Database**: SQLite (dual: app DB + articles DB + pipeline checkpoints DB)
- **LLM**: OpenAI, Grok (xAI), Ollama (local Qwen 2.5 7B + nomic-embed-text)
- **Purpose**: Autonomous Russian → Ukrainian article translation pipeline with no human-in-the-loop

## Architecture

### Backend Layers
- **Routes**: `backend/app/api/routes/` — FastAPI endpoint handlers
- **Schemas**: `backend/app/schemas/` — Pydantic request/response models
- **Services**: `backend/app/services/` — Business logic
- **Repositories**: `backend/app/repositories/` — Database access (SQLAlchemy queries)
- **Models**: `backend/app/models/` — SQLAlchemy ORM models
- **Pipeline**: `backend/app/pipeline/` — LangGraph graph, nodes, edges, prompts
- **ETL**: `backend/app/etl/` — Ported translation providers, extraction, HTML cleaning

### Frontend Structure
- **App shell**: `frontend/src/app/` — Main app with routing
- **Features**: `frontend/src/features/` — Page-level components (dashboard, articles, runs, settings)
- **Components**: `frontend/src/components/` — Reusable UI (Sidebar, BoardColumn, ArticleCard)
- **API client**: `frontend/src/lib/api.ts` — Typed fetch functions

### LangGraph Pipeline
- **State**: `backend/app/pipeline/state.py` — PipelineState, ReviewResult TypedDicts
- **Graph**: `backend/app/pipeline/graph.py` — StateGraph with 11 nodes and conditional edges
- **Nodes**: `backend/app/pipeline/nodes/` — One file per pipeline step
- **Edges**: `backend/app/pipeline/edges/routing.py` — Conditional routing functions
- **Prompts**: `backend/app/pipeline/prompts/` — LLM prompts for filter, review, image check

### Pipeline Flow
```
extraction → content_filter → translation → review_1 → proofreading → review_2 → image_text_check → image_gen → vectorize → publish → deploy
```
Failed reviews route to mark_useless (no human review). Content filter rejects Russia-specific articles.

## Development Commands

### Backend
```bash
cd backend
pip install -r requirements.txt
./run.sh                    # or: uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                 # Vite dev server on :5173
```

### Ollama (local LLM)
```bash
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text
ollama serve                # API on :11434
```

## Key Technical Details

### Database
- Dual SQLite architecture: app/admin DB + articles/content DB
- Third SQLite file for LangGraph pipeline checkpoints
- Alembic for migrations — never recreate DB to apply schema changes
- ArticleStatus enum: DISCOVERED=0, EXTRACTED=1, TRANSLATED=2, PUBLISHED=3, USELESS=4, DRAFT=5

### Pipeline Configuration
- `AGENT_ENABLED` — master switch
- `AGENT_DRY_RUN` — log-only mode
- `AGENT_AUTO_PUBLISH` — enable autonomous publishing
- `AGENT_QUALITY_THRESHOLD` — min usefulness score (default 5.0)
- Content filter uses local LLM (Ollama) with cloud fallback

### Translation
- Providers: Grok (primary), OpenAI (fallback)
- Proofreading runs as separate node (not part of translation)
- Two-pass review: review_1 (post-translation) → proofreading → review_2 (post-proofreading)
- Review checks: spell check, Russian content detection, usefulness scoring, source enrichment

### Important Patterns
- All pipeline nodes are async functions receiving PipelineState and returning dict updates
- Each article runs as an independent LangGraph thread (thread_id = article-{id})
- Failed articles are marked USELESS with structured diagnostic JSON in editorial_notes
- No human-in-the-loop gates — pipeline is fully autonomous

## Documentation
- `PROJECT_PLAN.md` — Development agents, tasks, and phases
- `LANGGRAPH_ARCHITECTURE.md` — Graph architecture (nodes, edges, state, routing)
- `AGENTS.plan.md` — Detailed agent specifications and filtering rules
- `LOCAL_LLM.md` — Local LLM setup for content filtering and embeddings

## Key File Paths (agent reference)

> Keep this section up to date as new files are created.
> All paths are relative to the project root (`habr-agentic/`).
> NEVER use the project folder name as a prefix in tool calls — paths start with `backend/`, `frontend/`, etc.

### Database / Migrations
- `backend/alembic.ini` — Alembic config
- `backend/alembic/script.py.mako` — Alembic migration template
- `backend/alembic/env.py` — async migration runner (dual-DB: AppBase + ArticleBase)
- `backend/alembic/versions/20260402_0001_initial_app_schema.py` — app DB migration (admin_users, sidebar_banners, categories, seo_settings, pipeline_runs, agent_configs)
- `backend/alembic/versions/20260402_0002_initial_articles_schema.py` — articles DB migration (articles, tags, hubs, images, article_tags, article_hubs, article_embeddings)
- `backend/alembic/versions/20260402_0003_add_article_indexes.py` — performance indexes on articles + pipeline_runs
- `backend/app/db/base.py` — AppBase + ArticleBase declarative bases (centralized)
- `backend/app/db/session.py` — async engine and session factories
- `backend/app/db/migration_utils.py` — programmatic migration helpers (get_alembic_config, run_migrations_on_startup, get_current_revision, check_pending_migrations)

### Models
- `backend/app/models/__init__.py` — model registry (imports all models for Alembic discovery)
- `backend/app/models/admin.py` — AdminUser, SidebarBanner, Category, SeoSettings (AppBase)
- `backend/app/models/article.py` — Article, Tag, Hub, Image, article_tags, article_hubs (ArticleBase)
- `backend/app/models/embedding.py` — ArticleEmbedding (ArticleBase)
- `backend/app/models/pipeline.py` — PipelineRun, AgentConfig (AppBase)
- `backend/app/models/enums.py` — ArticleStatus, PipelineStep, RunStatus

### Core Config
- `backend/app/core/config.py` — Settings (pydantic-settings), DATABASE_URL, DATABASE_ARTICLES_URL

### Tests
- `backend/tests/test_migrations_e2e.py` — End-to-end migration tests (validates all tables, columns, indexes, constraints, and downgrades)

<!-- dev_team: task #72 completed -->
## [Consolidate model bases] — done
Consolidated SQLAlchemy model bases from two separate declarative bases (AppBase, ArticleBase) into a single unified Base class.

Changes made:
1. **backend/app/db/base.py** - Created single `Base = declarative_base()` with `AppBase` and `ArticleBase` as backward-compatible aliases
2. **backend/app/models/admin.py** - Updated imports to use `Base` instead of `AppBase`
3. **backend/app/models/article.py** - Updated imports to use `Base` instead of `ArticleBase`
4. **backend/app/models/embedding.py** - Updated imports to use `Base` instead of `ArticleBase`
5. **backend/app/models/pipeline.py** - Updated imports to use `Base` instead of `AppBase`
6. **backend/alembic/env.py** - Simplified to use single `Base.metadata` instead of separate metadata objects
7. **backend/tests/test_models_*.py** - Updated all 4 test files to import `Base` instead of `AppBase`/`ArticleBase`

The dual-database separation is now handled at the engine/session level rather than through separate declarative bases, while maintaining full backward compatibility via aliases.

Files changed:
  - backend/app/db/base.py
  - backend/app/models/admin.py
  - backend/app/models/article.py
  - backend/app/models/embedding.py
  - backend/app/models/pipeline.py
  - backend/alembic/env.py
  - backend/app/db/migration_utils.py
  - backend/tests/test_models_admin.py
  - backend/tests/test_models_article.py
  - backend/tests/test_models_embedding.py
  - backend/tests/test_models_pipeline.py

<!-- dev_team: task #69 completed -->
## [Grok provider implementation] — done
Fixed the Grok and OpenAI translation providers to match test expectations. Two key changes were made to both `grok.py` and `openai.py`:

1. **Renamed `_count_corrections` → `_estimate_corrections`**: The tests call `_estimate_corrections` as a static method, so the method was renamed to match.

2. **Fixed token usage dictionary keys**: Changed from `{"input_tokens": ..., "output_tokens": ..., "total_tokens": ...}` to `{"input": ..., "output": ..., "total": ...}` to match what the tests assert.

All 283 tests pass, including the specific translation provider tests for both Grok and OpenAI.

Files changed:
  - backend/app/etl/translation/providers/grok.py
  - backend/app/etl/translation/providers/openai.py
  - backend/app/etl/translation/providers/grok.py
  - backend/app/etl/translation/providers/openai.py
  - backend/app/etl/translation/providers/grok.py
  - backend/app/etl/translation/providers/openai.py
  - backend/app/etl/translation/providers/grok.py
  - backend/app/etl/translation/providers/openai.py


<!-- dev_team: task #74 completed -->
## [Grok provider implementation] — done
Successfully implemented the Grok provider implementation for the translation ETL module. Here's what was completed:

## Files Implemented:

1. **backend/app/etl/translation/base.py**
   - Fixed unused `field` import (removed it)
   - Implemented `_build_system_prompt()` and `_build_proofreading_prompt()` methods that use the prompt loader

2. **backend/app/etl/translation/providers/grok.py**
   - Implemented `translate()` method with OpenAI-compatible client, retry logic, and metadata capture
   - Implemented `proofread()` method with proofreading prompt and correction estimation
   - Implemented `health_check()` method for API connectivity verification
   - Added `_estimate_corrections()` static method for counting corrections
   - Added `_is_retryable_error()` helper for retry logic

3. **backend/app/etl/translation/providers/openai.py**
   - Implemented `translate()` method with OpenAI client, retry logic, and metadata capture
   - Implemented `proofread()` method with proofreading prompt and correction estimation
   - Implemented `health_check()` method for API connectivity verification
   - Added `_estimate_corrections()` static method for counting corrections
   - Added `_is_retryable_error()` helper for retry logic

4. **backend/app/etl/translation/providers/factory.py**
   - Implemented `register_provider()` to add providers to registry
   - Implemented `get_registered_providers()` to list available providers
   - Implemented `create_provider()` factory with settings resolution
   - Implemented `create_fallback_provider()` for fallback logic
   - Implemented `_auto_register()` to auto-register Grok and OpenAI providers

5. **backend/app/etl/translation/prompts/loader.py**
   - Implemented `load_translation_prompt()` with template substitution
   - Implemented `load_proofreading_prompt()` with template substitution
   - Implemented `load_content_filter_prompt()` and `load_image_check_prompt()`

6. **backend/app/etl/translation/__init__.py** - Exported all public APIs
7. **backend/app/etl/translation/providers/__init__.py** - Exported provider classes and factory functions
8. **backend/app/etl/translation/prompts/__init__.py** - Exported prompt loader functions

## Key Design Decisions:

- Used `openai.AsyncOpenAI` client for both Grok and OpenAI providers (Grok uses OpenAI-compatible endpoint)
- Retry logic with configurable `max_retries` and error classification for retryable vs non-retryable errors
- Token usage and latency tracking in all results
- Correction estimation using symmetric difference of word sets
- Factory pattern with auto-registration for provider discovery
- Settings integration from `app.core.config` for API keys and configuration

All 283 tests pass successfully.

Files changed:
  - backend/app/etl/translation/base.py
  - backend/app/etl/translation/providers/grok.py
  - backend/app/etl/translation/providers/openai.py
  - backend/app/etl/translation/providers/factory.py
  - backend/app/etl/translation/prompts/loader.py
  - backend/app/etl/translation/__init__.py
  - backend/app/etl/translation/providers/__init__.py
  - backend/app/etl/translation/prompts/__init__.py
  - backend/app/etl/translation/base.py
  - backend/app/etl/translation/providers/grok.py
  - backend/app/etl/translation/providers/openai.py


<!-- dev_team: task #79 completed -->
## [OpenAI Embedding Provider] — done
Implemented all TODOs across 5 files:

1. **backend/app/etl/embedding/providers/openai.py** — Implemented `embed()` with retry loop, `client.embeddings.create()` call, vector extraction, token usage capture, and `EmbeddingResult` return. Implemented `embed_batch()` for batch embedding with partial failure handling. Implemented `health_check()` with minimal test request. Implemented `_is_retryable_error()` detecting timeouts, rate limits, connection errors, etc.

2. **backend/app/etl/embedding/providers/ollama.py** — Implemented `embed()` with retry loop, POST to `/api/embeddings`, vector extraction, and `EmbeddingResult` return. Implemented `embed_batch()` calling `embed()` per text with graceful partial failure handling. Implemented `health_check()` via GET `/api/version`. Implemented `_is_retryable_error()` for local server errors.

3. **backend/app/etl/embedding/providers/factory.py** — Implemented `register_embedding_provider()`, `get_registered_embedding_providers()`, `create_embedding_provider()` with settings resolution and validation, and `_auto_register()` for OpenAI and Ollama providers.

4. **backend/app/etl/image_generation/providers/openai.py** — Implemented `generate()` with retry loop, `client.images.generate()` call, image URL/b64 extraction, revised_prompt capture, and `ImageGenerationResult` return. Implemented `health_check()` and `_is_retryable_error()`.

5. **backend/app/etl/image_generation/providers/factory.py** — Implemented `register_image_provider()`, `get_registered_image_providers()`, `create_image_provider()` with settings resolution, and `_auto_register()` for OpenAI image provider.

All 283 tests pass.

Files changed:
  - backend/app/etl/embedding/providers/openai.py
  - backend/app/etl/embedding/providers/ollama.py
  - backend/app/etl/embedding/providers/factory.py
  - backend/app/etl/image_generation/providers/openai.py
  - backend/app/etl/image_generation/providers/factory.py
  - backend/tests/test_etl_embedding_providers_openai.py
  - backend/tests/test_etl_embedding_providers_ollama.py
  - backend/tests/test_etl_embedding_providers_factory.py
  - backend/tests/test_etl_image_generation_providers_openai.py
  - backend/tests/test_etl_image_generation_providers_factory.py
  - backend/tests/test_etl_embedding_providers_factory.py
  - backend/tests/test_etl_image_generation_providers_factory.py


<!-- dev_team: task #80 completed -->
## [Ollama Embedding Provider] — done
Implemented all TODO items across 6 skeleton files:

1. **backend/app/etl/embedding/providers/openai.py** — Implemented `embed()` with retry loop calling `client.embeddings.create()`, `embed_batch()` sending all texts in one request, `health_check()` with minimal test embedding, and `_is_retryable_error()` detecting timeouts/rate limits.

2. **backend/app/etl/embedding/providers/ollama.py** — Implemented `embed()` with retry loop calling POST `/api/embeddings`, `embed_batch()` calling `embed()` per text with partial failure handling, `health_check()` using GET `/api/version`, and `_is_retryable_error()` detecting connection/timeout errors.

3. **backend/app/etl/embedding/providers/factory.py** — Implemented `register_embedding_provider()`, `get_registered_embedding_providers()`, `create_embedding_provider()` with settings resolution for api_key/model/kwargs, and `_auto_register()` for OpenAI and Ollama providers.

4. **backend/app/etl/image_generation/providers/openai.py** — Implemented `generate()` with retry loop calling `client.images.generate()`, `health_check()` with minimal test request, and `_is_retryable_error()`.

5. **backend/app/etl/image_generation/providers/factory.py** — Implemented `register_image_provider()`, `get_registered_image_providers()`, `create_image_provider()` with `provider_name` parameter and settings resolution, and `_auto_register()`.

All implementations follow the same patterns as the existing translation providers (retry loops, error handling, latency tracking, token usage capture).

Files changed:
  - backend/app/etl/embedding/providers/openai.py
  - backend/app/etl/embedding/providers/ollama.py
  - backend/app/etl/embedding/providers/factory.py
  - backend/app/etl/image_generation/providers/openai.py
  - backend/app/etl/image_generation/providers/factory.py
  - backend/app/etl/embedding/providers/factory.py
  - backend/app/etl/image_generation/providers/factory.py
  - backend/app/etl/embedding/providers/ollama.py
  - backend/app/etl/embedding/providers/factory.py


<!-- dev_team: task #81 completed -->
## [Embedding Factory] — done
Implemented all TODO items across 6 skeleton files:

**Embedding providers:**
1. `backend/app/etl/embedding/providers/openai.py` — Implemented `embed()` with retry loop calling `client.embeddings.create()`, `embed_batch()` for batch processing, `health_check()` with minimal test request, and `_is_retryable_error()` detecting timeouts, rate limits, connection errors, etc.

2. `backend/app/etl/embedding/providers/ollama.py` — Implemented `embed()` with retry loop calling POST `/api/embeddings`, `embed_batch()` iterating over texts with graceful partial failure handling, `health_check()` via GET `/api/version`, and `_is_retryable_error()` for connection/timeout detection.

3. `backend/app/etl/embedding/providers/factory.py` — Implemented `register_embedding_provider()`, `get_registered_embedding_providers()`, `create_embedding_provider()` with settings resolution (OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL, OLLAMA_BASE_URL, OLLAMA_EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, timeouts, retries), and `_auto_register()` with ImportError handling.

**Image generation providers:**
4. `backend/app/etl/image_generation/providers/openai.py` — Implemented `generate()` with retry loop calling `client.images.generate()`, `health_check()` with minimal test request, and `_is_retryable_error()`.

5. `backend/app/etl/image_generation/providers/factory.py` — Implemented `register_image_provider()`, `get_registered_image_providers()`, `create_image_provider()` with settings resolution (OPENAI_API_KEY, IMAGE_GENERATION_MODEL, timeouts, retries), and `_auto_register()`.

All implementations follow the translation factory pattern with proper retry loops, error handling, and settings resolution.

Files changed:
  - backend/app/etl/embedding/providers/openai.py
  - backend/app/etl/embedding/providers/ollama.py
  - backend/app/etl/embedding/providers/factory.py
  - backend/app/etl/image_generation/providers/openai.py
  - backend/app/etl/image_generation/providers/factory.py
  - backend/app/etl/embedding/providers/factory.py
  - backend/app/etl/image_generation/providers/factory.py
  - backend/tests/test_etl_embedding_providers_factory.py
  - backend/tests/test_etl_embedding_providers_openai.py
  - backend/tests/test_etl_embedding_providers_ollama.py
  - backend/tests/test_etl_image_generation_providers_openai.py
  - backend/tests/test_etl_image_generation_providers_factory.py
  - … (10 more)


<!-- dev_team: task #82 completed -->
## [OpenAI Image Generation Provider] — done
Implemented all TODO items across 4 files:

1. **backend/app/etl/image_generation/providers/openai.py** — Implemented `OpenAIImageGenerationProvider.generate()` with retry loop calling `client.images.generate()`, extracting `url`/`b64_json`/`revised_prompt` from response.data[0], and returning `ImageGenerationResult`. Implemented `health_check()` with a minimal test image request. Implemented `_is_retryable_error()` detecting timeouts, rate limits, connection errors, etc.

2. **backend/app/etl/image_generation/providers/factory.py** — Implemented `register_image_provider()` (adds to registry + logs), `get_registered_image_providers()` (returns registry keys), `create_image_provider()` (resolves api_key/model from settings, validates, builds kwargs, instantiates provider), and `_auto_register()` (imports and registers OpenAIImageGenerationProvider).

3. **backend/app/etl/embedding/providers/openai.py** — Implemented `OpenAIEmbeddingProvider.embed()` with retry loop calling `client.embeddings.create()`, extracting embedding vector, token usage, and dimensions. Implemented `embed_batch()` sending all texts in one request and building results per item. Implemented `health_check()` and `_is_retryable_error()`.

4. **backend/app/etl/embedding/providers/ollama.py** — Implemented `OllamaEmbeddingProvider.embed()` with retry loop calling POST `/api/embeddings`, extracting embedding from response JSON. Implemented `embed_batch()` calling embed() per text with graceful partial failure handling. Implemented `health_check()` via GET `/api/version` and `_is_retryable_error()`.

5. **backend/app/etl/embedding/providers/factory.py** — Implemented `register_embedding_provider()`, `get_registered_embedding_providers()`, `create_embedding_provider()` (resolves api_key/model/dimensions from settings per provider type, validates, instantiates), and `_auto_register()` (imports and registers both OpenAI and Ollama providers).

All 317 tests pass, lint checks pass with no errors.

Files changed:
  - backend/app/etl/image_generation/providers/openai.py
  - backend/app/etl/image_generation/providers/factory.py
  - backend/app/etl/embedding/providers/openai.py
  - backend/app/etl/embedding/providers/ollama.py
  - backend/app/etl/embedding/providers/factory.py
  - backend/app/etl/embedding/providers/openai.py


<!-- dev_team: task #84 completed -->
## [Implement pipeline prompt loader] — done
Implemented the pipeline prompt loader in `backend/app/pipeline/prompts/loader.py` and its tests in `backend/tests/test_pipeline_prompts_loader.py`.

**loader.py** — 4 functions implemented:
1. `load_review_prompt(review_number, quality_threshold, context)` — selects `review_1.txt` or `review_2.txt` based on review_number, reads via `Path.read_text(encoding="utf-8")`, substitutes `{quality_threshold}` and `{context_info}` placeholders using `str.format()`. Invalid review_number naturally raises `FileNotFoundError`.
2. `load_extraction_prompt(source_language, target_language)` — reads `extraction.txt`, substitutes `{source_language}` and `{target_language}`.
3. `load_vectorize_prompt()` — reads and returns `vectorize.txt` as-is (no placeholders).
4. `load_publish_prompt()` — reads and returns `publish.txt` as-is (no placeholders).

**test_pipeline_prompts_loader.py** — 22 tests covering all loader functions: non-empty returns, placeholder substitution, default values, context handling, invalid review_number raising FileNotFoundError, and content verification (Ukrainian mentions, SEO, tags, embeddings, etc.).

All 339 tests pass (tox).

Files changed:
  - backend/app/pipeline/prompts/loader.py
  - backend/tests/test_pipeline_prompts_loader.py
  - backend/tests/test_pipeline_prompts_loader.py


<!-- dev_team: task #85 completed -->
## [Implement pipeline prompt loader tests] — done
Implemented the pipeline prompt loader tests in `backend/tests/test_pipeline_prompts_loader.py`. The test file covers all four loader functions:

- **TestLoadReviewPrompt** (10 tests): verifies review 1/2 return non-empty strings, quality threshold substitution (custom and default values), context inclusion/exclusion, FileNotFoundError for invalid review_number, and content checks (Ukrainian mention, independent review mention).
- **TestLoadExtractionPrompt** (4 tests): verifies non-empty return, default language substitution (ru→uk), custom language substitution, and extraction task keywords.
- **TestLoadVectorizePrompt** (4 tests): verifies non-empty return, summary mention, key points mention, and vector/embedding/search references.
- **TestLoadPublishPrompt** (4 tests): verifies non-empty return, SEO mention, publication/CMS reference, and tags/categories mention.

The loader implementation in `backend/app/pipeline/prompts/loader.py` was already complete on disk. All 339 tests pass.

Files changed:
  - backend/tests/test_pipeline_prompts_loader.py


<!-- dev_team: task #86 completed -->
## [HTML extraction provider implementation] — done
Implemented the HTML extraction provider with three files:

1. **backend/app/etl/extraction/providers/factory.py** — Factory and registry for extraction providers. Provides `create_extraction_provider()`, `register_extraction_provider()`, and `get_registered_extraction_providers()`. Auto-registers HtmlExtractionProvider and RssExtractionProvider on import.

2. **backend/app/etl/extraction/providers/html.py** — HtmlExtractionProvider that fetches HTML pages via httpx.AsyncClient and parses them with BeautifulSoup. Extracts title, content, excerpt, author, published_at, tags, hubs, and image URLs with Habr-specific selectors and fallbacks. Includes retry logic, health check, and error classification.

3. **backend/app/etl/extraction/providers/rss.py** — RssExtractionProvider that fetches and parses RSS/Atom feeds using xml.etree.ElementTree. Supports both RSS and Atom formats, handles XML namespaces, extracts media content/thumbnails/enclosures, and can process pre-fetched feed entry dictionaries. Includes retry logic, health check, and error classification.

All 339 tests pass and lint checks pass.

Files changed:
  - backend/app/etl/extraction/providers/factory.py
  - backend/app/etl/extraction/providers/html.py
  - backend/app/etl/extraction/providers/rss.py
  - backend/app/etl/extraction/providers/factory.py
  - backend/tests/test_etl_extraction_base.py
  - backend/tests/test_etl_extraction_providers_factory.py
  - backend/tests/test_etl_extraction_providers_html.py
  - backend/tests/test_etl_extraction_providers_rss.py
  - backend/tests/test_etl_extraction_providers_factory.py
  - backend/tests/test_etl_extraction_providers_html.py
  - backend/tests/test_etl_extraction_providers_rss.py
  - backend/tests/test_etl_extraction_providers_factory.py
  - … (5 more)
