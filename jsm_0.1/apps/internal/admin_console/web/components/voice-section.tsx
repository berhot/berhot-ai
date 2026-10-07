"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchVoiceOverview, fetchVoiceActivity, type VoiceStatus, type VoiceActivity } from "../../../../shared/voice-api";
import { useVoiceStrings } from "../../../../shared/voice-strings";
import { focusRing } from "./styles";

export function VoiceSection({ activity = false }: { activity?: boolean }) {
  const t = useVoiceStrings();
  const [status, setStatus] = useState<VoiceStatus | null>(null);
  const [turns, setTurns] = useState<VoiceActivity[]>([]);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const [overview, recent] = await Promise.all([fetchVoiceOverview(), fetchVoiceActivity()]);
      if (signal?.aborted) return;
      setStatus(overview); setTurns(recent.turns); setError(null);
    } catch (cause) {
      if (!signal?.aborted) setError(cause instanceof Error ? cause.message : String(cause));
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const initial = setTimeout(() => void refresh(controller.signal), 0);
    const timer = setInterval(() => void refresh(controller.signal), 5000);
    return () => { clearTimeout(initial); clearInterval(timer); controller.abort(); };
  }, [refresh]);

  return <section>
    <header className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-line-strong pb-4">
      <h1 className="text-2xl font-medium">{activity ? t.activityTitle : t.voiceTitle}</h1>
      <div className="flex gap-4 text-sm"><button onClick={() => void refresh()} className={`text-muted underline ${focusRing}`}>{t.retry}</button>
        <a href="/chat/" className={`rounded-full bg-amber px-4 py-2 text-amber-ink ${focusRing}`}>{t.openChat}</a></div>
    </header>
    {error && <p role="alert" className="mb-4 text-danger">{error}</p>}
    {!status && !error && <p role="status">{t.loading}</p>}
    {!activity && status && <>
      <div className="mb-6 flex items-center gap-3 rounded-xl border border-line bg-surface p-5" role="status">
        <span className={`size-3 rounded-full ${status.status === "ready" ? "bg-amber" : "bg-danger"}`} />
        <div><p className="font-medium">{status.status === "ready" ? t.ready : status.status === "starting" ? t.starting : t.unavailable}</p>
          <p className="mt-1 text-sm text-muted">{status.detail ?? (status.busy ? t.busy : t.idle)}</p></div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[[t.asr, status.asr], [t.tts, status.tts], [t.device, status.device], [t.retention, t.deleted]].map(([label, value]) =>
          <div key={label} className="rounded-xl border border-line p-5"><p className="text-xs text-faint">{label}</p><p dir="auto" className="mt-3 break-words font-medium">{value ?? "—"}</p></div>)}
      </div>
      <div className="my-8 space-y-3 rounded-xl bg-surface p-5 text-sm text-muted">
        <p className="text-paper">{t.flow}</p><p>{t.selected}</p><p>{t.limits}</p><p>{t.privacy}</p>
      </div>
    </>}
    <h2 className="mb-2 text-lg font-medium">{t.recent}</h2>
    <p className="mb-4 text-sm text-faint">{t.sessionOnly}</p>
    {turns.length === 0 ? <p className="border-y border-line py-8 text-muted">{t.noTurns}</p> :
      <div className="overflow-x-auto"><table className="w-full min-w-[36rem] text-start text-sm">
        <thead><tr className="border-b border-line text-faint">{[t.time, t.model, t.status, t.latency].map((title) => <th key={title} className="p-3 text-start font-normal">{title}</th>)}</tr></thead>
        <tbody>{turns.map((turn) => <tr key={turn.id} className="border-b border-line">
          <td className="p-3"><time dateTime={turn.at}>{new Date(turn.at).toLocaleTimeString()}</time><p className="mt-1 font-mono text-[10px] text-faint">{turn.id.slice(0, 12)}</p></td>
          <td dir="auto" className="p-3">{turn.model}</td>
          <td className={`p-3 ${turn.status === "completed" ? "text-paper" : "text-danger"}`}>{turn.status === "completed" ? t.completed : t.error}</td>
          <td className="p-3 tabular-nums"><span dir="ltr">{(turn.total_ms / 1000).toFixed(2)} s</span>
            {turn.timings && <details className="mt-1 text-xs text-muted"><summary className="cursor-pointer">ASR / LLM / TTS</summary>
              <p dir="ltr" className="mt-2">{["asr", "llm", "tts"].map((key) => `${key.toUpperCase()} ${((turn.timings?.[key] ?? 0) / 1000).toFixed(2)}s`).join(" · ")}</p></details>}
          </td>
        </tr>)}</tbody>
      </table></div>}
  </section>;
}
