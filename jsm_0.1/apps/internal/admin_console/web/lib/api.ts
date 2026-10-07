// Read-only client for the JSM API. URLs are absolute paths: `next dev`
// proxies them, and the static export is served by the API server itself.
// This console only ever issues GET requests.

export type Model = {
  id: string;
  name: string;
  display_name: string;
  parameters: number | null;
  trainable_parameters: number | null;
  epochs: number | null;
  global_step: number | null;
  tokens_seen: number | null;
  vocab_size: number | null;
  context_length: number | null;
  latest: boolean;
  /** `/models` lists real models only; training snapshots are "checkpoint". */
  kind: "model" | "checkpoint";
};

export type Health = {
  status: string;
  device: string | null;
};

export type TrainingStats = {
  epochs_completed: number | null;
  global_step: number | null;
  tokens_seen: number | null;
  training_seconds: number | null;
  final_loss: number | null;
  learning_rate: number | null;
};

export type TrainingRun = {
  run_id: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  device: string | null;
  checkpoint: string | null;
  model_config: Record<string, unknown> | null;
  training_config: Record<string, unknown> | null;
  training_stats: Partial<TrainingStats> | null;
  model_stats: Record<string, unknown> | null;
};

export type Overview = {
  status: string;
  device: string | null;
  model_count: number | null;
  latest_model: Model | null;
  training_run_count: number | null;
  latest_training_run: TrainingRun | null;
};

export type DataSummary = {
  uploads: number | null;
  upload_files: number | null;
  incoming_batches: number | null;
  inspections: number | null;
  quarantined_batches: number | null;
  provenance_decisions: number | null;
  raw_batches: number | null;
  extracted_batches: number | null;
  processed_batches: Record<string, number | null> | null;
  dataset_documents: Record<string, number | null> | null;
};

/** The endpoints this console reads, and nothing else. */
export const ENDPOINTS = {
  health: "/health",
  models: "/models",
  overview: "/admin/overview",
  runs: "/admin/training/runs",
  data: "/admin/data/summary",
} as const;

/**
 * Why a read failed. `detail` is the server's own message and is shown
 * as-is; every other kind is worded by the console in the viewer's language.
 */
export type ApiFailure =
  | { kind: "detail"; detail: string }
  | { kind: "status"; status: number }
  | { kind: "network" }
  | { kind: "notJson" }
  | { kind: "unexpected" }
  | { kind: "unknown" };

export class ApiError extends Error {
  readonly failure: ApiFailure;

  constructor(failure: ApiFailure) {
    super(failure.kind);
    this.name = "ApiError";
    this.failure = failure;
  }
}

/** Pull FastAPI's `detail` out of an error body, if it has one. */
async function failureOf(response: Response): Promise<ApiFailure> {
  try {
    const body: unknown = await response.json();
    const detail = (body as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return { kind: "detail", detail };
    }
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => (item as { msg?: unknown } | null)?.msg)
        .filter((msg): msg is string => typeof msg === "string" && msg !== "");
      if (messages.length > 0) {
        return { kind: "detail", detail: messages.join("; ") };
      }
    }
  } catch {
    // Body was not JSON; the status code is all we have.
  }
  return { kind: "status", status: response.status };
}

async function getJson(path: string): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(path, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
  } catch {
    throw new ApiError({ kind: "network" });
  }
  if (!response.ok) throw new ApiError(await failureOf(response));
  try {
    return await response.json();
  } catch {
    throw new ApiError({ kind: "notJson" });
  }
}

async function getObject<T>(path: string): Promise<T> {
  const body = await getJson(path);
  if (typeof body !== "object" || body === null || Array.isArray(body)) {
    throw new ApiError({ kind: "unexpected" });
  }
  return body as T;
}

export function fetchHealth(): Promise<Health> {
  return getObject<Health>(ENDPOINTS.health);
}

export async function fetchModels(): Promise<Model[]> {
  const body = await getObject<{ models?: unknown }>(ENDPOINTS.models);
  return Array.isArray(body.models) ? (body.models as Model[]) : [];
}

export function fetchOverview(): Promise<Overview> {
  return getObject<Overview>(ENDPOINTS.overview);
}

export async function fetchRuns(): Promise<TrainingRun[]> {
  const body = await getObject<{ runs?: unknown }>(ENDPOINTS.runs);
  return Array.isArray(body.runs) ? (body.runs as TrainingRun[]) : [];
}

export function fetchDataSummary(): Promise<DataSummary> {
  return getObject<DataSummary>(ENDPOINTS.data);
}
