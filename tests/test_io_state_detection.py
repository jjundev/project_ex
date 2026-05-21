"""io_state 상태 감지 함수 테스트."""
from __future__ import annotations

from pathlib import Path

import pytest

from harness_core.io_state import (
    _exercise_files_present,
    _has_exercise_section,
    _has_expected_values_section,
    detect_pre_report_state,
    detect_result_report_state,
)


# ---------------------------------------------------------------------------
# _has_expected_values_section
# ---------------------------------------------------------------------------

def test_has_expected_values_section_true(tmp_path: Path) -> None:
    report = tmp_path / "예비보고서.md"
    report.write_text("# 제목\n\n## 예상 결과 값\n\n| V1 | 5V |\n", encoding="utf-8")
    assert _has_expected_values_section(report) is True


def test_has_expected_values_section_false(tmp_path: Path) -> None:
    report = tmp_path / "예비보고서.md"
    report.write_text("# 제목\n\n## 실험 이론\n\n텍스트\n", encoding="utf-8")
    assert _has_expected_values_section(report) is False


def test_has_expected_values_section_missing_file(tmp_path: Path) -> None:
    assert _has_expected_values_section(tmp_path / "없는파일.md") is False


# ---------------------------------------------------------------------------
# detect_pre_report_state
# ---------------------------------------------------------------------------

def _make_pass_review(path: Path) -> None:
    path.write_text("## 결과\n최종 판정: PASS\n", encoding="utf-8")


def _make_fail_review(path: Path) -> None:
    path.write_text("## 결과\n최종 판정: FAIL\n", encoding="utf-8")


def test_detect_pre_report_state_no_report(tmp_path: Path) -> None:
    result = detect_pre_report_state(output_dir=tmp_path)
    assert result["step"] == "p1g"
    assert result["error"] is None


def test_detect_pre_report_state_report_no_theory_review(tmp_path: Path) -> None:
    (tmp_path / "15주차_예비보고서.md").write_text("# 예비보고서\n", encoding="utf-8")
    result = detect_pre_report_state(output_dir=tmp_path)
    assert result["step"] == "p1r"
    assert result["error"] is None


def test_detect_pre_report_state_theory_fail(tmp_path: Path) -> None:
    (tmp_path / "15주차_예비보고서.md").write_text("# 예비보고서\n", encoding="utf-8")
    _make_fail_review(tmp_path / "pre_review_theory.md")
    result = detect_pre_report_state(output_dir=tmp_path)
    assert result["step"] == "p1g"


def test_detect_pre_report_state_theory_pass_no_expected_values(tmp_path: Path) -> None:
    (tmp_path / "15주차_예비보고서.md").write_text("# 예비보고서\n## 이론\n", encoding="utf-8")
    _make_pass_review(tmp_path / "pre_review_theory.md")
    result = detect_pre_report_state(output_dir=tmp_path)
    assert result["step"] == "p2g"
    assert result["error"] is None


def test_detect_pre_report_state_theory_pass_expected_values_no_calc_review(tmp_path: Path) -> None:
    (tmp_path / "15주차_예비보고서.md").write_text(
        "# 예비보고서\n## 이론\n\n## 예상 결과 값\n\n| V | 5V |\n",
        encoding="utf-8",
    )
    _make_pass_review(tmp_path / "pre_review_theory.md")
    result = detect_pre_report_state(output_dir=tmp_path)
    assert result["step"] == "p2r"
    assert result["error"] is None


def test_detect_pre_report_state_done(tmp_path: Path) -> None:
    (tmp_path / "15주차_예비보고서.md").write_text(
        "# 예비보고서\n## 예상 결과 값\n\n| V | 5V |\n",
        encoding="utf-8",
    )
    _make_pass_review(tmp_path / "pre_review_theory.md")
    _make_pass_review(tmp_path / "pre_review.md")
    result = detect_pre_report_state(output_dir=tmp_path)
    assert result["step"] == "done"
    assert result["error"] is None


# ---------------------------------------------------------------------------
# detect_result_report_state
# ---------------------------------------------------------------------------

def _setup_pre_done(output_dir: Path) -> None:
    """예비보고서 완성 상태 설정."""
    (output_dir / "15주차_예비보고서.md").write_text("# 예비보고서\n", encoding="utf-8")
    _make_pass_review(output_dir / "pre_review.md")


def test_detect_result_report_state_no_pre_report(tmp_path: Path) -> None:
    result = detect_result_report_state(output_dir=tmp_path, measured_dir=tmp_path)
    assert result["error"] is not None
    assert result["step"] is None


def test_detect_result_report_state_pre_not_complete(tmp_path: Path) -> None:
    (tmp_path / "15주차_예비보고서.md").write_text("# 예비보고서\n", encoding="utf-8")
    # pre_review.md 없음 → 예비보고서 미완성
    result = detect_result_report_state(output_dir=tmp_path, measured_dir=tmp_path)
    assert result["error"] is not None


