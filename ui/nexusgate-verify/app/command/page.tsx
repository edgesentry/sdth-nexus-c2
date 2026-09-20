"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { EvidenceChipModal } from "@/components/EvidenceChipModal";
import { ScreenChrome } from "@/components/ScreenChrome";
import { WarningPicture } from "@/components/WarningPicture";
import {
  approve,
  collectEvidenceUris,
  getC2BaseUrl,
  ingressDualSarFixture,
  ingressSentinelFixture,
  interpret,
  ontologyState,
  propose,
  resetRuntime,
} from "@/lib/c2";
import type { CourseOfAction, Finding, OntologyState } from "@/lib/types";

const DEFAULT_UNIT = "CUE-NODE-01";
const DEFAULT_TIMEOUT = 30;

export default function CommandPage() {
  const [state, setState] = useState<OntologyState | null>(null);
  const [finding, setFinding] = useState<Finding | null>(null);
  const [coa, setCoa] = useState<CourseOfAction | null>(null);
  const [scenario, setScenario] = useState("S2");
  const [unitId, setUnitId] = useState(DEFAULT_UNIT);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string>("");
  const [remaining, setRemaining] = useState<number | null>(null);
  const [chipOpen, setChipOpen] = useState<string | null>(null);
  const [interpretNote, setInterpretNote] = useState<string>("");

  const refresh = useCallback(async () => {
    const next = await ontologyState();
    setState(next);
    return next;
  }, []);

  useEffect(() => {
    void refresh().catch((err: Error) => setLog(err.message));
  }, [refresh]);

  useEffect(() => {
    if (remaining === null || remaining <= 0 || !coa) return;
    const id = window.setInterval(() => {
      setRemaining((r) => (r === null ? null : Math.max(0, r - 0.1)));
    }, 100);
    return () => window.clearInterval(id);
  }, [remaining, coa]);

  const evidenceUris = useMemo(
    () => (state ? collectEvidenceUris(state) : []),
    [state],
  );

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
      role="command"
      status={`Core ${getC2BaseUrl()} · pending ${state?.pending_proposals.length ?? 0}`}
    >
      <div className="bp-grid">
        <section className="bp-panel">
          <h2>Screen 1 · Propose</h2>
          <div className="bp-controls">
            <label>
              Scenario
              <select
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
                disabled={busy}
              >
                <option value="S1">S1</option>
                <option value="S2">S2 (hero amber)</option>
                <option value="S3">S3 (maritime / SAR)</option>
              </select>
            </label>
            <label>
              Unit ID
              <input
                value={unitId}
                onChange={(e) => setUnitId(e.target.value)}
                disabled={busy}
              />
            </label>
          </div>
          <div className="bp-actions">
            <button
              type="button"
              className="bp-btn"
              disabled={busy}
              onClick={() =>
                void run("Proposed", async () => {
                  const res = await propose({
                    scenario_id: scenario,
                    unit_id: unitId,
                  });
                  setFinding(res.finding ?? null);
                  setCoa(res.coa);
                  setRemaining(
                    res.status === "QUEUED" ? DEFAULT_TIMEOUT : null,
                  );
                  await refresh();
                })
              }
            >
              Propose
            </button>
            <button
              type="button"
              className="bp-btn ghost"
              disabled={busy}
              onClick={() =>
                void run("Interpret (no seal)", async () => {
                  const res = await interpret({
                    scenario_id: scenario,
                    force_heuristic: true,
                  });
                  setInterpretNote(
                    `source=${String(res.source)} hypotheses=${
                      Array.isArray(res.hypotheses) ? res.hypotheses.length : 0
                    }`,
                  );
                  await refresh();
                })
              }
            >
              Interpret
            </button>
            <button
              type="button"
              className="bp-btn ghost"
              disabled={busy}
              onClick={() =>
                void run("Sentinel fixture ingested", async () => {
                  await ingressSentinelFixture();
                  await refresh();
                })
              }
            >
              Ingress Sentinel fixture
            </button>
            <button
              type="button"
              className="bp-btn ghost"
              disabled={busy}
              onClick={() =>
                void run("Dual-SAR fixture ingested", async () => {
                  await ingressDualSarFixture();
                  await refresh();
                })
              }
            >
              Ingress Dual-SAR fixture
            </button>
            <button
              type="button"
              className="bp-btn ghost"
              disabled={busy}
              onClick={() =>
                void run("Reset", async () => {
                  await resetRuntime();
                  setFinding(null);
                  setCoa(null);
                  setRemaining(null);
                  setInterpretNote("");
                  await refresh();
                })
              }
            >
              Reset
            </button>
            <button
              type="button"
              className="bp-btn ghost"
              disabled={busy}
              onClick={() => void run("Refreshed", () => refresh().then(() => undefined))}
            >
              Refresh
            </button>
          </div>
          {interpretNote ? <p className="bp-dim">{interpretNote}</p> : null}
          {log ? <p className="bp-log">{log}</p> : null}
        </section>

        <WarningPicture
          finding={finding}
          coa={coa}
          ontologyAlert={state?.amber_alert?.alert}
        />

        <section className="bp-panel bp-gate">
          <h2>Operator gate</h2>
          {coa ? (
            <>
              <p className="bp-mono">coa_id · {coa.coa_id}</p>
              {remaining !== null ? (
                <p className="bp-countdown" aria-live="polite">
                  {remaining.toFixed(1)}s · timeout → fail-closed
                </p>
              ) : (
                <p className="bp-dim">No live countdown (already decided or not queued).</p>
              )}
              <div className="bp-actions">
                <button
                  type="button"
                  className="bp-btn approve"
                  disabled={busy || remaining === null}
                  onClick={() =>
                    void run("Approved → inbox", async () => {
                      await approve({ coa_id: coa.coa_id, decision: "y" });
                      setRemaining(null);
                      await refresh();
                    })
                  }
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="bp-btn deny"
                  disabled={busy || remaining === null}
                  onClick={() =>
                    void run("Denied", async () => {
                      await approve({ coa_id: coa.coa_id, decision: "n" });
                      setRemaining(null);
                      await refresh();
                    })
                  }
                >
                  Deny
                </button>
              </div>
              <p className="bp-dim">
                Tell Screen 2 the same unit <code>{unitId}</code>. UI never seals
                tokens — Core does on approve.
              </p>
            </>
          ) : (
            <p className="bp-dim">Queue a proposal to enable Approve / Deny.</p>
          )}
        </section>

        <EvidenceChipModal
          uris={evidenceUris}
          openUri={chipOpen}
          onOpen={setChipOpen}
          onClose={() => setChipOpen(null)}
        />

        <section className="bp-panel bp-panel-muted">
          <h2>Ontology snapshot</h2>
          <p className="bp-dim">
            scenario={state?.scenario_id ?? "—"} · tracks=
            {state?.tracks.length ?? 0} · observations=
            {state?.observations.length ?? 0} · inbox_depth=
            {state?.inbox_depth ?? 0}
          </p>
          <ul className="bp-track-list">
            {(state?.tracks ?? []).slice(0, 8).map((t) => (
              <li key={t.track_id}>
                <strong>{t.track_id}</strong>{" "}
                <span className="bp-dim">
                  {t.modalities.join("+")} · conf {t.confidence.toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </ScreenChrome>
  );
}
