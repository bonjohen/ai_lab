# Design Document: Multi-Model Chat Page, JSON-Configured First Version

## 1. Purpose

This document defines a first implementation of a chat page that can operate against multiple model backends selected from JSON configuration rather than hard-coded provider logic in the user interface. The immediate target is core text chat plus normalized metadata. The design is intentionally conservative. It exposes only a small common set of runtime parameters in the main interface and places advanced overrides behind an expandable panel. The system is intended to support local-machine models, home-network models, direct provider APIs, and router-style providers. A key early use case is managing and using Ollama instances running across a home network.

This version is meant to be detailed enough for a coding agent to create a planning document, identify implementation milestones, and begin breaking the work into components.

## 2. Product Intent

The product is a single chat experience that lets a user choose from configured model sources and hold normal chat conversations while preserving provenance about which backend answered each turn. The same page should work whether the target is a local Ollama process, a remote Ollama node on the LAN, a cloud API provider, or a router that chooses a downstream model.

The first version does not attempt deep infrastructure orchestration, provider-specific feature parity, or multimodal unification. It focuses on a stable text chat contract, explicit source selection, streaming responses, and enough operational awareness to make home-network Ollama usage practical.

## 3. Design Constraints

The user interface must not contain provider secrets. The browser must talk only to the application backend. Configuration is file-based JSON for now. Core text chat and metadata are normalized. The initial UI must present only a small common parameter set. Any advanced provider-specific controls must sit behind an expandable section and must not be required for normal usage.

The design must preserve future expansion to non-text models, richer capabilities, routing logic, comparison workflows, and operational controls, but that future work must not complicate the first implementation unnecessarily.

## 4. First-Version Scope

The first version includes a chat page, a backend application service, a JSON configuration loader, a provider adapter layer, conversation persistence, message persistence, execution provenance capture, health checks, and basic Ollama node awareness.

The first version supports these source classes: fixed local endpoint, fixed LAN endpoint, direct provider endpoint, and router endpoint. A source may point directly to one endpoint or to one logical route. A route may resolve to one of several endpoints based on simple preferred-order rules.

The first version supports these user capabilities: choose a source, start a conversation, continue a conversation, receive streamed responses, inspect which source answered, view basic source details, and inspect basic Ollama node health and model inventory. It also supports forking a conversation into a new chat with a different selected source.

The first version does not include tool calling, multimodal input, image generation, embeddings, agent orchestration, benchmarking dashboards, model pull and delete actions, or fine-grained provider parameter parity.

## 5. Core Product Decisions

The first important decision is that the browser talks only to one backend API owned by the application. The UI never talks directly to Ollama or to any cloud provider. This keeps secrets off the client, centralizes normalization, and makes future routing and policy enforcement easier.

The second important decision is that configuration is split into safe UI-facing metadata and backend-only private connection details, even though both are stored in JSON files for now. The backend merges them into runtime objects. This allows the UI to render source names, tags, and capabilities without exposing credentials or unnecessary internal details.

The third important decision is that conversations are source-pinned by default. If the user wants the same prompt history sent to another model, that should create a new conversation fork. Silent mid-thread engine switching should be avoided in the first version because it reduces clarity and weakens provenance.

The fourth important decision is that only a small common runtime parameter set is visible in the default interface. The likely set is temperature, max output tokens if applicable, and system prompt override if enabled by policy. Everything else belongs in an advanced panel.

## 6. Supported Source Types

A local source refers to a model backend on the same machine as the backend application. In practice this may still be reached over HTTP, but it is conceptually local.

A LAN source refers to a model backend hosted elsewhere on the home network. The main first-version target here is Ollama.

A provider source refers to a direct third-party or self-hosted API endpoint that exposes a supported chat interface.

A router source refers to a logical API that may decide which actual downstream model is used. The system must preserve both the configured route identity and the downstream resolved model identity if the router returns it.

## 7. User Experience

The page has three logical regions. The left side contains conversation history and source selection. The center contains the message thread and composer. The right side contains source details and diagnostics when opened. On smaller screens, the right side becomes a drawer or collapsible panel.

The main composer shows the active source clearly. The user can choose a configured source before starting a new conversation. Existing conversations remember their chosen source. Every assistant message displays compact provenance, such as source display name, endpoint nickname or route name, resolved model name, elapsed time, and token counts if known.

