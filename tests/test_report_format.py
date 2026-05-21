"""보고서 markdown 표 무결성 회귀 테스트.

11주차 Table 7.7 사례: 헤더 셀 안에 `\\|θ_T\\| = \\|θ_1\\| + \\|θ_2\\|` 처럼
escape 된 vertical bar 가 들어가면 Notion·일부 GFM 렌더러가 escape 를 무시하고
컬럼 분리자로 처리해 표가 9 컬럼으로 쪼개진다. 이 테스트는 reviewer LLM 의 Step 0a
무결성 체크가 누락되더라도 깨진 표가 output/ 에 잔존하지 않도록 결정론적으로 막는다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"


def _iter_tables(text: str) -> list[list[str]]:
    """markdown 본문에서 표(연속된 `|...|` 라인)를 추출하여 라인 리스트로 반환."""
    tables: list[list[str]] = []
    current: list[str] = []
    in_code_block = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            if current:
                tables.append(current)
                current = []
            continue
        if in_code_block:
            continue
        is_table_row = line.lstrip().startswith("|") and line.rstrip().endswith("|")
        if is_table_row:
            current.append(line)
        else:
            if current:
                tables.append(current)
                current = []
    if current:
        tables.append(current)
    return tables


def _cell_count(row: str) -> int:
    """표 한 행에서 (이스케이프되지 않은) `|` 갯수로 셀 수를 센다.

    셀 수 = (raw `|` 갯수) − 1. `\\|` escape 는 셀 안의 잘못된 문자로 간주하여
    파이프로 *세지 않는다* — 그 자체가 별도 violation 으로 잡힌다.
    """
    # \| escape 는 일단 마스킹해서 raw pipe 갯수에서 제외
    masked = row.replace(r"\|", "\x00")
    pipes = masked.count("|")
    return pipes - 1


def _markdown_files() -> list[Path]:
    if not OUTPUT_DIR.exists():
        return []
    return sorted(p for p in OUTPUT_DIR.glob("*.md") if p.is_file())


@pytest.mark.parametrize("md_path", _markdown_files(), ids=lambda p: p.name)
def test_markdown_tables_have_consistent_column_count(md_path: Path) -> None:
    """output/*.md 내 모든 markdown 표의 헤더·구분자·본문 셀 수가 일치해야 한다."""
    text = md_path.read_text(encoding="utf-8")
    for tbl in _iter_tables(text):
        if len(tbl) < 2:
            continue  # 표가 아닌 단일 `| ... |` 라인은 스킵
        header_cells = _cell_count(tbl[0])
        for i, row in enumerate(tbl):
            row_cells = _cell_count(row)
            assert row_cells == header_cells, (
                f"{md_path.name}: 표 셀 수 불일치 — 헤더 {header_cells} vs "
                f"row {i} {row_cells}\n  header: {tbl[0]!r}\n  row: {row!r}"
            )


@pytest.mark.parametrize("md_path", _markdown_files(), ids=lambda p: p.name)
def test_markdown_tables_have_no_escaped_pipes(md_path: Path) -> None:
    """output/*.md 내 markdown 표 안에 `\\|` escape 가 등장하면 FAIL.

    Notion·일부 GFM 렌더러가 escape 를 무시해 셀 구조를 깨뜨림.
    """
    text = md_path.read_text(encoding="utf-8")
    for tbl in _iter_tables(text):
        for i, row in enumerate(tbl):
            assert r"\|" not in row, (
                f"{md_path.name}: 표 셀 안에 \\| escape 검출 — row {i}: {row!r}. "
                "헤더에서 vertical bar 를 제거하고 수식은 표 외부 bullet 으로 옮기세요."
            )


@pytest.mark.parametrize("md_path", _markdown_files(), ids=lambda p: p.name)
def test_markdown_tables_have_no_html_breaks(md_path: Path) -> None:
    """output/*.md 내 markdown 표 셀에 `<br>` 사용 금지."""
    text = md_path.read_text(encoding="utf-8")
    pat = re.compile(r"<br\s*/?>", re.IGNORECASE)
    for tbl in _iter_tables(text):
        for i, row in enumerate(tbl):
            assert not pat.search(row), (
                f"{md_path.name}: 표 셀 안에 <br> 검출 — row {i}: {row!r}. "
                "여러 줄 설명은 표 위·아래 bullet 으로 분리하세요."
            )
