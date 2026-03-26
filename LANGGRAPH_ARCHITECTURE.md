# LangGraph Architecture

## Why LangGraph

| Approach | Verdict | Reason |
|----------|---------|--------|
| Raw asyncio loop | Rejected | Manual state management, no checkpointing |
| Celery/task queues | Rejected | Needs Redis/RabbitMQ, no graph semantics, overkill for single server + SQLite |
| Temporal/Prefect | Rejected | Heavy infrastructure, overkill for this scale |
| **LangGraph** | **Selected** | Native state machine, checkpointing, conditional routing, lightweight |

**Key reasons:**

1. **State machine semantics** — pipeline is a directed graph with conditional branches. LangGraph models this natively.
2. **Checkpointing** — crash recovery resumes from last completed node. Critical for long translation jobs.
3. **Observability** — graph visualization, step-by-step state inspection, LangSmith tracing.
4. **Lightweight** — in-process with SQLite persistence. No extra infrastructure.

---

## Pipeline Overview

Two-pass review cycle: translate → review → proofread → review. Each review performs spell check, Russian content detection, usefulness assessment, and article enrichment with sources.

```
extraction → content_filter → translation → review_1 → proofreading → review_2 → image_text_check → image_gen → vectorize → publish → deploy
```

---

## Graph Diagram

```
                    ┌─────────────┐
                    │  extraction  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
              ┌─────┤content_filter├─────┐
              │     └─────────────┘     │
          reject                     accept
              │                         │
     ┌────────▼────────┐        ┌───────▼───────┐
     │  mark_useless   │        │  translation   │
     └────────┬────────┘        └───────┬───────┘
              │                         │
            END                 ┌───────▼───────┐
                                │   review_1     │
                                └───────┬───────┘
                                   ┌────┴────┐
                                 fail      pass
                                   │         │
                          ┌────────▼────────┐  ┌──▼────────────┐
                          │  mark_useless   │  │  proofreading   │
                          └────────┬────────┘  └───────┬────────┘
                                   │                   │
                                 END             ┌─────▼───────┐
                                                 │  review_2    │
                                                 └──────┬──────┘
                                                   ┌────┴────┐
                                                 fail      pass
                                                   │         │
                                          ┌────────▼────────┐  ┌──▼──────────────┐
                                          │  mark_useless   │  │image_text_check  │
                                          └────────┬────────┘  └───────┬─────────┘
                                                   │                   │
                                                 END           ┌──────▼──────┐
                                                               │  image_gen   │
                                                               └──────┬──────┘
                                                                      │
                                                               ┌──────▼──────┐
                                                               │  vectorize   │
                                                               └──────┬──────┘
                                                                      │
                                                               ┌──────▼──────┐
                                                               │   publish    │
                                                               └──────┬──────┘
                                                                      │
                                                               ┌──────▼──────┐
                                                               │   deploy     │
                                                               └──────┬──────┘
                                                                      │
                                                                    END
```

When a review fails, the article is marked as USELESS with detailed diagnostic data (review results, spell errors, Russian fragments, usefulness score) stored in `editorial_notes` and logged for analysis.

---

## State

### PipelineState

Top-level typed dictionary flowing through the entire graph.

| Field Group | Fields | Populated By |
|------------|--------|-------------|
| **Identity** | `article_id`, `source_title`, `source_url` | Entry point |
| **Content** | `source_content`, `target_content`, `target_title`, `target_excerpt` | extraction, translation |
| **Content Filter** | `filter_decision` (accept/reject), `filter_confidence`, `filter_reason`, `russia_topics` | content_filter |
| **Translation** | `translation_provider`, `word_count_original`, `word_count_translated`, `image_prompt` | translation |
| **Review 1** | `review_1` (ReviewResult) | review_1 |
| **Proofreading** | `proofreading_passed`, `proofreading_issues`, `proofreading_quality_score` | proofreading |
| **Review 2** | `review_2` (ReviewResult) | review_2 |
| **Image Text Check** | `images_with_russian_text`, `images_regenerated` | image_text_check |
| **Image Gen** | `lead_image`, `image_generated` | image_gen |
| **Vectorization** | `embedding`, `embedding_model`, `related_article_ids` | vectorize |
| **Publishing** | `published`, `deployed` | publish, deploy |
| **Metadata** | `current_step`, `error`, `retry_count` | All nodes |

