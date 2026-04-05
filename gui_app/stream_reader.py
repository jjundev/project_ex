from __future__ import annotations

from .constants import ANSI, NOTION_STEP_RE, NOTION_UPLOAD_RE, PHASE_ROUND_RE, PHASE_START_RE, ROLE_ORDER


def read_stream(stream, name: str, *, state, on_stream_done=None) -> None:
    try:
        for line in stream:
            clean = ANSI.sub("", line.rstrip("\n"))
            if not clean:
                continue

            # Notion 배포 단계 마커 → phase_start 이벤트만 emit, 로그에는 출력 안 함
            ms = NOTION_STEP_RE.search(clean)
            if ms:
                state.broadcast({"type": "phase_start", "title": ms.group(1)})
                continue

            is_err = name == "err"
            if is_err or ("✗" in clean or ("FAIL" in clean and "[harness]" in clean)):
                tag = "error"
            elif "── Phase" in clean and "라운드" in clean:
                tag = "gan"
            elif "[harness]" in clean or "[deploy]" in clean:
                tag = "info"
            else:
                tag = "default"

            state.broadcast({"type": "log", "text": clean + "\n", "tag": tag})

            # Notion 블록 업로드 진행률 → notion_upload 이벤트
            mu = NOTION_UPLOAD_RE.search(clean)
            if mu:
                state.broadcast({
                    "type": "notion_upload",
                    "uploaded": int(mu.group(1)),
                    "total": int(mu.group(2)),
                })

            for role in ROLE_ORDER:
                if f"▶ {role} 시작" in clean:
                    state.broadcast({"type": "stage", "role": role, "state": "active"})
                elif f"✓ {role} 완료" in clean:
                    state.broadcast({"type": "stage", "role": role, "state": "done"})
                elif f"✗ {role} 실패" in clean:
                    state.broadcast({"type": "stage", "role": role, "state": "failed"})

            m = PHASE_START_RE.search(clean)
            if m:
                state.broadcast({
                    "type": "phase_start",
                    "title": f"{m.group(1)}: {m.group(2)}",
                })

            m = PHASE_ROUND_RE.search(clean)
            if m:
                state.broadcast({
                    "type": "phase_round",
                    "phase": int(m.group(1)),
                    "round": int(m.group(2)),
                    "maxRounds": int(m.group(3)),
                })
    finally:
        if on_stream_done is not None:
            on_stream_done()
