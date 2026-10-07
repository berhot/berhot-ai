"use client";

import { describeFailure, useStrings, type Failure } from "@/lib/i18n";
import { eyebrow, focusRing } from "./styles";

export function ModelsLoading() {
  const t = useStrings();
  return <p className="text-[14px] text-faint">{t.readingCheckpoints}</p>;
}

export function ModelsError({
  failure,
  onRetry,
}: {
  failure: Failure;
  onRetry: () => void;
}) {
  const t = useStrings();
  return (
    <div role="alert">
      <p className={`${eyebrow} !text-danger`}>{t.couldNotLoadModels}</p>
      <p
        dir="auto"
        className="mt-1.5 text-[15px] leading-6 [overflow-wrap:anywhere] text-danger"
      >
        {describeFailure(failure, t)}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className={`mt-4 h-9 rounded-[5px] border border-line-strong px-3 text-[13px] text-paper transition-colors hover:border-amber ${focusRing}`}
      >
        {t.tryAgain}
      </button>
    </div>
  );
}

export function NoModels() {
  const t = useStrings();
  return (
    <div role="status">
      <p className="text-[17px] text-paper">{t.noModelsFound}</p>
      <p className="mt-1.5 max-w-[30rem] text-[14px] leading-6 text-muted">
        {t.noModelsHint}
      </p>
    </div>
  );
}
