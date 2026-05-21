from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Callable

from .config import (
    BOOK_DIR,
    EXERCISE_DIR,
    MEASURED_DIR,
    NOTE_DIR,
    OUTPUT_DIR,
    REPORT_SECTIONS,
    STT_DIR,
)


def _has_exercise_section(report_path: Path) -> bool:
    """결과보고서에 '# 연습 문제' 섹션이 있는지 확인한다."""
    if not report_path.exists():
        return False
    body = report_path.read_text(encoding="utf-8", errors="ignore")
    return re.search(r"(?m)^\s*#\s*연습 문제\b", body) is not None


def _exercise_files_present(exercise_dir: Path = EXERCISE_DIR) -> bool:
    """input/exercise/에 처리 가능한 파일이 하나라도 있는지 확인한다."""
    if not exercise_dir.exists():
        return False
    allowed = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".pdf", ".md", ".txt"}
    for f in exercise_dir.glob("*"):
        if f.is_file() and f.suffix.lower() in allowed:
            return True
    return False


def _has_expected_values_section(report_path: Path) -> bool:
    """예비보고서에 '## 예상 결과 값' 섹션이 있는지 확인한다."""
    if not report_path.exists():
        return False
    body = report_path.read_text(encoding="utf-8", errors="ignore")
    return re.search(r"(?m)^\s*##\s*예상 결과 값\b", body) is not None


def detect_pre_report_state(output_dir: Path = OUTPUT_DIR) -> dict:
    """예비보고서 파이프라인 현재 상태를 감지한다.

    Returns:
        dict with keys:
          - step: "p1g" | "p1r" | "p2g" | "p2r" | "done"
          - label: 한국어 설명
          - error: None (예비보고서는 차단 조건 없음)
    """
    pre_reports = _find_pre_reports(output_dir=output_dir)

    if not pre_reports:
        return {"step": "p1g", "label": "처음부터 시작 (예비보고서 없음)", "error": None}

    latest_pre = Path(sorted(pre_reports)[-1])

    if _has_expected_values_section(latest_pre):
        # Phase 2 내용 이미 생성됨 → Phase 1 review 여부 무관, Phase 2 review 상태만 확인
        calc_review = output_dir / "pre_review.md"
        if not calc_review.exists():
            return {"step": "p2r", "label": "Phase 2 검토 시작 (예상 결과 값 생성 완료)", "error": None}
        calc_verdict = parse_review_verdict(calc_review)
        if calc_verdict == "FAIL":
            return {"step": "p2g", "label": "Phase 2 재생성 필요 (KVL/KCL 검토 FAIL)", "error": None}
        if calc_verdict == "PASS":
            return {"step": "done", "label": "예비보고서 완성됨", "error": None}
        return {"step": "p2g", "label": "Phase 2 상태 불명확 → Phase 2부터 재시작", "error": None}

    # Phase 2 미생성 → Phase 1 review 상태 확인
    theory_review = output_dir / "pre_review_theory.md"
    if not theory_review.exists():
        return {"step": "p1r", "label": "Phase 1 검토 시작 (이론 섹션 생성 완료)", "error": None}

    theory_verdict = parse_review_verdict(theory_review)
    if theory_verdict == "FAIL":
        return {"step": "p1g", "label": "Phase 1 재생성 필요 (이론 검토 FAIL)", "error": None}

    return {"step": "p2g", "label": "Phase 2 생성 시작 (예상 결과 값 미생성)", "error": None}


