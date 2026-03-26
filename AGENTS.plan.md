# Agents Implementation Plan

## Updated Pipeline Flow

```
DiscoveryAgent → ExtractionAgent → ContentFilterAgent → TranslationAgent → QualityGateAgent → ImageAgent → PublishingAgent
                                        ↓ (reject)
                                   Mark USELESS + delete
```

The key change from the original plan: a **ContentFilterAgent** is inserted after extraction and before translation. This agent analyzes the extracted source content for Russia-specific relevance and decides whether the article should proceed or be discarded.

---

## Agent 1: ContentFilterAgent

### Purpose

Analyze extracted articles to determine if they are about Russia-specific topics that have no value to a global/Ukrainian audience. Filter them out before wasting translation resources.

### Position in Pipeline

```
EXTRACTED → ContentFilterAgent → EXTRACTED (pass, proceed to translation)
                              → USELESS (reject, article deleted)
```

### Filtering Rules

#### REJECT (mark USELESS + delete) — Russia-specific content:

1. **Russian government/politics** — articles about Russian laws, regulations, governmental bans, sanctions lists, Roskomnadzor blocks, Russian court decisions
2. **Russia-locked services** — articles about services that only operate in Russia (Gosuslugi, Yandex.Taxi in Russia, VK-specific features, Sberbank internal tools, etc.)
3. **Russian company internals** — articles about internal processes of Russian companies (Yandex hiring in Moscow, Mail.ru office culture, Sber team structure)
4. **Russian market analysis** — articles specifically about the Russian IT market, Russian salaries, Russian developer surveys
5. **Russian infrastructure** — articles about Russian hosting providers (Selectel Russia-only features), Russian payment systems (Mir card specifics), Russian telecom

#### PASS (proceed to translation) — globally relevant content:

1. **International services** — articles about AWS, GCP, Azure, GitHub, Docker, Kubernetes, etc., even if written by a Russian author
2. **Universal technical knowledge** — programming tutorials, algorithm explanations, architecture patterns, DevOps practices
3. **Open-source projects** — articles about open-source tools regardless of author's nationality
4. **International company experience** — experience at companies operating globally, even if the author is based in Russia
5. **Technology reviews** — reviews of globally available technologies, frameworks, libraries
6. **Career/soft skills** — general career advice, management practices, team dynamics (not Russia-specific)

#### EDGE CASES — pass with note:

1. **Mixed content** — article is mostly global but mentions Russian services in passing → PASS, the existing translation prompt already strips Russia-related paragraphs
2. **Russian alternative to global service** — article compares a Russian service to a global one → PASS if the comparison provides value for the global service understanding
3. **Author works at Russian company but topic is universal** — PASS, topic matters more than employer

### Implementation

#### LLM Analysis Prompt

```
You are a content relevance analyst for a Ukrainian tech blog that translates
Habr.com articles from Russian to Ukrainian.

Analyze the following article and determine if it is relevant for an
international/Ukrainian audience, or if it is specific to Russia and should
be filtered out.

REJECT the article if it is PRIMARILY about:
- Russian government regulations, laws, bans, or sanctions
- Services that only operate in Russia or are locked to Russian users
- Internal processes of Russian companies with no global relevance
- Russian market analysis, Russian developer surveys, Russian salary reports
- Russian-specific infrastructure (hosting, payments, telecom)

ACCEPT the article if it is PRIMARILY about:
- Universal technical knowledge (programming, architecture, DevOps, etc.)
- International services and tools (AWS, Docker, Kubernetes, etc.)
- Open-source projects
- General career advice and management practices
- Technology that is available and relevant worldwide

For MIXED content (mostly global but mentions Russia in passing), ACCEPT it —
Russia-specific paragraphs will be removed during translation.

Return a JSON response:
{
  "decision": "accept" | "reject",
  "confidence": 0.0-1.0,
  "reason": "Brief explanation of the decision",
  "russia_specific_topics": ["list", "of", "detected", "russia-specific", "topics"],
  "global_topics": ["list", "of", "detected", "globally-relevant", "topics"]
}

Article title: {title}
Article content:
{source_content}
```

