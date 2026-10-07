"use client";

import type { Model } from "@/lib/api";
import { useStrings } from "@/lib/i18n";
import { ChevronIcon } from "./icons";
import { focusRing } from "./styles";

type Props = {
  models: Model[];
  selectedId: string;
  onSelect: (id: string) => void;
  status: "loading" | "ready" | "error";
};

/** Native select: full keyboard and screen-reader support for free. */
export function ModelPicker({ models, selectedId, onSelect, status }: Props) {
  const t = useStrings();
  const empty = models.length === 0;
  const isLatest = models.some(
    (model) => model.id === selectedId && model.latest,
  );
  const placeholder =
    status === "loading"
      ? t.loadingModels
      : status === "error"
        ? t.modelsUnavailable
        : t.noModelsFound;

  return (
    <div className="relative min-w-0 flex-1 sm:w-64 sm:flex-none">
      {isLatest && (
        <span
          aria-hidden
          title={t.latestModel}
          className="pointer-events-none absolute start-2.5 top-1/2 size-[6px] -translate-y-1/2 rounded-full bg-amber"
        />
      )}
      <select
        aria-label={t.model}
        value={empty ? "" : selectedId}
        onChange={(event) => onSelect(event.target.value)}
        disabled={empty}
        className={`h-9 w-full appearance-none truncate rounded-[5px] border border-line bg-surface pe-7 text-[13px] text-paper transition-colors hover:border-line-strong disabled:text-faint disabled:hover:border-line ${isLatest ? "ps-6" : "ps-2.5"} ${focusRing}`}
      >
        {empty && <option value="">{placeholder}</option>}
        {models.map((model) => (
          <option key={model.id} value={model.id}>
            {model.display_name}
            {model.latest ? ` (${t.latest})` : ""}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute end-2.5 top-1/2 -translate-y-1/2 text-faint">
        <ChevronIcon />
      </span>
    </div>
  );
}