def detect_result_report_state(
    output_dir: Path = OUTPUT_DIR,
    measured_dir: Path = MEASURED_DIR,
    exercise_dir: Path = EXERCISE_DIR,
) -> dict:
    """결과보고서 파이프라인 현재 상태를 감지한다 (3-phase).

    Phase 1 = 실험 결과 (result_review_data.md)
    Phase 2 = 연습 문제 (result_review_exercise.md), input/exercise/ 비면 skip
    Phase 3 = 고찰 (result_review.md)

    Returns:
        dict with keys:
          - step: "p1g" | "p1r" | "p2g" | "p2r" | "p3g" | "p3r" | "done" | None (차단 시)
          - label: 한국어 설명
          - error: None | str  — None이 아니면 실행 불가
    """
    pre_reports = _find_pre_reports(output_dir=output_dir)
    if not pre_reports:
        return {
            "step": None,
            "label": "",
            "error": "예비보고서가 없습니다. 먼저 예비보고서 모드를 완료하세요.",
        }

    pre_review_path = output_dir / "pre_review.md"
    if parse_review_verdict(pre_review_path) != "PASS":
        return {
            "step": None,
            "label": "",
            "error": "예비보고서가 완성되지 않았습니다 (pre_review.md PASS 필요).",
        }

    measurements = _find_measurements(measured_dir=measured_dir)
    if not measurements:
        return {
            "step": None,
            "label": "",
            "error": f"측정값 파일이 없습니다. {measured_dir}/ 에 *측정값.md 를 추가하세요.",
        }

    result_reports = _find_result_report_paths(output_dir=output_dir)
    if not result_reports:
        return {"step": "p1g", "label": "처음부터 시작 (결과보고서 없음)", "error": None}

    # ── Phase 1 (실험 결과) ──
    data_review = output_dir / "result_review_data.md"
    if not data_review.exists():
        return {"step": "p1r", "label": "Phase 1 검토 시작 (실험 결과 생성 완료)", "error": None}

    data_verdict = parse_review_verdict(data_review)
    if data_verdict == "FAIL":
        return {"step": "p1g", "label": "Phase 1 재생성 필요 (실험 결과 검토 FAIL)", "error": None}

    # Phase 1 PASS → Phase 2 (연습 문제) 분기
    latest_result = max(result_reports, key=lambda p: (p.stat().st_mtime, p.name))
    has_exercise_input = _exercise_files_present(exercise_dir=exercise_dir)
    has_exercise_section = _has_exercise_section(latest_result)

    if has_exercise_input or has_exercise_section:
        # Phase 2 활성 — 자료가 있거나 이미 작성된 섹션이 있음
        if not has_exercise_section:
            return {"step": "p2g", "label": "Phase 2 생성 시작 (연습 문제 섹션 미생성)", "error": None}

        exercise_review = output_dir / "result_review_exercise.md"
        if not exercise_review.exists():
            return {"step": "p2r", "label": "Phase 2 검토 시작 (연습 문제 생성 완료)", "error": None}

        exercise_verdict = parse_review_verdict(exercise_review)
        if exercise_verdict == "FAIL":
            return {"step": "p2g", "label": "Phase 2 재생성 필요 (연습 문제 검토 FAIL)", "error": None}
        if exercise_verdict == "UNKNOWN":
            return {"step": "p2g", "label": "Phase 2 상태 불명확 → Phase 2부터 재시작", "error": None}
        # exercise_verdict == "PASS" → fall through to Phase 3
    # Phase 2 자료 없고 섹션도 없음 → exercise-skip 경로로 Phase 3 직진

    # ── Phase 3 (고찰) ──
    if not _has_discussion_section(latest_result):
        return {"step": "p3g", "label": "Phase 3 생성 시작 (고찰 섹션 미생성)", "error": None}

    result_review = output_dir / "result_review.md"
    if not result_review.exists():
        return {"step": "p3r", "label": "Phase 3 검토 시작 (고찰 생성 완료)", "error": None}

    result_verdict = parse_review_verdict(result_review)
    if result_verdict == "FAIL":
        return {"step": "p3g", "label": "Phase 3 재생성 필요 (고찰 검토 FAIL)", "error": None}

    if result_verdict == "PASS":
        return {"step": "done", "label": "결과보고서 완성됨", "error": None}

    return {"step": "p3g", "label": "Phase 3 상태 불명확 → Phase 3부터 재시작", "error": None}