### ReviewResult (nested structure)

| Field | Type | Description |
|-------|------|-------------|
| `passed` | bool | Overall pass/fail |
| `spell_errors` | list[dict] | `{word, suggestion, context}` |
| `russian_fragments` | list[str] | Detected Russian text that shouldn't be there |
| `usefulness_score` | float | 1-10 rating for Ukrainian tech audience |
| `usefulness_notes` | str | Explanation of score |
| `suggested_sources` | list[dict] | `{title, url, relevance}` — external references to enrich the article |
| `suggested_expansions` | list[str] | Sections/paragraphs to add |
| `content_after_fixes` | str or null | Content with auto-fixes applied (spelling, Russian removal) |

---

## Nodes

### extraction

- **Role**: Fetch full HTML content from Habr, download images
- **LLM**: None
- **Wraps**: `ArticleContentExtractionService`
- **Input**: article_id (DISCOVERED)
- **Output**: source_content, lead_image → status EXTRACTED
- **Errors**: 404/parse error → mark_useless; 429 → retry

### content_filter

- **Role**: Classify article as globally relevant vs. Russia-specific
- **LLM**: Local (Qwen 2.5 7B via Ollama), cloud fallback (gpt-4o-mini)
- **Input**: source_title + first 3000 chars of source_content
- **Output**: filter_decision, filter_confidence, filter_reason, russia_topics
- **Errors**: LLM unavailable → fallback to cloud; both fail → accept (fail-open)

### mark_useless

- **Role**: Terminal node — mark article as USELESS, store diagnostic data, log reason
- **LLM**: None
- **Triggered by**: content_filter reject, review_1 fail, review_2 fail
- **Output**: status → USELESS, editorial_notes populated with structured rejection data (which step failed, review scores, spell errors, Russian fragments, usefulness score)
- **Logging**: Full diagnostic dump to application log for analysis and pipeline tuning

### translation

