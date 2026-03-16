import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";
import type {
  Conversation,
  Message,
  SourceListItem,
  StreamEvent,
} from "./api";
import {
  createConversation,
  fetchConversation,
  fetchConversations,
  fetchSources,
  forkConversation,
  streamChat,
} from "./api";
import Composer from "./components/Composer";
import ConversationList from "./components/ConversationList";
import DiagnosticsPanel from "./components/DiagnosticsPanel";
import MessageThread from "./components/MessageThread";
import RuntimeOptions from "./components/RuntimeOptions";
import SourcePicker from "./components/SourcePicker";

export default function App() {
  const [sources, setSources] = useState<SourceListItem[]>([]);
  const [selectedSource, setSelectedSource] = useState<SourceListItem | null>(
    null
  );
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConv, setActiveConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [diagOpen, setDiagOpen] = useState(false);
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(2048);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchSources().then(setSources);
    fetchConversations().then(setConversations);
  }, []);

  const loadConversation = useCallback(async (conv: Conversation) => {
    const full = await fetchConversation(conv.id);
    setActiveConv(full);
    setMessages(full.messages || []);
  }, []);

  const handleNewChat = useCallback(async () => {
    if (!selectedSource) return;
    const conv = await createConversation(selectedSource.id);
    setActiveConv(conv);
    setMessages([]);
    setConversations((prev) => [conv, ...prev]);
  }, [selectedSource]);

  const handleSend = useCallback(
    (text: string) => {
      if (!activeConv || !selectedSource) return;

      const userMsg: Message = {
        id: crypto.randomUUID(),
        conversation_id: activeConv.id,
        role: "user",
        content: text,
        created_at: new Date().toISOString(),
        execution_id: null,
      };
      const updatedMessages = [...messages, userMsg];
      setMessages(updatedMessages);
      setIsStreaming(true);
      setStreamingContent("");

      const chatMessages = updatedMessages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const controller = streamChat(
        activeConv.id,
        selectedSource.id,
        chatMessages,
        { temperature, max_tokens: maxTokens },
        (event: StreamEvent) => {
          if (event.type === "delta" && event.content) {
            setStreamingContent((prev) => prev + event.content);
          } else if (event.type === "error") {
            setStreamingContent(
              (prev) =>
                prev + `\n\n[Error: ${event.error_message || "Unknown error"}]`
            );
          }
        },
        () => {
          setIsStreaming(false);
          setStreamingContent("");
          loadConversation(activeConv);
        },
        (err: string) => {
          setIsStreaming(false);
          setStreamingContent(`[Connection error: ${err}]`);
        }
      );

      abortRef.current = controller;
    },
    [activeConv, selectedSource, messages, temperature, maxTokens, loadConversation]
  );

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
  }, []);

  const handleFork = useCallback(async () => {
    if (!activeConv || !selectedSource) return;
    const forked = await forkConversation(activeConv.id, selectedSource.id);
    setConversations((prev) => [forked, ...prev]);
    loadConversation(forked);
  }, [activeConv, selectedSource, loadConversation]);

  return (
    <div className="app-layout">
      <div className="left-panel">
        <h2>Sources</h2>
        <SourcePicker
          sources={sources}
          selectedId={selectedSource?.id || null}
          onSelect={setSelectedSource}
        />
        <h2>Conversations</h2>
        <ConversationList
          conversations={conversations}
          activeId={activeConv?.id || null}
          onSelect={loadConversation}
          onNew={handleNewChat}
        />
      </div>

      <div className="center-panel">
        <div className="center-header">
          {activeConv && (
            <div className="conv-header">
              <span>{activeConv.title || `Chat ${activeConv.id.slice(0, 8)}`}</span>
              <button className="fork-btn" onClick={handleFork} title="Fork to selected source">
                Fork
              </button>
              <button
                className="diag-toggle"
                onClick={() => setDiagOpen(!diagOpen)}
              >
                {diagOpen ? "Hide" : "Info"}
              </button>
            </div>
          )}
          <RuntimeOptions
            temperature={temperature}
            maxTokens={maxTokens}
            onTemperatureChange={setTemperature}
            onMaxTokensChange={setMaxTokens}
            supportsTemperature={
              selectedSource?.capabilities.supports_temperature ?? true
            }
            supportsMaxTokens={
              selectedSource?.capabilities.supports_max_tokens ?? true
            }
          />
        </div>

        <MessageThread
          messages={messages}
          streamingContent={streamingContent}
          isStreaming={isStreaming}
        />

        <Composer
          onSend={handleSend}
          onCancel={handleCancel}
          isStreaming={isStreaming}
          disabled={!activeConv || !selectedSource}
          sourceName={selectedSource?.display_name || null}
        />
      </div>

      <DiagnosticsPanel
        sourceId={selectedSource?.id || null}
        open={diagOpen}
        onClose={() => setDiagOpen(false)}
      />
    </div>
  );
}
