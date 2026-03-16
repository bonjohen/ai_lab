import { useEffect, useState } from "react";
import type { HealthSummary, InventorySummary, SourceDetail } from "../api";
import {
  fetchHealth,
  fetchInventory,
  fetchSourceDetail,
  refreshHealth,
  refreshInventory,
} from "../api";

interface Props {
  sourceId: string | null;
  open: boolean;
  onClose: () => void;
}

export default function DiagnosticsPanel({ sourceId, open, onClose }: Props) {
  const [health, setHealth] = useState<HealthSummary[]>([]);
  const [inventory, setInventory] = useState<InventorySummary[]>([]);
  const [sourceDetail, setSourceDetail] = useState<SourceDetail | null>(null);

  useEffect(() => {
    if (open) {
      fetchHealth().then(setHealth);
      fetchInventory().then(setInventory);
    }
  }, [open]);

  useEffect(() => {
    if (sourceId && open) {
      fetchSourceDetail(sourceId).then(setSourceDetail);
    }
  }, [sourceId, open]);

  if (!open) return null;

  return (
    <div className="diagnostics-panel">
      <div className="diag-header">
        <h3>Diagnostics</h3>
        <button className="close-btn" onClick={onClose}>
          X
        </button>
      </div>

      {sourceDetail && (
        <section className="diag-section">
          <h4>Source: {sourceDetail.display_name}</h4>
          <div className="diag-detail">
            <span>Class: {sourceDetail.source_class}</span>
            {sourceDetail.endpoint_display_name && (
              <span>Endpoint: {sourceDetail.endpoint_display_name}</span>
            )}
            {sourceDetail.route_display_name && (
              <span>
                Route: {sourceDetail.route_display_name} (
                {sourceDetail.route_endpoint_count} endpoints)
              </span>
            )}
            {sourceDetail.default_model && (
              <span>Model: {sourceDetail.default_model}</span>
            )}
          </div>
        </section>
      )}

      <section className="diag-section">
        <div className="diag-section-header">
          <h4>Endpoint Health</h4>
          <button
            className="refresh-btn"
            onClick={() => refreshHealth().then(setHealth)}
          >
            Refresh
          </button>
        </div>
        <div className="health-list">
          {health.map((h) => (
            <div key={h.endpoint_id} className="health-item">
              <span
                className={`health-dot ${h.healthy === true ? "healthy" : h.healthy === false ? "unhealthy" : "unknown"}`}
              />
              <span className="health-name">{h.display_name}</span>
              {h.latency_ms != null && (
                <span className="health-latency">{h.latency_ms}ms</span>
              )}
              <span className="health-detail">{h.detail}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="diag-section">
        <div className="diag-section-header">
          <h4>Model Inventory</h4>
          <button
            className="refresh-btn"
            onClick={() => refreshInventory().then(setInventory)}
          >
            Refresh
          </button>
        </div>
        {inventory.map((inv) => (
          <div key={inv.endpoint_id} className="inventory-node">
            <div className="inv-node-name">
              {inv.display_name} ({inv.model_count} models)
            </div>
            <ul className="inv-model-list">
              {inv.models.map((m) => (
                <li key={m.name}>{m.name}</li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    </div>
  );
}