- **Role**: Translate article from Russian to Ukrainian (without proofreading — that's a separate node)
- **LLM**: Cloud (Grok primary, OpenAI fallback)
- **Wraps**: `ArticleTranslationService.translate(enable_proofreading=False)`
- **Output**: target_content, target_title, target_excerpt, image_prompt
- **Errors**: Provider failure → fallback; timeout → retry; max retries → DRAFT

### review_1 (Post-Translation Review)

- **Role**: First comprehensive review of translated content
- **LLM**: Cloud provider
- **Checks**:
  1. **Spell check** — Ukrainian spelling and grammar errors. Auto-fix obvious mistakes.
  2. **Russian detection** — scan for remaining Russian words/phrases/sentences. Detect Russian-specific Cyrillic (ы, э, ъ). Verify ИИ→ШІ. Auto-remove detectable fragments.
  3. **Usefulness assessment** — rate 1-10 for Ukrainian tech audience. Consider: technical depth, practical value, uniqueness. Articles that lose value when decontextualized from Russian ecosystem get lower scores.
  4. **Source enrichment** — suggest authoritative external sources (docs, papers, blogs) as references. Suggest sections/paragraphs to expand. These are suggestions, not auto-applied.
- **Auto-fix**: Fixable issues (spelling, Russian fragments) are applied to target_content. Fixed content flows to proofreading.
- **Pass criteria**: usefulness >= 5, no unfixable Russian content, spelling auto-fixed
- **Fail criteria**: usefulness < 5, Russian content that can't be auto-removed, critical quality issues → routes to mark_useless with full diagnostic data

### proofreading

- **Role**: Professional-grade proofreading after review_1 fixes
- **LLM**: Cloud provider (same as translation or dedicated proofreading model)
- **Wraps**: `BaseTranslator.proofread_translation()`
- **Focus**: Fluency, natural Ukrainian phrasing, technical accuracy, consistent terminology, HTML preservation
- **Output**: proofread target_content, quality score, issues list

### review_2 (Post-Proofreading Review)

- **Role**: Final automated quality gate — same checks as review_1 on proofread version
- **LLM**: Same prompt as review_1
- **Additional concerns**:
  - Verify review_1 fixes were preserved (proofreading didn't reintroduce Russian text)
  - Verify proofreading didn't introduce new spelling errors
  - Re-assess usefulness (should remain stable or improve)
- **Pass criteria**: Same as review_1 but stricter — this is the final automated gate
- **Fail**: Routes to mark_useless with combined diagnostic data from both review passes

### image_text_check

- **Role**: Detect text in article images; if Russian, regenerate with Ukrainian text
- **LLM**: Vision model (GPT-4o or equivalent)
- **Process**:
  1. Extract all image paths from target_content HTML
  2. Send each image to vision LLM — detect if text is present, what language
  3. For images with Russian text: generate new prompt describing same visual with Ukrainian text, regenerate via image API, replace file
- **Skip conditions**: Code screenshots, language-neutral diagrams, brand logos
- **Non-blocking**: Vision model unavailable or regeneration fails → proceed with warning

### image_gen

- **Role**: Generate AI lead image if missing or default Habr image
- **LLM**: Image generation (Runware → OpenAI DALL-E → Grok fallback)
- **Wraps**: `RunwareService` / image generation pipeline
- **Input**: image_prompt from translation step
- **Non-blocking**: All providers fail → proceed without image

### vectorize

- **Role**: Create vector embedding for semantic search and related articles
- **LLM**: Embedding model (local `nomic-embed-text` via Ollama, cloud `text-embedding-3-small` fallback)
- **Process**:
  1. Prepare text: title + excerpt + stripped HTML content (truncated to model max)
  2. Generate embedding vector
  3. Store in `article_embeddings` table (JSON-serialized float array in SQLite)
  4. Compute cosine similarity against all existing published article embeddings
  5. Store top-K related article IDs on the article record
  6. Update related articles of existing articles that now match this one
- **Why SQLite, not a vector DB**: At this scale (hundreds to low thousands of articles), cosine similarity over JSON-decoded vectors is fast enough. pgvector/ChromaDB would be premature.
- **Output**: embedding stored, related_article_ids populated

### publish

- **Role**: Set article status to PUBLISHED
- **LLM**: None
- **Gated**: Only executes if `AGENT_AUTO_PUBLISH = True`
- **Records**: approved_by="pipeline_agent", approved_at=now()

### deploy

- **Role**: Regenerate static site and deploy to DigitalOcean
- **LLM**: None
- **Wraps**: `SiteGeneratorService` + `deploy_to_digitalocean`
- **Batching**: Collects published articles over a window before regenerating
- **Cooldown**: Max one deployment per configured interval

---

## Edges

### Linear Edges

| From | To |
|------|----|
| extraction | content_filter |
| mark_useless | END |
| translation | review_1 |
| proofreading | review_2 |
| image_text_check | image_gen |
| image_gen | vectorize |
| vectorize | publish |
| deploy | END |

### Conditional Edges

| After Node | Condition | Routes To |
|-----------|-----------|-----------|
| **content_filter** | reject | mark_useless |
| | accept | translation |
| **review_1** | passed | proofreading |
| | failed | mark_useless |
| **review_2** | passed | image_text_check |
| | failed | mark_useless |
| **publish** | published (auto_publish=true) | deploy |
| | not published | END |

---

## New Database Models

### ArticleEmbedding table

| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | Auto-increment |
| article_id | Integer FK → articles, unique, indexed | One embedding per article |
| embedding | Text | JSON-serialized float array |
| embedding_model | String | Model used to generate |
| dimensions | Integer | Vector dimensions (768 or 1536) |
| created_at | DateTime | Auto-set |
| updated_at | DateTime | Auto-update |

### Article model addition

| Column | Type | Description |
|--------|------|-------------|
| related_article_ids | Text, nullable | JSON array of article_ids for "Related Articles" block |

### Pipeline checkpoint database

Third SQLite file (`pipeline_checkpoints.db`) managed by LangGraph's `AsyncSqliteSaver`. Stores graph state per article thread.

---

## Scheduling

| Loop | Interval | Purpose |
|------|----------|---------|
| Discovery | 6 hours | Run `ArticleDiscoveryService`, spawn pipeline per new article |
| Pipeline | 5 minutes | Pick up DISCOVERED articles not yet in pipeline, invoke graph |
| Metadata | Periodic (low priority) | Translate untranslated tags/hubs, generate missing URLs |

All loops run as `asyncio` tasks within the FastAPI process lifespan. No external scheduler needed.

Each article gets its own LangGraph thread (`thread_id = article-{id}`) for independent checkpointing and crash recovery.

---

## Failed Article Handling

When any review node fails, the article is routed to `mark_useless`:

1. Article status set to USELESS
2. `editorial_notes` populated with structured JSON containing:
   - Which step failed (content_filter, review_1, review_2)
   - Review scores and issues from all completed review passes
   - Spell errors, Russian fragments, usefulness score
   - Suggested sources and expansions (for manual recovery if desired)
3. Full diagnostic data logged at WARNING level for pipeline tuning
4. Article excluded from future pipeline runs

Failed articles remain queryable in the admin UI (filter by USELESS status) for manual inspection if needed, but the pipeline itself is fully autonomous with no human gates.

---

## Provider Mapping

| Node | Provider | Model | Local/Cloud |
|------|----------|-------|-------------|
| content_filter | Ollama (fallback: OpenAI) | Qwen 2.5 7B (fallback: gpt-4o-mini) | Local (fallback: Cloud) |
| translation | Grok (fallback: OpenAI) | grok-3 (fallback: configurable) | Cloud |
| review_1, review_2 | OpenAI or Grok | Configurable | Cloud |
| proofreading | Same as translation | Same as translation | Cloud |
| image_text_check | OpenAI | GPT-4o (vision) | Cloud |
| image_gen | Runware → OpenAI → Grok | Flux.1 → DALL-E → Grok | Cloud |
| vectorize | Ollama (fallback: OpenAI) | nomic-embed-text (fallback: text-embedding-3-small) | Local (fallback: Cloud) |

---

## File Structure

```
backend/app/agents/
    __init__.py
    graph.py                       # StateGraph definition, compilation, pipeline creation
    state.py                       # PipelineState, ReviewResult type definitions
    nodes/
        __init__.py
        extraction.py
        content_filter.py
        mark_useless.py
        translation.py             # Proofreading OFF — separate node handles it
        review.py                  # Shared logic for review_1 and review_2
        proofreading.py
        image_text_check.py        # Vision OCR + Russian text detection + image regeneration
        image_gen.py               # Lead image generation
        vectorize.py               # Embedding generation + related articles
        publish.py
        deploy.py
    edges/
        __init__.py
        routing.py                 # All conditional routing functions
    prompts/
        content_filter.py          # Russia-relevance classification
        review.py                  # Spell check + Russian detection + usefulness + enrichment
        image_text_check.py        # Vision model text detection
    discovery.py                   # Separate discovery cycle (feeds articles into graph)
    metadata.py                    # Background tag/hub translation
    scheduler.py                   # FastAPI lifespan loop functions
    embeddings.py                  # Embedding generation, cosine similarity, related articles
    config.py                      # Agent configuration

backend/app/api/routers/agents.py  # Pipeline management API
backend/app/api/schemas/agents.py  # Request/response models
```

---

## Node ↔ Service Mapping

| Node | Existing Service | New Code |
|------|-----------------|----------|
| extraction | `ArticleContentExtractionService` | Wrap |
| content_filter | — | New (local LLM call) |
| mark_useless | Article status update logic | Reuse |
| translation | `ArticleTranslationService` | Wrap (proofreading=False) |
| review_1 / review_2 | — | New (multi-check LLM prompt) |
| proofreading | `BaseTranslator.proofread_translation()` | Wrap |
| image_text_check | — | New (vision LLM + image regen) |
| image_gen | `RunwareService` | Wrap |
| vectorize | — | New (embeddings + similarity) |
| publish | Article publish logic | Reuse |
| deploy | `deploy_to_digitalocean` | Wrap |

**5 existing services wrapped, 4 new capabilities**: content filter, review, image text check, vectorize.

---

## Dependencies

```
langgraph>=0.4
langgraph-checkpoint-sqlite>=2.0
```

Local models via Ollama (no pip dependency):
- `qwen2.5:7b-instruct` — content filtering
- `nomic-embed-text` — article embeddings

No LangChain dependency. Existing OpenAI SDK calls remain unchanged.
