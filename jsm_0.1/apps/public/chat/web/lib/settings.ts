// Generation settings are kept as the raw text the user typed and only
// turned into numbers when a request is sent.

export const TEMPERATURE = { min: 0, max: 2, step: 0.1, fallback: 0 };
export const MAX_NEW_TOKENS = { min: 1, max: 512, step: 1, fallback: 80 };

export type SettingsDraft = { temperature: string; maxNewTokens: string };

export const DEFAULT_SETTINGS: SettingsDraft = {
  temperature: TEMPERATURE.fallback.toFixed(1),
  maxNewTokens: String(MAX_NEW_TOKENS.fallback),
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Empty or non-numeric input falls back to the default. */
function parse(raw: string, fallback: number): number {
  const value = raw.trim() === "" ? NaN : Number(raw);
  return Number.isFinite(value) ? value : fallback;
}

export function resolveTemperature(raw: string): number {
  const value = parse(raw, TEMPERATURE.fallback);
  return clamp(value, TEMPERATURE.min, TEMPERATURE.max);
}

export function resolveMaxNewTokens(raw: string): number {
  const value = Math.trunc(parse(raw, MAX_NEW_TOKENS.fallback));
  return clamp(value, MAX_NEW_TOKENS.min, MAX_NEW_TOKENS.max);
}

export function formatTemperature(value: number): string {
  return Number.isInteger(value * 10) ? value.toFixed(1) : String(value);
}
