// Latin labels are mono, uppercase and tracked. None of that suits Arabic
// (tracking breaks letter joining), so every such style has an `ar:` reset.

/** Shared accent focus ring for every interactive control. */
export const focusRing =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber";

/** Label typography: mono caps in English, plain sans in Arabic. */
const caps =
  "font-mono tracking-[0.14em] uppercase ar:font-sans ar:tracking-normal";

/** Column heads, readout keys, eyebrows. */
export const label = `${caps} text-[10.5px] leading-4 font-normal text-faint ar:text-[12px]`;

/** A literal API key or path used as a label: Latin in both languages. */
export const keyLabel = "font-mono text-[11px] leading-4 font-normal text-faint";

/** Small print: notes, counts, context lines. */
export const note =
  "font-mono text-[11px] leading-5 text-faint ar:font-sans ar:text-[12.5px]";

/** Quiet bordered control (refresh, retry). */
export const quietButton = `${caps} inline-flex h-8 items-center gap-2 rounded-[4px] border border-line px-2.5 text-[11px] text-muted transition-colors hover:border-line-strong hover:text-paper disabled:pointer-events-none disabled:opacity-50 ar:text-[12.5px] ${focusRing}`;

/** Small bordered badge. */
export const badge = `${caps} inline-flex items-center gap-1.5 rounded-[3px] border px-1.5 py-px text-[10px] leading-4 ar:text-[11.5px]`;

/** Table cells. Start/end follow the reading direction. */
const cell = "px-2.5 first:ps-3 last:pe-3";
export const th = `${label} ${cell} border-b border-line-strong py-2 text-start whitespace-nowrap`;
export const thNum = `${label} ${cell} border-b border-line-strong py-2 text-end whitespace-nowrap`;
export const td = `${cell} border-b border-line py-2.5 align-top whitespace-nowrap`;
export const tdNum = `${td} text-end font-mono text-[13px] text-paper tabular-nums`;
export const tdMono = `${td} font-mono text-[12.5px] text-muted tabular-nums`;
