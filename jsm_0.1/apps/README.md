# JSM apps

Client applications. They talk to the JSM backend over its HTTP API and
contain no model, tokenizer or inference code — that all lives in `src/`.

```
apps/
├── public/                  customer-facing products
│   ├── website/web/         served at /
│   └── chat/web/            served at /chat   (ios/ and android/ come later)
├── internal/                company staff tools
│   └── admin_console/web/   served at /admin  (read-only)
└── shared/                  design tokens and Next.js config used by every web app
```

Each `web/` folder is a Next.js + Tailwind CSS app, built as a static export
(`out/`) that the API server serves. This directory is one npm workspace.

```
npm install          # once
npm run build        # build all three; restart `python -m scripts.serve` afterwards
npm run lint

npm run dev:website  # http://localhost:3000/
npm run dev:chat     # http://localhost:3001/chat/
npm run dev:admin    # http://localhost:3012/admin/
```

The dev servers proxy API calls to `http://127.0.0.1:8000`
(override with `JSM_API_URL`), so keep `python -m scripts.serve` running.

## Text and voice chat

`/chat/` uses the real checkpoints returned by `/models`. The model picker selects
the JSM checkpoint for both text and voice replies. Text requests go through
`POST /api/chat` with up to eight previous messages. The rounded composer supports
Enter to send, Shift+Enter for a newline, recording, and mono PCM16 WAV upload.

Choose **JSM Voice**, confirm recording permission, then record and press **Stop
and send**. The server runs local Whisper → selected JSM checkpoint → local Piper.
The transcript and a playable synthetic response appear in the conversation.
Browser recording is limited to 30 seconds; WAV uploads must be 0.2–30 seconds,
mono PCM16, 8–48 kHz, and under 3 MB. Microphone access requires localhost or HTTPS.
Typing still sends a text turn in either mode. This is turn-based voice, not token
streaming or an always-listening browser conversation.

`/admin/#voice` displays actual speech model readiness, device, and retention.
`/admin/#voice-activity` displays the last 100 voice requests, outcome, selected
checkpoint, and processing times. Activity is in memory for the current server
session and contains no audio or transcript. Both pages refresh every five seconds.

## Run the integrated server

Prepare the sibling `jsm-voice` environment and download its models once using
the commands in [JSM Voice's README](../../jsm-voice/README.md). Then build these
apps and run `python -m scripts.serve` from `jsm_0.1`. The server starts one persistent
worker with `jsm-voice/.venv` automatically; speech models load once. No separate
public voice port or second manual server is needed. Text remains available if
speech dependencies or weights are missing; voice status explains the failure.

The worker communicates with the text server through private process pipes,
avoiding the projects' conflicting `src` package names. It does not make an HTTP
loop back into an authenticated server. A file lock prevents multiple servers
from sharing and deleting each other's voice jobs. Run one API process per voice
workspace. Busy inference returns 429 instead of building an unbounded queue.

| Environment variable | Purpose |
| --- | --- |
| `JSM_PORT` | API port, default `8000`; the server binds to `127.0.0.1` |
| `JSM_VOICE_ROOT` | Override the sibling voice project directory |
| `JSM_VOICE_PYTHON` | Override its Python executable |
| `JSM_ENV=production` | Refuse startup without operator and admin passwords of at least 16 characters |
| `JSM_ACCESS_USERNAME` | Basic-auth operator name, default `operator` |
| `JSM_ACCESS_PASSWORD` | Protect chat, API, and static assets |
| `JSM_ADMIN_PASSWORD` | Admin credential; also permits normal operator requests |
| `JSM_ALLOWED_HOSTS` | Comma-separated accepted hostnames; defaults to loopback names |
| `JSM_ALLOWED_ORIGINS` | Explicit browser origins for a TLS reverse proxy or separate development origin |

For an operator deployment, set production mode and supply credentials through
the process environment or a secret manager. Put the loopback server behind an
HTTPS reverse proxy and configure its public hostname and origin. Do not forward
untrusted clients to an unauthenticated loopback configuration. Basic auth supplies
operator/admin access, not individual customer accounts or tenant isolation.
Local development permits loopback requests without credentials. Non-loopback
peers are refused when credentials are absent. Cross-origin writes and oversized
request bodies are rejected; no permissive CORS is installed.

## Audio privacy and recovery

Web requests own isolated temporary folders under `jsm-voice/storage/web-jobs/`.
Source audio, standardized audio, segments, manifests, generated speech, and turn
results are deleted together after success or ordinary processing failure. The
response sends audio bytes directly to the requesting browser, with no public
artifact URL. The browser holds conversation data and audio in memory until clear
or reload. A process crash can leave a temporary folder; the next worker startup
removes abandoned jobs after acquiring exclusive ownership. Do not treat Git
exclusion as protection from OneDrive or other filesystem synchronization.

Recording cancellation closes browser tracks without uploading. Cancelling an
already submitted turn discards its response; native inference may finish before
its temporary files are deleted. The worker protocol has a 120-second response
deadline, but a native text generation call in the host is not forcibly preempted.
Use a process supervisor and resource limits for unattended operation. Worker
startup failures appear in `jsm-voice/artifacts/logs/web-worker.log`. A stopped or
timed-out worker requires restarting the API.

The current tiny JSM checkpoints are experimental text models. Wiring them to a
chat interface does not make them instruction-tuned or establish response quality.
Piper's selected voice is Jordanian Arabic. The interface labels generated speech.

## Verification

From `jsm_0.1`, install `requirements-dev.txt` and run `python -m pytest tests`.
Run the existing speech suite separately from `jsm-voice`. From `apps`, run:

```powershell
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser tests use a running integrated server (`JSM_TEST_URL`, default
`http://127.0.0.1:8000`) and real models. Set `JSM_TEST_WAV` to a consented speech
WAV for upload/microphone tests; the local default is the existing `speech_001.wav`.
Chromium uses that WAV as an automated microphone fixture. API and speech inference
are real. Permission-denial tests simulate a browser refusal. Screenshots and
traces stay in ignored `apps/test-results/`.

Verification on 2026-10-07 passed 20 API tests, 132 speech tests, seven browser
tests, all three production builds, and workspace lint. The live tests ran against
the published 2,000-token JSM checkpoint after the concurrent training run saved
it. Keep each deployed checkpoint paired with its training tokenizer; replacing
only the tokenizer can make existing checkpoints unusable until matching weights
are published. Do not use active training artifacts as immutable releases.

`npm audit --omit=dev` reported no production dependency findings. The full audit
still reports five high-severity entries in the development lint dependency chain
(`eslint-config-next` → `fast-glob` → `micromatch` → `braces`). The suggested automatic
fix downgrades Next's lint configuration across a major version, so it was not
applied to this integration. This remains development-tool maintenance.
