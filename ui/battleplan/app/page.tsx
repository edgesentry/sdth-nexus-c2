import Link from "next/link";

import { ScreenChrome } from "@/components/ScreenChrome";
import { getC2BaseUrl } from "@/lib/c2";

export default function HubPage() {
  return (
    <ScreenChrome role="hub" status={`Core ${getC2BaseUrl()}`}>
      <section className="bp-hero">
        <p className="bp-kicker">Phase 3 · frozen REST</p>
        <h1>BattlePlan</h1>
        <p className="bp-lede">
          Two-screen Picture→Tasking over the same C2 paths as curl / TUI.
          Screen 1 proposes and approves; Screen 2 acks. Core alone seals
          DecisionTokens.
        </p>
        <div className="bp-actions">
          <Link className="bp-btn" href="/command">
            Open Screen 1 · Command
          </Link>
          <Link className="bp-btn ghost" href="/recipient">
            Open Screen 2 · Recipient
          </Link>
        </div>
        <ol className="bp-steps">
          <li>
            Start Core: <code>uv run sdth-c2-server</code>
          </li>
          <li>
            Run UI: <code>cd ui/battleplan && npm run dev</code>
          </li>
          <li>Propose S2 on Screen 1 → Approve → Ack on Screen 2</li>
        </ol>
      </section>
    </ScreenChrome>
  );
}
