// The handful of icons the page needs, drawn inline.

const base = {
  width: 16,
  height: 16,
  viewBox: "0 0 16 16",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.4,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
} as const;

export function TrashIcon() {
  return (
    <svg {...base}>
      <path d="M2.5 4.5h11M6.5 4.5v-2h3v2M4 4.5l.6 9h6.8l.6-9M6.6 7v4M9.4 7v4" />
    </svg>
  );
}

export function SlidersIcon() {
  return (
    <svg {...base}>
      <path d="M2 4.5h6M11.5 4.5H14M2 11.5h2.5M8 11.5h6" />
      <circle cx="9.75" cy="4.5" r="1.75" />
      <circle cx="6.25" cy="11.5" r="1.75" />
    </svg>
  );
}

export function ChevronIcon() {
  return (
    <svg {...base} width={12} height={12}>
      <path d="M4 6.5l4 4 4-4" />
    </svg>
  );
}

export function SendIcon() {
  return (
    <svg {...base} strokeWidth={1.6}>
      <path d="M8 13V3M3.5 7.5L8 3l4.5 4.5" />
    </svg>
  );
}

export function InfoIcon() {
  return (
    <svg {...base}>
      <circle cx="8" cy="8" r="5.75" />
      <path d="M8 7.25v3.5M8 5.2v.1" />
    </svg>
  );
}

export function CloseIcon() {
  return (
    <svg {...base}>
      <path d="M4 4l8 8M12 4l-8 8" />
    </svg>
  );
}
