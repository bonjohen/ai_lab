# AI Lab

A multi-model chat application for managing and using LLM instances across a home network. Chat with local Ollama nodes, cloud APIs, and routers through a single unified interface with full provenance tracking.

## What it does

- **Single chat page** that works with any configured model backend — local Ollama, LAN Ollama nodes, OpenAI-compatible APIs, or routers
- **Source selection** — pick from configured sources grouped by type (local, LAN, provider, router), with searchable tags
- **Streaming responses** via SSE with real-time text assembly
- **Provenance tracking** — every assistant message records which source was selected, which endpoint handled the request, which model answered, token usage, and timing
- **Route resolution** — define routes spanning multiple endpoints with automatic failover to the first healthy node
- **Health monitoring** — background health checks and Ollama model inventory refresh on configurable intervals
- **Conversation persistence** — SQLite storage for conversations, messages, and execution records that survive restarts
- **Conversation forking** — fork a conversation to a different source while preserving message history and original provenance

## Architecture

```
Browser ──► FastAPI Backend ──► Adapter Layer ──► Model Endpoints
  (React)     (normalized API)    (per-provider)    (Ollama, OpenAI, routers)
```

Four layers, strictly separated:

1. **Chat UI** (React + Vite) — display, interaction, streaming assembly. No provider semantics.
2. **Application Backend** (FastAPI) — normalized API, config loading, policy enforcement, route resolution, provenance recording.
3. **Adapter Layer** — translates normalized requests to provider-specific calls. Selected by endpoint `provider_type`.
4. **Model Endpoints** — Ollama instances, OpenAI-compatible APIs, routers.

Key entities (kept separate by design): **Source** → **Route** → **Endpoint**, plus **CapabilityProfile** and **Policy**.

## Prerequisites

- Python 3.11+
- Node.js 18+
- At least one Ollama instance running (or any OpenAI-compatible endpoint)

## Quick start

**Backend:**

```bash
cd app/backend
pip install -e ".[dev]"
python -m uvicorn app.main:app --port 8100
```

**Frontend:**

```bash
cd app/frontend
npm install
npm run dev
```

Open the frontend URL (default `http://localhost:5173`). Select a source, start a new chat, and send a message.

## Configuration

All configuration lives in `app/backend/config/` as JSON files. The backend loads and validates these on startup.

| File | Purpose |
|------|---------|
| `app_config.json` | Health check intervals, database path, log level |
| `capabilities.json` | Reusable feature profiles (streaming, temperature, max_tokens support) |
| `endpoints.json` | Concrete connection targets — URL, provider type, health check settings |
| `routes.json` | Logical resolvers over multiple endpoints with failover strategy |
| `sources.json` | What the UI shows — references an endpoint or route + capability profile |
| `policies.json` | Runtime defaults/limits, allowed parameter overrides |

### Adding an endpoint

Add an entry to `endpoints.json`:

```json
{
    "id": "my-ollama",
    "display_name": "My Ollama Node",
    "provider_type": "ollama",
    "base_url": "http://192.168.1.50:11434",
    "default_model": "llama3:latest",
    "is_ollama_node": true,
    "health_check": { "enabled": true, "timeout_seconds": 5.0, "path": "/" },
    "tags": ["lan"]
}
```

Then add a source in `sources.json` pointing to it:

```json
{
    "id": "my-ollama-source",
    "display_name": "My Ollama",
    "source_class": "lan",
    "endpoint_id": "my-ollama",
    "capability_profile_id": "ollama-chat",
    "tags": ["lan"],
    "visible": true,
    "policy_id": "default"
}
```

Supported `provider_type` values: `ollama`, `openai_compatible`, `provider_native`, `router_api`.

### Validation

The config loader validates all cross-references on startup. If anything is wrong, it logs actionable errors with the filename, object ID, and field name, then refuses to start.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/sources` | List configured sources (UI-safe metadata only) |
| `GET` | `/api/sources/:id` | Source detail |
| `POST` | `/api/conversations` | Create conversation `{ source_id, title? }` |
| `GET` | `/api/conversations` | List conversations |
| `GET` | `/api/conversations/:id` | Get conversation with messages and execution records |
| `POST` | `/api/conversations/:id/fork` | Fork to new source `{ new_source_id }` |
| `POST` | `/api/chat` | Submit chat request, returns SSE stream |
| `GET` | `/api/health` | Endpoint health summaries |
| `GET` | `/api/inventory` | Ollama model inventory by node |
| `POST` | `/api/health/refresh` | Manual health refresh |
| `POST` | `/api/inventory/refresh` | Manual inventory refresh |

### SSE stream events

The chat endpoint returns normalized events: `started`, `delta` (incremental text), `metadata` (token usage, timing), `completed`, `error`, `cancelled`.

## Tests

```bash
cd app/backend
python -m pytest tests/ -v
```

54 tests covering config validation, persistence CRUD, conversation forking, chat orchestration, route resolution, and API endpoints.

## Project structure

```
app/
  backend/
    app/
      adapters/       # Provider adapters (Ollama, OpenAI-compatible, router)
      config/         # Config loader and view model builder
      models/         # Pydantic models (config entities, chat contracts, UI views)
      persistence/    # SQLite schema and repository pattern
      routes/         # FastAPI route handlers
      services/       # Chat orchestration, health scheduler, route resolver
    config/           # JSON configuration files
    tests/            # pytest suite
  frontend/
    src/
      components/     # React components (SourcePicker, MessageThread, etc.)
      api.ts          # API client and SSE consumer
      App.tsx         # Main app with three-panel layout
docs/
  initial_design.md   # Design document
  initial_plan.md     # Implementation plan with task tracking
```

## Design documents

- [`docs/initial_design.md`](docs/initial_design.md) — Full design document covering architecture, configuration strategy, persistence model, and acceptance criteria
- [`docs/initial_plan.md`](docs/initial_plan.md) — Phased implementation plan with task status
