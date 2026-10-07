/** Shared accent focus ring for every interactive control. */
export const focusRing =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber";

/**
 * Small label: tracked mono capitals in English, plain Plex Arabic in
 * Arabic (letter-spacing breaks the joins between Arabic letters).
 */
export const eyebrow =
  "text-[11px] text-faint ltr:font-mono ltr:tracking-[0.12em] ltr:uppercase rtl:text-[13px]";

/** Bordered header control, as a button or a link. */
export const headerControl =
  "flex h-9 shrink-0 items-center gap-2 rounded-[5px] border border-line px-2.5 text-[13px] text-muted transition-colors hover:border-line-strong hover:text-paper";