def test_detect_result_report_state_no_measurements(tmp_path: Path) -> None:
    _setup_pre_done(tmp_path)
    measured_dir = tmp_path / "measured"
    measured_dir.mkdir()
    result = detect_result_report_state(output_dir=tmp_path, measured_dir=measured_dir)
    assert result["error"] is not None


def test_detect_result_report_state_no_result_report(tmp_path: Path) -> None:
    _setup_pre_done(tmp_path)
    measured_dir = tmp_path / "measured"
    measured_dir.mkdir()
    (measured_dir / "15주차_측정값.md").write_text("# 측정값\n", encoding="utf-8")
    result = detect_result_report_state(output_dir=tmp_path, measured_dir=measured_dir)
    assert result["step"] == "p1g"
    assert result["error"] is None


def test_detect_result_report_state_report_no_data_review(tmp_path: Path) -> None:
    _setup_pre_done(tmp_path)
    measured_dir = tmp_path / "measured"
    measured_dir.mkdir()
    (measured_dir / "15주차_측정값.md").write_text("# 측정값\n", encoding="utf-8")
    (tmp_path / "15주차_결과보고서.md").write_text("# 결과보고서\n", encoding="utf-8")
    result = detect_result_report_state(output_dir=tmp_path, measured_dir=measured_dir)
    assert result["step"] == "p1r"


def test_detect_result_report_state_data_pass_no_exercise_or_discussion(tmp_path: Path) -> None:
    """Phase 1 PASS, 보고서에 # 연습 문제·# 고찰 모두 없고 exercise 자료 있음 → p2g."""
    _setup_pre_done(tmp_path)
    measured_dir = tmp_path / "measured"
    measured_dir.mkdir()
    (measured_dir / "15주차_측정값.md").write_text("# 측정값\n", encoding="utf-8")
    exercise_dir = tmp_path / "exercise"
    exercise_dir.mkdir()
    (exercise_dir / "ex1.png").write_text("", encoding="utf-8")
    (tmp_path / "15주차_결과보고서.md").write_text("# 결과보고서\n", encoding="utf-8")
    _make_pass_review(tmp_path / "result_review_data.md")
    result = detect_result_report_state(
        output_dir=tmp_path, measured_dir=measured_dir, exercise_dir=exercise_dir
    )
    assert result["step"] == "p2g"


def test_detect_result_report_state_exercise_skip_routes_to_p3g(tmp_path: Path) -> None:
    """exercise 비어있고 Phase 1 PASS → Phase 2 건너뛰고 p3g."""
    _setup_pre_done(tmp_path)
    measured_dir = tmp_path / "measured"
    measured_dir.mkdir()
    (measured_dir / "15주차_측정값.md").write_text("# 측정값\n", encoding="utf-8")
    exercise_dir = tmp_path / "exercise"
    exercise_dir.mkdir()
    (tmp_path / "15주차_결과보고서.md").write_text("# 결과보고서\n", encoding="utf-8")
    _make_pass_review(tmp_path / "result_review_data.md")
    result = detect_result_report_state(
        output_dir=tmp_path, measured_dir=measured_dir, exercise_dir=exercise_dir
    )
    assert result["step"] == "p3g"


def test_detect_result_report_state_phase2_written_no_review(tmp_path: Path) -> None:
    """Phase 1 PASS, # 연습 문제 작성됨, exercise review 없음 → p2r."""
    _setup_pre_done(tmp_path)
    measured_dir = tmp_path / "measured"
    measured_dir.mkdir()
    (measured_dir / "15주차_측정값.md").write_text("# 측정값\n", encoding="utf-8")
    exercise_dir = tmp_path / "exercise"
    exercise_dir.mkdir()
    (exercise_dir / "ex1.png").write_text("", encoding="utf-8")
    (tmp_path / "15주차_결과보고서.md").write_text(
        "# 결과보고서\n\n# 실험 결과\n데이터\n\n# 연습 문제\n풀이\n",
        encoding="utf-8",
    )
    _make_pass_review(tmp_path / "result_review_data.md")
    result = detect_result_report_state(
        output_dir=tmp_path, measured_dir=measured_dir, exercise_dir=exercise_dir
    )
    assert result["step"] == "p2r"


def test_detect_result_report_state_phase2_review_fail(tmp_path: Path) -> None:
    """exercise review FAIL → p2g 재생성."""
    _setup_pre_done(tmp_path)
    measured_dir = tmp_path / "measured"
    measured_dir.mkdir()
    (measured_dir / "15주차_측정값.md").write_text("# 측정값\n", encoding="utf-8")
    exercise_dir = tmp_path / "exercise"
    exercise_dir.mkdir()
    (exercise_dir / "ex1.png").write_text("", encoding="utf-8")
    (tmp_path / "15주차_결과보고서.md").write_text(
        "# 결과보고서\n\n# 실험 결과\n데이터\n\n# 연습 문제\n풀이\n",
        encoding="utf-8",
    )
    _make_pass_review(tmp_path / "result_review_data.md")
    _make_fail_review(tmp_path / "result_review_exercise.md")
    result = detect_result_report_state(
        output_dir=tmp_path, measured_dir=measured_dir, exercise_dir=exercise_dir
    )
    assert result["step"] == "p2g"


