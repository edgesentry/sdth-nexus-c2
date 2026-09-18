import { Container, type StopParams } from "@cloudflare/containers";

const AUDIT_STORAGE_KEY = "audit_records";

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

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const container = env.C2_CONTAINER.getByName("demo");
    return container.fetch(request);
  },
} satisfies ExportedHandler<Env>;
