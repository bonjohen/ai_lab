# Implementation Plan: Multi-Model Chat Application v1

**Source document:** `docs/initial_design.md`
**Status:** In Progress — Phase 4

---

## Open Questions (need answers before Phase 1)

1. **Technology stack** — The design doc is stack-agnostic. Recommended:
   - **Backend:** Python + FastAPI (async, SSE support, good Ollama library ecosystem)
   - **Frontend:** React + Vite (fast dev loop, good streaming/SSE support)
   - **Persistence:** SQLite via aiosqlite (or SQLAlchemy async)

2. **Monorepo layout** — Proposed:
   ```
   app/
     frontend/        ← React/Vite
     backend/         ← FastAPI
       config/        ← JSON config files
       adapters/      ← Provider adapters
       persistence/   ← SQLite models and migrations
       routes/        ← API route handlers
       models/        ← Shared domain models and contracts
   config/            ← Example/default JSON config files
   ```

3. **Auth for cloud providers** — The design doc says secrets go in a private JSON file or env vars. Which approach do you prefer for v1? 

Accept this approach: Recommendation: `.env` file + a `secrets.json` gitignored, with env vars taking precedence.

4. **Ollama test environment** — Do you have Ollama nodes running now? How many, and on what addresses? This affects how we write example config and test.

--- This machine has (RTX 4070):
  llama3-8k:latest (currently running)
  llama3:8b-instruct-q8_0 ()
  deepseek-r1:1.5b-tier2-light
  deepseek-r1:1.5b-tier1-micro

I have these to use, but they are not configured yet.
  NVIDIA DGX Spark 128G
  Mac Mini M4 24G
  Macbook M4 64G

## Phase 1: Project Scaffolding & Configuration Subsystem

**Goal:** Backend loads, validates, and serves JSON configuration. No chat yet.

### Tasks

- [X] **1.1** Initialize project structure (package.json / pyproject.toml, Vite config, FastAPI app skeleton)
- [X] **1.2** Define JSON schemas for all six config files:
  - `app_config.json` — refresh intervals, feature flags, persistence settings
  - `capabilities.json` — reusable capability profiles (streaming, temperature, max_tokens, etc.)
  - `endpoints.json` — concrete connection targets with provider_type, transport, auth ref, health-check config
  - `routes.json` — logical resolvers: candidate endpoint list, selection strategy, fallback policy
  - `sources.json` — UI-selectable targets referencing endpoint_id or route_id, capability profile, tags
  - `policies.json` — runtime limits, allowed overrides, timeouts, retry rules
- [X] **1.3** Build configuration loader module
  - Read all JSON files from config directory
  - Validate cross-references (design doc §15): no duplicate IDs, source→endpoint/route integrity, capability profile existence, policy resolution
  - Emit actionable errors with filename, object ID, and field name
  - Produce one coherent in-memory configuration model
- [X] **1.4** Build UI-safe source list view model (design doc §26)
  - Transform internal config into display-safe metadata: id, display_name, source_class, tags, capability_summary, default_model_label, health_summary
  - Strip auth data, private network details, policy internals
- [X] **1.5** Expose backend API: `GET /api/sources` (list) and `GET /api/sources/:id` (detail)
- [X] **1.6** Write example config files for a realistic setup (local Ollama, LAN Ollama, one OpenAI-compatible placeholder)
- [X] **1.7** Unit tests for config loader: valid config, missing references, duplicate IDs, malformed entries

**Exit criteria:** Backend starts, loads config, returns source list via API. Invalid config produces clear errors.

---

## Phase 2: Persistence & Conversation Models

**Goal:** Conversations and messages persist in SQLite. No provider calls yet.

### Tasks

- [X] **2.1** Define SQLite schema and migration system
  - `conversations` — id, title, source_id, created_at, updated_at, archived
  - `messages` — id, conversation_id, role, content, created_at, execution_id (nullable)
  - `executions` — id, selected_source_id, resolved_endpoint_id, route_id, requested_model, resolved_model, adapter_type, request_options_json, token_usage_json, status, error_code, error_message, started_at, completed_at, correlation_id
  - `endpoint_health_snapshots` — id, endpoint_id, status, latency_ms, checked_at, details_json
  - `endpoint_inventory_snapshots` — id, endpoint_id, models_json, refreshed_at
- [X] **2.2** Build persistence module with repository pattern
  - Conversation CRUD: create, list, get (with messages + execution summaries)
  - Message CRUD: append user/assistant messages
  - Execution CRUD: create, update on completion