The source picker is grouped and searchable. It supports tags such as local, LAN, provider, router, coding, reasoning, fast, cheap, and preferred. The first version may implement these as display filters only.

The advanced parameter panel is collapsed by default. It should contain only settings supported by the selected source and allowed by policy. If a source does not support a parameter, the UI must hide or disable it rather than guessing.

## 8. Functional Requirements

The backend must load sources, endpoints, routes, policies, and capability profiles from JSON files at startup and optionally support reload on file change or manual refresh.

The UI must be able to request a list of available sources, grouped and filtered, with display-safe metadata only.

The backend must accept a normalized chat request containing conversation identity, selected source identity, user messages, and a small set of normalized runtime options.

The backend must stream normalized response events back to the UI.

The system must persist conversations, messages, and execution records.

The system must preserve per-response provenance, including the selected source, resolved endpoint, resolved model, route identity if applicable, timing, and token usage if available.

The system must expose health information for configured endpoints and basic model inventory for Ollama endpoints.

The system must support explicit conversation fork.

The system must expose advanced runtime options only if the selected source supports them and policy allows them.

## 9. Non-Functional Requirements

The system must feel responsive during streaming. Health checks and inventory refreshes must not block chat traffic.

Configuration errors must surface clearly in backend logs and in a minimal admin-facing diagnostic view.

The system must degrade gracefully when a configured source is offline. The user should receive a precise error such as endpoint unreachable, model missing, authentication failed, or request timed out.

The architecture must be easy to extend with new adapters. The provider-specific code must live behind a normalized adapter contract.

The system must be testable without requiring all providers to be online at once. Adapters and route resolution must be unit-testable in isolation.

## 10. System Architecture

The system has four main layers.

The first layer is the chat page. It owns display state, interaction state, streaming assembly, and simple client-side filtering. It does not own provider semantics.

The second layer is the application backend. It exposes the normalized API used by the UI. It loads configuration, applies policy, resolves sources into endpoints, chooses adapters, handles streaming, records provenance, and returns normalized responses.

The third layer is the adapter layer. Each adapter knows how to translate normalized requests into provider-specific requests and translate provider-specific responses back into normalized events.

The fourth layer is the model endpoint layer. This includes Ollama instances, provider APIs, and routers.

This separation is mandatory. It is the main architectural boundary that keeps the UI stable while the backend grows.

## 11. File-Based Configuration Strategy

The system uses JSON files rather than database-managed source configuration. The backend reads configuration from a configuration directory. The recommended first-cut files are sources.json, endpoints.json, routes.json, policies.json, capabilities.json, and app_config.json. Sensitive settings should live in a separate private file or environment-variable overlay rather than in UI-safe configuration.

The coding agent should treat configuration loading as a first-class subsystem rather than sprinkling file reads across the codebase. The loader should validate cross-references, merge defaults, reject malformed entries, and expose one coherent in-memory configuration model to the rest of the application.

The UI must never receive the raw configuration files. It should receive only a backend-generated view model.

## 12. Recommended Configuration Files

The file app_config.json holds application-wide behavior such as refresh intervals, feature flags, persistence settings, and UI policy defaults.

The file capabilities.json defines reusable capability profiles. These describe whether a source supports streaming, system prompts, temperature, top_p, max output tokens, structured output, tool calling, vision, and similar concerns. In the first version, only text-chat-relevant fields matter, but the schema should leave room for future fields.

The file endpoints.json defines concrete connection targets. Each endpoint entry should include id, provider type, transport details, authentication reference if needed, health-check settings, optional tags, and operational metadata such as whether it is an Ollama node.

The file routes.json defines logical sources that resolve across endpoints. Each route entry should include id, display name, candidate endpoints in preferred order, selection policy, fallback policy, and optional constraints such as required model presence.

The file sources.json defines what the UI can show and select. Each source points either to a single endpoint or to a route, includes a display name, source type, tags, capability profile reference, and UI-facing defaults.

The file policies.json defines runtime limits and allowed overrides. It should specify which parameters the main UI can expose, which advanced overrides are allowed, per-source or per-provider timeouts, retry rules, and failover behavior.

## 13. Configuration Entity Definitions

A CapabilityProfile is a reusable definition of supported features and runtime controls. It exists so that many sources can share one behavior profile.

An Endpoint is one concrete backend target. It has network identity and provider semantics.

A Route is one logical resolver over multiple endpoints. It does not itself perform inference; it picks where the request goes.

