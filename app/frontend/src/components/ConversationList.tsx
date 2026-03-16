import type { Conversation } from "../api";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (conv: Conversation) => void;
  onNew: () => void;
}

export default function ConversationList({
  conversations,
  activeId,
  onSelect,
  onNew,
}: Props) {
  return (
    <div className="conversation-list">
      <button className="new-chat-btn" onClick={onNew}>
        + New Chat
      </button>
      {conversations.map((conv) => (
        <button
          key={conv.id}
          className={`conv-item ${conv.id === activeId ? "active" : ""}`}
          onClick={() => onSelect(conv)}
        >
          <span className="conv-title">
            {conv.title || conv.id.slice(0, 8)}
          </span>
          <span className="conv-source">{conv.source_id}</span>
        </button>
      ))}
    </div>
  );
}
