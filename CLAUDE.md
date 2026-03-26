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