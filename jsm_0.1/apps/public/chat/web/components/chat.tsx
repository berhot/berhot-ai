"use client";

import { useEffect, useRef, useState } from "react";
import {
  continuationOf,
  defaultModel,
  failureOf,
  generate,
  modelReadout,
} from "@/lib/api";
import { useStrings, type Failure } from "@/lib/i18n";
import {
  DEFAULT_SETTINGS,
  resolveMaxNewTokens,
  resolveTemperature,
  type SettingsDraft,
} from "@/lib/settings";
import { useModels } from "@/lib/use-models";
import { AboutDialog } from "./about-dialog";
import { Composer } from "./composer";
import { EmptyState } from "./empty-state";
import { InfoIcon, TrashIcon } from "./icons";
import { Specimen, UserPrompt, type ChatMessage } from "./messages";
import { ModelPicker } from "./model-picker";
import { ReadoutLine } from "./readout-line";
import { SettingsPopover } from "./settings-popover";
import { focusRing, headerControl } from "./styles";

export function Chat() {
  const t = useStrings();
  const { state: modelsState, retry } = useModels();
  // Empty until the user picks one; the latest model stands in until then.
  const [pickedId, setPickedId] = useState("");
  const [settings, setSettings] = useState<SettingsDraft>(DEFAULT_SETTINGS);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [generating, setGenerating] = useState(false);

  const nextId = useRef(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const aboutRef = useRef<HTMLDialogElement>(null);

  // Keep the newest message in view.
  useEffect(() => {
    if (messages.length > 0) {
      endRef.current?.scrollIntoView({ block: "end" });
    }
  }, [messages]);

  const models = modelsState.status === "ready" ? modelsState.models : [];
  const selected =
    models.find((model) => model.id === pickedId) ?? defaultModel(models);
  const readout = selected ? modelReadout(selected) : [];
  const canSend = draft.trim() !== "" && !generating && selected !== null;

  async function send() {
    if (!canSend || !selected) return;

    const prompt = draft;
    // Settings are resolved now, at send time, not when they were typed.
    const temperature = resolveTemperature(settings.temperature);
    const maxNewTokens = resolveMaxNewTokens(settings.maxNewTokens);
    const replyId = nextId.current + 1;
    nextId.current += 2;

    setMessages((current) => [
      ...current,
      { id: replyId - 1, role: "user", text: prompt },
      {
        id: replyId,
        role: "assistant",
        // Captured here so later picker changes never rename this reply.
        label: selected.display_name,
        temperature,
        maxNewTokens,
        status: "pending",
        text: "",
        failure: null,
      },
    ]);
    setDraft("");
    setGenerating(true);

    let outcome:
      | { status: "done"; text: string }
      | { status: "error"; failure: Failure };
    try {
      const text = await generate({
        prompt,
        model: selected.id,
        temperature,
        max_new_tokens: maxNewTokens,
      });
      outcome = { status: "done", text: continuationOf(prompt, text) };
    } catch (error) {
      outcome = { status: "error", failure: failureOf(error) };
    }

    // A reply cleared mid-flight is simply not found here.
    setMessages((current) =>
      current.map((message) =>
        message.id === replyId && message.role === "assistant"
          ? { ...message, ...outcome }
          : message,
      ),
    );
    setGenerating(false);
    textareaRef.current?.focus();
  }

  function clearChat() {
    setMessages([]);
    textareaRef.current?.focus();
  }

  function fillExample(text: string) {
    setDraft(text);
    textareaRef.current?.focus();
  }

  return (
    <div className="flex h-dvh flex-col bg-ink text-paper">
      <header className="shrink-0 border-b border-line">
        <div className="relative mx-auto w-full max-w-[60rem] px-4 pt-3 pb-2.5 sm:px-6">
          <div className="flex items-center gap-2 sm:gap-3">
            <h1 className="me-auto flex items-center gap-2.5 font-mono text-[15px] font-medium tracking-[0.22em]">
              <span aria-hidden className="h-4 w-[3px] bg-amber" />
              JSM
            </h1>

            <button
              type="button"
              onClick={() => aboutRef.current?.showModal()}
              aria-label={t.aboutJsm}
              title={t.aboutJsm}
              aria-haspopup="dialog"
              className={`${headerControl} ${focusRing}`}
            >
              <InfoIcon />
            </button>

            <button
              type="button"
              onClick={clearChat}
              disabled={messages.length === 0}
              aria-label={t.clearChat}
              className={`${headerControl} disabled:pointer-events-none disabled:opacity-40 ${focusRing}`}
            >
              <TrashIcon />
              <span className="hidden md:inline">{t.clearChat}</span>
            </button>

            <SettingsPopover
              generation={{ settings, onChange: setSettings }}
            />

            <ModelPicker
              models={models}
              selectedId={selected?.id ?? ""}
              onSelect={setPickedId}
              status={modelsState.status}
            />
          </div>

          <p
            aria-live="polite"
            className="mt-2 min-h-4 text-[11px] leading-4 text-faint tabular-nums ltr:font-mono ltr:tracking-wide rtl:text-[13px] rtl:leading-5"
          >
            {modelsState.status === "loading" && t.readingCheckpoints}
            {modelsState.status === "error" && (
              <span className="text-danger">{t.modelsUnavailable}</span>
            )}
            {modelsState.status === "ready" &&
              (selected ? <ReadoutLine readout={readout} /> : t.noModelsFound)}
          </p>
        </div>
      </header>

      <main
        aria-label={t.conversation}
        className={`min-h-0 flex-1 overflow-x-hidden overflow-y-auto focus-visible:-outline-offset-2 ${focusRing}`}
      >
        <div className="mx-auto flex min-h-full w-full max-w-[48rem] flex-col px-4 sm:px-6">
          {messages.length === 0 ? (
            <EmptyState
              state={modelsState}
              hasModel={selected !== null}
              onExample={fillExample}
              onRetry={retry}
            />
          ) : (
            <ol className="flex flex-col gap-7 pt-8 pb-10" aria-live="polite">
              {messages.map((message) => (
                <li key={message.id} className="motion-safe:animate-rise">
                  {message.role === "user" ? (
                    <UserPrompt text={message.text} />
                  ) : (
                    <Specimen message={message} />
                  )}
                </li>
              ))}
            </ol>
          )}
          <div ref={endRef} />
        </div>
      </main>

      <Composer
        textareaRef={textareaRef}
        value={draft}
        onChange={setDraft}
        onSend={send}
        canSend={canSend}
        hasModel={selected !== null}
      />

      <AboutDialog dialogRef={aboutRef} model={selected} />
    </div>
  );
}