#### Confidence Thresholds

| Confidence | Decision | Action |
|-----------|----------|--------|
| reject, confidence >= 0.8 | Auto-reject | Mark USELESS, set `editorial_notes` with reason, delete |
| reject, confidence 0.5–0.8 | Low-confidence reject | Mark USELESS, set `editorial_notes`, do NOT delete — flag for human review |
| accept, confidence >= 0.5 | Auto-accept | Proceed to TranslationAgent |

#### Token Optimization

The full `source_content` may be too long for analysis. Strategy:
1. Send only the first 3000 characters of `source_content` + article title
2. This is enough for the LLM to determine topic relevance without processing the full article
3. Falls back to full content if the first chunk is ambiguous (confidence < 0.5)

#### Provider

- Use a cheap, fast model for this step (e.g., `gpt-4o-mini` or `grok-3-mini`)
- This is a classification task, not a creative task — smaller models perform well
- Configure via `AGENT_CONTENT_FILTER_PROVIDER` setting

### Database Changes

No new tables needed. Uses existing fields:
- `status` → set to `ArticleStatus.USELESS` on reject
- `editorial_notes` → populated with rejection reason and detected Russia-specific topics

New config setting:
```python
AGENT_CONTENT_FILTER_PROVIDER: str = "openai"   # Provider for content filtering
AGENT_CONTENT_FILTER_MODEL: str = "gpt-4o-mini" # Cheap model for classification
AGENT_CONTENT_FILTER_CONFIDENCE: float = 0.8     # Auto-reject threshold
```

### Interaction with Existing Filtering

The system already has two levels of Russia-related filtering:

1. **`_analyze_content()` in base_translator.py** — analyzes content quality (promotional, too short, mostly code). This stays unchanged but runs AFTER ContentFilterAgent.
2. **Translation prompt** — strips individual Russia-related paragraphs during translation. This stays unchanged as a safety net for mixed-content articles that pass the filter.

The new ContentFilterAgent is a **pre-translation gate** — it catches entirely Russia-centric articles before translation resources are spent. The three layers work together:

```
ContentFilterAgent (whole-article Russia relevance check)
    ↓ pass
_analyze_content (quality/substance check during translation setup)
    ↓ pass
Translation prompt (paragraph-level Russia reference removal)
    ↓
Translated article with Russia-specific paragraphs stripped
```

---

## Agent 2: DiscoveryAgent

### Purpose
Discover new articles from Habr on a schedule.

### Wraps
`ArticleDiscoveryService.update_articles()`

### Behavior
- Runs on schedule (default every 6 hours via `AGENT_DISCOVERY_INTERVAL_MINUTES`)
- Configurable page depth: `AGENT_DISCOVERY_PAGES` (default 3)
- Sets discovered articles to status `DISCOVERED`
- Logs count of newly discovered articles per run

### Error Handling
- Habr 429/503 → retry with jittered backoff
- Network timeout → retry up to `AGENT_MAX_RETRIES`

---

## Agent 3: ExtractionAgent

### Purpose
Extract article content and download images for discovered articles.

### Wraps
`ArticleContentExtractionService.extract_article()`

### Behavior
- Picks up articles with status `DISCOVERED`
- Extracts HTML content, downloads and processes images
- Updates status to `EXTRACTED` on success
- On permanent failure (404, parsing error) → mark `USELESS` with reason
- Rate limit: configurable delay between extractions (default 2 seconds)

### Error Handling
- HTTP 404 → mark USELESS ("article not found or deleted")
- Parsing error → mark USELESS with error details
- HTTP 429/503 → retry with backoff
- Image download failure → proceed (non-blocking), log warning

---

## Agent 4: TranslationAgent

### Purpose
Translate extracted articles from Russian to Ukrainian with proofreading always enabled.

### Wraps
`ArticleTranslationService.translate(enable_proofreading=True)`

### Behavior
- Picks up articles with status `EXTRACTED` that passed ContentFilterAgent
- Proofreading is always enabled — no toggle
- Provider selected from `AGENT_DEFAULT_TRANSLATION_PROVIDER` (default: grok)
- After translation, also runs:
  - `update_article_target_path()` — URL generation
  - `translate_code_comments_if_needed()` — code block localization
  - Tag/hub translation for untranslated tags
