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