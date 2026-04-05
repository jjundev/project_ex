#!/usr/bin/env python3
"""Notion 배포 스크립트.

생성된 Markdown 보고서를 Notion 페이지로 변환하여 배포한다.

Usage:
    python harness_core/notion_deploy.py \
        --file output/6주차_예비보고서.md \
        --parent-url https://www.notion.so/... \
        --token secret_...
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("✗ 'requests' 패키지가 필요합니다: pip install requests", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Notion API
# ---------------------------------------------------------------------------

_BASE           = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def create_page(token: str, parent_id: str, title: str) -> str:
    """부모 페이지 아래에 새 페이지를 생성하고 page_id를 반환한다."""
    resp = requests.post(
        f"{_BASE}/pages",
        headers=_headers(token),
        json={
            "parent": {"type": "page_id", "page_id": parent_id},
            "properties": {
                "title": {
                    "title": [{"type": "text", "text": {"content": title}}]
                }
            },
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def append_blocks(token: str, page_id: str, blocks: list[dict]) -> None:
    """페이지에 블록 목록을 추가한다."""
    resp = requests.patch(
        f"{_BASE}/blocks/{page_id}/children",
        headers=_headers(token),
        json={"children": blocks},
        timeout=30,
    )
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Markdown 파서
# ---------------------------------------------------------------------------

_INLINE_RE = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`|([^*`\n]+)")


def parse_inline(text: str) -> list[dict]:
    """인라인 마크다운(**bold**, `code`)을 Notion rich_text 배열로 변환한다."""
    parts: list[dict] = []
    for m in _INLINE_RE.finditer(text):
        if m.group(1):
            parts.append({
                "type": "text",
                "text": {"content": m.group(1)},
                "annotations": {"bold": True},
            })
        elif m.group(2):
            parts.append({
                "type": "text",
                "text": {"content": m.group(2)},
                "annotations": {"code": True},
            })
        elif m.group(3):
            parts.append({
                "type": "text",
                "text": {"content": m.group(3)},
            })
    if not parts:
        parts = [{"type": "text", "text": {"content": text}}]
    return parts


def _is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and len(s) > 2


def _is_separator_row(cells: list[str]) -> bool:
    return all(re.match(r"^:?-+:?$", c.strip()) for c in cells if c.strip())


def parse_table(lines: list[str]) -> dict | None:
    """테이블 라인 목록을 Notion table 블록으로 변환한다."""
    rows: list[list[str]] = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not _is_separator_row(cells):
            rows.append(cells)

    if not rows:
        return None

    table_width = max(len(r) for r in rows)

    notion_rows: list[dict] = []
    for row in rows:
        padded = row + [""] * (table_width - len(row))
        notion_rows.append({
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": [parse_inline(cell) for cell in padded]},
        })

    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": table_width,
            "has_column_header": True,
            "has_row_header": True,
            "children": notion_rows,
        },
    }


# ---------------------------------------------------------------------------
# Bullet list 헬퍼
# ---------------------------------------------------------------------------

def _is_bullet(line: str) -> bool:
    """라인이 bullet 항목인지 확인한다 (들여쓰기 포함)."""
    return line.lstrip().startswith("- ")


def _parse_bullet(line: str) -> tuple[int, str]:
    """bullet 라인에서 (indent_level, text)를 반환한다."""
    stripped = line.lstrip()
    indent = len(line) - len(stripped)
    return indent // 2, stripped[2:]


def _build_bullet_blocks(items: list[tuple[int, str]]) -> list[dict]:
    """(level, text) 목록을 중첩된 bulleted_list_item 블록 트리로 변환한다."""
    roots: list[dict] = []
    stack: list[tuple[int, dict]] = []  # (level, block)

    for level, text in items:
        block = {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": parse_inline(text)},
        }

        # 현재 level 이상의 항목을 스택에서 제거
        while stack and stack[-1][0] >= level:
            stack.pop()

        if stack:
            parent = stack[-1][1]
            parent["bulleted_list_item"].setdefault("children", []).append(block)
        else:
            roots.append(block)

        stack.append((level, block))

    return roots


def _para(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": parse_inline(text)},
    }


_EMPTY_BLOCK = {"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}
_HTML_COMMENT_RE = re.compile(r"^\s*<!--.*-->\s*$")


def _last_block_type(blocks: list[dict]) -> str | None:
    """마지막 블록의 타입을 반환한다."""
    return blocks[-1]["type"] if blocks else None


def _is_empty_block(block: dict) -> bool:
    return block.get("type") == "paragraph" and not block.get("paragraph", {}).get("rich_text")


def _raw_heading_level(stripped: str) -> int | None:
    """stripped된 라인의 헤딩 레벨(1~4)을 반환한다. 헤딩이 아니면 None."""
    if stripped.startswith("#### "):
        return 4
    if stripped.startswith("### "):
        return 3
    if stripped.startswith("## "):
        return 2
    if stripped.startswith("# "):
        return 1
    return None


def parse_markdown(text: str) -> list[dict]:
    """Markdown 텍스트를 Notion 블록 목록으로 변환한다."""
    blocks: list[dict] = []
    lines = text.splitlines()
    n = len(lines)

    # ── 헤딩 정규화: 구 템플릿(##섹션)과 신 템플릿(#섹션)을 자동 감지 ──────
    # 페이지 제목(첫 번째 # heading) 이후 등장하는 최소 헤딩 레벨을 찾는다.
    # 최소 레벨이 2이면(구 템플릿) shift=1을 적용해 ##→heading_1 로 올린다.
    _title_seen = False
    _min_lvl = 4
    for _line in lines:
        _s = _line.strip()
        if not _title_seen:
            if _s.startswith("# ") and not _s.startswith("## "):
                _title_seen = True
            continue
        _lvl = _raw_heading_level(_s)
        if _lvl is not None:
            _min_lvl = min(_min_lvl, _lvl)
    _shift = max(0, _min_lvl - 1)  # 구 템플릿: 1, 신 템플릿: 0

    i = 0
    title_skipped = False

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # ── 코드 블록 ───────────────────────────────────────────────────────
        if stripped.startswith("```"):
            code_lang = stripped[3:].strip()
            code_buf: list[str] = []
            i += 1
            while i < n and lines[i].rstrip() != "```":
                code_buf.append(lines[i])
                i += 1
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "language": code_lang or "plain text",
                    "rich_text": [{"type": "text", "text": {"content": "\n".join(code_buf)}}],
                },
            })
            if i < n:
                i += 1  # skip closing ```
            continue

        # ── 테이블 ─────────────────────────────────────────────────────────
        if _is_table_row(line):
            table_buf: list[str] = []
            while i < n and _is_table_row(lines[i]):
                table_buf.append(lines[i])
                i += 1
            tbl = parse_table(table_buf)
            if tbl:
                blocks.append(tbl)
            continue

        # ── HTML 주석 ──────────────────────────────────────────────────────
        if _HTML_COMMENT_RE.match(line):
            if "목차" in stripped:
                blocks.append({
                    "object": "block",
                    "type": "table_of_contents",
                    "table_of_contents": {"color": "gray"},
                })
            i += 1
            continue

        # ── 첫 번째 # Heading → 스킵 (페이지 제목으로 사용) ────────────────
        if not title_skipped and stripped.startswith("# ") and not stripped.startswith("## "):
            title_skipped = True
            i += 1
            continue

        # ── Bullet list ────────────────────────────────────────────────────
        if _is_bullet(line):
            bullet_items: list[tuple[int, str]] = []
            while i < n:
                if _is_bullet(lines[i]):
                    level, btext = _parse_bullet(lines[i])
                    bullet_items.append((level, btext))
                    i += 1
                elif lines[i].strip() == "":
                    # 빈 줄 → 뒤에 bullet이 계속되면 그룹 분리
                    j = i + 1
                    while j < n and lines[j].strip() == "":
                        j += 1
                    if j < n and _is_bullet(lines[j]):
                        blocks.extend(_build_bullet_blocks(bullet_items))
                        bullet_items = []
                        blocks.append(dict(_EMPTY_BLOCK))
                        i = j
                    else:
                        break
                else:
                    break
            if bullet_items:
                blocks.extend(_build_bullet_blocks(bullet_items))
            continue

        # ── 구분선 → Notion 배포 시 생략 ─────────────────────────────────────
        if stripped == "---":
            i += 1
            continue

        # ── 제목 (Notion은 3단계까지, _shift로 자동 정규화) ─────────────────
        _raw_lvl = _raw_heading_level(stripped)
        if _raw_lvl is not None:
            adj = max(1, min(3, _raw_lvl - _shift))   # 1~3 으로 클램프
            htype = f"heading_{adj}"
            text_body = stripped[_raw_lvl + 1:]        # "# " / "## " 등 제거
            blocks.append({
                "object": "block",
                "type": htype,
                htype: {"rich_text": parse_inline(text_body)},
            })
            i += 1
            continue

        # ── 빈 줄 → empty block ────────────────────────────────────────────
        if not stripped:
            if blocks:
                last = _last_block_type(blocks)
                # heading/divider 직후이거나 직전이 이미 empty block이면 스킵
                if last not in ("heading_1", "heading_2", "heading_3") \
                   and not _is_empty_block(blocks[-1]):
                    blocks.append(dict(_EMPTY_BLOCK))
            i += 1
            continue

        # ── 일반 단락 ──────────────────────────────────────────────────────
        blocks.append(_para(stripped))
        i += 1

    return blocks


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------

_PAGE_ID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|[0-9a-f]{32})",
    re.I,
)


def parse_page_id(url: str) -> str:
    """Notion URL 또는 페이지 ID 문자열에서 32자 hex ID를 추출한다."""
    m = _PAGE_ID_RE.search(url)
    if not m:
        raise ValueError(f"Notion page ID를 URL에서 찾을 수 없습니다: {url}")
    return m.group(1).replace("-", "")


def _chunks(blocks: list[dict], size: int = 90):
    """블록 목록을 size 단위로 나눈다. 테이블은 분리하지 않는다."""
    batch: list[dict] = []
    for block in blocks:
        batch.append(block)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


# ---------------------------------------------------------------------------
# 메인 배포 로직
# ---------------------------------------------------------------------------

def deploy(file: Path, parent_url: str, token: str) -> None:
    # 1. 페이지 ID 파싱
    try:
        parent_id = parse_page_id(parent_url)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)

    # 2. 파일 읽기
    try:
        md_text = file.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"✗ 파일을 찾을 수 없습니다: {file}", file=sys.stderr)
        sys.exit(1)

    print("[deploy:step] 파일 파싱")
    title  = _extract_title(md_text, file.stem)
    blocks = parse_markdown(md_text)
    total  = len(blocks)
    print(f"[deploy] 파일 읽기 완료: {file.name} ({total}개 블록)")

    # 3. 페이지 생성
    print("[deploy:step] 페이지 생성")
    try:
        page_id = create_page(token, parent_id, title)
    except requests.HTTPError as e:
        print(f"✗ 페이지 생성 실패 ({e.response.status_code}): {e.response.text}", file=sys.stderr)
        sys.exit(1)

    print(f"[deploy] ✓ 페이지 생성: {title}")

    # 4. 블록 업로드 (90개씩 분할)
    print("[deploy:step] 블록 업로드")
    uploaded = 0
    for chunk in _chunks(blocks):
        try:
            append_blocks(token, page_id, chunk)
        except requests.HTTPError as e:
            print(
                f"✗ 블록 업로드 실패 ({e.response.status_code}): {e.response.text}",
                file=sys.stderr,
            )
            sys.exit(1)
        uploaded += len(chunk)
        print(f"[deploy] 블록 업로드 {uploaded}/{total}")

    # 5. 완료
    print("[deploy:step] 배포 완료")
    page_url = f"https://www.notion.so/{page_id}"
    print(f"[deploy] ✓ 배포 완료 — {page_url}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    # Windows 파이프 환경에서 UTF-8 강제 (✓, — 등 비ASCII 출력 보호)
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

    ap = argparse.ArgumentParser(description="Markdown 보고서를 Notion에 배포한다")
    ap.add_argument("--file",       required=True, help="배포할 .md 파일 경로")
    ap.add_argument("--parent-url", required=True, help="Notion 상위 페이지 URL 또는 ID")
    ap.add_argument("--token",      required=True, help="Notion Internal Integration Token")
    args = ap.parse_args()

    deploy(Path(args.file), args.parent_url, args.token)


if __name__ == "__main__":
    main()
