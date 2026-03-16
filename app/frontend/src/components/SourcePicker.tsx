import { useState } from "react";
import type { SourceListItem } from "../api";

interface Props {
  sources: SourceListItem[];
  selectedId: string | null;
  onSelect: (source: SourceListItem) => void;
}

const CLASS_ORDER = ["local", "lan", "provider", "router"];

export default function SourcePicker({ sources, selectedId, onSelect }: Props) {
  const [filter, setFilter] = useState("");

  const filtered = sources.filter(
    (s) =>
      s.display_name.toLowerCase().includes(filter.toLowerCase()) ||
      s.tags.some((t) => t.toLowerCase().includes(filter.toLowerCase()))
  );

  const grouped = CLASS_ORDER.map((cls) => ({
    label: cls.charAt(0).toUpperCase() + cls.slice(1),
    items: filtered.filter((s) => s.source_class === cls),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="source-picker">
      <input
        type="text"
        placeholder="Search sources..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="source-search"
      />
      {grouped.map((group) => (
        <div key={group.label} className="source-group">
          <div className="source-group-label">{group.label}</div>
          {group.items.map((s) => (
            <button
              key={s.id}
              className={`source-item ${s.id === selectedId ? "selected" : ""}`}
              onClick={() => onSelect(s)}
            >
              <span className="source-name">{s.display_name}</span>
              {s.default_model && (
                <span className="source-model">{s.default_model}</span>
              )}
              <div className="source-tags">
                {s.tags.map((t) => (
                  <span key={t} className="tag">
                    {t}
                  </span>
                ))}
                {s.is_route && <span className="tag route-tag">route</span>}
              </div>
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}
