# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Multi-Model Chat Application — a web app that lets users chat against multiple model backends (Ollama, cloud APIs, routers) selected from JSON configuration. The primary use case is managing and using Ollama instances across a home network. Repository is currently in its initial design phase with no source code yet.

The design document lives at `docs/initial_design.md`.

## CRITICAL: Plan Before Implementing

- **ALWAYS create a plan document before doing any implementation work.** When the user asks you to build, fix, refactor, or implement something, write a plan document in `docs/` first (e.g., `docs/feature_name_plan.md`) and present it for review.
- **Do NOT start writing code until the user has reviewed and approved the plan.**
- Plan documents should include: goals, affected files, step-by-step approach, and any open questions.
- Small, obvious fixes (typos, one-line changes) are exempt — use judgment.
- **NEVER use an Anthropic API key.** Do not import, configure, or wire `AnthropicAdapter` or any direct API key-based adapter.

## Architecture (from design doc)

Four-layer architecture:

1. **Chat Page (UI)** — display state, interaction, streaming assembly, client-side filtering. No provider semantics.
2. **Application Backend** — normalized API, configuration loading, policy enforcement, route resolution, adapter selection, streaming, provenance recording.
3. **Adapter Layer** — translates normalized requests to provider-specific requests and back. Selected by endpoint `provider_type` (not source type).
4. **Model Endpoint Layer** — Ollama instances, provider APIs, routers.

Key entities (keep these separate, do not collapse): **Source** (user-selectable UI target) → **Route** (logical resolver over endpoints) → **Endpoint** (concrete backend target). Plus **CapabilityProfile** and **Policy**.

Configuration is file-based JSON: `sources.json`, `endpoints.json`, `routes.json`, `policies.json`, `capabilities.json`, `app_config.json`. Browser talks only to the application backend, never directly to providers.

Persistence target: SQLite. Key tables: conversations, messages, executions, endpoint_health_snapshots, endpoint_inventory_snapshots.

### Implementation Milestones (from design doc)

1. Configuration loading and validation → UI-safe source list
2. Persistence and conversation models
3. Adapter integration (Ollama first)
4. Route resolution and multi-node Ollama
5. UI provenance, diagnostics, health, inventory views
6. Direct provider and router adapters

## jcodemunch MCP Integration

This project has a **jcodemunch MCP server** configured for code intelligence.

- **Repo identifier**: `bonjohen/ai_lab` (use this for all `repo` parameters)
- **Index**: Run `index_repo(url: "bonjohen/ai_lab", use_ai_summaries: false)` to index/re-index. Use `incremental: true` (default) after code changes.
- **AI summaries are disabled** (`use_ai_summaries: false`) — do not enable them.

### When to Use jcodemunch vs Built-in Tools

- **Use jcodemunch** for: understanding code structure, finding symbol definitions, exploring unfamiliar parts of the codebase
- **Use built-in Read/Glob/Grep** for: reading specific known files, making edits, simple pattern matching
- **Prefer `search_symbols`** over Grep when looking for function/class/type definitions
- **Prefer `get_file_outline`** before reading a large file to understand its structure first

## Workflow Rules

### Task Tracking

Tasks use checkbox syntax:
- `[ ]` — pending
- `[~]` — actively in progress (only ONE task at a time)
- `[X]` — complete

- Commit at each phase end
- Echo banners for task/phase transitions
- Don't stop between phases — continue to the next
- At the completion of all phases, push
- Do not prefix bash commands with `cd /c/Projects/ai_lab` — the working directory is already set to the project root
