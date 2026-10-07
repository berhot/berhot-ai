// Client for the JSM API. Paths are absolute ("/models"): `next dev`
// proxies them, and the static export is served by the API server itself.

import type { Failure } from "./i18n";

export type Model = {
  id: string;
  name: string;
  display_name: string;
  /** `/models` lists real models only; training snapshots are left out. */
  kind: "model" | "checkpoint";
  parameters: number | null;
  trainable_parameters: number | null;
  epochs: number | null;
  global_step: number | null;
  tokens_seen: number | null;
  vocab_size: number | null;
  context_length: number | null;
  latest: boolean;
};

export type GenerateRequest = {
  prompt: string;
  model: string;
  temperature: number;
  max_new_tokens: number;
};

export type ReadoutKey = "params" | "tokensSeen" | "epochs" | "context" | "vocab";
export type Readout = { key: ReadoutKey; value: string };

/** A non-2xx response. `detail` is null when the body had none. */
export class ApiError extends Error {
  constructor(
    readonly detail: string | null,
    readonly status: number,
  ) {
    super(detail ?? `Request failed (${status})`);
  }
}

/** Read FastAPI's `detail` (a string, or a list of `{ msg }`). */
async function toApiError(response: Response): Promise<ApiError> {
  let detail: string | null = null;
  try {
    const body: unknown = await response.json();
    const raw = (body as { detail?: unknown } | null)?.detail;
    if (typeof raw === "string" && raw.trim()) {
      detail = raw;
    } else if (Array.isArray(raw)) {
      const messages = raw
        .map((item) => (item as { msg?: unknown } | null)?.msg)
        .filter((msg): msg is string => typeof msg === "string" && msg !== "");
      if (messages.length > 0) detail = messages.join("; ");
    }
  } catch {
    // Body was not JSON; the status code is all we have.
  }
  return new ApiError(detail, response.status);
}

/** Reduce anything thrown by the calls below to displayable data. */
export function failureOf(error: unknown): Failure {
  if (error instanceof ApiError) {
    return { detail: error.detail, status: error.status };
  }
  const detail = error instanceof Error && error.message ? error.message : null;
  return { detail, status: null };
}

export async function fetchModels(): Promise<Model[]> {
  const response = await fetch("/models");
  if (!response.ok) throw await toApiError(response);
  const body = (await response.json()) as { models?: Model[] };
  return Array.isArray(body.models) ? body.models : [];
}

/** Returns the full text: prompt + continuation. */
export async function generate(request: GenerateRequest): Promise<string> {
  const response = await fetch("/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) throw await toApiError(response);
  const body = (await response.json()) as { text?: unknown };
  return typeof body.text === "string" ? body.text : "";
}

/** The API echoes the prompt; only the continuation is shown. */
export function continuationOf(prompt: string, text: string): string {
  return text.startsWith(prompt) ? text.slice(prompt.length) : text;
}

/** The model that is preselected: the latest, else the first. */
export function defaultModel(models: Model[]): Model | null {
  return models.find((model) => model.latest) ?? models[0] ?? null;
}

// Western digits in both languages, so readouts stay tabular.
const number = new Intl.NumberFormat("en-US");

/** Model metadata, skipping the fields an older checkpoint lacks. */
export function modelReadout(model: Model): Readout[] {
  const fields: [ReadoutKey, number | null][] = [
    ["params", model.parameters],
    ["tokensSeen", model.tokens_seen],
    ["epochs", model.epochs],
    ["context", model.context_length],
    ["vocab", model.vocab_size],
  ];
  return fields
    .filter(
      (field): field is [ReadoutKey, number] => typeof field[1] === "number",
    )
    .map(([key, value]) => ({ key, value: number.format(value) }));
}
