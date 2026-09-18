"use client";

import type { CourseOfAction, Finding } from "@/lib/types";

type Props = {
  finding: Finding | null;
  coa: CourseOfAction | null;
  ontologyAlert?: string | null;
};

export function WarningPicture({ finding, coa, ontologyAlert }: Props) {
  if (!finding && !ontologyAlert) {
    return (
      <section className="bp-panel bp-panel-muted">
        <h2>Warning Picture</h2>
        <p className="bp-dim">Propose a scenario to load the amber picture.</p>
      </section>
    );
  }

  const alertLabel = finding?.amber_alert ?? ontologyAlert ?? "—";
  const breakdown = finding?.source_breakdown ?? {};
  const social = (breakdown.social ?? {}) as Record<string, unknown>;
  const radar = (breakdown.radar ?? {}) as Record<string, unknown>;

  return (
    <section className="bp-panel bp-warning" aria-live="polite">
      <div className="bp-warning-banner">
        <span>WARNING PICTURE</span>
        <span className="bp-amber">{alertLabel}</span>
      </div>
      {finding?.picture_summary ? (
        <p className="bp-summary">{finding.picture_summary}</p>
      ) : null}
      <dl className="bp-kv">
        {finding ? (
          <>
            <div>
              <dt>Scenario</dt>
              <dd>{finding.scenario_id}</dd>
            </div>
            <div>
              <dt>Threat class</dt>
              <dd>{finding.threat_class}</dd>
            </div>
            <div>
              <dt>Warning window</dt>
              <dd>~{finding.warning_minutes_est.toFixed(0)} min</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>{finding.confidence.toFixed(2)}</dd>
            </div>
            <div>
              <dt>Mismatch</dt>
              <dd>{finding.mismatch_m.toFixed(0)} m</dd>
            </div>
            {social.claimed_count != null && radar.contact_count != null ? (
              <div>
                <dt>Count claim</dt>
                <dd>
                  social={String(social.claimed_count)} vs radar=
                  {String(radar.contact_count)}
                </dd>
              </div>
            ) : null}
            <div>
              <dt>If false, collapses when</dt>
              <dd>{finding.adversarial_hypothesis}</dd>
            </div>
          </>
        ) : null}
        {coa ? (
          <div>
            <dt>Recommended COA</dt>
            <dd>
              {coa.intent} → [{coa.target_coordinates.join(", ")}]
            </dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}