- Updates status to `TRANSLATED` on success
- Populates `TranslationResult` with `quality_score`, `proofreading_passed`, `proofreading_issues`

### Error Handling
- Provider API error → fallback to secondary provider
- Rate limit → retry with backoff
- Content too long → attempt chunked translation or mark DRAFT with note
- After `AGENT_MAX_RETRIES` → mark DRAFT, set `editorial_notes`

---

## Agent 5: QualityGateAgent

### Purpose
Automated validation replacing human review. Uses LLM scoring and heuristic checks.

### Validation Checks

1. **Length ratio** — translated vs. original word count, flag if outside 0.6–1.5x
2. **HTML integrity** — BeautifulSoup parse, verify no broken tags, `<pre><code>` preserved
3. **Empty content** — reject if `target_content` is empty or trivially short
4. **Title present** — reject if `target_title` is missing
5. **Excerpt present** — reject if `target_excerpt` is missing
6. **LLM quality score** — cheap LLM call rates fluency/accuracy/technical correctness 1–10
7. **Duplicate detection** — title similarity or content hash vs. existing PUBLISHED articles
8. **Proofreading signals** — use `proofreading_passed` and `proofreading_issues` from TranslationResult
9. **ШІ check** — verify "ИИ" was correctly translated to "ШІ" (not "АІ")

### Outcomes

| Score | Condition | Action |
|-------|-----------|--------|
| >= 7 | All heuristics pass | Auto-approve → ready for publishing |
| 5–7 | Minor issues | Proceed with `editorial_notes` warning |
| < 5 | Critical issues | Mark DRAFT, set `editorial_notes`, notify admin |

---

## Agent 6: ImageAgent

### Purpose
Generate lead images for translated articles that lack custom visuals.

### Behavior
- Triggers after translation succeeds
- Detects default Habr images (`habr_ru.png`)
- Uses `image_prompt` field from translation metadata
- Provider cascade: Runware (Flux.1) → OpenAI DALL-E → Grok
- Falls back to Grok prompt generation if no `image_prompt`
- Stores generated image in `MEDIA_PATH`, updates `lead_image` field

### Error Handling
- Provider failure → fallback to next provider
- All providers fail → proceed without image, log warning (non-blocking)

---

## Agent 7: PublishingAgent

### Purpose
Publish approved articles, regenerate site, and deploy.

### Behavior
- Picks up articles with status `TRANSLATED` that passed QualityGateAgent
- Sets `status = PUBLISHED`, `approved_by = "pipeline_agent"`, `approved_at = now()`
- Batches articles over `AGENT_BATCH_PUBLISH_WINDOW_MINUTES` (default 30 min) before triggering site regeneration
- Site regeneration via `create_site_generator().generate_site()`
- Deployment via `deploy_to_digitalocean()` with cooldown (default 60 min between deploys)
- Only deploys if `AGENT_AUTO_PUBLISH = True`

### Error Handling
- Site generation failure → retry, do not revert article status
- Deployment failure → retry, notify admin, articles remain PUBLISHED (site will deploy on next successful run)

---

## Agent 8: MetadataAgent

### Purpose
Background maintenance of tags, hubs, and URL metadata.

### Behavior
- Runs periodically (low priority, after main pipeline steps)
- Translates untranslated tags via `TagTranslationService`
- Translates untranslated hubs via `HubTranslationService`
- Generates English URLs for articles missing `target_path`
- Non-blocking — failures are logged but don't affect the main pipeline

---

## PipelineOrchestrator

### Responsibilities
- Runs as `asyncio` background task inside FastAPI process
- Schedules discovery at `AGENT_DISCOVERY_INTERVAL_MINUTES`
- Runs pipeline processing at `AGENT_PIPELINE_INTERVAL_MINUTES`
- For each article in the queue, determines the next agent based on current status
- Records all step outcomes in `PipelineRun` table
- Handles retries with exponential backoff
- Exposes status via `/api/agents/*` endpoints

