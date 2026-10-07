/** Browser microphone -> bounded mono PCM16 WAV. No third-party speech service. */
export class VoiceRecorder {
  private chunks: Float32Array[] = [];
  private frames = 0;
  private closed = false;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private node: AudioWorkletNode | undefined;

  private constructor(private stream: MediaStream, private context: AudioContext) {}

  static async start(onLimit: () => void): Promise<VoiceRecorder> {
    if (!navigator.mediaDevices?.getUserMedia || !window.isSecureContext) {
      throw new Error("Microphone access requires localhost or HTTPS.");
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: {
      channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true,
    } });
    let context: AudioContext | undefined;
    try {
      context = new AudioContext({ sampleRate: 16000 });
      await context.audioWorklet.addModule("/chat/pcm-recorder.js");
      await context.resume();
      const recorder = new VoiceRecorder(stream, context);
      const node = new AudioWorkletNode(context, "pcm-recorder");
      recorder.node = node;
      node.port.onmessage = ({ data }: MessageEvent<Float32Array>) => {
        if (recorder.closed) return;
        const remaining = context!.sampleRate * 30 - recorder.frames;
        const chunk = data.slice(0, Math.max(0, remaining));
        recorder.chunks.push(chunk);
        recorder.frames += chunk.length;
        if (remaining <= data.length) onLimit();
      };
      // A zero-gain output keeps the graph running without microphone feedback.
      const silent = context.createGain();
      silent.gain.value = 0;
      context.createMediaStreamSource(stream).connect(node).connect(silent).connect(context.destination);
      recorder.timer = setTimeout(onLimit, 30000);
      return recorder;
    } catch (error) {
      stream.getTracks().forEach((track) => track.stop());
      await context?.close();
      throw error;
    }
  }

  stop(): Blob {
    const rate = this.context.sampleRate;
    this.close();
    const bytes = new ArrayBuffer(44 + this.frames * 2);
    const view = new DataView(bytes);
    const word = (at: number, text: string) => [...text].forEach((c, i) => view.setUint8(at + i, c.charCodeAt(0)));
    word(0, "RIFF"); view.setUint32(4, bytes.byteLength - 8, true); word(8, "WAVE");
    word(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
    view.setUint16(22, 1, true); view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true);
    view.setUint16(32, 2, true); view.setUint16(34, 16, true); word(36, "data");
    view.setUint32(40, this.frames * 2, true);
    let offset = 44;
    for (const chunk of this.chunks) for (const sample of chunk) {
      const bounded = Math.max(-1, Math.min(1, sample));
      view.setInt16(offset, Math.round(bounded * (bounded < 0 ? 32768 : 32767)), true);
      offset += 2;
    }
    this.chunks = [];
    return new Blob([bytes], { type: "audio/wav" });
  }

  close() {
    if (this.closed) return;
    this.closed = true;
    clearTimeout(this.timer);
    this.node?.disconnect();
    this.node?.port.close();
    this.stream.getTracks().forEach((track) => track.stop());
    void this.context.close();
  }
}
