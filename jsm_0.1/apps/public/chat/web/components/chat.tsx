"use client";

import { useEffect, useRef, useState } from "react";
import {
  defaultModel,
  failureOf,
  modelReadout,
} from "@/lib/api";
import { useStrings } from "@/lib/i18n";
import { VoiceRecorder } from "@/lib/recorder";
import { fetchVoiceStatus, sendChat, sendVoice, replyAudio, type VoiceStatus, type HistoryMessage } from "../../../../shared/voice-api";
import { useVoiceStrings } from "../../../../shared/voice-strings";
import { VoiceControls } from "./voice-controls";
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
  const v = useVoiceStrings();
  const { state: modelsState, retry } = useModels();
  // Empty until the user picks one; the latest model stands in until then.
  const [pickedId, setPickedId] = useState("");
  const [settings, setSettings] = useState<SettingsDraft>(DEFAULT_SETTINGS);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [generating, setGenerating] = useState(false);
  const [mode, setMode] = useState<"text" | "voice">("text");
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus | null>(null);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const [phase, setPhase] = useState<"idle" | "permission" | "recording" | "processing">("idle");
  const recorder = useRef<VoiceRecorder | null>(null);
  const recordingAttempt = useRef(0);
  const active = useRef<AbortController | null>(null);
  const audioUrls = useRef<string[]>([]);

  const nextId = useRef(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const aboutRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const attempts = recordingAttempt;
    let mounted = true;
    async function refresh() {
      try { const status = await fetchVoiceStatus(); if (mounted) setVoiceStatus(status); }
      catch { if (mounted) setVoiceStatus(null); }
    }
    void refresh();
    const timer = setInterval(refresh, 5000);
    return () => {
      mounted = false; clearInterval(timer); attempts.current++;
      recorder.current?.close(); active.current?.abort();
      audioUrls.current.forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

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
  const canSend = draft.trim() !== "" && !generating && phase === "idle" && selected !== null;

  async function send(audio?: Blob) {
    if ((!audio && !canSend) || !selected || active.current || (audio && !consent)) return;

    const prompt = audio ? v.recorded : draft;
    // Settings are resolved now, at send time, not when they were typed.
    const temperature = resolveTemperature(settings.temperature);
    const maxNewTokens = resolveMaxNewTokens(settings.maxNewTokens);
    const history: HistoryMessage[] = messages.flatMap((message, index): HistoryMessage[] => {
      const user = messages[index - 1];
      if (message.role !== "assistant" || message.status !== "done" || user?.role !== "user") return [];
      return [{ role: "user", text: user.text.slice(0, 4000) }, { role: "assistant", text: message.text.slice(0, 4000) }];
    }).slice(-8);
    const options = { model: selected.id, temperature, max_new_tokens: Math.min(512, maxNewTokens), history };
    const controller = new AbortController();
    active.current = controller;
    document.querySelectorAll("audio").forEach((player) => player.pause());
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
    setVoiceError(null);
    if (audio) setPhase("processing");
    try {
      const voice = audio ? await sendVoice(audio, options, controller.signal) : null;
      const result = voice ?? await sendChat(prompt, options, controller.signal);
      if (active.current !== controller) return;
      const audioUrl = voice ? replyAudio(voice.audio) : undefined;
      if (audioUrl) audioUrls.current.push(audioUrl);
      setMessages((current) => current.map((message) => {
        if (message.id === replyId - 1 && voice) return { ...message, text: voice.transcript };
        if (message.id === replyId && message.role === "assistant") return {
          ...message, status: "done", text: result.text, audioUrl, latencyMs: voice?.timings.total,
        };
        return message;
      }));
    } catch (error) {
      if (active.current !== controller) return;
      setMessages((current) => current.map((message) => message.id === replyId && message.role === "assistant"
        ? { ...message, status: "error", failure: failureOf(error) } : message));
    } finally {
      if (active.current === controller) {
        active.current = null; setGenerating(false); setPhase("idle"); textareaRef.current?.focus();
        if (audio) void fetchVoiceStatus().then(setVoiceStatus).catch(() => setVoiceStatus(null));
      }
    }
  }

  function cancel() {
    recordingAttempt.current++;
    recorder.current?.close(); recorder.current = null;
    active.current?.abort(); active.current = null;
    setGenerating(false); setPhase("idle");
    setMessages((current) => current.map((message) => message.role === "assistant" && message.status === "pending"
      ? { ...message, status: "error", failure: { detail: v.stopped, status: null } } : message));
  }

  async function startRecording() {
    if (!consent || phase !== "idle" || generating) return;
    const attempt = ++recordingAttempt.current;
    setVoiceError(null); setPhase("permission");
    document.querySelectorAll("audio").forEach((player) => player.pause());
    try {
      const captured = await VoiceRecorder.start(stopRecording);
      if (attempt !== recordingAttempt.current) { captured.close(); return; }
      recorder.current = captured; setPhase("recording");
    } catch (error) {
      if (attempt !== recordingAttempt.current) return;
      setPhase("idle"); setVoiceError(error instanceof Error ? `${v.permission} ${error.message}` : v.permission);
    }
  }

  function stopRecording() {
    const captured = recorder.current;
    if (!captured) return;
    recorder.current = null;
    void send(captured.stop());
  }

  function clearChat() {
    cancel();
    audioUrls.current.forEach((url) => URL.revokeObjectURL(url)); audioUrls.current = [];
    setMessages([]);
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
        onSend={() => void send()}
        canSend={canSend}
        hasModel={selected !== null}
        disabled={phase === "recording" || phase === "permission"}
        controls={<VoiceControls mode={mode} onMode={setMode} status={voiceStatus} error={voiceError}
          phase={phase} consent={consent} onConsent={setConsent} busy={generating} hasModel={selected !== null}
          onRecord={startRecording} onStop={stopRecording} onCancel={cancel} onFile={(file) => void send(file)}
          onRefresh={() => { void fetchVoiceStatus().then(setVoiceStatus).catch((error) => setVoiceError(String(error))); }} />}
      />

      <AboutDialog dialogRef={aboutRef} model={selected} />
    </div>
  );
}
