"use client";

import { describeFailure, useStrings, type Failure } from "@/lib/i18n";
import { formatTemperature } from "@/lib/settings";
import { eyebrow } from "./styles";

export type ChatMessage =
  | { id: number; role: "user"; text: string }
  | {
      id: number;
      role: "assistant";
      /** Model display name, frozen when the prompt was sent. */
      label: string;
      /** The settings the request was sent with. */
      temperature: number;
      maxNewTokens: number;
      status: "pending" | "done" | "error";
      /** The continuation, once `status` is "done". */
      text: string;
      /** Why it failed, once `status` is "error". */
      failure: Failure | null;
    };

// Model output is unpredictable: keep its whitespace, never let it overflow.
const rawText = "whitespace-pre-wrap [overflow-wrap:anywhere]";

/** The user's prompt: compact, quiet, pushed to the end edge. */
export function UserPrompt({ text }: { text: string }) {
  const t = useStrings();
  return (
    <div className="flex justify-end ps-10 sm:ps-24">
      <div className="max-w-full min-w-0 rounded-[6px] border border-line bg-surface px-3.5 py-2">
        <span className="sr-only">{t.promptPrefix}</span>
        <p dir="auto" className={`text-[15px] leading-7 text-muted ${rawText}`}>
          {text}
        </p>
      </div>
    </div>
  );
}

/** The model's reply, laid out as a specimen under examination. */
export function Specimen({
  message,
}: {
  message: Extract<ChatMessage, { role: "assistant" }>;
}) {
  const t = useStrings();
  const { status, text } = message;
  const isError = status === "error";

  return (
    <article
      className={`relative border-s ps-4 sm:ps-6 ${isError ? "border-danger/50" : "border-line-strong"}`}
    >
      {/* Margin marker: where the reading starts. */}
      <span
        aria-hidden
        className={`absolute top-[5px] -start-[3px] size-[5px] ${isError ? "bg-danger" : "bg-amber"}`}
      />

      <header className="flex items-center gap-3 text-[11px] leading-4 text-faint">
        {/* The model label stays LTR whatever the page direction. */}
        <span
          dir="ltr"
          className="min-w-0 truncate font-mono tracking-[0.08em] text-muted uppercase"
        >
          JSM<span className="mx-1.5 text-faint">·</span>
          {message.label}
        </span>
        <span aria-hidden className="h-px min-w-4 flex-1 bg-line" />
        <span className="shrink-0 tabular-nums ltr:font-mono ltr:tracking-[0.08em] ltr:uppercase rtl:text-[13px]">
          {t.conditions(
            formatTemperature(message.temperature),
            message.maxNewTokens,
          )}
        </span>
      </header>

      <div className="pt-3 pb-1">
        {status === "pending" && (
          <p className="flex items-center gap-2.5 text-[14px] text-muted">
            <span
              aria-hidden
              className="h-[1.1em] w-[7px] bg-amber motion-safe:animate-caret"
            />
            {t.generating}
          </p>
        )}

        {status === "done" &&
          (text === "" ? (
            <p>
              <span
                dir="ltr"
                title={t.eosTitle}
                className="inline-block rounded-[3px] border border-line-strong px-1.5 py-0.5 font-mono text-[12px] tracking-wide text-faint"
              >
                [EOS]
              </span>
            </p>
          ) : (
            <p
              dir="auto"
              className={`text-[1.3rem] leading-[2.05] text-paper sm:text-[1.45rem] ${rawText}`}
            >
              {text}
            </p>
          ))}

        {isError && message.failure && (
          <div role="alert">
            <p className={`${eyebrow} !text-danger`}>{t.error}</p>
            <p
              dir="auto"
              className={`mt-1 text-[15px] leading-7 text-danger ${rawText}`}
            >
              {describeFailure(message.failure, t)}
            </p>
          </div>
        )}
      </div>
    </article>
  );
}