A Source is one user-selectable target shown in the UI. It references either an endpoint or a route. The selected source is what the user sees. The resolved endpoint is what actually handles the request.

A Policy is a rule set for defaults, limits, retries, failover, and which parameters are exposed.

This distinction is important and should not be collapsed. The coding agent should preserve these identities separately in both configuration loading and runtime metadata.

## 14. Example Logical Shape of the JSON Files

The exact JSON syntax can be finalized by the coding agent, but the logical shape should follow these rules.

Each object needs a stable id string.

Each cross-reference uses ids rather than names.

A source references one capability profile and exactly one target, which is either endpoint_id or route_id.

A route references one or more endpoint ids in preference order.

An endpoint includes one provider_type value, such as ollama, openai_compatible, provider_native, or router_api.

A policy may be global, provider-scoped, or source-scoped. Resolution should allow defaults and overrides.

A capability profile should separate support flags from allowed UI controls.

## 15. Configuration Validation Rules

The loader must reject duplicate ids.

A source must reference either endpoint_id or route_id, but not both.

A route must reference at least one valid endpoint.

A capability profile id referenced by a source must exist.

A policy reference must resolve if specified.

A source marked visible in the UI must reference a valid target and capability profile.

If an endpoint is marked as an Ollama node, it must include fields needed for model inventory and health checks.

If a route requires model presence, its candidate endpoints must all be eligible for model inventory queries.

The loader should emit errors with filename, object id, and field name so configuration problems are easy to fix.

## 16. Backend API

The backend must expose a normalized API. The first version should include these conceptual operations.

There is an operation to list UI-visible sources with display metadata, grouped tags, and safe default controls.

There is an operation to get one source detail record, including safe diagnostics and capability information.

There is an operation to create a conversation.

There is an operation to list conversations.

There is an operation to get one conversation with messages and execution summaries.

There is an operation to fork a conversation.

There is an operation to submit a chat request.

There is an operation to stream a chat response.

There is an operation to cancel an in-flight request.

There is an operation to list endpoint health.

There is an operation to list Ollama model inventory by node.

There is an operation to refresh health or inventory on demand if the user has access.

The transport can be REST plus server-sent events, REST plus websocket streaming, or a comparable pattern. The design does not require one specific mechanism, but it does require that the event stream be normalized.

## 17. Normalized Chat Request

A normalized chat request should include conversation_id, source_id, message list, optional system prompt, and normalized runtime options. The runtime options in the main UI should be a small, common set only. The likely first-cut set is temperature, max output tokens, and stream true or false. The advanced section may later include top_p, seed, repetition penalties, reasoning settings, and provider-specific extras, but those must remain optional and policy-gated.

The request must not assume that every provider supports every parameter. The adapter must receive only what the selected source and policy allow.

## 18. Normalized Stream Event Model

The streaming response should use application-owned event types rather than raw provider chunks. The first version should define a minimum event model with the following lifecycle.

A started event identifies the execution record and confirms the resolved source, endpoint, and model if already known.

A delta event carries incremental assistant text.

A metadata event may provide token usage, latency milestones, route resolution details, or provider notices.

A completed event finalizes the assistant message and execution record.

An error event terminates the stream with a normalized error code and human-readable message.

A cancelled event indicates user cancellation.

The UI assembles assistant text from delta events and updates provenance when metadata arrives.

## 19. Adapter Contract

Each provider adapter must implement a common interface. Conceptually, each adapter must be able to validate runtime options for a source, perform a health check, list models if supported, submit a normalized chat request, and emit normalized stream events.

The Ollama adapter must support local and remote HTTP targets, model listing, health checks, and text chat streaming.

The direct provider adapter must support one or more cloud or self-hosted APIs. The first version may start with one OpenAI-compatible contract if that simplifies implementation.

The router adapter must support route-aware metadata and pass through resolved model identity if returned.

The coding agent should implement adapter selection by endpoint provider_type, not by source type. That keeps the design cleaner.

## 20. Route Resolution

Route resolution must happen on the backend before the chat request is handed to an adapter. A route contains a candidate endpoint list in preferred order and one simple selection strategy for the first version.

The recommended first strategy is first healthy endpoint that satisfies required conditions. If the route also specifies required model presence, the backend should choose the first healthy candidate whose inventory indicates that the requested model exists there.

If the route fails to resolve, the user should receive a specific failure such as no healthy endpoint, model not present on any eligible node, or route misconfiguration.

