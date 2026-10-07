"use client";

import type { Readout } from "@/lib/api";
import { useStrings } from "@/lib/i18n";

/** `884,480 params · 5,418 tokens seen · …` on one wrapping line. */
export function ReadoutLine({ readout }: { readout: Readout[] }) {
  const t = useStrings();
  if (readout.length === 0) return <>{t.noMetadata}</>;

  return (
    <span className="flex flex-wrap gap-x-2">
      {readout.map(({ key, value }, index) => (
        <span key={key} className="whitespace-nowrap">
          {t.readoutInline[key](value)}
          {index < readout.length - 1 && <span className="ms-2">·</span>}
        </span>
      ))}
    </span>
  );
}
