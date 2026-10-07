"use client";

import { useEffect, useState } from "react";

import { fetchLatestModel, formatCount, type Model } from "@/lib/api";
import { useStrings } from "@/lib/i18n";
import { label } from "./styles";

type State =
  | { status: "loading" }
  | { status: "ready"; model: Model | null }
  | { status: "unavailable" };

/**
 * The current model, read from GET /models on mount. Every state keeps
 * the same frame so the page does not jump when the answer arrives.
 */
export function LiveModel() {
  const t = useStrings();
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetchLatestModel(controller.signal)
      .then((model) => setState({ status: "ready", model }))
      .catch(() => {
        if (!controller.signal.aborted) setState({ status: "unavailable" });
      });
    return () => controller.abort();
  }, []);

  const model = state.status === "ready" ? state.model : null;
  const figures = [
    { term: t.models.parameters, value: model?.parameters, unit: "" },
    { term: t.models.context, value: model?.context_length, unit: t.models.tokens },
    { term: t.models.vocabulary, value: model?.vocab_size, unit: t.models.tokens },
  ];

  return (
    <div
      aria-live="polite"
      aria-busy={state.status === "loading"}
      className="border-y border-line-strong"
    >
      <div className={`${label} flex items-center justify-between gap-4 py-3`}>
        <span>{t.models.current}</span>
        <span
          lang="en"
          dir="ltr"
          className="font-mono text-[11px] tracking-[0.06em] normal-case"
        >
          GET /models
        </span>
      </div>

      <div className="border-t border-line py-7">
        <p className="flex min-h-10 flex-wrap items-center gap-x-4 gap-y-2">
          {model ? (
            <>
              {/* From the API: shown as-is, in whichever script it uses. */}
              <bdi className="text-[clamp(1.6rem,3vw,2.25rem)] leading-10 font-medium tracking-[-0.015em] [overflow-wrap:anywhere]">
                {model.display_name}
              </bdi>
              <span className="flex items-center gap-2 rounded-[3px] border border-amber/60 px-2 py-1 font-mono text-[10px] leading-none tracking-[0.14em] text-amber uppercase ar:font-sans ar:text-[12px] ar:tracking-normal">
                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-amber" />
                {t.models.latest}
              </span>
            </>
          ) : (
            <span className="text-[17px] text-muted">
              {state.status === "loading" && t.models.loading}
              {state.status === "ready" && t.models.none}
              {state.status === "unavailable" && t.models.unavailable}
            </span>
          )}
        </p>

        <dl className="mt-7 grid grid-cols-1 gap-y-6 sm:grid-cols-3 sm:gap-x-8">
          {figures.map(({ term, value, unit }) => (
            <div
              key={term}
              className="flex flex-col-reverse gap-2 sm:border-s sm:border-line sm:ps-5"
            >
              <dt className={label}>
                {term}
                {unit && ` · ${unit}`}
              </dt>
              <dd
                className={`font-mono text-[clamp(1.75rem,3.4vw,2.75rem)] leading-none tabular-nums ${
                  model ? "text-paper" : "text-line-strong"
                }`}
              >
                <span dir="ltr" lang="en" className="inline-block">
                  {formatCount(value)}
                </span>
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
