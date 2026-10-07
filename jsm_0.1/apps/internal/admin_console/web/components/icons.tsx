// The handful of icons the console needs, drawn inline.

const base = {
  width: 14,
  height: 14,
  viewBox: "0 0 16 16",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.4,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
} as const;

type Props = { className?: string };

export function RefreshIcon({ className }: Props) {
  return (
    <svg {...base} className={className}>
      <path d="M13 8a5 5 0 1 1-1.6-3.7M13 2.5v2.6h-2.6" />
    </svg>
  );
}

/** Points along the reading direction; callers rotate it when expanded. */
export function ChevronIcon({ className }: Props) {
  return (
    <svg {...base} width={12} height={12} className={className}>
      <path d="M6 4l4 4-4 4" />
    </svg>
  );
}

/** "Leaves this app" arrow, mirrored for right-to-left. */
export function ArrowOutIcon() {
  return (
    <svg {...base} width={12} height={12} className="rtl:-scale-x-100">
      <path d="M5 11l6-6M6 5h5v5" />
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
