# Local LLM Setup for Agentic Pipeline

## Purpose

Run a local LLM on M1 16GB for the ContentFilterAgent (Russia-relevance classification). The task is binary classification of Russian text with JSON output — a small, multilingual model is sufficient.

## Hardware Constraints

- Apple M1, 16GB unified memory
- ~8–10GB available for the model (OS + FastAPI process take the rest)
- Metal GPU acceleration via Ollama or MLX

## Model Recommendations

### Tier 1: Best Fit

| Model | Size (Q4) | RAM Usage | Russian Quality | Speed on M1 | Notes |
|-------|-----------|-----------|----------------|-------------|-------|
| **Qwen 2.5 7B Instruct** | ~4.5GB | ~6GB | Excellent | ~30 tok/s | Best multilingual for the size. Strong Russian, reliable JSON output |
| **Gemma 2 9B Instruct** | ~5.5GB | ~7GB | Very good | ~20 tok/s | Google's model, strong reasoning for classification |
| **Mistral Nemo 12B Instruct** | ~7GB | ~9GB | Very good | ~15 tok/s | Tight fit on 16GB but doable. Best reasoning in this tier |

### Tier 2: Viable Alternatives

| Model | Size (Q4) | RAM Usage | Russian Quality | Speed on M1 | Notes |
|-------|-----------|-----------|----------------|-------------|-------|
| **Llama 3.1 8B Instruct** | ~4.5GB | ~6GB | Good | ~25 tok/s | Solid all-around but weaker Russian than Qwen |
| **Phi-3.5 Mini 3.8B Instruct** | ~2.3GB | ~4GB | Decent | ~45 tok/s | Fastest. Good for binary classification but less reliable on nuanced Russian context |
| **Qwen 2.5 14B Instruct** | ~8.5GB | ~10GB | Excellent | ~10 tok/s | Best quality but very tight on 16GB. May swap under load |

### Not Recommended

- **Llama 3.1 70B** — won't fit
- **Mixtral 8x7B** — too large for 16GB
- **Any model > 14B** — memory pressure causes swapping

## Primary Recommendation

**Qwen 2.5 7B Instruct** — best balance for this use case:
- Best-in-class Russian/Ukrainian language understanding at this size
- Reliable structured JSON output
- Comfortable memory headroom (~6GB leaves room for FastAPI)
- Fast enough that content filtering won't bottleneck the pipeline (~2–3 seconds per article)
- If accuracy is insufficient, step up to **Gemma 2 9B** before trying larger models

## Runtime: Ollama (Recommended)

Simplest setup. Exposes an OpenAI-compatible API that integrates with the existing OpenAI SDK in the codebase.

### Install and Run

```bash
# Install
brew install ollama

# Pull the model
ollama pull qwen2.5:7b-instruct

# Start the server (runs on localhost:11434)
ollama serve
```

### Python Integration

Uses the same `openai` SDK already in requirements — just swap `base_url`:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",  # Dummy key, Ollama doesn't require auth
)

response = client.chat.completions.create(
    model="qwen2.5:7b-instruct",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"},
)
```

### Ollama Configuration

For optimal performance on M1 16GB, set these environment variables before running `ollama serve`:

```bash
export OLLAMA_NUM_PARALLEL=1        # Single request at a time (pipeline is sequential)
export OLLAMA_MAX_LOADED_MODELS=1   # Only keep one model in memory
export OLLAMA_KEEP_ALIVE=30m        # Unload model after 30 min idle to free RAM
```

## Alternative Runtime: MLX

Apple's own ML framework. Slightly faster on Apple Silicon but more setup.

```bash
pip install mlx-lm

# Run as OpenAI-compatible server
mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
```

Then use `base_url="http://localhost:8080/v1"` in the OpenAI client.

## Backend Configuration

Add to `backend/app/core/config.py`:

```python
# Local LLM for content filtering
AGENT_CONTENT_FILTER_BASE_URL: str = "http://localhost:11434/v1"
AGENT_CONTENT_FILTER_MODEL: str = "qwen2.5:7b-instruct"
AGENT_CONTENT_FILTER_API_KEY: str = "ollama"
AGENT_CONTENT_FILTER_CONFIDENCE: float = 0.8
```

## Integration with ContentFilterAgent

The ContentFilterAgent creates its own OpenAI client with the local LLM settings, separate from the cloud providers used for translation and quality checks:

```python
class ContentFilterAgent(BaseAgent):
    def __init__(self):
        self.client = OpenAI(
            base_url=settings.AGENT_CONTENT_FILTER_BASE_URL,
            api_key=settings.AGENT_CONTENT_FILTER_API_KEY,
        )
        self.model = settings.AGENT_CONTENT_FILTER_MODEL

    async def analyze(self, title: str, content: str) -> dict:
        # Send first 3000 chars + title for token efficiency
        truncated = content[:3000]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": build_filter_prompt(title, truncated)}],
            response_format={"type": "json_object"},
            temperature=0.1,  # Low temperature for consistent classification
        )
        return json.loads(response.choices[0].message.content)
```

## Fallback Strategy

If the local LLM is unavailable (Ollama not running, model not loaded):

1. Log a warning
2. Fall back to cloud provider (`gpt-4o-mini` via OpenAI API)
3. If cloud also unavailable, skip filtering and proceed to translation (fail-open to avoid blocking the pipeline)

Configure fallback in settings:

```python
AGENT_CONTENT_FILTER_FALLBACK_PROVIDER: str = "openai"
AGENT_CONTENT_FILTER_FALLBACK_MODEL: str = "gpt-4o-mini"
```

## Performance Expectations

| Metric | Qwen 2.5 7B on M1 16GB |
|--------|------------------------|
| Time per article | ~2–3 seconds |
| Input tokens | ~1000–1500 (3000 chars of Russian text) |
| Output tokens | ~50–100 (JSON response) |
| RAM usage | ~6GB steady state |
| Pipeline impact | Negligible — classification is much faster than translation |
