# JSM Voice

JSM Voice is a local modular Arabic voice assistant foundation. It reads or records audio, standardizes it, detects speech, transcribes Arabic, calls the existing JSM text API, and synthesizes a response WAV. The current tiny JSM checkpoint validates the pipeline but does not produce dependable conversation. The Piper voice is Jordanian Arabic, not a claimed Saudi voice.

The JSM web apps now integrate this pipeline at `/chat/`, with voice operations at
`/admin/#voice` and `/admin/#voice-activity`. The text API owns a persistent private
`scripts.web_worker` process using this environment. Web turns use isolated,
temporary artifact directories and delete them after processing. See the
[integrated apps guide](../jsm_0.1/apps/README.md) for startup, access controls,
browser recording, deployment boundaries, and tests. The CLI behavior below is
unchanged.

## Setup

Run commands from `jsm-voice` with its Python environment active. This implementation was validated with Python 3.14 on Windows.

```powershell
python -m pip install -r requirements-dev.txt
python -m scripts.download_asr_model
python -m scripts.download_tts_model
```

The download commands fetch model weights into ignored `artifacts/` directories. ASR and TTS inference run locally. The JSM text API must already be running: from the sibling `jsm_0.1` project and its environment, run `python -m scripts.serve`. Its model manager owns checkpoint loading and caching.

## Commands

```powershell
python -m scripts.inspect_audio storage/uploads/speech_001.wav
python -m scripts.standardize_audio storage/uploads/speech_001.wav
python -m scripts.segment_audio storage/uploads/speech_001.wav
python -m scripts.build_voice_manifest storage/uploads/speech_001.wav
python -m scripts.transcribe_audio storage/uploads/speech_001.wav
python -m scripts.respond_audio storage/uploads/speech_001.wav
python -m scripts.synthesize_audio "مرحبا بك"
python -m scripts.voice_turn storage/uploads/speech_001.wav
python -m scripts.voice_chat --list-devices
python -m scripts.voice_chat --consent
python -m scripts.detect_utterance --consent
python -m scripts.voice_chat --consent --streaming
python -m scripts.voice_chat --consent --streaming --barge-in
python -m pytest
```

`python3 -m pytest` is equivalent where `python3` selects the project environment. Tests use mocks only inside `tests/` and do not need model downloads, a running JSM server, or physical audio devices.

The default sequential chat records eight seconds after Enter and stops after at most twenty turns. `--seconds` and `--max-turns` override those limits. Ctrl+C closes audio streams. Streaming waits for sustained speech and ends after silence or the configured duration cap. Barge-in needs headphones because acoustic echo cancellation is not implemented; the microphone may otherwise detect the assistant's own speakers.

## Own voice

The project trains its own voice from recordings, with its own code: a letter-based text frontend, an acoustic model that learns its own letter-to-sound alignment, and Griffin-Lim waveform synthesis. No external voice model, phonemizer, aligner, or vocoder is involved. The voice sounds like whoever recorded the corpus, so a Saudi voice needs a Saudi speaker.

```powershell
python -m scripts.record_voice_corpus --speaker faris --consent
python -m scripts.train_voice --speaker faris --minutes 120
```

`record_voice_corpus` shows one sentence at a time from `data/voice_prompts/saudi.txt` (800 Saudi sentences, about an hour of speech, taken from the Apache-2.0 dataset `VohoAI/voho-saudi-dialogues`). It records at 22,050 Hz, rejects takes that are clipped, too quiet, or too short, and keeps progress between sessions in `storage/voice_corpus/<speaker>/`. Record only a speaker who has agreed to it; `--consent` records that statement in `speaker.json`.

`train_voice` writes `artifacts/models/tts/jsm-saudi.pt` and continues from where it stopped when run again. To speak with it, set `"backend": "jsm"` and `"voice": "jsm-saudi"` in `configs/tts.json`. Twenty recordings are the minimum to train at all; a clear voice needs several hundred and a few hours of training. Griffin-Lim gives an understandable but slightly metallic sound; a trained vocoder is the next step for a natural one.

Until an own voice is trained, the default backend is Piper's `ar_JO-kareem-medium`, a third-party Jordanian voice. Whisper speech recognition is also a third-party model.

Every backend speaks through `src/tts/prosody.py`, which belongs to this project: it speaks one sentence at a time, sets the pause after each by its punctuation, splits a long unpunctuated reply at a joining word, and adds a quiet generated breath after about five seconds of speech. `"natural_pauses": false` turns this off for Piper. Piper's `noise_scale` and `noise_w_scale` control how much its pitch and timing vary.

## Configuration