def test_detect_result_report_state_phase2_pass_no_discussion(tmp_path: Path) -> None:
    """Phase 1·2 PASS, # 고찰 없음 → p3g."""
    _setup_pre_done(tmp_path)
    measured_dir = tmp_path / "measured"
    measured_dir.mkdir()
    (measured_dir / "15주차_측정값.md").write_text("# 측정값\n", encoding="utf-8")
    exercise_dir = tmp_path / "exercise"
    exercise_dir.mkdir()
    (exercise_dir / "ex1.png").write_text("", encoding="utf-8")
    (tmp_path / "15주차_결과보고서.md").write_text(
        "# 결과보고서\n\n# 실험 결과\n데이터\n\n# 연습 문제\n풀이\n",
        encoding="utf-8",
    )
    _make_pass_review(tmp_path / "result_review_data.md")
    _make_pass_review(tmp_path / "result_review_exercise.md")
    result = detect_result_report_state(
        output_dir=tmp_path, measured_dir=measured_dir, exercise_dir=exercise_dir
    )
    assert result["step"] == "p3g"


def test_detect_result_report_state_phase3_written_no_review(tmp_path: Path) -> None:
    """Phase 3 작성 완료, 고찰 review 없음 → p3r."""
    _setup_pre_done(tmp_path)
    measured_dir = tmp_path / "measured"
    measured_dir.mkdir()
    (measured_dir / "15주차_측정값.md").write_text("# 측정값\n", encoding="utf-8")
    exercise_dir = tmp_path / "exercise"
    exercise_dir.mkdir()
    (exercise_dir / "ex1.png").write_text("", encoding="utf-8")
    (tmp_path / "15주차_결과보고서.md").write_text(
        "# 결과보고서\n\n# 실험 결과\n데이터\n\n# 연습 문제\n풀이\n\n# 고찰\n내용\n",
        encoding="utf-8",
    )
    _make_pass_review(tmp_path / "result_review_data.md")
    _make_pass_review(tmp_path / "result_review_exercise.md")
    result = detect_result_report_state(
        output_dir=tmp_path, measured_dir=measured_dir, exercise_dir=exercise_dir
    )
    assert result["step"] == "p3r"


def test_detect_result_report_state_done(tmp_path: Path) -> None:
    _setup_pre_done(tmp_path)
    measured_dir = tmp_path / "measured"
    measured_dir.mkdir()
    (measured_dir / "15주차_측정값.md").write_text("# 측정값\n", encoding="utf-8")
    exercise_dir = tmp_path / "exercise"
    exercise_dir.mkdir()
    (tmp_path / "15주차_결과보고서.md").write_text(
        "# 결과보고서\n\n# 고찰\n\n내용\n", encoding="utf-8"
    )
    _make_pass_review(tmp_path / "result_review_data.md")
    _make_pass_review(tmp_path / "result_review.md")
    result = detect_result_report_state(
        output_dir=tmp_path, measured_dir=measured_dir, exercise_dir=exercise_dir
    )
    assert result["step"] == "done"
    assert result["error"] is None


# ---------------------------------------------------------------------------
# _has_exercise_section / _exercise_files_present helpers
# ---------------------------------------------------------------------------

def test_has_exercise_section_true(tmp_path: Path) -> None:
    report = tmp_path / "결과보고서.md"
    report.write_text("# 결과보고서\n\n# 연습 문제\n\n풀이\n", encoding="utf-8")
    assert _has_exercise_section(report) is True


def test_has_exercise_section_false(tmp_path: Path) -> None:
    report = tmp_path / "결과보고서.md"
    report.write_text("# 결과보고서\n\n# 실험 결과\n\n데이터\n", encoding="utf-8")
    assert _has_exercise_section(report) is False


def test_has_exercise_section_missing_file(tmp_path: Path) -> None:
    assert _has_exercise_section(tmp_path / "없는파일.md") is False


def test_exercise_files_present_empty_dir(tmp_path: Path) -> None:
    exercise_dir = tmp_path / "exercise"
    exercise_dir.mkdir()
    assert _exercise_files_present(exercise_dir=exercise_dir) is False


def test_exercise_files_present_missing_dir(tmp_path: Path) -> None:
    assert _exercise_files_present(exercise_dir=tmp_path / "nope") is False


def test_exercise_files_present_with_image(tmp_path: Path) -> None:
    exercise_dir = tmp_path / "exercise"
    exercise_dir.mkdir()
    (exercise_dir / "ex1.png").write_text("", encoding="utf-8")
    assert _exercise_files_present(exercise_dir=exercise_dir) is True


def test_exercise_files_present_ignores_unknown_ext(tmp_path: Path) -> None:
    exercise_dir = tmp_path / "exercise"
    exercise_dir.mkdir()
    (exercise_dir / "ex1.xyz").write_text("", encoding="utf-8")
    assert _exercise_files_present(exercise_dir=exercise_dir) is False
