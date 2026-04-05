from __future__ import annotations

from pathlib import Path

import harness


def test_parse_review_verdict_pass_fail_unknown(tmp_path: Path) -> None:
    pass_path = tmp_path / "pass.md"
    pass_path.write_text("## 결과\n최종 판정: PASS\n", encoding="utf-8")
    assert harness.parse_review_verdict(pass_path) == "PASS"

    fail_path = tmp_path / "fail.md"
    fail_path.write_text("## 결과\n최종 판정: FAIL\n", encoding="utf-8")
    assert harness.parse_review_verdict(fail_path) == "FAIL"

    unknown_path = tmp_path / "unknown.md"
    unknown_path.write_text("## 결과\n판정 없음\n", encoding="utf-8")
    assert harness.parse_review_verdict(unknown_path) == "UNKNOWN"

    missing_path = tmp_path / "missing.md"
    assert harness.parse_review_verdict(missing_path) == "UNKNOWN"


def test_extract_fail_items_only_fail_lines(tmp_path: Path) -> None:
    review_path = tmp_path / "review.md"
    review_path.write_text(
        "\n".join(
            [
                "### 실험 목적",
                "- 판정: PASS (설명에서 FAIL 단어가 언급될 수 있음)",
                "- 계산: FAIL (수치 불일치)",
                "최종 판정: FAIL",
            ]
        ),
        encoding="utf-8",
    )

    fail_lines = harness.extract_fail_items(review_path).splitlines()

    assert fail_lines == [
        "- 계산: FAIL (수치 불일치)",
        "최종 판정: FAIL",
    ]


class _FixedNow:
    def strftime(self, _fmt: str) -> str:
        return "20260101_120000"


class _FixedDateTime:
    @staticmethod
    def now() -> _FixedNow:
        return _FixedNow()


def test_archive_path_collision_uses_timestamp_and_counter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(harness, "datetime", _FixedDateTime)

    base_archive = tmp_path / "pre_review_round1.md"
    base_archive.write_text("old", encoding="utf-8")

    src = tmp_path / "pre_review.md"
    src.write_text("first", encoding="utf-8")

    first = harness._archive_if_exists(src, base_archive)
    assert first is not None
    assert first.name == "pre_review_round1_20260101_120000.md"
    assert first.read_text(encoding="utf-8") == "first"

    src.write_text("second", encoding="utf-8")
    second = harness._archive_if_exists(src, base_archive)
    assert second is not None
    assert second.name == "pre_review_round1_20260101_120000_1.md"
    assert second.read_text(encoding="utf-8") == "second"


def test_select_result_reviewer_prompt_phase1(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(harness, "OUTPUT_DIR", tmp_path)

    report = tmp_path / "15주차_결과보고서.md"
    report.write_text("# 15주차 결과보고서\n\n# 실험 결과\n\n데이터\n", encoding="utf-8")

    prompt, review_path, mode = harness._select_result_reviewer_prompt()

    assert mode == "phase1"
    assert review_path == tmp_path / "result_review_data.md"
    assert "실험 결과 섹션" in prompt


def test_select_result_reviewer_prompt_phase2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(harness, "OUTPUT_DIR", tmp_path)

    report = tmp_path / "15주차_결과보고서.md"
    report.write_text(
        "# 15주차 결과보고서\n\n# 실험 결과\n\n데이터\n\n# 고찰\n\n분석\n",
        encoding="utf-8",
    )

    prompt, review_path, mode = harness._select_result_reviewer_prompt()

    assert mode == "phase2"
    assert review_path == tmp_path / "result_review.md"
    assert "고찰 섹션" in prompt
