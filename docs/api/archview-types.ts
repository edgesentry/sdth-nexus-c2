/**
 * ARCHVIEW ↔ NexusGate frozen REST TypeScript contract (#94).
 *
 * Hand-written to match tests/unit/test_c2_rest_contract.py `*_KEYS`.
 * OpenAPI responses are dict[str, Any] — do not generate from /openapi.json.
 *
 * Naming note:
 * - Ontology amber object uses field `alert` (contradiction class string).
 * - Finding / proposal payloads use string key `amber_alert` for the same class.
 * - Approve uses `operator_id` (not effector `unit_id`; that is set at proposals/inbox).
 *
 * Copy or import into ARCHVIEW after Core publishes this file (#95).
 */

/** GET /api/ontology/state */
export interface OntologyState {
  scenario_id: string | null;
  tracks: Track[];
  observations: Observation[];
  amber_alert: AmberAlert | null;
  pending_proposals: string[];
  inbox_depth: number;
}

export interface Track {
  track_id: string;
  latitude: number;
  longitude: number;
  speed_mps: number | null;
  confidence: number;
  source_ids: string[];
  modalities: string[];
  updated_at: string;
  attributes: Record<string, unknown>;
}

export interface Observation {
  observation_id: string;
  source_id: string;
  entity_hint: string | null;
  latitude: number;
  longitude: number;
  altitude_m: number | null;
  speed_mps: number | null;
  heading_deg: number | null;
  confidence: number;
  observed_at: string;
  modality: string;
  attributes: Record<string, unknown>;
  raw_digest: string;
}

/** Nested under ontology.amber_alert — contradiction class is `alert`. */
export interface AmberAlert {
  alert: string;
  threat_class: string;
  mismatch_m: number | null;
  picture_summary: string;
  source_breakdown: Record<string, unknown>;
  scenario_id: string | null;
}

export interface CourseOfAction {
  coa_id: string;
  tier: string;
  target_entity_id: string;
  target_coordinates: [number, number] | number[];
  intent: string;
  timeout_seconds: number;
  pre_conditions: unknown[];
  post_conditions: unknown[];
  invariants: unknown[];
  confidence: number;
  corroborating_sources: string[];
  raw_input_digest: string;
  speed_kt: number | null;
  metadata: Record<string, unknown>;
}

/**
 * Finding on proposal responses.
 * `amber_alert` here is the contradiction *class string* (not the ontology object).
 */
export interface Finding {
  amber_alert: string;
  [key: string]: unknown;
}

export interface DecisionToken {
  token_id: string;
  coa_id: string;
  verdict: string;
  issued_at: string;
  operator_id: string | null;
  reason: string;
  digest: string;
}

/** POST /api/gate/proposals — status QUEUED */
export interface ProposalQueued {
  status: "QUEUED";
  coa: CourseOfAction;
  finding: Finding;
}

/** POST /api/gate/proposals — Tier-0 auto APPROVED */
export interface ProposalApproved {
  status: "APPROVED";
  coa: CourseOfAction;
  token: DecisionToken;
  finding: Finding;
}

/** POST /api/gate/proposals — REJECTED_FAST */
export interface ProposalRejected {
  status: "REJECTED_FAST";
  reason: string;
  coa: CourseOfAction;
  token: DecisionToken;
}

export type ProposalResponse = ProposalQueued | ProposalApproved | ProposalRejected;

/** POST /api/gate/approve request body */
export interface ApproveRequest {
  coa_id: string;
  decision: "y" | "n";
  /** Human operator id — not the effector unit_id. */
  operator_id?: string;
}

/** POST /api/gate/approve response */
export interface ApproveResponse {
  status: string;
  coa: CourseOfAction;
  token: DecisionToken;
}

/** GET /api/audit/trail */
export interface AuditTrail {
  count: number;
  path: string;
  records: AuditRecord[];
}

export interface AuditRecord {
  class_name: string;
  activity_name: string;
  severity: string;
  time: string;
  metadata: Record<string, unknown>;
  prev_hash: string;
  hash: string;
}

/** GET /api/audit/health — ARCHVIEW audit pill (#93) */
export interface AuditHealth {
  verified: boolean;
  broken: number;
  count: number;
  label: string;
}

/** GET /api/recipient/inbox?unit_id= */
export interface InboxResponse {
  unit_id: string;
  taskings: Tasking[];
  count: number;
}

export interface Tasking {
  coa: CourseOfAction;
  token: DecisionToken;
  unit_id: string;
  issued_at: string;
  status: string;
}

/** POST /api/recipient/ack */
export interface AckRequest {
  coa_id: string;
  unit_id: string;
  status?: string;
  message?: string;
  telemetry?: Record<string, unknown>;
  signature?: string;
}

export interface AckResponse {
  status: string;
  ack: AckRecord;
  audit_hash: string;
}

export interface AckRecord {
  ack_id: string;
  coa_id: string;
  unit_id: string;
  status: string;
  message: string;
  telemetry: Record<string, unknown>;
  signature: string;
  token_digest: string;
  acked_at: string;
}
