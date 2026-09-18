"use client";

import { evidenceUrl } from "@/lib/c2";

type Props = {
  uris: string[];
  openUri: string | null;
  onOpen: (uri: string) => void;
  onClose: () => void;
};

export function EvidenceChipModal({ uris, openUri, onOpen, onClose }: Props) {
  if (uris.length === 0) {
    return (
      <section className="bp-panel bp-panel-muted">
        <h2>Evidence chips</h2>
        <p className="bp-dim">
          No <code>evidence_image_uri</code> on current tracks. Load Sentinel
          fixture (S3 path) to preview SAR chips.
        </p>
      </section>
    );
  }

  const resolved = openUri ? evidenceUrl(openUri) : null;

  return (
    <section className="bp-panel">
      <h2>Evidence chips</h2>
      <ul className="bp-chip-list">
        {uris.map((uri) => {
          const src = evidenceUrl(uri);
          return (
            <li key={uri}>
              <button
                type="button"
                className="bp-chip-thumb"
                onClick={() => onOpen(uri)}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={src ?? undefined} alt={`Evidence ${uri}`} />
                <span>{uri.split("/").pop()}</span>
              </button>
            </li>
          );
        })}
      </ul>

      {openUri && resolved ? (
        <div
          className="bp-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Evidence chip preview"
          onClick={onClose}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
          }}
        >
          <div
            className="bp-modal"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          >
            <header className="bp-modal-head">
              <h3>HITL chip verify</h3>
              <button type="button" className="bp-btn ghost" onClick={onClose}>
                Close
              </button>
            </header>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img className="bp-modal-img" src={resolved} alt={openUri} />
            <p className="bp-dim bp-mono">{openUri}</p>
          </div>
        </div>
      ) : null}
    </section>
  );
}
