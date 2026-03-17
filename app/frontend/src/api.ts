const API_BASE = "http://localhost:8100/api";

export interface CapabilitySummary {
  supports_streaming: boolean;
  supports_system_prompt: boolean;
  supports_temperature: boolean;
  supports_max_tokens: boolean;
}

export interface SourceListItem {
  id: string;
  display_name: string;
  source_class: string;
  tags: string[];
  capabilities: CapabilitySummary;
  default_model: string | null;
  is_route: boolean;
  health_status: string | null;
}

export interface SourceDetail extends SourceListItem {
  endpoint_display_name: string | null;
  route_display_name: string | null;
  route_endpoint_count: number | null;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  created_at: string;
  execution_id: string | null;
  execution?: Execution;
}

export interface Execution {
  id: string;
  selected_source_id: string;
  resolved_endpoint_id: string | null;
  resolved_model: string | null;
  token_usage_json: string | null;
  status: string;
  started_at: string;
  completed_at: string | null;
}

export interface Conversation {
  id: string;
  title: string | null;
  source_id: string;
  created_at: string;
  updated_at: string;
  messages?: Message[];
}

export interface StreamEvent {
  type: string;
  execution_id?: string;
  source_id?: string;
  endpoint_id?: string;
  model?: string;
  content?: string;
  token_usage?: Record<string, number>;
  timing?: Record<string, unknown>;
  error_code?: string;
  error_message?: string;
}

export interface HealthSummary {
  endpoint_id: string;
  display_name: string;
  healthy: boolean | null;
  latency_ms: number | null;
  detail: string;
}

export interface InventorySummary {
  endpoint_id: string;
  display_name: string;
  models: { name: string; size: number | null }[];
  model_count: number;
}

export async function fetchSources(): Promise<SourceListItem[]> {
  const resp = await fetch(`${API_BASE}/sources`);
  return resp.json();
}

export async function fetchSourceDetail(id: string): Promise<SourceDetail> {
  const resp = await fetch(`${API_BASE}/sources/${id}`);
  return resp.json();
}

export async function fetchConversations(): Promise<Conversation[]> {
  const resp = await fetch(`${API_BASE}/conversations`);
  return resp.json();
}

export async function fetchConversation(id: string): Promise<Conversation> {
  const resp = await fetch(`${API_BASE}/conversations/${id}`);
  return resp.json();
}

export async function updateConversation(
  id: string,
  updates: { source_id?: string; title?: string }
): Promise<Conversation> {
  const resp = await fetch(`${API_BASE}/conversations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  return resp.json();
}

export async function createConversation(
  sourceId: string,
  title?: string
): Promise<Conversation> {
  const resp = await fetch(`${API_BASE}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_id: sourceId, title }),
  });
  return resp.json();
}

export async function forkConversation(
  id: string,
  newSourceId: string
): Promise<Conversation> {
  const resp = await fetch(`${API_BASE}/conversations/${id}/fork`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_source_id: newSourceId }),
  });
  return resp.json();
}

export function streamChat(
  conversationId: string,
  sourceId: string,
  messages: { role: string; content: string }[],
  options: { temperature?: number; max_tokens?: number } = {},
  onEvent: (event: StreamEvent) => void,
  onDone: () => void,
  onError: (err: string) => void
): AbortController {
  const controller = new AbortController();

  fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: conversationId,
      source_id: sourceId,
      messages,
      options: { ...options, stream: true },
    }),
    signal: controller.signal,
  })
    .then(async (resp) => {
      const reader = resp.body?.getReader();
      if (!reader) {
        onError("No response body");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event: StreamEvent = JSON.parse(line.slice(6));
              onEvent(event);
            } catch {
              // skip malformed
            }
          }
        }
      }
      onDone();
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        onError(err.message);
      }
    });

  return controller;
}

export async function fetchHealth(): Promise<HealthSummary[]> {
  const resp = await fetch(`${API_BASE}/health`);
  return resp.json();
}

export async function fetchInventory(): Promise<InventorySummary[]> {
  const resp = await fetch(`${API_BASE}/inventory`);
  return resp.json();
}

export async function refreshHealth(): Promise<HealthSummary[]> {
  const resp = await fetch(`${API_BASE}/health/refresh`, { method: "POST" });
  return resp.json();
}

export async function refreshInventory(): Promise<InventorySummary[]> {
  const resp = await fetch(`${API_BASE}/inventory/refresh`, { method: "POST" });
  return resp.json();
}
