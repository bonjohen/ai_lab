import { useState } from "react";

interface Props {
  onSend: (text: string) => void;
  onCancel: () => void;
  isStreaming: boolean;
  disabled: boolean;
  sourceName: string | null;
}

export default function Composer({
  onSend,
  onCancel,
  isStreaming,
  disabled,
  sourceName,
}: Props) {
  const [text, setText] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || disabled) return;
    onSend(text.trim());
    setText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form className="composer" onSubmit={handleSubmit}>
      {sourceName && <div className="composer-source">Source: {sourceName}</div>}
      <div className="composer-row">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={disabled ? "Select a source to start..." : "Type a message..."}
          disabled={disabled}
          rows={3}
        />
        {isStreaming ? (
          <button type="button" className="cancel-btn" onClick={onCancel}>
            Stop
          </button>
        ) : (
          <button type="submit" disabled={disabled || !text.trim()}>
            Send
          </button>
        )}
      </div>
    </form>
  );
}
