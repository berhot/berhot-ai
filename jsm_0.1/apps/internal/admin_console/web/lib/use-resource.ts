"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, type ApiFailure } from "./api";

/** One API read. Each resource fails and recovers on its own. */
export type Resource<T> = {
  data: T | null;
  error: ApiFailure | null;
  /** True for the first read and for every re-read. */
  loading: boolean;
  /** When `data` was last read, in epoch milliseconds. */
  loadedAt: number | null;
  reload: () => void;
};

type State<T> = Omit<Resource<T>, "reload">;

function failureOf(error: unknown): ApiFailure {
  return error instanceof ApiError ? error.failure : { kind: "unknown" };
}

/** `fetcher` must be a stable (module-level) function. */
export function useResource<T>(fetcher: () => Promise<T>): Resource<T> {
  const [state, setState] = useState<State<T>>({
    data: null,
    error: null,
    loading: true,
    loadedAt: null,
  });
  const [attempt, setAttempt] = useState(0);

  // Runs on mount and again on each reload.
  useEffect(() => {
    let cancelled = false;
    fetcher().then(
      (data) => {
        if (cancelled) return;
        setState({ data, error: null, loading: false, loadedAt: Date.now() });
      },
      (error: unknown) => {
        if (cancelled) return;
        setState({
          data: null,
          error: failureOf(error),
          loading: false,
          loadedAt: null,
        });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [fetcher, attempt]);

  // Data already on screen stays there while it is re-read.
  const reload = useCallback(() => {
    setState((current) => ({ ...current, loading: true }));
    setAttempt((current) => current + 1);
  }, []);

  return { ...state, reload };
}
