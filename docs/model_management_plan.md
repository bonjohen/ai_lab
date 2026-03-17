# Plan: Model Management (Load/Unload/Host)

**Status:** Draft — awaiting review

## Goal

Add the ability to view available models on each Ollama node, and load/unload models on demand. This goes beyond v1's read-only inventory view to allow operational control over which models are active.

## Context

The v1 design doc (§21) explicitly deferred "remote pull, delete, or runtime tuning operations." This feature adds a controlled subset: viewing, loading, and unloading models — not pulling new models from registries or deleting model files.

### Ollama API surface involved

| Operation | Ollama Endpoint | Effect |
|-----------|----------------|--------|
| List models | `GET /api/tags` | Already implemented (inventory refresh) |
| Show running models | `GET /api/ps` | Lists models currently loaded in memory |
| Load a model | `POST /api/generate` with `keep_alive` | Loads model into GPU/RAM |
| Unload a model | `POST /api/generate` with `keep_alive: 0` | Evicts model from memory |

## Affected files

### Backend (new/modified)

| File | Change |
|------|--------|
| `app/adapters/base.py` | Add `list_running_models()` and `load_model()` / `unload_model()` to contract |
| `app/adapters/ollama.py` | Implement via `/api/ps` and `/api/generate` |
| `app/services/health.py` | Add running-model cache alongside inventory cache |
| `app/routes/health.py` | Add `GET /api/models` (all models by node), `GET /api/models/running` (loaded models), `POST /api/models/load`, `POST /api/models/unload` |
| `app/models/views.py` | Add `ModelStatus` view model (name, size, loaded, VRAM usage) |

### Frontend (new/modified)

| File | Change |
|------|--------|
| `src/api.ts` | Add fetch/load/unload model API calls |
| `src/components/DiagnosticsPanel.tsx` | Expand inventory section with load/unload buttons and running status |
| `src/components/ModelManager.tsx` | **New** — dedicated model management view per node |

## Step-by-step approach

### Phase A: Backend — model status and control

1. Add `list_running_models(endpoint)` to `BaseAdapter` and implement in `OllamaAdapter` via `GET /api/ps`
2. Add `load_model(endpoint, model_name)` and `unload_model(endpoint, model_name)` to adapter
3. Extend `HealthService` with a running-models cache refreshed alongside inventory
4. Add API endpoints:
   - `GET /api/models` — all known models per node (from inventory) with `loaded: bool` status
   - `GET /api/models/running` — only currently loaded models with VRAM/RAM usage
   - `POST /api/models/load` — `{ endpoint_id, model_name, keep_alive? }` — load a model
   - `POST /api/models/unload` — `{ endpoint_id, model_name }` — unload a model
5. Unit tests for new adapter methods and API endpoints

### Phase B: Frontend — model management UI

1. Add API client functions for model load/unload
2. Build `ModelManager` component:
   - Per-node expandable sections
   - Each model shows: name, size, loaded status (green/gray indicator), VRAM usage if loaded
   - Load button (for unloaded models), Unload button (for loaded models)
   - Loading state feedback during load/unload operations
3. Integrate into diagnostics panel or as a tab alongside existing inventory view
4. Update source picker to show which models are currently loaded (optional enhancement)

## Open questions

1. **Should model load/unload be available for all endpoints or only Ollama nodes?** Recommendation: Ollama only for v1, since other providers don't expose this control.
2. **Keep-alive duration** — Ollama's `keep_alive` parameter controls how long a model stays loaded. Should the UI expose this, or use a sensible default (e.g., 5 minutes)? Recommendation: default to `5m`, expose as an advanced option.
3. **Safety** — Loading a large model can exhaust GPU memory. Should we show available VRAM before loading? Recommendation: show memory info from `/api/ps` but don't block the operation.
