from __future__ import annotations

import io
import json
import threading
import time
import urllib.request
from urllib.error import HTTPError

import pytest

import gui


def _wait_until(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def _request(
    base_url: str,
    path: str,
    method: str = "GET",
    payload: dict | None = None,
) -> tuple[int, dict, str]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return resp.status, dict(resp.headers.items()), body
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        return e.code, dict(e.headers.items()), body


def _cleanup_proc(proc) -> None:
    if proc is None:
        return
    try:
        running = proc.poll() is None
    except Exception:
        running = False

    if running and hasattr(proc, "terminate"):
        try:
            proc.terminate()
        except Exception:
            pass

    if hasattr(proc, "kill"):
        try:
            proc.kill()
        except Exception:
            pass

    if hasattr(proc, "wait"):
        try:
            proc.wait(timeout=1)
        except Exception:
            pass


@pytest.fixture
def gui_server(monkeypatch):
    app_state = gui._AppState()
    monkeypatch.setattr(gui, "state", app_state)

    server = gui._ThreadingHTTPServer(("127.0.0.1", 0), gui.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield base_url, app_state
    finally:
        _cleanup_proc(app_state.proc)
        app_state.proc = None
        app_state._listeners.clear()
        app_state._stream_done = 0
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class _RunningProc:
    def __init__(self) -> None:
        self.terminated = False

    def poll(self):
        return None

    def terminate(self) -> None:
        self.terminated = True


class _FakePopenProc:
    def __init__(self) -> None:
        self.stdout = io.StringIO(
            "\033[36m[harness]\033[0m ▶ pre-generator 시작\n"
            "\033[36m[harness]\033[0m ── Phase 1: 실험 목적·준비물·이론 ──\n"
            "\033[36m[harness]\033[0m ── Phase 1 라운드 1/2 ──\n"
            "\033[36m[harness]\033[0m ✓ pre-generator 완료 (1s, turns=1, cost=$0.0000)\n"
        )
        self.stderr = io.StringIO("")
        self._returncode = 0
        self.terminated = False

    def poll(self):
        return -15 if self.terminated else self._returncode

    def terminate(self) -> None:
        self.terminated = True


def test_root_page_served(gui_server) -> None:
    base_url, _ = gui_server

    status, headers, body = _request(base_url, "/")

    assert status == 200
    assert "text/html" in headers.get("Content-Type", "")
    assert "보고서 자동화 하네스" in body
    assert "실행하기" in body
    assert "중단" in body
    assert "미리보기" in body


def test_preview_runs_harness_dry_run(gui_server, monkeypatch) -> None:
    base_url, _ = gui_server
    # 파일 시스템에 예비보고서가 없으면 step=p1g → 처음부터 실행
    monkeypatch.setattr(gui, "_STATE_DETECTION_AVAILABLE", False)

    status, headers, body = _request(
        base_url,
        "/preview?mode=pre&rounds=2",
    )

    assert status == 200
    assert "text/plain" in headers.get("Content-Type", "")
    assert "실행 경로: pre-generator → pre-reviewer" in body
    assert "예비보고서 2단계: Phase 1 (이론) + Phase 2 (예상 결과 값)" in body
    assert "최대 GAN 라운드 (Phase당): 2" in body


def test_start_rejects_when_already_running(gui_server) -> None:
    base_url, app_state = gui_server
    app_state.proc = _RunningProc()

    status, _headers, body = _request(
        base_url,
        "/start",
        method="POST",
        payload={"mode": "pre", "maxRounds": 1},
    )

    assert status == 400
    assert "이미 실행 중" in body


def test_start_emits_expected_events_with_mocked_popen(gui_server, monkeypatch) -> None:
    base_url, app_state = gui_server
    fake_proc = _FakePopenProc()

    def _fake_popen(*args, **kwargs):
        return fake_proc

    monkeypatch.setattr(gui.subprocess, "Popen", _fake_popen)
    # 파일 시스템 접근 없이 step=p1g 반환하도록 설정
    monkeypatch.setattr(gui, "_STATE_DETECTION_AVAILABLE", False)

    listener: list[str] = []
    app_state.add_listener(listener)
    try:
        status, _headers, body = _request(
            base_url,
            "/start",
            method="POST",
            payload={"mode": "pre", "maxRounds": 2},
        )
        assert status == 200
        assert '"ok": true' in body.lower()

        assert _wait_until(
            lambda: any(json.loads(raw).get("type") == "done" for raw in list(listener)),
            timeout=3,
        )

        events = [json.loads(raw) for raw in listener]

        assert any(e.get("type") == "clear" for e in events)
        assert any(
            e.get("type") == "log" and e.get("tag") == "dim" and "--from pre-generator" in e.get("text", "")
            for e in events
        )
        assert any(e.get("type") == "running" and e.get("value") is True for e in events)
        assert any(
            e.get("type") == "stage"
            and e.get("role") == "pre-generator"
            and e.get("state") == "active"
            for e in events
        )
        assert any(
            e.get("type") == "stage"
            and e.get("role") == "pre-generator"
            and e.get("state") == "done"
            for e in events
        )
        assert any(e.get("type") == "phase_start" and "Phase 1" in e.get("title", "") for e in events)
        assert any(
            e.get("type") == "phase_round"
            and e.get("phase") == 1
            and e.get("round") == 1
            and e.get("maxRounds") == 2
            for e in events
        )
        assert any(e.get("type") == "done" and e.get("code") == 0 for e in events)
        assert any(e.get("type") == "running" and e.get("value") is False for e in events)
    finally:
        app_state.remove_listener(listener)


def test_stop_terminates_running_process(gui_server) -> None:
    base_url, app_state = gui_server
    proc = _RunningProc()
    app_state.proc = proc

    status, _headers, body = _request(base_url, "/stop", method="POST", payload={})

    assert status == 200
    assert '"ok": true' in body.lower()
    assert proc.terminated is True


def test_reader_parses_log_tags_and_events(monkeypatch) -> None:
    app_state = gui._AppState()
    monkeypatch.setattr(gui, "state", app_state)

    listener: list[str] = []
    app_state.add_listener(listener)
    try:
        sample = io.StringIO(
            "\033[36m[harness]\033[0m ▶ pre-generator 시작\n"
            "\033[36m[harness]\033[0m ── Phase 1: 실험 목적·준비물·이론 ──\n"
            "\033[36m[harness]\033[0m ── Phase 1 라운드 2/3 ──\n"
            "\033[36m[harness]\033[0m ✓ pre-generator 완료 (1s, turns=1, cost=$0.0000)\n"
            "\033[31m[harness]\033[0m ✗ pre-reviewer 실패 (1s) — FAIL\n"
            "plain output line\n"
        )

        gui._reader(sample, "out")

        events = [json.loads(raw) for raw in listener]
        log_events = [e for e in events if e.get("type") == "log"]
        tags = {e.get("tag") for e in log_events}

        assert {"info", "gan", "error", "default"} <= tags
        assert any(
            e.get("type") == "stage"
            and e.get("role") == "pre-generator"
            and e.get("state") == "active"
            for e in events
        )
        assert any(
            e.get("type") == "stage"
            and e.get("role") == "pre-generator"
            and e.get("state") == "done"
            for e in events
        )
        assert any(
            e.get("type") == "stage"
            and e.get("role") == "pre-reviewer"
            and e.get("state") == "failed"
            for e in events
        )
        assert any(
            e.get("type") == "phase_start" and e.get("title") == "Phase 1: 실험 목적·준비물·이론"
            for e in events
        )
        assert any(
            e.get("type") == "phase_round"
            and e.get("phase") == 1
            and e.get("round") == 2
            and e.get("maxRounds") == 3
            for e in events
        )
    finally:
        app_state.remove_listener(listener)

