// Client for the JSM API. URLs are relative: `next dev` proxies them,
// and the static export is served by the API server itself.
//
// The website only ever reads GET /models. It must never call /generate:
// opening the site must not load a model.

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
};

/** The model marked `latest`, or null when none is published. */
export async function fetchLatestModel(
  signal?: AbortSignal,
): Promise<Model | null> {
  const response = await fetch("/models", { signal });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  const body = (await response.json()) as { models?: unknown } | null;
  const models = Array.isArray(body?.models) ? (body.models as Model[]) : [];
  return models.find((model) => model?.latest === true) ?? null;
}

const number = new Intl.NumberFormat("en-US");

/** `884,480`, or an em dash when the checkpoint did not record the field. */
export function formatCount(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value)
    ? number.format(value)
    : "—";
}
