"use client";

import { useCallback, useEffect, useState } from "react";

import { ScreenChrome } from "@/components/ScreenChrome";
import { ack, auditTrail, getC2BaseUrl, inbox } from "@/lib/c2";
import type { AuditTrail, InboxItem } from "@/lib/types";

const DEFAULT_UNIT = "CUE-NODE-01";

export default function RecipientPage() {
  const [unitId, setUnitId] = useState(DEFAULT_UNIT);
  const [items, setItems] = useState<InboxItem[]>([]);
  const [trail, setTrail] = useState<AuditTrail | null>(null);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState("");
  const [autoPoll, setAutoPoll] = useState(true);

  const refresh = useCallback(async () => {
    const [box, audit] = await Promise.all([inbox(unitId), auditTrail()]);
    setItems(box.taskings ?? []);
    setTrail(audit);
  }, [unitId]);

  useEffect(() => {
    void refresh().catch((err: Error) => setLog(err.message));
  }, [refresh]);

  useEffect(() => {
    if (!autoPoll) return;
    const id = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(id);
  }, [autoPoll, refresh]);

  async function run(label: string, fn: () => Promise<void>) {
    setBusy(true);
    setLog("");
    try {
      await fn();
      setLog(label);
    } catch (err) {
      setLog(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScreenChrome
      role="recipient"
      status={`Core ${getC2BaseUrl()} · inbox ${items.length}`}
    >
      <div className="bp-grid">
        <section className="bp-panel">
          <h2>Screen 2 · Recipient</h2>
          <div className="bp-controls">
            <label>
              Unit ID
              <input
                value={unitId}
                onChange={(e) => setUnitId(e.target.value)}
                disabled={busy}
              />
            </label>
            <label className="bp-check">
              <input
                type="checkbox"
                checked={autoPoll}
                onChange={(e) => setAutoPoll(e.target.checked)}
              />
              Auto-poll 2s
            </label>
          </div>
          <div className="bp-actions">
            <button
              type="button"
              className="bp-btn"
              disabled={busy}
              onClick={() => void run("Polled", () => refresh())}
            >
              Poll inbox
            </button>
          </div>
          {log ? <p className="bp-log">{log}</p> : null}
        </section>

        <section className="bp-panel">
          <h2>Pending taskings</h2>
          {items.length === 0 ? (
            <p className="bp-dim">Inbox empty — approve on Screen 1 first.</p>
          ) : (
            <ul className="bp-inbox">
              {items.map((item) => (
                <li key={item.coa.coa_id}>
                  <div>
                    <p className="bp-mono">{item.coa.coa_id}</p>
                    <p>
                      {item.coa.intent} · {item.status}
                    </p>
                    <p className="bp-dim">issued {item.issued_at}</p>
                  </div>
                  <button
                    type="button"
                    className="bp-btn approve"
                    disabled={busy || item.status === "ACKED"}
                    onClick={() =>
                      void run("Ack sealed", async () => {
                        await ack({
                          coa_id: item.coa.coa_id,
                          unit_id: unitId,
                        });
                        await refresh();
                      })
                    }
                  >
                    Ack
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bp-panel bp-panel-muted">
          <h2>Audit trail (tail)</h2>
          <p className="bp-dim">
            {trail?.count ?? 0} records · {trail?.path ?? "—"}
          </p>
          <ol className="bp-audit">
            {(trail?.records ?? [])
              .slice(-8)
              .reverse()
              .map((rec, i) => (
                <li key={`${String(rec.hash)}-${i}`}>
                  <span className="bp-mono">
                    {String(rec.activity_name ?? rec.class_uid ?? "event")}
                  </span>
                  <span className="bp-dim">
                    {" "}
                    · {String(rec.hash ?? "").slice(0, 12)}…
                  </span>
                </li>
              ))}
          </ol>
        </section>
      </div>
    </ScreenChrome>
  );
}