- [X] **2.3** Expose backend API:
  - `POST /api/conversations` — create
  - `GET /api/conversations` — list
  - `GET /api/conversations/:id` — get with messages
  - `POST /api/conversations/:id/fork` — fork to new source
- [X] **2.4** Implement conversation fork logic (design doc §24)
  - Copy visible messages, retain original provenance on copied assistant messages, pin to new source
- [X] **2.5** Unit tests for persistence: CRUD operations, fork integrity, execution linkage

**Exit criteria:** Can create/list/get/fork conversations via API. Data survives backend restart.

---

## Phase 3: Ollama Adapter & Core Chat

**Goal:** User can chat with a single configured Ollama endpoint with streamed responses and provenance.

### Tasks

- [X] **3.1** Define adapter contract interface (design doc §19)
  - `validate_options(source, options)` — check runtime options
  - `health_check(endpoint)` — return health status
  - `list_models(endpoint)` — return model inventory
  - `chat(request)` → async generator of normalized stream events
- [X] **3.2** Define normalized stream event types (design doc §18)
  - `started` — execution_id, resolved source/endpoint/model
  - `delta` — incremental text content
  - `metadata` — token usage, timing, route details
  - `completed` — final message and execution record
  - `error` — normalized error code + message
  - `cancelled` — user cancellation
- [X] **3.3** Define normalized chat request model (design doc §17)
  - conversation_id, source_id, messages, system_prompt (optional), runtime_options (temperature, max_tokens, stream)
- [X] **3.4** Build Ollama adapter
  - HTTP client for Ollama API (local and remote targets)
  - `/api/chat` streaming → normalized delta events
  - `/api/tags` → model inventory
  - Health check via `/` or `/api/tags`
  - Map Ollama errors to normalized error codes
- [X] **3.5** Build adapter registry — select adapter by endpoint `provider_type`
- [X] **3.6** Build chat orchestration service
  - Resolve source → endpoint (direct, no routes yet)
  - Select adapter by provider_type
  - Apply policy: filter runtime options to what source+policy allow
  - Generate correlation_id
  - Stream response, persist execution record on completion
  - Persist assistant message with execution_id reference
- [X] **3.7** Expose backend API:
  - `POST /api/chat` — submit chat request, return SSE stream
  - (cancel deferred to Phase 5 with UI integration)
- [X] **3.8** Define normalized error model (design doc §28)
  - Error codes: configuration_error, endpoint_unreachable, auth_failed, model_not_found, timeout, invalid_request, provider_error, route_resolution_failed, cancelled
  - User-facing message + internal diagnostic message
- [X] **3.9** Unit tests for chat service: successful chat, error persistence, policy defaults, invalid source

**Exit criteria:** Backend can chat with Ollama, stream normalized events, persist provenance. Errors are normalized.

---

## Phase 4: Route Resolution & Multi-Node Ollama

**Goal:** Routes resolve across multiple Ollama endpoints. Health checks and inventory run on schedule.

### Tasks

- [X] **4.1** Build route resolver module (design doc §20)
  - First-healthy-endpoint strategy
  - Model-presence check: skip endpoints missing the requested model
  - Record resolution decisions (selected/skipped and why) for execution logs
  - Return specific failures: no healthy endpoint, model not present, misconfiguration
- [X] **4.2** Build health check scheduler
  - Background task: periodic lightweight health checks for all endpoints
  - Cache results in endpoint_health_snapshots
  - Configurable interval from app_config.json
  - Non-blocking: health refresh never blocks chat requests
- [X] **4.3** Build Ollama inventory refresh scheduler
  - Background task: periodic model inventory refresh for Ollama endpoints
  - Cache results in endpoint_inventory_snapshots
  - Less frequent than health checks
  - Cached inventory available for route resolution model-presence decisions
- [X] **4.4** Expose backend API:
  - `GET /api/health` — list endpoint health summaries
  - `GET /api/inventory` — list Ollama model inventory by node
  - `POST /api/health/refresh` — manual health refresh
  - `POST /api/inventory/refresh` — manual inventory refresh
- [X] **4.5** Update chat orchestration to use route resolver when source references a route
- [X] **4.6** Unit tests: route resolver with first_healthy, model presence, edge cases (8 tests)

**Exit criteria:** Chat works through routes. Unhealthy endpoints are skipped. Health and inventory update in background.

