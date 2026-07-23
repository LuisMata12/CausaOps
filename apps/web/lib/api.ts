export type Service = {
  id: string;
  name: string;
  environment: string;
  status: string;
};

export type Deployment = {
  id: string;
  version: string;
  commit_sha: string;
  timestamp: string;
  status: string;
  changed_files: string[];
  metadata: Record<string, unknown>;
};

export type Evidence = {
  id: string;
  evidence_type: string;
  reference_id: string;
  description: string;
  timestamp: string;
  payload: Record<string, unknown>;
};

export type EvidenceBackedClaim = {
  statement: string;
  confidence: number;
  evidence_ids: string[];
};

export type DiagnosisOutput = {
  schema_version: "1.0";
  conclusion: "supported" | "insufficient_evidence";
  summary: string;
  probable_cause: EvidenceBackedClaim | null;
  alternative_causes: EvidenceBackedClaim[];
  recommended_action: {
    type: "no_action" | "continue_monitoring" | "propose_simulated_rollback";
    rationale: string;
    risk: "low" | "medium" | "high";
    evidence_ids: string[];
  };
  missing_information: string[];
  needs_human_review: true;
};

export type Diagnosis = {
  id: string;
  incident_id: string;
  provider: "groq";
  model: string;
  profile: "test" | "primary";
  status: "pending" | "completed" | "rejected" | "provider_error";
  conclusion: "supported" | "insufficient_evidence" | null;
  confidence: number | null;
  response_payload: DiagnosisOutput | null;
  cited_evidence_ids: string[];
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
};

export type Incident = {
  id: string;
  service_id: string;
  deployment_id: string | null;
  title: string;
  severity: "low" | "medium" | "high" | "critical";
  status: string;
  started_at: string;
  detected_at: string;
  resolved_at: string | null;
  event_count: number;
  summary: string;
  detection_context: {
    request_count?: number;
    error_count?: number;
    error_rate?: number;
    p95_latency_ms?: number | null;
    active_rules?: string[];
    deployment_age_minutes?: number | null;
  };
  service: Service;
  deployment: Deployment | null;
  evidence?: Evidence[];
  diagnoses?: Diagnosis[];
};

const baseUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export async function apiGet<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${baseUrl}${path}`, { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function formatUtc(value: string): string {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

export function formatDuration(start: string, end: string | null): string {
  const milliseconds = new Date(end ?? Date.now()).getTime() - new Date(start).getTime();
  const minutes = Math.max(0, Math.floor(milliseconds / 60_000));
  if (minutes < 60) return `${minutes}m`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}
