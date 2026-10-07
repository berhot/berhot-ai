"use client";

import { useEffect, useState } from "react";
import { failureOf, fetchModels, type Model } from "./api";
import type { Failure } from "./i18n";

export type ModelsState =
  | { status: "loading" }
  | { status: "ready"; models: Model[] }
  | { status: "error"; failure: Failure };

/** Loads `/models` on mount, and again on each `retry()`. */
export function useModels(): { state: ModelsState; retry: () => void } {
  const [state, setState] = useState<ModelsState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchModels().then(
      (models) => {
        if (!cancelled) setState({ status: "ready", models });
      },
      (error: unknown) => {
        if (!cancelled) setState({ status: "error", failure: failureOf(error) });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const retry = () => {
    setState({ status: "loading" });
    setAttempt((current) => current + 1);
  };

  return { state, retry };
}