---

## Phase 5: Chat UI

**Goal:** Functional chat page with source selection, streaming display, and provenance.

### Tasks

- [ ] **5.1** Build frontend scaffolding (React + Vite, API client, SSE consumer)
- [ ] **5.2** Build three-panel layout (design doc §7)
  - Left: conversation list + source picker
  - Center: message thread + composer
  - Right: source details / diagnostics (collapsible)
- [ ] **5.3** Build source picker
  - Grouped by source class (local, LAN, provider, router)
  - Searchable, tag-filterable
  - Show health indicator per source
- [ ] **5.4** Build conversation list
  - Create new conversation (with source selection)
  - List existing conversations with title/label and source badge
  - Select conversation to load messages
- [ ] **5.5** Build message thread with streaming
  - SSE consumer assembles delta events into assistant text in real time
  - User messages render immediately
  - Cancel button for in-flight requests
- [ ] **5.6** Build provenance display on assistant messages
  - Source display name, resolved model, elapsed time, token counts
  - Compact inline display, expandable for full execution details
- [ ] **5.7** Build runtime parameter controls
  - Default: temperature, max output tokens (small common set only)
  - Advanced panel: collapsed by default, shows only source-supported + policy-allowed params
- [ ] **5.8** Build conversation fork action
  - "Fork to different source" button → pick new source → create forked conversation
- [ ] **5.9** Build diagnostics panel (right side)
  - Ollama node details: display name, health status, model list, freshness timestamps
  - Endpoint health overview
  - Manual refresh buttons
- [ ] **5.10** Build error rendering
  - Request-specific errors inline in conversation thread
  - Source-specific errors in diagnostics panel
- [ ] **5.11** Responsive layout: right panel becomes drawer on smaller screens

**Exit criteria:** User can select sources, chat with streaming, see provenance, view diagnostics, fork conversations — all through the browser.

---

## Phase 6: OpenAI-Compatible & Router Adapters

**Goal:** Support cloud APIs and routers beyond Ollama.

### Tasks

- [ ] **6.1** Build OpenAI-compatible adapter
  - Chat completions API streaming → normalized events
  - Auth via secrets.json / env vars
  - Health check via lightweight API call
  - Map API errors to normalized error codes
- [ ] **6.2** Build router adapter
  - Preserve both configured route identity and downstream resolved model identity
  - Pass through resolved model name from router response
- [ ] **6.3** Update source picker and provenance display to handle router metadata (requested model vs resolved model)
- [ ] **6.4** Add example config for at least one cloud provider and one router
- [ ] **6.5** Integration test: chat through OpenAI-compatible endpoint, verify provenance includes resolved model

**Exit criteria:** Can chat against Ollama, OpenAI-compatible APIs, and routers. Provenance is correct for all adapter types.

---

## Cross-Cutting Concerns (addressed incrementally across phases)

### Logging & Observability (design doc §30)
- **Phase 1:** Log config load results
- **Phase 3:** Log request start/complete/fail with correlation_id, adapter decisions
- **Phase 4:** Log route resolution decisions, health changes, inventory refresh results
- **Phase 5:** Correlation_id visible in diagnostics panel

### Security (design doc §29)
- **Phase 1:** Secrets file gitignored, UI-safe view models only
- **Phase 3:** Backend holds credentials, client never sees them
- **Phase 6:** Auth for cloud providers via env/secrets overlay

### Testing Strategy
- **Unit tests:** Config validation, persistence CRUD, route resolution logic, adapter request/response mapping
- **Integration tests:** Ollama round-trip (Phase 3), route failover (Phase 4), cloud provider round-trip (Phase 6)
- **Manual tests:** UI workflows (Phase 5), responsive layout, error states

---

## v1 Acceptance Criteria (design doc §34)

All of these must be true before v1 is considered complete:

- [ ] App loads JSON configuration and rejects invalid references with actionable errors
- [ ] UI displays configured sources and allows selection
- [ ] User can start a conversation, send a prompt, and receive streamed text
- [ ] Assistant messages display source provenance (selected source, resolved model)
- [ ] Conversations and messages persist across restarts
- [ ] Backend queries Ollama nodes for health and model inventory, exposed in diagnostics
- [ ] Routes spanning multiple endpoints resolve to first healthy eligible target
- [ ] Errors are normalized and rendered clearly
- [ ] Default UI exposes only temperature + max_tokens; advanced controls are collapsed and policy-gated
