/** Shared accent focus ring for every interactive control. */
export const focusRing =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber";

/** The page column: one measure for header, bands and footer. */
export const container = "mx-auto w-full max-w-[86rem] px-5 sm:px-8 lg:px-12";

/**
 * Small label, as on a proof sheet: tracked mono capitals for Latin,
 * plain untracked Plex Sans for Arabic (tracking breaks letter joining).
 */
export const label =
  "font-mono text-[11px] leading-4 tracking-[0.16em] text-faint uppercase ar:font-sans ar:text-[13px] ar:leading-5 ar:tracking-normal";

/** Navigation text: the same split between Latin and Arabic. */
export const navText =
  "font-mono text-[12px] tracking-[0.12em] uppercase ar:font-sans ar:text-[14px] ar:tracking-normal";

/** Quiet text link with a hairline underline. */
export const textLink = `rounded-[2px] underline decoration-line-strong decoration-1 underline-offset-[6px] transition-colors hover:text-paper hover:decoration-amber ${focusRing}`;