`configs/voice.json` references typed audio, VAD, ASR, LLM, TTS, device, streaming, and privacy settings, plus runtime paths. `voice_turn` and `voice_chat` accept `--config` for this bundle. Component CLIs retain their component config options.

Component config references resolve relative to the bundle file. Runtime paths resolve relative to the project root. The full pipeline validates 16 kHz mono PCM16 ASR input and separate output directories. Standalone standardization supports other configured rates. Piper uses its voice's native sample rate; the selected voice produces 22,050 Hz audio.

## Runtime data

| Location | Responsibility |
| --- | --- |
| `storage/uploads/` | Original files, never overwritten by processing |
| `storage/recordings/` | Temporary microphone WAVs and consent receipts |
| `storage/standardized/` | Derived mono PCM16 WAVs |
| `storage/segments/` | Timestamped segment WAVs and segmentation JSON |
| `storage/manifests/` | Source traceability, annotations, and ASR transcripts |
| `storage/generated/` | Synthetic response WAVs and text/voice metadata |
| `storage/turns/` | Voice-turn results and interactive timing records |
| `artifacts/models/` | Downloaded ASR and TTS weights |
| `artifacts/logs/voice.jsonl` | Structured operational events without transcript text |

Runtime data and weights are excluded from Git. The real recording is not a committed test fixture. Source IDs use SHA-256. Segment identities include the processing configuration and standardized artifact identity. Integer sample positions are authoritative; end positions are exclusive. Timestamps refer to the start of standardized audio.

## Model and timing behavior

ASR and TTS models load once per service instance and are reused for chat turns. The existing JSM server caches its model independently. Single CLI invocations naturally load fresh local model instances. ASR supports CPU int8 and configurable CUDA, with a CPU fallback. The default TTS configuration uses CPU.

Whisper converts the waveform into acoustic features, encodes a speech representation, and decodes text tokens. The JSM text BPE tokenizer receives the resulting transcript later; it does not decode PCM or serve as an audio tokenizer.

One monotonic timing utility records capture, standardization, VAD, ASR, LLM, TTS, playback startup, playback, and overall interaction durations. A shared turn ID connects nested stage events. Processing latency excludes initial model loading and playback; interactive metadata includes capture and playback separately. Native model work is cooperatively cancelled between stages, while speaker playback checks cancellation between short blocks.

## Privacy and trust boundaries

Microphone commands require `--consent` by default. This is an operator assertion, not identity verification or proof that everyone nearby consented. Receipts record consent time, source type, unknown rights, retention expiry, and a null speaker identifier. Corpus annotations preserve those fields without inferring personal identity, language variety, or dialect from keywords.

With `delete_temporary_recordings=true`, full chat turns delete their receipted microphone source WAV after processing, including processing failures. Receipts remain as deletion records. Uploads are not deleted. The diagnostic `detect_utterance` command retains its output for inspection. Retention expiry is metadata: there is no automatic expiry sweeper for derived WAVs, transcripts, results, or diagnostic recordings yet.

Configured runtime roots are checked before production recording/output flows. General low-level file APIs are for trusted application callers. Source files, configs, receipts, and checkpoints are local trust boundaries; a process with write access to these files can change them. The application is designed for one local operator and does not provide authentication, tenant isolation, encryption at rest, or defenses against a hostile local filesystem actor.

Whisper and Piper do not upload recordings or text during inference. Model downloads explicitly contact package/model hosts. The JSM adapter permits loopback endpoints by default, bypasses environment proxies, and rejects redirects. Enabling `allow_remote` explicitly allows transcript/history transfer to the configured endpoint. The current workspace is under OneDrive, whose synchronization is outside the application's control; ignored Git files can still be synchronized by OneDrive.

Transcripts and generated text remain in local manifests and result JSON. Logs omit transcript content. Generated speech is marked synthetic. A voice is trained only from a corpus recorded with `record_voice_corpus` under the speaker's stated consent; speaker biometric identification is not implemented. Dependencies and each voice model's dataset/license terms require review before redistribution or deployment.

## Current limits

The pipeline is functional, but conversation quality depends on the tiny JSM checkpoint. VAD boundaries and ASR accuracy require evaluation on consented Saudi speech; backend labels are not a dialect-quality guarantee. Audio is currently processed in memory. Barge-in has no echo cancellation, and CPU cancellation does not preempt a running native inference call. Concurrent writers, multi-user access, corpus-wide expiry deletion, packaged installation, and immutable model release IDs remain deployment work.

The architecture keeps waveform processing, speech models, devices, and application orchestration separate. A future native audio-token model can be added as another pipeline; it is not implemented here.
