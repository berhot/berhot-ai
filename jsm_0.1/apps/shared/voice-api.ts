export type VoiceStatus = {
  status: "starting" | "ready" | "unavailable";
  detail: string | null;
  busy: boolean;
  asr?: string;
  tts?: string;
  device?: string;
  sample_rate_hz?: number;
  max_recording_seconds?: number;
  retained_audio: boolean;
};

export type HistoryMessage = { role: "user" | "assistant"; text: string };
export type TurnOptions = { model: string; temperature: number; max_new_tokens: number; history: HistoryMessage[] };
export type VoiceReply = { turn_id: string; transcript: string; text: string; audio: string; synthetic: boolean; voice: string; model: string; timings: Record<string, number> };
export type VoiceActivity = { id: string; at: string; model: string; status: "completed" | "error"; total_ms: number; timings?: Record<string, number> };

export async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, { cache: "no-store", ...options });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status}).`);
  }
  if (!body) throw new Error("The server returned an invalid response.");
  return body as T;
}

export const fetchVoiceStatus = () => requestJson<VoiceStatus>("/api/voice/status");
export const fetchVoiceOverview = () => requestJson<VoiceStatus>("/admin/voice/overview");
export const fetchVoiceActivity = () => requestJson<{ turns: VoiceActivity[] }>("/admin/voice/turns");

export function sendChat(prompt: string, options: TurnOptions, signal: AbortSignal) {
  return requestJson<{ text: string; model: string }>("/api/chat", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, ...options }), signal,
  });
}

export async function sendVoice(audio: Blob, options: TurnOptions, signal: AbortSignal) {
  if (audio.size > 3_000_000) throw new Error("WAV files must be smaller than 3 MB.");
  const bytes = new Uint8Array(await audio.arrayBuffer());
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 16384) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 16384));
  }
  return requestJson<VoiceReply>("/api/voice/turn", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ audio: btoa(binary), consent: true, ...options }), signal,
  });
}

export function replyAudio(encoded: string): string {
  const bytes = Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0));
  return URL.createObjectURL(new Blob([bytes], { type: "audio/wav" }));
}
