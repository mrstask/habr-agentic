# Habr Agentic Pipeline — Project Plan

## Overview

A standalone agentic content pipeline that discovers, filters, translates, reviews, and publishes Habr articles to a Ukrainian tech blog. Built on LangGraph for workflow orchestration with a Kanban-style ops dashboard for monitoring.

**This is a new project.** It is not an extension of the admin_app. Useful implementations (translation providers, ETL services, site generator) will be copied and adapted, not imported.

---

## What Gets Copied from admin_app

| Component | Source Path | What to Copy | Adapt |
|-----------|-----------|-------------|-------|
| Translation providers | `backend/app/etl/translation/providers/` | `base_translator.py`, `openai_translator.py`, `grok_translator.py` | Async-native rewrite, remove `asyncio.to_thread` wrappers |
| Translation prompts | `backend/app/etl/translation/prompts/` | `translation.py`, `style.py`, `analysis.py` | Keep as-is |
| HTML cleaner | `backend/app/utils/html_cleaner.py` | Image tokenization, URL restoration | Keep as-is |
| Article extraction | `backend/app/etl/extraction/` | `article_discovery.py`, `article_content_extraction.py` | Adapt to new models |
| Image generation | `backend/app/api/services/runware.py` | Runware service | Keep as-is |
| Site generator | `backend/app/etl/generation/site_generator.py` | Jinja2 template rendering | Adapt to new DB schema |
| Jinja2 templates | `backend/app/templates/` | All templates | Keep as-is |
| Config patterns | `backend/app/core/config.py` | Pydantic Settings class | Extend with agent config |

## What Gets Copied from ai-ui

| Component | Source Path | What to Copy | Adapt |
|-----------|-----------|-------------|-------|
| Backend architecture | `backend/app/` | Layered pattern (routes → services → repositories → models) | Use for all new code |
| Orchestration boundary | `backend/app/orchestration/` | `base.py` ABC, `langgraph_adapter.py` placeholder | Implement real LangGraph adapter |
| DB setup | `backend/app/db/` | Session factory, Alembic config, init pattern | Reuse |
| Frontend shell | `frontend/src/` | App shell, Sidebar, TopBar, routing pattern | Adapt for pipeline dashboard |
| Kanban board | `frontend/src/features/tasks/` | DashboardPage, BoardColumn, TaskCard | Adapt columns to pipeline statuses |
| Run history | `frontend/src/features/runs/` | RunsPage pattern | Adapt for pipeline run tracking |
| API client | `frontend/src/lib/api.ts` | Fetch-based typed API client | Extend for pipeline endpoints |
| Constants pattern | `backend/app/constants/` | Numeric status mapping | Use for ArticleStatus, PipelineStep |

---

## Tech Stack

### Backend
- **Framework**: FastAPI
- **ORM**: SQLAlchemy 2.x (async)
- **Migrations**: Alembic
- **Database**: SQLite (3 files: app, articles, pipeline checkpoints)
- **Orchestration**: LangGraph with `AsyncSqliteSaver`
- **LLM**: OpenAI SDK (cloud providers + Ollama for local)
- **Validation**: Pydantic v2

### Frontend
- **Framework**: React 19
- **Build**: Vite
- **Language**: TypeScript (strict)
- **Styling**: CSS (or Ant Design — TBD based on preference)

### Local LLM
- **Runtime**: Ollama
- **Content filter model**: Qwen 2.5 7B Instruct
- **Embedding model**: nomic-embed-text

---

## Development Agents

These are the AI agent roles responsible for building the application. Each agent has a defined scope, capabilities, and deliverables.

### Agent 1: Architect

- **Slug**: `architect`
- **Role**: System design, data modeling, API contract definition
- **Capabilities**: Database schema design, API specification, project structure, dependency management
- **Deliverables**:
  - Final project directory structure
  - SQLAlchemy models and Alembic migrations
  - Pydantic schemas for all endpoints
  - API router stubs with typed signatures
  - Configuration class with all settings
  - `pyproject.toml` or `requirements.txt`

### Agent 2: Pipeline Builder

- **Slug**: `pipeline-builder`
- **Role**: Implement the LangGraph pipeline — state, nodes, edges, graph compilation
- **Capabilities**: LangGraph StateGraph, node functions, conditional routing, checkpointing
- **Deliverables**:
  - `PipelineState` and `ReviewResult` type definitions
  - All 11 node implementations (extraction → deploy)
  - Routing functions for conditional edges
  - Graph compilation with `AsyncSqliteSaver`
  - Discovery loop and metadata maintenance
  - Scheduler integration with FastAPI lifespan
