import type {
  AckResponse,
  ApproveResponse,
  AuditTrail,
  InboxResponse,
  OntologyState,
  ProposalResponse,
} from "./types";

function baseUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_C2_BASE_URL?.trim() || "http://127.0.0.1:8080";
  return raw.replace(/\/$/, "");
}

function authHeaders(): HeadersInit {
  const token = process.env.NEXT_PUBLIC_C2_API_TOKEN?.trim();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function c2Fetch<T>(
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const headers: Record<string, string> = {
    ...(authHeaders() as Record<string, string>),
    ...(init?.headers as Record<string, string> | undefined),
  };
  let body = init?.body;
  if (init?.json !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  const res = await fetch(`${baseUrl()}${path}`, {
    ...init,
    headers,
    body,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const err = (await res.json()) as { detail?: string };
      if (err.detail) detail = err.detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status} ${path}: ${detail}`);
  }
  return (await res.json()) as T;
}

/** Map repo-relative fixture URIs to Core static mount. */
export function evidenceUrl(uri: string | undefined | null): string | null {
  if (!uri) return null;
  if (/^https?:\/\//i.test(uri)) return uri;
  const name = uri.replace(/^.*\//, "");
  if (!name) return null;
  return `${baseUrl()}/static/fixtures/${encodeURIComponent(name)}`;
}

export function getC2BaseUrl(): string {
  return baseUrl();
}

export function ontologyState(): Promise<OntologyState> {
  return c2Fetch("/api/ontology/state");
}

export function resetRuntime(): Promise<{ status: string }> {
  return c2Fetch("/api/admin/reset", { method: "POST" });
}

export function propose(opts: {
  scenario_id: string;
  unit_id: string;
  interpret?: boolean;
  force_heuristic?: boolean;
  timeout_seconds?: number;
}): Promise<ProposalResponse> {
  return c2Fetch("/api/gate/proposals", { method: "POST", json: opts });
}

export function approve(opts: {
  coa_id: string;
  decision: "y" | "n";
  operator_id?: string;
}): Promise<ApproveResponse> {
  return c2Fetch("/api/gate/approve", {
    method: "POST",
    json: {
      coa_id: opts.coa_id,
      decision: opts.decision,
      operator_id: opts.operator_id ?? "nexusgate-verify-screen1",
    },
  });
}

export function interpret(opts: {
  scenario_id: string;
  force_heuristic?: boolean;
}): Promise<Record<string, unknown>> {
  return c2Fetch("/api/interpret", { method: "POST", json: opts });
}

export function ingressSentinelFixture(): Promise<Record<string, unknown>> {
  return c2Fetch("/api/ingress/candidate-event", {
    method: "POST",
    json: { use_sentinel_fixture: true },
  });
}

export function ingressDualSarFixture(): Promise<Record<string, unknown>> {
  return c2Fetch("/api/ingress/candidate-event", {
    method: "POST",
    json: { dual_sar: true },
  });
}

export function inbox(unitId: string): Promise<InboxResponse> {
  return c2Fetch(
    `/api/recipient/inbox?unit_id=${encodeURIComponent(unitId)}`,
  );
}

export function ack(opts: {
  coa_id: string;
  unit_id: string;
  message?: string;
}): Promise<AckResponse> {
  return c2Fetch("/api/recipient/ack", {
    method: "POST",
    json: {
      coa_id: opts.coa_id,
      unit_id: opts.unit_id,
      status: "ACKED",
      message: opts.message ?? "nexusgate-verify-screen2",
    },
  });
}

export function auditTrail(): Promise<AuditTrail> {
  return c2Fetch("/api/audit/trail");
}

/** Collect evidence_image_uri from tracks + observations. */
export function collectEvidenceUris(state: OntologyState): string[] {
  const uris = new Set<string>();
  for (const t of state.tracks) {
    const u = t.attributes?.evidence_image_uri;
    if (typeof u === "string" && u) uris.add(u);
  }
  for (const o of state.observations) {
    const u = o.attributes?.evidence_image_uri;
    if (typeof u === "string" && u) uris.add(u);
  }
  return [...uris];
}
