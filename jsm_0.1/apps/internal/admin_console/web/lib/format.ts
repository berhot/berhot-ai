// Formatting for readouts. Anything missing becomes an em dash, never a
// made-up zero.

export const DASH = "—";

const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** 884480 -> "884,480" */
export function formatCount(value: unknown): string {
  return isNumber(value) ? integer.format(value) : DASH;
}

/** 2.107672 -> "2.1077" */
export function formatLoss(value: unknown): string {
  return isNumber(value) ? value.toFixed(4) : DASH;
}

/** Text from the API, or a dash when it is absent or blank. */
export function formatText(value: unknown): string {
  return typeof value === "string" && value.trim() !== "" ? value : DASH;
}

/** A config value of unknown shape, shown as plainly as possible. */
export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return DASH;
  if (typeof value === "number") {
    if (!isNumber(value)) return DASH;
    return Number.isInteger(value) ? integer.format(value) : String(value);
  }
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") return value === "" ? DASH : value;
  return JSON.stringify(value);
}

function parse(iso: unknown): Date | null {
  if (typeof iso !== "string" || iso === "") return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

const pad = (value: number) => String(value).padStart(2, "0");

/** UTC ISO string -> "2026-10-05 11:25:50" in the viewer's local time. */
export function formatDateTime(iso: unknown): string {
  const date = parse(iso);
  if (!date) return formatText(iso);
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  );
}

/** Epoch milliseconds -> "11:25:50" local. */
export function formatClock(ms: number): string {
  const date = new Date(ms);
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

/** The viewer's offset at a given moment, e.g. "UTC+03:00". */
export function utcOffsetLabel(at: Date = new Date()): string {
  const minutes = -at.getTimezoneOffset();
  const sign = minutes < 0 ? "-" : "+";
  const abs = Math.abs(minutes);
  return `UTC${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}

/** Unit wording for durations, supplied by the active language. */
export type DurationWords = {
  seconds: (value: string) => string;
  minutes: (minutes: string, seconds: string) => string;
  hours: (hours: string, minutes: string) => string;
};

/** Seconds -> "16.9 s", "3m 12s", "1h 04m" (or the Arabic equivalents). */
export function formatSeconds(seconds: unknown, words: DurationWords): string {
  if (!isNumber(seconds) || seconds < 0) return DASH;
  if (seconds < 60) return words.seconds(seconds.toFixed(1));
  const whole = Math.round(seconds);
  if (whole < 3600) {
    return words.minutes(String(Math.floor(whole / 60)), pad(whole % 60));
  }
  return words.hours(
    String(Math.floor(whole / 3600)),
    pad(Math.floor((whole % 3600) / 60)),
  );
}

/** Wall-clock time between two ISO timestamps. */
export function formatDuration(
  startIso: unknown,
  endIso: unknown,
  words: DurationWords,
): string {
  const start = parse(startIso);
  const end = parse(endIso);
  if (!start || !end) return DASH;
  return formatSeconds((end.getTime() - start.getTime()) / 1000, words);
}