### Pipeline State Machine

```
DISCOVERED
    ↓ ExtractionAgent
EXTRACTED
    ↓ ContentFilterAgent
    ├── reject → USELESS (delete if high confidence)
    └── pass ↓
EXTRACTED (filtered)
    ↓ TranslationAgent (proofreading always on)
TRANSLATED
    ↓ QualityGateAgent
    ├── fail → DRAFT (human review queue)
    └── pass ↓
TRANSLATED (quality passed)
    ↓ ImageAgent (non-blocking)
    ↓ PublishingAgent (if AGENT_AUTO_PUBLISH=True)
PUBLISHED
    ↓ Site generation + deployment (batched)
```

### Execution Order per Cycle

```python
async def process_cycle(self):
    # 1. Content filter: analyze EXTRACTED articles for Russia relevance
    await self.content_filter_agent.process_pending()

    # 2. Translate: process filtered EXTRACTED articles
    await self.translation_agent.process_pending()

    # 3. Quality gate: validate TRANSLATED articles
    await self.quality_gate_agent.process_pending()

    # 4. Images: generate for quality-passed articles
    await self.image_agent.process_pending()

    # 5. Publish: batch publish approved articles
    await self.publishing_agent.process_pending()

    # 6. Metadata: background maintenance
    await self.metadata_agent.process_pending()
```

---

## Configuration Summary

```python
# Master controls
AGENT_ENABLED: bool = False
AGENT_DRY_RUN: bool = True
AGENT_AUTO_PUBLISH: bool = False

# Scheduling
AGENT_DISCOVERY_INTERVAL_MINUTES: int = 360
AGENT_PIPELINE_INTERVAL_MINUTES: int = 5
AGENT_DISCOVERY_PAGES: int = 3

# Content filter
AGENT_CONTENT_FILTER_PROVIDER: str = "openai"
AGENT_CONTENT_FILTER_MODEL: str = "gpt-4o-mini"
AGENT_CONTENT_FILTER_CONFIDENCE: float = 0.8

# Translation
AGENT_DEFAULT_TRANSLATION_PROVIDER: str = "grok"

# Quality gate
AGENT_QUALITY_THRESHOLD: float = 7.0
AGENT_QUALITY_CHECK_PROVIDER: str = "openai"

# Publishing
AGENT_BATCH_PUBLISH_WINDOW_MINUTES: int = 30
AGENT_DEPLOY_COOLDOWN_MINUTES: int = 60

# Error handling
AGENT_MAX_RETRIES: int = 3
```

---

## File Structure

```
backend/app/agents/
    __init__.py
    orchestrator.py
    base_agent.py
    discovery_agent.py
    extraction_agent.py
    content_filter_agent.py    ← NEW: Russia-relevance filtering
    translation_agent.py
    quality_gate_agent.py
    image_agent.py
    publishing_agent.py
    metadata_agent.py
    prompts/
        content_filter.py      ← NEW: LLM prompt for relevance analysis
    config.py
    models.py

backend/app/api/routers/agents.py
backend/app/api/schemas/agents.py
```

---

## Implementation Phases

### Phase 1: Infrastructure + ContentFilterAgent (Week 1–2)
- Base classes, orchestrator skeleton, PipelineRun model, agent config
- **ContentFilterAgent with LLM prompt** — this is the highest-value new agent
- Agents API router
- Deploy with `AGENT_ENABLED = False`, test content filter manually via API

### Phase 2: Discovery + Extraction (Week 3–4)
- DiscoveryAgent, ExtractionAgent
- Enable pipeline, content filter runs automatically on extracted articles
- Human still handles translation+

### Phase 3: Translation + Quality Gate (Week 5–6)
- TranslationAgent (proofreading always on), QualityGateAgent
- `AGENT_AUTO_PUBLISH = False` — human reviews agent output
- Calibrate quality threshold

### Phase 4: Image + Publishing (Week 7–8)
- ImageAgent, PublishingAgent
- Enable `AGENT_AUTO_PUBLISH = True`
- Monitor and tune
