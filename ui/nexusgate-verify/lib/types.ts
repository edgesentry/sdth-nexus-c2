/** Frozen C2 REST shapes used by BattlePlan (see docs/api/rest.md). */

export type AmberAlert = {
  alert: string | null;
  threat_class: string;
  mismatch_m: number;
  picture_summary: string;
  source_breakdown: Record<string, unknown>;
  scenario_id: string;
};

export type Finding = {
  scenario_id: string;
  threat_class: string;
  amber_alert: string | null;
  warning_minutes_est: number;
  confidence: number;
  mismatch_m: number;
  picture_summary: string;
  adversarial_hypothesis: string;
  approach_sources: string[];
  spoof_sources: string[];
  other_sources: string[];
  source_breakdown: Record<string, unknown>;
};

export type Track = {
  track_id: string;
  latitude: number;
  longitude: number;
  speed_mps: number;
  confidence: number;
  source_ids: string[];
  modalities: string[];
  updated_at: string | null;
  attributes: Record<string, unknown>;
};

export type Observation = {
  observation_id: string;
  source_id: string;
  entity_hint: string | null;
  latitude: number;
  longitude: number;
  modality: string;
  confidence: number;
  attributes: Record<string, unknown>;
};

export type OntologyState = {
  scenario_id: string | null;
  tracks: Track[];
  observations: Observation[];
  amber_alert: AmberAlert | null;
  pending_proposals: string[];
  inbox_depth: number;
};

export type CourseOfAction = {
  coa_id: string;
  intent: string;
  target_coordinates: [number, number] | number[];
  max_speed_mps?: number;
  unit_id?: string;
  timeout_seconds?: number;
  tier?: string;
};

export type ProposalResponse = {
  status: string;
  reason?: string;
  coa: CourseOfAction;
  finding?: Finding | null;
  token?: Record<string, unknown>;
  interpretation?: Record<string, unknown>;
};

export type ApproveResponse = {
  status: string;
  reason?: string;
  coa?: CourseOfAction;
  token?: Record<string, unknown>;
  unit_id?: string;
};

export type InboxItem = {
  coa: CourseOfAction;
  token: Record<string, unknown>;
  unit_id: string;
  issued_at: string;
  status: string;
  ack?: Record<string, unknown>;
};

export type InboxResponse = {
  unit_id: string;
  count: number;
  /** Frozen contract key (docs/api/rest.md) — not `items`. */
  taskings: InboxItem[];
};

export type AckResponse = {
  status: string;
  ack: Record<string, unknown>;
  audit_hash: string;
};

export type AuditTrail = {
  count: number;
  path: string;
  records: Array<Record<string, unknown>>;
};
