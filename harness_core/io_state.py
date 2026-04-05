from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Callable

from .config import BOOK_DIR, EXPERIMENT_DIR, INPUT_DIR, NOTE_DIR, OUTPUT_DIR


def collect_docx_files(
    book_dir: Path = BOOK_DIR,
    note_dir: Path = NOTE_DIR,
    experiment_dir: Path = EXPERIMENT_DIR,
) -> dict[str, list[str]]:
    """docx/ 하위 파일 목록을 수집하여 반환한다."""
    result: dict[str, list[str]] = {"book": [], "note": [], "experiment": []}
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}

    if book_dir.exists():
        result["book"] = sorted(
            str(f) for f in book_dir.glob("*") if f.is_file() and f.suffix.lower() in image_exts
        )
    if note_dir.exists():
        result["note"] = sorted(str(f) for f in note_dir.glob("*") if f.is_file())
    if experiment_dir.exists():
        result["experiment"] = sorted(str(f) for f in experiment_dir.glob("*.txt") if f.is_file())

    return result


def _find_pre_reports(output_dir: Path = OUTPUT_DIR) -> list[str]:
    """output/ 에서 예비보고서 파일을 찾는다."""
    if not output_dir.exists():
        return []
    return sorted(str(f) for f in output_dir.glob("*예비보고서.md"))


def _find_measurements(input_dir: Path = INPUT_DIR) -> list[str]:
    """input/ 에서 측정값 파일을 찾는다."""
    if not input_dir.exists():
        return []
    return sorted(str(f) for f in input_dir.glob("*측정값.md"))


def _find_result_report_paths(output_dir: Path = OUTPUT_DIR) -> list[Path]:
    """output/ 에서 결과보고서 파일 경로를 찾는다."""
    if not output_dir.exists():
        return []
    return sorted(f for f in output_dir.glob("*결과보고서.md") if f.is_file())


def _find_result_reports(output_dir: Path = OUTPUT_DIR) -> list[str]:
    """output/ 에서 결과보고서 파일 목록을 찾는다."""
    return [str(f) for f in _find_result_report_paths(output_dir=output_dir)]


def _latest_result_report(output_dir: Path = OUTPUT_DIR) -> Path | None:
    """가장 최근에 수정된 결과보고서 파일을 반환한다."""
    paths = _find_result_report_paths(output_dir=output_dir)
    if not paths:
        return None
    return max(paths, key=lambda p: (p.stat().st_mtime, p.name))


def _has_discussion_section(report_path: Path) -> bool:
    """결과보고서에 '# 고찰' 섹션이 있는지 확인한다."""
    if not report_path.exists():
        return False
    body = report_path.read_text(encoding="utf-8", errors="ignore")
    return re.search(r"(?m)^\s*#\s*고찰\b", body) is not None


def parse_review_verdict(review_path: Path) -> str:
    """검토 파일에서 최종 판정 → PASS / FAIL / UNKNOWN 반환."""
    if not review_path.exists():
        return "UNKNOWN"
    for line in review_path.read_text(encoding="utf-8").splitlines():
        if "최종 판정" in line:
            if "FAIL" in line:
                return "FAIL"
            if "PASS" in line:
                return "PASS"
    return "UNKNOWN"


def extract_fail_items(review_path: Path) -> str:
    """검토 파일에서 판정 FAIL 줄만 추출하여 반환한다.

    '판정: FAIL' 또는 '최종 판정: FAIL' 형태의 줄만 추출한다.
    PASS 줄 주석에 'FAIL'이 언급된 위양성을 방지하기 위해 정규식을 사용한다.
    """
    if not review_path.exists():
        return ""
    lines = review_path.read_text(encoding="utf-8").splitlines()
    return "\n".join(l for l in lines if re.search(r":\s*FAIL", l))


def _reserve_archive_path(
    base_archive_path: Path,
    now: Callable[[], datetime] | None = None,
) -> Path:
    """기존 파일과 충돌하지 않는 아카이브 경로를 반환한다."""
    if not base_archive_path.exists():
        return base_archive_path

    now_fn = now or datetime.now
    stamp = now_fn().strftime("%Y%m%d_%H%M%S")
    candidate = base_archive_path.with_name(f"{base_archive_path.stem}_{stamp}{base_archive_path.suffix}")
    index = 1
    while candidate.exists():
        candidate = base_archive_path.with_name(
            f"{base_archive_path.stem}_{stamp}_{index}{base_archive_path.suffix}"
        )
        index += 1
    return candidate


def _archive_if_exists(
    src_path: Path,
    base_archive_path: Path,
    now: Callable[[], datetime] | None = None,
) -> Path | None:
    """소스 파일이 있으면 충돌 없는 경로로 아카이브한 뒤 경로를 반환한다."""
    if not src_path.exists():
        return None
    archive_path = _reserve_archive_path(base_archive_path, now=now)
    src_path.replace(archive_path)
    return archive_path

