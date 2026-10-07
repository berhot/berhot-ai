"use client";

import type { ModelsState } from "@/lib/use-models";
import { ModelsError, ModelsLoading, NoModels } from "./model-states";
import { useVoiceStrings } from "../../../../shared/voice-strings";

type Props = {
  state: ModelsState;
  hasModel: boolean;
  onRetry: () => void;
};

/** A nearly blank page: one line to start from. */
export function EmptyState({ state, hasModel, onRetry }: Props) {
  const v = useVoiceStrings();

  return (
    <section className="flex flex-1 flex-col justify-center py-12 motion-safe:animate-rise">
      {state.status === "loading" && <ModelsLoading />}
      {state.status === "error" && (
        <ModelsError failure={state.failure} onRetry={onRetry} />
      )}
      {state.status === "ready" && !hasModel && <NoModels />}

      {hasModel && (
        <h2 className="text-3xl font-medium leading-relaxed text-paper">{v.empty}</h2>
      )}
    </section>
  );
}
