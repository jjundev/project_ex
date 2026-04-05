from __future__ import annotations

import re
import threading
from pathlib import Path

from .constants import HARNESS, NOTION_DEPLOY, PROJECT_DIR, PYTHON, _STEP_CLI_ARGS


def preview_text(qs: dict, *, get_state, subprocess_module) -> str:
    mode = qs.get("mode", ["pre"])[0]
    max_rounds = qs.get("rounds", ["3"])[0]
    detected = get_state(mode)
    step = detected.get("step") or "p1g"
    cli_roles = _STEP_CLI_ARGS.get(mode, _STEP_CLI_ARGS["pre"])
    cmd = [
        PYTHON,
        str(HARNESS),
        "--from",
        cli_roles["from"],
        "--to",
        cli_roles["to"],
        "--max-rounds",
        max_rounds,
        "--start-step",
        step,
        "--dry-run",
    ]
    res = subprocess_module.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_DIR))
    return res.stdout or res.stderr or "결과 없음"


def check_state_payload(qs: dict, *, get_state) -> tuple[dict, int]:
    mode = qs.get("mode", ["pre"])[0]
    if mode not in ("pre", "result"):
        return {"error": "mode must be pre or result"}, 400
    return get_state(mode), 200


def list_reports_payload(*, output_dir: Path) -> dict:
    files = []
    if output_dir.exists():
        for file in sorted(output_dir.glob("*.md")):
            if re.search(r"\d+주차.*(예비|결과)보고서\.md$", file.name):
                files.append(
                    {
                        "name": file.name,
                        "path": str(file),
                        "size": file.stat().st_size,
                    }
                )
    return {"files": files}


def start_pipeline(
    body: dict,
    *,
    state,
    get_state,
    subprocess_module,
    reader,
) -> tuple[dict, int]:
    if state.proc and state.proc.poll() is None:
        return {"error": "이미 실행 중"}, 400

    mode = body.get("mode", "pre")
    max_rounds = body.get("maxRounds", 3)

    # 최신 파일 상태 재감지
    detected = get_state(mode)
    if detected.get("error"):
        return {"error": detected["error"]}, 400

    step = detected.get("step", "p1g")
    if step == "done":
        return {"error": "이미 완성됨 — 실행할 단계가 없습니다."}, 400

    cli_roles = _STEP_CLI_ARGS.get(mode, _STEP_CLI_ARGS["pre"])
    cmd = [
        PYTHON,
        str(HARNESS),
        "--from",
        cli_roles["from"],
        "--to",
        cli_roles["to"],
        "--max-rounds",
        str(max_rounds),
        "--start-step",
        step,
    ]

    state.broadcast({"type": "clear"})
    state.broadcast({"type": "log", "text": f"$ {' '.join(cmd[2:])}\n\n", "tag": "dim"})

    state._stream_done = 0
    state.proc = subprocess_module.Popen(
        cmd,
        stdout=subprocess_module.PIPE,
        stderr=subprocess_module.PIPE,
        text=True,
        bufsize=1,
        cwd=str(PROJECT_DIR),
    )
    state.broadcast({"type": "running", "value": True})

    threading.Thread(target=reader, args=(state.proc.stdout, "out"), daemon=True).start()
    threading.Thread(target=reader, args=(state.proc.stderr, "err"), daemon=True).start()

    return {"ok": True}, 200


def stop_pipeline(*, state) -> tuple[dict, int]:
    if state.proc and state.proc.poll() is None:
        state.proc.terminate()
    return {"ok": True}, 200


def deploy_notion(
    body: dict,
    *,
    state,
    subprocess_module,
    reader,
) -> tuple[dict, int]:
    if state.proc and state.proc.poll() is None:
        return {"error": "이미 실행 중"}, 400

    file_path = body.get("file", "")
    parent_url = body.get("parentUrl", "")
    token = body.get("token", "")

    if not file_path or not parent_url or not token:
        return {"error": "file, parentUrl, token 모두 필요합니다."}, 400

    if not Path(file_path).exists():
        return {"error": f"파일을 찾을 수 없습니다: {file_path}"}, 400

    cmd = [
        PYTHON,
        str(NOTION_DEPLOY),
        "--file",
        file_path,
        "--parent-url",
        parent_url,
        "--token",
        token,
    ]

    state.broadcast({"type": "clear"})
    state.broadcast(
        {
            "type": "log",
            "text": f"$ notion_deploy --file {Path(file_path).name}\n\n",
            "tag": "dim",
        }
    )

    state._stream_done = 0
    state.proc = subprocess_module.Popen(
        cmd,
        stdout=subprocess_module.PIPE,
        stderr=subprocess_module.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
        cwd=str(PROJECT_DIR),
    )
    state.broadcast({"type": "running", "value": True})

    threading.Thread(target=reader, args=(state.proc.stdout, "out"), daemon=True).start()
    threading.Thread(target=reader, args=(state.proc.stderr, "err"), daemon=True).start()

    return {"ok": True}, 200
