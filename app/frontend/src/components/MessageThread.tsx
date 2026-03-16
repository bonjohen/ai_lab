import { useEffect, useRef } from "react";
import type { Message } from "../api";

interface Props {
  messages: Message[];
  streamingContent: string;
  isStreaming: boolean;
}

function Provenance({ execution }: { execution: Message["execution"] }) {
  if (!execution) return null;
  const usage = execution.token_usage_json
    ? JSON.parse(execution.token_usage_json)
    : null;

  return (
    <div className="provenance">
      {execution.resolved_model && (
        <span className="prov-model">{execution.resolved_model}</span>
      )}
      {usage?.prompt != null && (
        <span className="prov-tokens">
          {usage.prompt}+{usage.completion} tokens
        </span>
      )}
      {execution.status === "error" && (
        <span className="prov-error">error</span>
      )}
    </div>
  );
}

export default function MessageThread({
  messages,
  streamingContent,
  isStreaming,
}: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  return (
    <div className="message-thread">
      {messages.map((msg) => (
        <div key={msg.id} className={`message ${msg.role}`}>
          <div className="message-role">{msg.role}</div>
          <div className="message-content">{msg.content}</div>
          {msg.role === "assistant" && msg.execution && (
            <Provenance execution={msg.execution} />
          )}
        </div>
      ))}
      {isStreaming && streamingContent && (
        <div className="message assistant streaming">
          <div className="message-role">assistant</div>
          <div className="message-content">{streamingContent}</div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
