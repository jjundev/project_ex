from __future__ import annotations

import json
import subprocess
import threading

class _AppState:
    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self._listeners: list[list] = []   # SSE 클라이언트별 이벤트 버퍼
        self._lock = threading.Lock()
        self._stream_done = 0

    def broadcast(self, event: dict) -> None:
        data = json.dumps(event, ensure_ascii=False)
        with self._lock:
            for buf in self._listeners:
                buf.append(data)

    def add_listener(self, buf: list) -> None:
        with self._lock:
            self._listeners.append(buf)

    def remove_listener(self, buf: list) -> None:
        with self._lock:
            if buf in self._listeners:
                self._listeners.remove(buf)

    def on_stream_done(self) -> None:
        should_notify = False
        proc = None
        with self._lock:
            self._stream_done += 1
            if self._stream_done >= 2:
                self._stream_done = 0
                proc = self.proc
                should_notify = True
        if should_notify:
            code = -1
            if proc is not None:
                wait_fn = getattr(proc, "wait", None)
                if callable(wait_fn):
                    try:
                        # poll() 대신 wait() 사용: Windows에서 파이프 EOF 직후
                        # 프로세스가 아직 완전히 종료되지 않아 poll()이 None을
                        # 반환하는 경쟁 조건을 방지한다.
                        code = wait_fn(timeout=10)
                    except subprocess.TimeoutExpired:
                        polled = proc.poll() if hasattr(proc, "poll") else None
                        code = polled if polled is not None else -1
                else:
                    polled = proc.poll() if hasattr(proc, "poll") else None
                    code = polled if polled is not None else -1
            self.broadcast({"type": "done", "code": code})
            self.broadcast({"type": "running", "value": False})
