"""One bounded, persistent speech worker, isolated from the text Python package."""

from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
from time import monotonic
from uuid import uuid4

from fastapi import HTTPException


class VoiceRuntime:
    def __init__(self):
        self.root = Path(os.environ.get("JSM_VOICE_ROOT", Path(__file__).resolve().parents[3] / "jsm-voice")).resolve()
        default_python = self.root / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
        self.python = Path(os.environ.get("JSM_VOICE_PYTHON", default_python))
        self.process = None
        self.lock = threading.Lock()
        self.state = "starting"
        self.detail = None
        self.metadata = {}
        self.events = deque(maxlen=100)
        self.responses = queue.Queue()
        self.stopping = False

    def start(self):
        threading.Thread(target=self._start, daemon=True, name="voice-startup").start()

    def _start(self):
        try:
            logs = self.root / "artifacts/logs"
            logs.mkdir(parents=True, exist_ok=True)
            with (logs / "web-worker.log").open("a", encoding="utf-8") as log:
                self.process = subprocess.Popen(
                    [str(self.python), "-B", "-m", "scripts.web_worker"], cwd=self.root,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                    text=True, encoding="utf-8", bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            if self.stopping:
                self.close()
                return
            threading.Thread(target=self._read, daemon=True, name="voice-protocol").start()
            ready = self.responses.get(timeout=120)
            if ready.get("event") != "ready":
                raise RuntimeError("Worker did not become ready.")
            self.metadata = {key: value for key, value in ready.items() if key != "event"}
            self.state = "ready"
        except Exception:
            self.state = "unavailable"
            self.detail = "Voice worker unavailable. Check its environment, downloaded models, and artifacts/logs/web-worker.log."
            self._terminate()

    def _read(self):
        try:
            for line in self.process.stdout:
                self.responses.put(json.loads(line))
        except (ValueError, OSError):
            pass
        finally:
            self.responses.put({"event": "exit"})

    def _send(self, document):
        self.process.stdin.write(json.dumps(document, ensure_ascii=True) + "\n")
        self.process.stdin.flush()

    def status(self):
        if self.process is not None and self.process.poll() is not None:
            self.state = "unavailable"
        return {"status": self.state, "detail": self.detail, **self.metadata,
                "busy": self.lock.locked(), "retained_audio": False}

    def recent(self):
        return {"turns": list(self.events), "limit": 100, "persistent": False}

    def turn(self, request, generate_reply):
        if self.status()["status"] != "ready":
            raise HTTPException(503, self.detail or "Voice models are still loading. Try again shortly.")
        if not self.lock.acquire(blocking=False):
            raise HTTPException(429, "Voice is processing another turn. Please try again shortly.", headers={"Retry-After": "3"})
        started = monotonic()
        record = {"id": uuid4().hex, "at": datetime.now(timezone.utc).isoformat(),
                  "model": request.model, "status": "error"}
        try:
            self._send(request.model_dump())
            deadline = monotonic() + 120
            while True:
                event = self.responses.get(timeout=max(0.01, deadline - monotonic()))
                if event["event"] == "generate":
                    try:
                        response = generate_reply(event["transcript"], request)
                    except HTTPException as error:
                        self._send({"error": str(error.detail)})
                        # Consume the worker's terminal response before reuse.
                        self.responses.get(timeout=10)
                        raise
                    self._send(response)
                elif event["event"] == "result":
                    record.update(status="completed", timings=event["timings"], id=event["turn_id"])
                    return {**event, "model": request.model}
                elif event["event"] == "error":
                    raise HTTPException(422 if event.get("error_type") == "ValueError" else 502, event["detail"])
                else:
                    raise RuntimeError("Voice worker exited.")
        except HTTPException:
            raise
        except (queue.Empty, OSError, RuntimeError, KeyError):
            self.state = "unavailable"
            self.detail = "Voice worker stopped or timed out. Restart the API to recover."
            self._terminate()
            raise HTTPException(504, self.detail)
        finally:
            record["total_ms"] = round((monotonic() - started) * 1000, 1)
            self.events.appendleft(record)
            self.lock.release()

    def _terminate(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def close(self):
        self.stopping = True
        self._terminate()