- **Dependencies**: Needs Architect agent output (models, schemas, config)

### Agent 3: ETL Porter

- **Slug**: `etl-porter`
- **Role**: Copy and adapt ETL services from admin_app to the new project
- **Capabilities**: Code migration, async rewrite, interface adaptation
- **Deliverables**:
  - Translation providers (async-native, no `asyncio.to_thread`)
  - Translation prompts (content, style, analysis)
  - HTML cleaner with image tokenization
  - Article discovery and extraction services
  - Image generation service (Runware)
  - Site generator with Jinja2 templates
- **Dependencies**: Needs Architect agent output (new model interfaces)

### Agent 4: Review Engine Builder

- **Slug**: `review-engine`
- **Role**: Build the new review system — spell check, Russian detection, usefulness scoring, source enrichment
- **Capabilities**: LLM prompt engineering, content analysis, multi-check validation
- **Deliverables**:
  - Review node implementation (shared for review_1 and review_2)
  - Review LLM prompt with 4-check JSON output
  - Content filter node with local LLM integration (Ollama)
  - Content filter prompt for Russia-relevance classification
  - Auto-fix logic (spelling corrections, Russian fragment removal)
- **Dependencies**: Needs Pipeline Builder output (node interface), ETL Porter output (translation prompts as reference)

### Agent 5: Vision & Embedding Builder

- **Slug**: `vision-embedding`
- **Role**: Build image text check and vectorization nodes
- **Capabilities**: Vision LLM integration, embedding generation, cosine similarity search
- **Deliverables**:
  - Image text check node (vision model OCR, Russian detection, image regeneration)
  - Image text check prompt for vision model
  - Vectorize node (embedding generation, storage, related articles)
  - `ArticleEmbedding` model and repository
  - Cosine similarity search function
  - Ollama embedding integration with cloud fallback
- **Dependencies**: Needs Architect agent output (models), Pipeline Builder output (node interface)

### Agent 6: Dashboard Builder

- **Slug**: `dashboard-builder`
- **Role**: Build the ops dashboard frontend and its backend API
- **Capabilities**: React, TypeScript, Vite, API client, Kanban board
- **Deliverables**:
  - App shell (sidebar, topbar, routing)
  - Pipeline dashboard — Kanban board with pipeline step columns
  - Article detail view with content preview
  - Pipeline run history page
  - Agent status and configuration page
  - Pipeline control panel (enable/disable, trigger, config)
  - API client with typed fetch functions
  - Backend API router for pipeline management (`/api/pipeline/*`)
- **Dependencies**: Needs Architect agent output (API contracts), Pipeline Builder output (state definition for display)

---

## Tasks

### Phase 1: Foundation

| # | Task | Agent | Priority | Description |
|---|------|-------|----------|-------------|
| 1.1 | Initialize project scaffold | Architect | Critical | Create directory structure, `pyproject.toml`/`requirements.txt`, Vite config, TypeScript config, `.gitignore` |
| 1.2 | Define database models | Architect | Critical | SQLAlchemy models: Article, Tag, Hub, Image, ArticleEmbedding, PipelineRun, AgentConfig. Admin models: AdminUser, SidebarBanner, Category, SeoSettings |
| 1.3 | Create Alembic migrations | Architect | Critical | Initial migration for all tables. Dual-database session factory |
| 1.4 | Define Pydantic schemas | Architect | High | Request/response schemas for all API endpoints |
| 1.5 | Define configuration class | Architect | Critical | Pydantic Settings with all env vars: DB URLs, LLM provider keys, agent settings, Ollama config |
| 1.6 | Create API router stubs | Architect | High | Stub routes for: articles, pipeline, dashboard, site, auth |
| 1.7 | Set up FastAPI app entry point | Architect | Critical | main.py with CORS, static mounts, router registration, lifespan hooks |

### Phase 2: ETL Services

| # | Task | Agent | Priority | Description |
|---|------|-------|----------|-------------|
| 2.1 | Port translation providers | ETL Porter | Critical | Copy and async-rewrite `base_translator.py`, `openai_translator.py`, `grok_translator.py`. Remove `asyncio.to_thread` wrappers |
| 2.2 | Port translation prompts | ETL Porter | Critical | Copy `translation.py`, `style.py`, `analysis.py` prompts. No changes needed |
| 2.3 | Port HTML cleaner | ETL Porter | High | Copy `html_cleaner.py` with image tokenization and URL restoration |
| 2.4 | Port article discovery service | ETL Porter | High | Copy and adapt `ArticleDiscoveryService` to new models |
| 2.5 | Port article extraction service | ETL Porter | High | Copy and adapt `ArticleContentExtractionService` to new models |
| 2.6 | Port image generation service | ETL Porter | Medium | Copy `RunwareService` and `generate_article_image` helper |
| 2.7 | Port site generator | ETL Porter | Medium | Copy `SiteGeneratorService` and Jinja2 templates. Adapt to new DB schema |
| 2.8 | Port deployment service | ETL Porter | Low | Copy `deploy_to_digitalocean` function |