def collect_docx_files(
    book_dir: Path = BOOK_DIR,
    note_dir: Path = NOTE_DIR,
    stt_dir: Path = STT_DIR,
    exercise_dir: Path = EXERCISE_DIR,
) -> dict[str, list[str]]:
    """input/ 하위 파일 목록을 수집하여 반환한다."""
    result: dict[str, list[str]] = {"book": [], "note": [], "stt": [], "exercise": []}
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}
    exercise_exts = image_exts | {".pdf", ".md", ".txt"}

    if book_dir.exists():
        result["book"] = sorted(
            str(f) for f in book_dir.glob("*") if f.is_file() and f.suffix.lower() in image_exts
        )
    if note_dir.exists():
        result["note"] = sorted(str(f) for f in note_dir.glob("*") if f.is_file())
    if stt_dir.exists():
        result["stt"] = sorted(str(f) for f in stt_dir.glob("*.txt") if f.is_file())
    if exercise_dir.exists():
        result["exercise"] = sorted(
            str(f) for f in exercise_dir.glob("*") if f.is_file() and f.suffix.lower() in exercise_exts
        )

    return result


def _find_pre_reports(output_dir: Path = OUTPUT_DIR) -> list[str]:
    """output/ 에서 예비보고서 파일을 찾는다."""
    if not output_dir.exists():
        return []
    return sorted(str(f) for f in output_dir.glob("*예비보고서.md"))


def _find_measurements(measured_dir: Path = MEASURED_DIR) -> list[str]:
    """input/measured/ 에서 측정값 파일을 찾는다."""
    if not measured_dir.exists():
        return []
    return sorted(str(f) for f in measured_dir.glob("*측정값.md"))


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
    """검토 파일 본문 전체를 그대로 반환한다.

    이전에는 ":\\s*FAIL" 매칭 줄만 추출했지만, 그 정규식은 reviewer가
    `### 발견된 문제점` 섹션에 적은 구체적 fix 지시(어디서/무엇을/어떻게 고칠지)를
    누락시켰다. generator가 라운드마다 같은 항목을 못 고치고 max_rounds를 초과하는
    실패의 직접 원인이었다. 이제 review 본문을 통째로 fail_summary로 전달해
    정보 손실을 0으로 만든다.
    """
    if not review_path.exists():
        return ""
    return review_path.read_text(encoding="utf-8")


def extract_pass_sections(review_path: Path) -> list[str]:
    """검토 파일에서 판정 PASS인 보고서 섹션 헤더 이름을 추출한다.

    `### {섹션명}` 다음에 같은 섹션 블록 안에서 `판정: PASS`가 나오고
    `판정: FAIL`이 나오지 않는 경우의 섹션명을 반환한다.

    review 파일에는 `### 경계 침범 체크`, `### STT 충돌 처리 체크`,
    `### 발견된 문제점` 같은 검토 카테고리 H3도 함께 있으므로,
    REPORT_SECTIONS 화이트리스트와 교집합하여 보고서 섹션 이름만 반환한다.
    """
    if not review_path.exists():
        return []

    lines = review_path.read_text(encoding="utf-8").splitlines()
    pass_sections: list[str] = []
    current: str | None = None
    has_pass = False
    has_fail = False

    def flush() -> None:
        nonlocal current, has_pass, has_fail
        if (
            current is not None
            and has_pass
            and not has_fail
            and current in REPORT_SECTIONS
        ):
            pass_sections.append(current)
        current = None
        has_pass = False
        has_fail = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            flush()
            current = stripped[4:].strip()
        elif current is not None:
            if re.search(r"판정\s*:\s*FAIL", stripped):
                has_fail = True
            elif re.search(r"판정\s*:\s*PASS", stripped):
                has_pass = True
    flush()

    return pass_sections


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