The route resolver must record why an endpoint was selected or skipped so that execution logs remain useful.

## 21. Ollama-Specific Design

Ollama nodes are first-class operational entities in the first version. An endpoint marked as ollama should support health checks and model inventory refresh.

For each Ollama endpoint, the backend should maintain a cached record containing node status, last successful contact, basic latency estimate, last inventory refresh, and the list of known models. This cache should have a short time-to-live and should refresh in the background rather than on every page load.

A source may point directly to one Ollama endpoint or indirectly through a route spanning multiple Ollama nodes.

The right-side diagnostics panel should display Ollama details such as node display name, address label if safe to show, last health result, model list, and freshness timestamps.

The first version should not attempt remote pull, delete, or runtime tuning operations against Ollama nodes.

## 22. Persistence Model

The persistence layer needs to store configuration-independent product data rather than configuration files themselves. The key persistent entities are Conversation, Message, ExecutionRecord, EndpointHealthSnapshot, and EndpointInventorySnapshot.

A Conversation stores identity, title or derived label, pinned source id, created time, updated time, and archival state.

A Message stores conversation id, role, content text, created time, and display metadata. Assistant messages should reference one ExecutionRecord.

An ExecutionRecord stores the selected source id, resolved endpoint id, route id if applicable, resolved model name, adapter type, request options actually used, timing, token usage, completion status, error code if any, and raw provider metadata if the application chooses to keep a sanitized subset for diagnostics.

EndpointHealthSnapshot stores point-in-time health state for endpoints.

EndpointInventorySnapshot stores point-in-time model inventory for endpoints that support it.

The coding agent may implement this in SQLite for simplicity. SQLite is sufficient for a first version.

## 23. Data Semantics for Provenance

The selected source id identifies what the user chose.

The resolved endpoint id identifies where the request actually went.

The route id identifies the logical resolver if one was used.

The resolved model name identifies the actual model that answered.

The requested model name may differ from the resolved model name for routers or aliases and should be stored separately if that distinction exists.

These fields are not optional niceties. They are required for trust, debugging, and future analytics.

## 24. Conversation Rules

A new conversation starts with one selected source id.

A conversation stays pinned to that source unless the user explicitly forks or retargets it.

If retargeting is ever allowed in place, the system should record a conversation event marking the source change. For the first version, explicit fork is preferred and in-place retargeting should be avoided or hidden.

A fork copies visible messages into a new conversation with a new selected source id. The copied assistant messages retain their original provenance; future assistant messages use the new source.

## 25. UI Parameter Model

The main UI should expose only a small common set of controls. The conservative recommendation is temperature and max output tokens. If system prompt override is supported and desired, it can also appear here, but it should be controlled by policy.

The advanced section is collapsed by default. It may include provider-specific fields only if policy allows them and the source supports them. The UI should show only supported controls. It must not show a giant shared form with irrelevant disabled fields.

The backend remains the final authority on which options are accepted. The UI is advisory; the backend is enforcing.

## 26. Source Listing View Model

The backend should transform raw configuration into a UI-safe source list. Each source entry returned to the client should include id, display name, source class, tags, capability summary, default model label if applicable, route indication if applicable, and a compact health summary if available.

The UI-safe model should not include raw auth data, full private network details unless explicitly intended, or hidden policy internals.

The coding agent should define a clear boundary between internal configuration models and public view models.

## 27. Health and Inventory Refresh Model

Health checks and inventory refreshes should run on a backend schedule. Suggested first-cut behavior is frequent lightweight health checks and less frequent inventory refreshes. Manual refresh may be available from the UI.

Health refresh should not block chat requests. If the cache is stale during a route decision, the backend may do a targeted live check for the candidate endpoint rather than forcing the user to wait on a full refresh cycle.

Inventory refresh for Ollama should be cached because model listings do not need to be real-time for every page render.

The UI should display freshness timestamps so stale information is visible.

## 28. Error Model

The backend should normalize errors into a small set of product-level codes. The first version should at least distinguish configuration_error, endpoint_unreachable, auth_failed, model_not_found, timeout, invalid_request, provider_error, route_resolution_failed, and cancelled.

Each normalized error should carry a user-facing message and an internal diagnostic message. The user-facing message should be short and precise. The internal diagnostic message should go to logs and optional admin diagnostics.

The UI should render errors inline in the conversation thread when the failure is request-specific and in the diagnostics panel when the failure is source-specific.

