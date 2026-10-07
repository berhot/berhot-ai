"use client";

import { useRef } from "react";
import type { VoiceStatus } from "../../../../shared/voice-api";
import { useVoiceStrings } from "../../../../shared/voice-strings";
import { focusRing } from "./styles";

type Props = {
  mode: "text" | "voice"; onMode: (mode: "text" | "voice") => void;
  status: VoiceStatus | null; error: string | null; phase: "idle" | "permission" | "recording" | "processing";
  consent: boolean; onConsent: (value: boolean) => void; busy: boolean; hasModel: boolean;
  onRecord: () => void; onStop: () => void; onCancel: () => void;
  onFile: (file: File) => void; onRefresh: () => void;
};

export function VoiceControls(props: Props) {
  const t = useVoiceStrings();
  const file = useRef<HTMLInputElement>(null);
  const recording = props.phase === "recording";
  const disabled = props.busy || props.phase !== "idle";
  const ready = props.status?.status === "ready" && !props.status.busy && props.hasModel && props.consent;
  const button = `rounded-full px-3 py-2 text-xs transition-colors disabled:opacity-40 ${focusRing}`;
  return <div className="mt-2 border-t border-line pt-2">
    <div className="flex flex-wrap items-center gap-2">
      <div className="me-auto flex rounded-full bg-ink p-0.5" role="group" aria-label={t.model}>
        {(["text", "voice"] as const).map((mode) => <button key={mode} type="button" disabled={disabled}
          aria-pressed={props.mode === mode} onClick={() => props.onMode(mode)}
          className={`${button} ${props.mode === mode ? "bg-raised text-paper" : "text-muted"}`}>{t[mode]}</button>)}
      </div>
      {props.busy || props.phase === "permission" ? <button type="button" onClick={props.onCancel} className={`${button} text-danger`}>{t.cancel}</button> : null}
      {props.mode === "voice" && <>
        <input ref={file} className="hidden" type="file" accept=".wav,audio/wav" onChange={(event) => {
          const selected = event.target.files?.[0]; if (selected) props.onFile(selected); event.target.value = "";
        }} />
        <button type="button" disabled={!ready || disabled} onClick={() => file.current?.click()} className={`${button} text-muted`}>{t.upload}</button>
        <button type="button" disabled={!recording && (!ready || disabled)} onClick={recording ? props.onStop : props.onRecord}
          className={`${button} flex items-center gap-2 ${recording ? "bg-danger text-white" : "bg-amber text-amber-ink"}`}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden>
            {recording ? <rect x="5" y="5" width="14" height="14" rx="2" fill="currentColor" /> : <><rect x="9" y="2" width="6" height="13" rx="3" /><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8" /></>}
          </svg>{recording ? t.stop : t.record}
        </button>
        {recording && <button type="button" onClick={props.onCancel} className={`${button} text-muted`}>{t.cancel}</button>}
      </>}
    </div>
    {props.mode === "voice" && <div className="mt-3 space-y-2 text-xs text-muted">
      <div className="flex items-center justify-between gap-2" role="status">
        <span className="flex items-center gap-2"><span className={`size-2 rounded-full ${recording ? "bg-danger animate-pulse" : props.status?.status === "ready" ? "bg-amber" : "bg-faint"}`} />
          {recording ? t.recording : props.phase === "processing" ? t.processing : props.status?.status === "ready" ? (props.status.busy ? t.busy : t.ready) : props.status?.status === "starting" ? t.starting : t.unavailable}
        </span>
        <button type="button" onClick={props.onRefresh} className={`underline ${focusRing}`}>{t.retry}</button>
      </div>
      <label className="flex items-start gap-2"><input type="checkbox" checked={props.consent} disabled={disabled}
        onChange={(event) => props.onConsent(event.target.checked)} className="mt-0.5 accent-amber" />{t.consent}</label>
      <p>{recording ? t.listeningHint : t.limits}</p>
      <p className="text-faint">{t.privacy}</p>
    </div>}
    {props.error && <p role="alert" className="mt-2 text-sm text-danger">{props.error}</p>}
  </div>;
}