### Phase 3: LangGraph Pipeline

| # | Task | Agent | Priority | Description |
|---|------|-------|----------|-------------|
| 3.1 | Define PipelineState and ReviewResult | Pipeline Builder | Critical | TypedDict definitions matching LANGGRAPH_ARCHITECTURE.md state spec |
| 3.2 | Implement extraction node | Pipeline Builder | Critical | Wrap `ArticleContentExtractionService`, handle 404/parse errors → mark_useless |
| 3.3 | Implement content_filter node | Review Engine | Critical | Local LLM call (Ollama Qwen 2.5 7B), cloud fallback, JSON classification output |
| 3.4 | Write content filter prompt | Review Engine | Critical | Russia-relevance classification prompt with accept/reject/confidence JSON output |
| 3.5 | Implement mark_useless node | Pipeline Builder | High | Set USELESS status, store structured diagnostic JSON in editorial_notes, log |
| 3.6 | Implement translation node | Pipeline Builder | Critical | Wrap `ArticleTranslationService.translate(enable_proofreading=False)` |
| 3.7 | Implement review node | Review Engine | Critical | Shared logic for review_1 and review_2: spell check, Russian detection, usefulness, enrichment |
| 3.8 | Write review prompt | Review Engine | Critical | Multi-check LLM prompt returning spell_errors, russian_fragments, usefulness_score, sources JSON |
| 3.9 | Implement proofreading node | Pipeline Builder | High | Wrap `BaseTranslator.proofread_translation()` |
| 3.10 | Implement image_text_check node | Vision & Embedding Builder | High | Vision model OCR, Russian text detection, image regeneration |
| 3.11 | Write image text check prompt | Vision & Embedding Builder | High | Vision model prompt for text detection and language identification |
| 3.12 | Implement image_gen node | Pipeline Builder | Medium | Wrap Runware/OpenAI/Grok image generation, non-blocking fallback |
| 3.13 | Implement vectorize node | Vision & Embedding Builder | High | Embedding generation (Ollama), storage, cosine similarity, related articles |
| 3.14 | Implement publish node | Pipeline Builder | Medium | Set PUBLISHED status, approved_by="pipeline_agent", gated by AGENT_AUTO_PUBLISH |
| 3.15 | Implement deploy node | Pipeline Builder | Medium | Wrap site generation + DigitalOcean deployment, batching and cooldown |
| 3.16 | Define routing functions | Pipeline Builder | Critical | `route_content_filter`, `route_review_1`, `route_review_2`, `route_publish` |
| 3.17 | Build and compile StateGraph | Pipeline Builder | Critical | Wire all nodes and edges, compile with `AsyncSqliteSaver` checkpointer |
| 3.18 | Implement discovery loop | Pipeline Builder | High | Periodic `ArticleDiscoveryService.update_articles()`, spawn pipeline per article |
| 3.19 | Implement pipeline processing loop | Pipeline Builder | High | Pick up DISCOVERED articles, invoke graph per article with thread_id |
| 3.20 | Implement metadata maintenance loop | Pipeline Builder | Low | Periodic tag/hub translation and URL generation |
| 3.21 | Integrate scheduler with FastAPI lifespan | Pipeline Builder | High | asyncio tasks for discovery, pipeline, metadata loops in lifespan context |

### Phase 4: Dashboard Backend API

| # | Task | Agent | Priority | Description |
|---|------|-------|----------|-------------|
| 4.1 | Pipeline status API | Dashboard Builder | High | `GET /api/pipeline/status` — queue sizes, last run times, agent health |
| 4.2 | Pipeline trigger API | Dashboard Builder | High | `POST /api/pipeline/trigger` — force immediate pipeline run |
| 4.3 | Pipeline toggle API | Dashboard Builder | High | `POST /api/pipeline/toggle` — enable/disable pipeline |
| 4.4 | Pipeline runs API | Dashboard Builder | High | `GET /api/pipeline/runs` — list runs with filtering by step/status/article |
| 4.5 | Pipeline config API | Dashboard Builder | Medium | `GET/POST /api/pipeline/config` — view/update agent runtime config |
| 4.6 | Articles API | Dashboard Builder | High | `GET /api/articles` — list with filtering by status, `GET /api/articles/{id}` — detail with pipeline history |
| 4.7 | Dashboard stats API | Dashboard Builder | Medium | `GET /api/dashboard/stats` — article counts by status, pipeline throughput, failure rates |