## 29. Security

The backend holds credentials and private connection details. The client receives only sanitized metadata.

Configuration files containing secrets should not be shipped with public assets. The coding agent should either use separate private JSON files ignored by source control or environment-variable substitution layered onto JSON configuration.

Administrative operations, if added later, must be separate from basic chat permissions. The first version may assume one trusted user on a home network, but the architecture should not force that assumption forever.

## 30. Logging and Observability

The backend should log configuration load results, route decisions, endpoint health changes, inventory refresh results, request start, request completion, request failure, and cancellation.

Each execution should have a correlation id. This id should connect UI request logs, backend request logs, adapter logs, and persistence records.

Logs should make it possible to answer these questions quickly: which source was selected, which endpoint was resolved, which model answered, how long it took, whether failover occurred, and why an error happened.

## 31. Suggested SQLite Schema Direction

The coding agent should create separate tables for conversations, messages, executions, endpoint_health_snapshots, endpoint_inventory_snapshots, and optionally conversation_events.

The conversations table should include source_id because the initial source choice matters operationally.

The messages table should store plain text content and role. Assistant messages should reference execution_id.

The executions table should store selected_source_id, resolved_endpoint_id, route_id, requested_model, resolved_model, adapter_type, request_options_json, token_usage_json, status, error_code, error_message, started_at, completed_at, and correlation_id.

The snapshots tables should be append-friendly so that history is available for diagnostics if desired, even if the UI only shows the latest snapshot.

## 32. Recommended Repository Structure

A clean first-cut repository should separate config, backend domain logic, adapters, persistence, and UI.

The configuration loader should live in its own module.

The route resolver should live in its own module.

Each adapter should live in its own provider module.

Normalized API request and response models should live in a shared contract module.

The persistence models and migration logic should live in a persistence module.

The UI should consume only the normalized contract and UI-safe view models.

The coding agent should avoid leaking adapter-specific types into the UI layer.

## 33. Planning Milestones

The first milestone is configuration loading and validation. At the end of this milestone, the backend can read JSON files, validate them, and expose a UI-safe source list.

The second milestone is persistence and conversation models. At the end of this milestone, the system can create and load conversations and messages even before provider integration is finished.

The third milestone is adapter integration with Ollama first. At the end of this milestone, the application can chat against one configured Ollama endpoint and stream normalized text.

The fourth milestone is route resolution and multi-node Ollama support. At the end of this milestone, the application can choose among home-network Ollama nodes.

The fifth milestone is UI provenance, diagnostics, health, and inventory views.

The sixth milestone is direct provider and router adapters.

This order keeps the first useful version small and aligned with the main use case.

## 34. Acceptance Criteria for Version One

A coding agent should treat version one as complete when the following are true.

The application can load JSON configuration and reject invalid references with actionable errors.

The UI can display configured sources and allow the user to choose one.

A user can start a conversation, send a prompt, and receive streamed text from a configured endpoint.

Assistant messages display source provenance including selected source and resolved model.

Conversations and messages persist across restarts.

The backend can query configured Ollama nodes for health and model inventory and expose that information in the diagnostics view.

A route spanning multiple endpoints can resolve to the first healthy eligible target.

Errors are normalized and rendered clearly.

The default UI exposes only a small common parameter set, while advanced controls are collapsed and policy-gated.

## 35. Immediate Follow-On Document

The next document the coding agent should produce is a concrete technical plan with four parts.

The first part should define the exact JSON schemas for app_config.json, capabilities.json, endpoints.json, routes.json, sources.json, and policies.json.

The second part should define the normalized backend API contract, including stream event payloads.

The third part should define the SQLite schema and migrations.

The fourth part should define the initial implementation task graph by milestone, component, and dependency.

## 36. Final Guidance to the Coding Agent

Do not overgeneralize for multimodal work yet. Build a clean text-chat core with strong provenance and clean adapter boundaries.

Do not let the UI learn provider semantics. Keep normalization in the backend.

Do not collapse Source, Route, and Endpoint into one object. The distinctions matter.

Do not expose a large parameter surface in the first version. Keep the default UI simple.

Do implement Ollama well first, because it is both the main user value and the best test of the architecture.

Do treat configuration loading and validation as a real subsystem, not an afterthought.

Do preserve future extensibility, but not at the cost of first-version clarity.

Comment: I can turn this into the next document with the exact JSON schema, API contract, and SQLite schema.
