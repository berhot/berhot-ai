"use client";

import { useStrings } from "@/lib/i18n";
import type { ModelsState } from "@/lib/use-models";
import { ModelsError, ModelsLoading, NoModels } from "./model-states";
import { focusRing } from "./styles";
import { useVoiceStrings } from "../../../../shared/voice-strings";

// Arabic first: it is what the model was mostly trained on.
const EXAMPLES = ["علي حسن", "مشروع", "Once upon a time"];

type Props = {
  state: ModelsState;
  hasModel: boolean;
  onExample: (text: string) => void;
  onRetry: () => void;
};

/** A nearly blank page: one line and a few prompts to start from. */
export function EmptyState({ state, hasModel, onExample, onRetry }: Props) {
  const t = useStrings();
  const v = useVoiceStrings();

  return (
    <section className="flex flex-1 flex-col justify-center py-12 motion-safe:animate-rise">
      {state.status === "loading" && <ModelsLoading />}
      {state.status === "error" && (
        <ModelsError failure={state.failure} onRetry={onRetry} />
      )}
      {state.status === "ready" && !hasModel && <NoModels />}

      {hasModel && (
        <>
          <h2 className="text-3xl font-medium leading-relaxed text-paper">{v.empty}</h2>
          <p className="mt-3 text-[16px] leading-7 text-muted">{v.hint}</p>
          <ul aria-label={t.examples} className="mt-4 flex flex-wrap gap-2">
            {EXAMPLES.map((example) => (
              <li key={example}>
                <button
                  type="button"
                  dir="auto"
                  onClick={() => onExample(example)}
                  className={`h-10 rounded-[5px] border border-line bg-surface px-3.5 text-[15px] text-paper transition-colors hover:border-amber/70 ${focusRing}`}
                >
                  {example}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
