#!/usr/bin/env python3
"""기초전기실험 보고서 자동화 하네스 GUI.

로컬 웹서버를 띄운 후 브라우저를 자동으로 엽니다.
추가 설치 없이 Python 표준 라이브러리만 사용합니다.

Usage:
    python gui.py          # 기본 포트 7788
    python gui.py --port 9000
"""
from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from gui_app.constants import (
    ANSI,
    DEFAULT_PORT,
    HARNESS,
    NOTION_DEPLOY,
    NOTION_STEP_RE,
    NOTION_UPLOAD_RE,
    PHASE_ROUND_RE,
    PHASE_START_RE,
    PROJECT_DIR,
    PYTHON,
    ROLE_LABEL,
    ROLE_MODEL,
    ROLE_ORDER,
    _STEP_CLI_ARGS,
)
from gui_app.server import _ThreadingHTTPServer, _free_port
from gui_app.services import (
    check_state_payload,
    deploy_notion,
    list_reports_payload,
    preview_text,
    start_pipeline,
    stop_pipeline,
)
from gui_app.state import _AppState
from gui_app.stream_reader import read_stream
from gui_app.ui_template import _build_html

# ---------------------------------------------------------------------------
# 상태 감지 (harness_core.io_state 활용)
# ---------------------------------------------------------------------------

try:
    from harness_core.io_state import detect_pre_report_state, detect_result_report_state
    from harness_core.config import OUTPUT_DIR as _OUTPUT_DIR, MEASURED_DIR as _MEASURED_DIR

    _STATE_DETECTION_AVAILABLE = True
except ImportError:
    _STATE_DETECTION_AVAILABLE = False
    _OUTPUT_DIR = PROJECT_DIR / "output"
    _MEASURED_DIR = PROJECT_DIR / "input" / "measured"


def _get_state(mode: str) -> dict:
    """파일 상태를 감지하여 step/label/error 딕셔너리를 반환한다."""
    if not _STATE_DETECTION_AVAILABLE:
        return {"step": "p1g", "label": "상태 감지 불가 (harness_core 없음)", "error": None}
    try:
        if mode == "pre":
            return detect_pre_report_state(output_dir=_OUTPUT_DIR)
        return detect_result_report_state(output_dir=_OUTPUT_DIR, measured_dir=_MEASURED_DIR)
    except Exception as exc:
        return {"step": "p1g", "label": "상태 감지 오류", "error": str(exc)}


state = _AppState()


# ---------------------------------------------------------------------------
# HTTP 핸들러
# ---------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._html()
        elif parsed.path == "/events":
            self._sse()
        elif parsed.path == "/preview":
            self._preview(parse_qs(parsed.query))
        elif parsed.path == "/check-state":
            self._check_state(parse_qs(parsed.query))
        elif parsed.path == "/list-reports":
            self._list_reports()
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self._read_json()
        if path == "/start":
            self._start(body)
        elif path == "/stop":
            self._stop()
        elif path == "/deploy-notion":
            self._deploy_notion(body)
        else:
            self.send_error(404)

    # ── GET 핸들러 ──────────────────────────────────────────────────────────

    def _html(self) -> None:
        data = _build_html().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        buf: list[str] = []
        state.add_listener(buf)
        try:
            while True:
                if buf:
                    items = buf.copy()
                    buf.clear()
                    for item in items:
                        self.wfile.write(f"data: {item}\n\n".encode("utf-8"))
                    self.wfile.flush()
                else:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                time.sleep(0.1)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            state.remove_listener(buf)

    def _preview(self, qs: dict) -> None:
        text = preview_text(qs, get_state=_get_state, subprocess_module=subprocess)
        data = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _check_state(self, qs: dict) -> None:
        payload, code = check_state_payload(qs, get_state=_get_state)
        self._json(payload, code)

    def _list_reports(self) -> None:
        self._json(list_reports_payload(output_dir=_OUTPUT_DIR))

    # ── POST 핸들러 ─────────────────────────────────────────────────────────

    def _start(self, body: dict) -> None:
        payload, code = start_pipeline(
            body,
            state=state,
            get_state=_get_state,
            subprocess_module=subprocess,
            reader=_reader,
        )
        self._json(payload, code)

    def _stop(self) -> None:
        payload, code = stop_pipeline(state=state)
        self._json(payload, code)

    def _deploy_notion(self, body: dict) -> None:
        payload, code = deploy_notion(
            body,
            state=state,
            subprocess_module=subprocess,
            reader=_reader,
        )
        self._json(payload, code)

    # ── 공통 ────────────────────────────────────────────────────────────────

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def _json(self, data: dict, code: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args) -> None:
        pass  # 서버 로그 억제


# ---------------------------------------------------------------------------
# 스트림 리더 스레드
# ---------------------------------------------------------------------------


def _reader(stream, name: str) -> None:
    current_state = state
    read_stream(stream, name, state=current_state, on_stream_done=current_state.on_stream_done)


# ---------------------------------------------------------------------------
# 서버 실행
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="보고서 자동화 하네스 GUI")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    _free_port(args.port)

    url = f"http://localhost:{args.port}"
    server = _ThreadingHTTPServer(("", args.port), Handler)

    print(f"GUI 서버 시작: {url}")
    print("브라우저가 자동으로 열립니다. 종료하려면 Ctrl+C 를 누르세요.")

    threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버 종료.")


if __name__ == "__main__":
    main()