### Phase 5: Dashboard Frontend

| # | Task | Agent | Priority | Description |
|---|------|-------|----------|-------------|
| 5.1 | Initialize frontend scaffold | Dashboard Builder | Critical | Vite + React + TypeScript setup, app shell, routing |
| 5.2 | Build sidebar and navigation | Dashboard Builder | High | Collapsible sidebar with: Dashboard, Articles, Pipeline, Runs, Settings |
| 5.3 | Build pipeline Kanban board | Dashboard Builder | Critical | Columns: DISCOVERED → EXTRACTED → FILTERED → TRANSLATED → REVIEWED → PUBLISHED. Article cards with status badges |
| 5.4 | Build article detail view | Dashboard Builder | High | Content preview (source + translated side-by-side), pipeline run history, review scores, editorial notes |
| 5.5 | Build pipeline run history page | Dashboard Builder | Medium | Table: article, step, status, started/completed, error, duration |
| 5.6 | Build pipeline control panel | Dashboard Builder | High | Enable/disable toggle, trigger button, config editor, provider status indicators |
| 5.7 | Build dashboard stats page | Dashboard Builder | Medium | Article counts by status, pipeline throughput chart, recent failures |
| 5.8 | Build API client | Dashboard Builder | High | Typed fetch functions for all backend endpoints |

### Phase 6: Integration & Polish

| # | Task | Agent | Priority | Description |
|---|------|-------|----------|-------------|
| 6.1 | End-to-end pipeline test | Pipeline Builder | Critical | Test full happy path: discovery → extraction → filter → translate → review_1 → proofread → review_2 → image_text_check → image_gen → vectorize → publish → deploy |
| 6.2 | Content filter accuracy test | Review Engine | High | Test with 20+ articles — verify Russia-specific articles rejected, global articles accepted |
| 6.3 | Review quality calibration | Review Engine | High | Tune usefulness threshold, spell check accuracy, Russian detection precision |
| 6.4 | Embedding quality test | Vision & Embedding Builder | Medium | Verify related article suggestions make semantic sense |
| 6.5 | Failure path testing | Pipeline Builder | High | Test all failure routes: extraction 404, filter reject, review_1 fail, review_2 fail, image gen fail, deploy fail |
| 6.6 | Checkpoint recovery test | Pipeline Builder | Medium | Kill process mid-pipeline, verify resume from last completed node |
| 6.7 | Documentation | Architect | Medium | README, CLAUDE.md, API docs, deployment guide |

---

## Project Structure

