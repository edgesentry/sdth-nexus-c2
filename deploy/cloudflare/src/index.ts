import { Container, type StopParams } from "@cloudflare/containers";

const AUDIT_STORAGE_KEY = "audit_records";

/** Shared team Bearer for Cloudflare front door (issue #38). */
type EnvWithAuth = Env & { C2_API_TOKEN?: string };

/**
 * Singleton FastAPI C2 Core. Disk is ephemeral; OCSF jsonl is snapshotted
 * into this Durable Object's SQLite so the hash chain survives sleep/restart.
 */
export class C2Container extends Container<Env> {
  defaultPort = 8080;
  sleepAfter = "30m";
  enableInternet = true;
  envVars = {
    C2_HOST: "0.0.0.0",
    C2_PORT: "8080",
    AUDIT_PATH: "/tmp/nexus-audit/gate.jsonl",
  };

  private containerHydrated = false;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.envVars = {
      ...this.envVars,
      ...optionalContainerEnv(env),
    };
  }

  override onStart(): void {
    this.containerHydrated = false;
    console.log("C2 container started");
  }

  override async onStop(_params: StopParams): Promise<void> {
    this.containerHydrated = false;
    await this.persistAudit();
    console.log("C2 container stopping; audit snapshot stored");
  }

  override onError(error: unknown): void {
    this.containerHydrated = false;
    console.error("C2 container error", error);
  }

  override async fetch(request: Request): Promise<Response> {
    await this.ctx.blockConcurrencyWhile(async () => {
      if (!this.containerHydrated) {
        await this.startAndWaitForPorts();
        await this.restoreAudit();
        this.containerHydrated = true;
      }
    });
    const response = await super.fetch(request);
    if (shouldPersistAudit(request, response)) {
      this.ctx.waitUntil(this.persistAudit());
    }
    return response;
  }

  private async persistAudit(): Promise<void> {
    try {
      const res = await this.containerFetch(new Request("http://container/api/audit/trail"));
      if (!res.ok) {
        console.error("audit persist read failed", res.status);
        return;
      }
      const body = (await res.json()) as { records?: unknown[] };
      await this.ctx.storage.put(AUDIT_STORAGE_KEY, body.records ?? []);
    } catch (err) {
      console.error("audit persist failed", err);
    }
  }

  private async restoreAudit(): Promise<void> {
    const records = await this.ctx.storage.get<unknown[]>(AUDIT_STORAGE_KEY);
    if (!records || records.length === 0) {
      return;
    }
    const res = await this.containerFetch(
      new Request("http://container/api/admin/audit/snapshot", {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ records }),
      }),
    );
    if (!res.ok) {
      console.error("audit restore failed", res.status, await res.text());
    }
  }
}

function shouldPersistAudit(request: Request, response: Response): boolean {
  const method = request.method.toUpperCase();
  if (method === "GET" || method === "HEAD" || method === "OPTIONS") {
    return false;
  }
  const path = new URL(request.url).pathname;
  if (path === "/api/admin/audit/snapshot" || path === "/health") {
    return false;
  }
  return response.ok;
}

function optionalContainerEnv(env: Env): Record<string, string> {
  const bag = env as Env & {
    LLM_BASE_URL?: string;
    LLM_API_KEY?: string;
    LLM_MODEL?: string;
  };
  const extra: Record<string, string> = {};
  if (bag.LLM_BASE_URL) extra.LLM_BASE_URL = bag.LLM_BASE_URL;
  if (bag.LLM_API_KEY) extra.LLM_API_KEY = bag.LLM_API_KEY;
  if (bag.LLM_MODEL) extra.LLM_MODEL = bag.LLM_MODEL;
  return extra;
}

/** Exported for unit-style source checks / future Vitest. */
export function pathRequiresBearer(pathname: string, method: string): boolean {
  if (method.toUpperCase() === "OPTIONS") {
    return false;
  }
  if (pathname === "/health") {
    return false;
  }
  return pathname === "/api" || pathname.startsWith("/api/");
}

export function unauthorizedResponse(): Response {
  return new Response(JSON.stringify({ detail: "Unauthorized" }), {
    status: 401,
    headers: {
      "content-type": "application/json",
      "www-authenticate": 'Bearer realm="sdth-c2-core"',
    },
  });
}

function timingSafeEqual(a: string, b: string): boolean {
  const enc = new TextEncoder();
  const ba = enc.encode(a);
  const bb = enc.encode(b);
  const len = Math.max(ba.byteLength, bb.byteLength);
  let diff = ba.byteLength ^ bb.byteLength;
  for (let i = 0; i < len; i++) {
    diff |= (ba[i] ?? 0) ^ (bb[i] ?? 0);
  }
  return diff === 0;
}

function extractBearer(request: Request): string {
  const header = request.headers.get("Authorization") ?? "";
  const match = /^Bearer\s+(\S+)/i.exec(header.trim());
  return match?.[1] ?? "";
}

/**
 * Returns a 401 Response when the request must be rejected; otherwise null.
 * If C2_API_TOKEN is unset, /api stays open (local `wrangler dev` without .dev.vars).
 */
export function authorizeRequest(request: Request, env: EnvWithAuth): Response | null {
  const url = new URL(request.url);
  if (!pathRequiresBearer(url.pathname, request.method)) {
    return null;
  }
  const expected = env.C2_API_TOKEN?.trim() ?? "";
  if (!expected) {
    console.warn("C2_API_TOKEN unset; Cloudflare /api is open (set wrangler secret for production)");
    return null;
  }
  const presented = extractBearer(request);
  if (!presented || !timingSafeEqual(presented, expected)) {
    return unauthorizedResponse();
  }
  return null;
}

function corsPreflight(request: Request): Response | null {
  if (request.method.toUpperCase() !== "OPTIONS") {
    return null;
  }
  return new Response(null, {
    status: 204,
    headers: {
      "access-control-allow-origin": request.headers.get("Origin") ?? "*",
      "access-control-allow-methods": "GET, POST, PUT, OPTIONS",
      "access-control-allow-headers": "Authorization, Content-Type",
      "access-control-max-age": "86400",
    },
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const preflight = corsPreflight(request);
    if (preflight) {
      return preflight;
    }
    const denied = authorizeRequest(request, env as EnvWithAuth);
    if (denied) {
      return denied;
    }
    const container = env.C2_CONTAINER.getByName("demo");
    return container.fetch(request);
  },
} satisfies ExportedHandler<Env>;