```
habr-agentic-pipeline/
├── backend/
│   ├── app/
│   │   ├── main.py                        # FastAPI app, lifespan, router registration
│   │   ├── core/
│   │   │   ├── config.py                  # Pydantic Settings (all env vars)
│   │   │   └── logging.py                 # Structured logging setup
│   │   ├── db/
│   │   │   ├── base.py                    # SQLAlchemy declarative bases (AdminBase, ArticleBase)
│   │   │   ├── session.py                 # Dual async session factories
│   │   │   └── init_db.py                 # Alembic auto-upgrade + seed
│   │   ├── models/
│   │   │   ├── article.py                 # Article, Tag, Hub, Image, article_tags, article_hubs
│   │   │   ├── admin.py                   # AdminUser, SidebarBanner, Category, SeoSettings
│   │   │   ├── pipeline.py                # PipelineRun, AgentConfig
│   │   │   ├── embedding.py               # ArticleEmbedding
│   │   │   └── enums.py                   # ArticleStatus, PipelineStep, RunStatus
│   │   ├── schemas/
│   │   │   ├── article.py
│   │   │   ├── pipeline.py
│   │   │   ├── dashboard.py
│   │   │   └── config.py
│   │   ├── repositories/
│   │   │   ├── article_repository.py
│   │   │   ├── pipeline_repository.py
│   │   │   └── embedding_repository.py
│   │   ├── services/
│   │   │   ├── auth.py
│   │   │   ├── site_generator.py
│   │   │   ├── deployment.py
│   │   │   └── runware.py
│   │   ├── api/
│   │   │   ├── router.py                  # Router aggregation
│   │   │   ├── deps.py                    # DB session dependencies
│   │   │   └── routes/
│   │   │       ├── articles.py
│   │   │       ├── pipeline.py
│   │   │       ├── dashboard.py
│   │   │       └── health.py
│   │   ├── pipeline/                      # LangGraph pipeline
│   │   │   ├── graph.py                   # StateGraph definition + compilation
│   │   │   ├── state.py                   # PipelineState, ReviewResult
│   │   │   ├── nodes/
│   │   │   │   ├── extraction.py
│   │   │   │   ├── content_filter.py
│   │   │   │   ├── mark_useless.py
│   │   │   │   ├── translation.py
│   │   │   │   ├── review.py
│   │   │   │   ├── proofreading.py
│   │   │   │   ├── image_text_check.py
│   │   │   │   ├── image_gen.py
│   │   │   │   ├── vectorize.py
│   │   │   │   ├── publish.py
│   │   │   │   └── deploy.py
│   │   │   ├── edges/
│   │   │   │   └── routing.py
│   │   │   ├── prompts/
│   │   │   │   ├── content_filter.py
│   │   │   │   ├── review.py
│   │   │   │   └── image_text_check.py
│   │   │   ├── discovery.py
│   │   │   ├── metadata.py
│   │   │   ├── scheduler.py
│   │   │   └── embeddings.py
│   │   ├── etl/                           # Ported from admin_app
│   │   │   ├── translation/
│   │   │   │   ├── providers/
│   │   │   │   │   ├── base_translator.py
│   │   │   │   │   ├── openai_translator.py
│   │   │   │   │   └── grok_translator.py
│   │   │   │   ├── prompts/
│   │   │   │   │   ├── translation.py
│   │   │   │   │   ├── style.py
│   │   │   │   │   └── analysis.py
│   │   │   │   └── article_translation.py
│   │   │   ├── extraction/
│   │   │   │   ├── article_discovery.py
│   │   │   │   └── article_content_extraction.py
│   │   │   └── utils/
│   │   │       └── html_cleaner.py
│   │   └── templates/                     # Jinja2 templates for static site
│   ├── alembic/
│   │   ├── versions/
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── alembic.ini
│   ├── requirements.txt
│   └── run.sh
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── app/
│   │   │   └── App.tsx
│   │   ├── features/
│   │   │   ├── dashboard/
│   │   │   │   └── DashboardPage.tsx      # Pipeline Kanban board
│   │   │   ├── articles/
│   │   │   │   ├── ArticlesPage.tsx       # Article list with status filter
│   │   │   │   └── ArticleDetailPage.tsx  # Content preview + pipeline history
│   │   │   ├── runs/
│   │   │   │   └── RunsPage.tsx           # Pipeline run history
│   │   │   └── settings/
│   │   │       └── SettingsPage.tsx       # Pipeline config + controls
│   │   ├── components/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── TopBar.tsx
│   │   │   ├── BoardColumn.tsx
│   │   │   ├── ArticleCard.tsx
│   │   │   └── PipelineControls.tsx
│   │   ├── lib/
│   │   │   └── api.ts                     # Typed API client
│   │   └── styles/
│   │       └── global.css
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── CLAUDE.md
├── README.md
├── PROJECT_PLAN.md                        # This file
├── LANGGRAPH_ARCHITECTURE.md              # Copied from admin_app
├── LOCAL_LLM.md                           # Copied from admin_app
└── .gitignore
```

---

## Agent Execution Order

```
Phase 1:  Architect ──────────────────────────────────────────────►
Phase 2:                ETL Porter ────────────────────────────────►
Phase 3:                    Pipeline Builder ──────────────────────►
                            Review Engine ─────────────────────────►
                            Vision & Embedding Builder ────────────►
Phase 4-5:                              Dashboard Builder ─────────►
Phase 6:  All agents ─────────────────────────────────────────────►
```

Architect goes first. ETL Porter and Pipeline Builder can work in parallel once models are defined. Dashboard Builder starts once API contracts are stable.

---

## Key Differences from admin_app

| Aspect | admin_app | habr-agentic-pipeline |
|--------|-----------|----------------------|
| Pipeline | Manual triggers, human review | Fully autonomous LangGraph |
| Architecture | Monolithic FastAPI | Layered (routes → services → repos → models) |
| Frontend build | Create React App | Vite |
| Frontend state | React Query + Ant Design | Fetch + lightweight (TBD) |
| Translation | Sync with `asyncio.to_thread` | Async-native |
| Review | Human editor | LLM-powered two-pass review |
| Quality gate | None (human judgment) | Automated spell check, Russian detection, usefulness scoring |
| Image validation | None | Vision model text detection |
| Related articles | None | Vector embeddings + cosine similarity |
| Migrations | Manual Python scripts | Alembic |
| Orchestration | None | LangGraph StateGraph with checkpointing |
| Telegram | Integrated | Excluded |