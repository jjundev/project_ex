from __future__ import annotations

import os
from pathlib import Path

import harness
from harness_core import pipeline, prompts
from harness_core.io_state import extract_pass_sections

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


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


def test_extract_fail_items_returns_full_review_body(tmp_path: Path) -> None:
    """extract_fail_items는 review 본문 전체를 그대로 generator에게 전달한다.

    이전 정규식 기반 추출은 `### 발견된 문제점` 섹션의 구체 fix 지시를
    누락시켜 generator의 부분 수정이 라운드마다 같은 항목을 못 고치는
    근본 원인이었다 (12주차 line 97 사례). 이제 정보 손실 없이 통째로 전달.
    """
    review_body = "\n".join(
        [
            "### 실험 목적",
            "- 판정: PASS (설명에서 FAIL 단어가 언급될 수 있음)",
            "- 계산: FAIL (수치 불일치)",
            "### 발견된 문제점",
            "- [실험 이론] 정현파 R/L/C: Ch 10 Part 1을 제거해야 함.",
            "최종 판정: FAIL",
        ]
    )
    review_path = tmp_path / "review.md"
    review_path.write_text(review_body, encoding="utf-8")

    result = harness.extract_fail_items(review_path)

    assert result == review_body
    assert "Ch 10 Part 1을 제거해야 함" in result


def test_extract_fail_items_returns_empty_for_missing_file(tmp_path: Path) -> None:
    assert harness.extract_fail_items(tmp_path / "nope.md") == ""


def test_extract_pass_sections_filters_review_categories(tmp_path: Path) -> None:
    """review 카테고리 H3는 보고서 섹션이 아니므로 PASS list에서 자동 제외."""
    review_path = tmp_path / "review.md"
    review_path.write_text(
        "\n".join(
            [
                "## 이론 섹션 검토 결과",
                "### 실험 목적",
                "- 판정: PASS",
                "### 실험 준비물",
                "- 판정: PASS",
                "### 실험 이론",
                "- 판정: FAIL (위상 부호 오류)",
                "### 경계 침범 체크",
                "- 판정: PASS",
                "### STT 충돌 처리 체크",
                "- 유형 A (수치 파라미터): PASS",
                "- 유형 B (절차/회로 변형): PASS",
                "최종 판정: FAIL",
            ]
        ),
        encoding="utf-8",
    )

    result = extract_pass_sections(review_path)

    assert result == ["실험 목적", "실험 준비물"]
    assert "경계 침범 체크" not in result
    assert "STT 충돌 처리 체크" not in result


def test_extract_fail_items_preserves_round2_fix_directive() -> None:
    """12주차 round 2 review 회귀 테스트.

    Round 3에 잔존한 "Ch 10 Part 1, C = 0.01 μF" 오기재는 round 2 review의
    `### 발견된 문제점` bullet에 명시적으로 적혀 있었지만, 이전 정규식이
    그 bullet을 generator에게 전달하지 않아 fix 실패 → max_rounds 초과로 이어졌다.
    이 테스트는 실제 round 2 review 파일을 fixture로 사용해 fix 지시가
    fail_summary에 보존되는지 영구 검증한다.
    """
    fixture = FIXTURES_DIR / "pre_review_theory_round2_12week.md"
    summary = harness.extract_fail_items(fixture)

    assert "Ch 10 Part 1" in summary
    assert "C = 0.01 μF" in summary
    assert "잘못된 사용처 표기임" in summary
    assert "최종 판정: FAIL" in summary


def test_extract_pass_sections_round2_filters_review_categories() -> None:
    """12주차 round 2 review의 PASS 섹션 추출이 보고서 섹션만 반환하는지 검증."""
    fixture = FIXTURES_DIR / "pre_review_theory_round2_12week.md"
    pass_sections = extract_pass_sections(fixture)

    assert "실험 목적" in pass_sections
    assert "실험 준비물" in pass_sections
    assert "실험 이론" not in pass_sections
    assert "경계 침범 체크" not in pass_sections
    assert "STT 충돌 처리 체크" not in pass_sections
    assert "발견된 문제점" not in pass_sections


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

    # exercise dir 비어있으면 PASS 상태에서 phase3로 가지만, data_review가 없으므로 phase1.
    prompt, review_path, mode = harness._select_result_reviewer_prompt()

    assert mode == "phase1"
    assert review_path == tmp_path / "result_review_data.md"
    assert "`# 실험 결과` 섹션" in prompt


def test_select_result_reviewer_prompt_phase2_exercise(tmp_path: Path, monkeypatch) -> None:
    """보고서에 `# 연습 문제`가 있고 `# 고찰`이 없으면 phase2(exercise) 자동 선택."""
    monkeypatch.setattr(harness, "OUTPUT_DIR", tmp_path)

    report = tmp_path / "15주차_결과보고서.md"
    report.write_text(
        "# 15주차 결과보고서\n\n# 실험 결과\n\n데이터\n\n# 연습 문제\n\n풀이\n",
        encoding="utf-8",
    )

    prompt, review_path, mode = harness._select_result_reviewer_prompt()

    assert mode == "phase2"
    assert review_path == tmp_path / "result_review_exercise.md"
    assert "`# 연습 문제` 섹션" in prompt


def test_select_result_reviewer_prompt_phase3(tmp_path: Path, monkeypatch) -> None:
    """보고서에 `# 고찰`이 있으면 phase3 자동 선택."""
    monkeypatch.setattr(harness, "OUTPUT_DIR", tmp_path)

    report = tmp_path / "15주차_결과보고서.md"
    report.write_text(
        "# 15주차 결과보고서\n\n# 실험 결과\n\n데이터\n\n# 고찰\n\n분석\n",
        encoding="utf-8",
    )

    prompt, review_path, mode = harness._select_result_reviewer_prompt()

    assert mode == "phase3"
    assert review_path == tmp_path / "result_review.md"
    assert "고찰 섹션" in prompt


def test_select_result_reviewer_prompt_exercise_skip_routes_to_phase3(
    tmp_path: Path, monkeypatch
) -> None:
    """exercise dir 비어있고 Phase 1 PASS 상태에서 단독 reviewer는 phase3로 직행해야 한다.

    Blocker Q11 회귀 방지. 과거 autodetect는 # 연습 문제 / # 고찰 모두 없을 때
    무조건 phase1으로 재진입하여 이미 PASS된 데이터 검토를 다시 돌리고 phase3에
    도달하지 못했다.
    """
    monkeypatch.setattr(harness, "OUTPUT_DIR", tmp_path)
    empty_exercise_dir = tmp_path / "exercise"
    empty_exercise_dir.mkdir()

    report = tmp_path / "15주차_결과보고서.md"
    report.write_text("# 15주차 결과보고서\n\n# 실험 결과\n\n데이터\n", encoding="utf-8")
    (tmp_path / "result_review_data.md").write_text("최종 판정: PASS\n", encoding="utf-8")

    prompt, review_path, mode = prompts._select_result_reviewer_prompt(
        output_dir=tmp_path, exercise_dir=empty_exercise_dir
    )

    assert mode == "phase3"
    assert review_path == tmp_path / "result_review.md"
    assert "고찰 섹션" in prompt


def test_result_generator_phase1_prompt_data_only() -> None:
    """Phase 1 generator는 # 실험 결과 섹션만 작성하고 연습 문제·고찰은 금지."""
    prompt = prompts._build_result_generator_phase1_prompt()

    assert "교재 스캔본 (input/book/) — Table 원형 확인용" in prompt
    assert "`input/book/` 이미지를 다시 읽어 각 교재 Table" in prompt
    assert "교재 Table 원형 구조를 최상위 기준" in prompt
    assert "교재에 없는 `Calculated`, `Measured`, `%(Difference)` 열을 임의로 추가하지 마세요" in prompt
    assert "`v_R = E - v_C`" in prompt
    assert "측정값에서 좌표나 파생값을 산출" in prompt
    assert "`X = R`, `V = E/√2`, `τ = RC` 같은 이론식은 이론 기준값" in prompt
    assert "측정 기반 산출값을 덮어쓰지 마세요" in prompt
    assert "측정 기반 산출값인지, 명판값 기반 이론 계산인지, 실측 소자값 기반 재계산인지" in prompt
    # Phase 1 boundary
    assert "`# 실험 결과` 섹션만 작성합니다" in prompt
    assert "`# 연습 문제` 섹션은 Phase 2에서" in prompt


def test_result_reviewer_phase1_prompt_data_only(tmp_path: Path) -> None:
    """Phase 1 reviewer는 # 실험 결과 검증만. 연습 문제 검증은 Phase 2로 이동."""
    report = tmp_path / "15주차_결과보고서.md"
    report.write_text("# 15주차 결과보고서\n\n# 실험 결과\n\n데이터\n", encoding="utf-8")

    prompt = prompts._build_result_reviewer_phase1_prompt(output_dir=tmp_path)

    assert "교재 스캔본 (input/book/) — Table 원형 확인용" in prompt
    assert "교재 Table 구조 대조" in prompt
    assert "임의 열 추가/누락 검증" in prompt
    assert "파생값 검증" in prompt
    assert "측정 기반 산출값 검증" in prompt
    assert "인접 측정점 보간 또는 명시된 판독 기준" in prompt
    assert "`X = R`, `V = E/√2`, `τ = RC` 같은 이론 기준값으로 단정" in prompt
    assert "Table 구조: PASS 또는 FAIL" in prompt
    # Phase 1 reviewer는 연습 문제 검증을 더 이상 포함하지 않는다
    assert "Calculated/Experimental Table 형식" not in prompt
    assert "Exercise 누락" not in prompt


def test_result_generator_phase2_prompt_exercise_only() -> None:
    """Phase 2 generator는 # 연습 문제만 추가하고 # 실험 결과는 read-only."""
    prompt = prompts._build_result_generator_phase2_prompt()

    assert "`# 연습 문제` 섹션만" in prompt
    assert "Phase 1에서 작성된 `# 실험 결과` 섹션은 절대 수정하지 마세요" in prompt
    assert "삽입 위치 규칙" in prompt
    assert "`# 고찰` 헤더가 있으면" in prompt
    assert "파일 *맨 끝*에" in prompt
    assert "실험 측정값" in prompt  # Type 3 Calculated/Experimental placeholder


def test_result_reviewer_phase2_prompt_exercise_only(tmp_path: Path) -> None:
    """Phase 2 reviewer는 # 연습 문제 11-항목 검증 + 섹션 위치."""
    prompt = prompts._build_result_reviewer_phase2_prompt(output_dir=tmp_path)

    assert "`# 연습 문제` 섹션" in prompt
    assert "섹션 위치" in prompt
    assert "Exercise 누락" in prompt
    assert "입력 파싱" in prompt
    assert "단위 변환" in prompt
    assert "단계별 계산 흐름" in prompt
    assert "공식 정확성" in prompt
    assert "재계산 일치" in prompt
    assert "단위 표기" in prompt
    assert "정답-본문 일관성" in prompt
    assert "Calculated/Experimental Table 형식" in prompt
    assert "실험 측정값" in prompt
    assert "자동 채움" in prompt
    assert "result_review_exercise.md" in prompt


def test_result_generator_phase3_prompt_protects_phase1_and_phase2() -> None:
    """Phase 3 generator는 고찰만 추가. Phase 1·2 섹션 모두 read-only."""
    prompt = prompts._build_result_generator_phase3_prompt()

    assert "`# 고찰` 섹션만" in prompt
    assert "Phase 1에서 작성된 `# 실험 결과` 섹션과 Phase 2에서 작성된 `# 연습 문제` 섹션은 절대 수정하지 마세요" in prompt
    assert "끼워 넣지 마세요" in prompt
    assert "측정 기반 산출값과 이론 기준값이 다르면 단순 계산 오류로 단정하지 말고" in prompt
    assert "보간값·판독값·이론 기준값을 구분" in prompt


def test_result_reviewer_phase3_prompt_checks_measured_vs_theory_discussion(tmp_path: Path) -> None:
    report = tmp_path / "15주차_결과보고서.md"
    report.write_text("# 15주차 결과보고서\n\n# 실험 결과\n\n데이터\n\n# 고찰\n\n분석\n", encoding="utf-8")

    prompt = prompts._build_result_reviewer_phase3_prompt(output_dir=tmp_path)

    assert "측정값-이론값 구분" in prompt
    assert "측정 기반 산출값과 이론 기준값의 차이를 단순 오류로 처리하지 않고" in prompt
    assert "소자 오차, 계측 한계, 그래프 판독 오차" in prompt


def test_result_skills_lock_table_16_5_and_16_6_structure() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    report_skill = (project_dir / "skills" / "result-report" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    review_skill = (project_dir / "skills" / "result-review" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    for skill_text in (report_skill, review_skill):
        assert "Table 16.5" in skill_text
        assert "`v_C`, `v_R`" in skill_text
        assert "`v_R`" in skill_text
        assert "`E - v_C`" in skill_text
        assert "Table 16.6" in skill_text
        assert "`1τ`, `5τ`" in skill_text
        assert "Calculated`, `Measured`, `%(Difference)` 열" in skill_text


def test_consume_previous_review_round1_no_file_fresh_start(
    tmp_path: Path, monkeypatch
) -> None:
    """round 1에 review 파일이 없으면 기존 동작과 동일하게 fresh start."""
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path)
    review_path = tmp_path / "pre_review_theory.md"

    fail_summary, skip = pipeline._consume_previous_review(
        review_path,
        round_num=1,
        archive_basename_template="pre_review_theory_round{}.md",
    )

    assert fail_summary == ""
    assert skip is False
    assert not (tmp_path / "pre_review_theory_round0.md").exists()


def test_consume_previous_review_round1_pass_precondition_true_skips_phase(
    tmp_path: Path, monkeypatch
) -> None:
    """이전 실행 PASS + 보고서 섹션 유효 → phase 전체 skip 신호. active review는 보존."""
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path)
    review_path = tmp_path / "pre_review_theory.md"
    review_path.write_text("## 검토\n최종 판정: PASS\n", encoding="utf-8")

    fail_summary, skip = pipeline._consume_previous_review(
        review_path,
        round_num=1,
        archive_basename_template="pre_review_theory_round{}.md",
        pass_skip_precondition=lambda: True,
    )

    assert fail_summary == ""
    assert skip is True
    # PASS-skip 시 active review 보존 (다음 실행에서도 PASS로 인식하기 위함)
    assert review_path.exists()


def test_consume_previous_review_round1_pass_precondition_false_archives(
    tmp_path: Path, monkeypatch
) -> None:
    """PASS verdict이지만 보고서 섹션이 stale (상위 phase 재실행 등) → archive 후 fresh start."""
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path)
    review_path = tmp_path / "pre_review.md"
    review_path.write_text("최종 판정: PASS\n", encoding="utf-8")

    fail_summary, skip = pipeline._consume_previous_review(
        review_path,
        round_num=1,
        archive_basename_template="pre_review_round{}.md",
        pass_skip_precondition=lambda: False,
    )

    assert fail_summary == ""
    assert skip is False
    assert not review_path.exists()
    assert (tmp_path / "pre_review_round0.md").exists()


def test_consume_previous_review_round1_fail_archives_and_returns_body(
    tmp_path: Path, monkeypatch
) -> None:
    """round 1에 FAIL review 존재 → archive 후 본문 통째 반환, phase 진행."""
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path)
    review_path = tmp_path / "pre_review_theory.md"
    body = "### 발견된 문제점\n- Ch X 항목 누락 — 강의노트 p.42 참조\n최종 판정: FAIL\n"
    review_path.write_text(body, encoding="utf-8")

    fail_summary, skip = pipeline._consume_previous_review(
        review_path,
        round_num=1,
        archive_basename_template="pre_review_theory_round{}.md",
        pass_skip_precondition=lambda: True,  # PASS-skip 대상이 아니므로 무시되어야 함
    )

    assert skip is False
    assert "Ch X 항목 누락" in fail_summary
    assert "최종 판정: FAIL" in fail_summary
    assert not review_path.exists()
    assert (tmp_path / "pre_review_theory_round0.md").exists()


def test_consume_previous_review_round1_unknown_archives_and_returns_body(
    tmp_path: Path, monkeypatch
) -> None:
    """판정 줄이 없는 (UNKNOWN) review도 fresh start 대신 본문을 인계한다."""
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path)
    review_path = tmp_path / "pre_review_theory.md"
    review_path.write_text("판정 줄이 없는 부분 작성된 검토 메모\n", encoding="utf-8")

    fail_summary, skip = pipeline._consume_previous_review(
        review_path,
        round_num=1,
        archive_basename_template="pre_review_theory_round{}.md",
    )

    assert skip is False
    assert "판정 줄이 없는 부분 작성된 검토 메모" in fail_summary
    assert (tmp_path / "pre_review_theory_round0.md").exists()


def test_consume_previous_review_round1_archive_fail_inherits_body(
    tmp_path: Path, monkeypatch
) -> None:
    """active가 없어도 최신 archive review가 있으면 round 1에 인계한다."""
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path)
    review_path = tmp_path / "pre_review_theory.md"
    archived_review = tmp_path / "pre_review_theory_round0.md"
    archived_review.write_text("archive FAIL 본문\n최종 판정: FAIL\n", encoding="utf-8")

    fail_summary, skip = pipeline._consume_previous_review(
        review_path,
        round_num=1,
        archive_basename_template="pre_review_theory_round{}.md",
    )

    assert skip is False
    assert "archive FAIL 본문" in fail_summary
    assert archived_review.exists()


def test_consume_previous_review_round1_newer_archive_wins_over_active(
    tmp_path: Path, monkeypatch
) -> None:
    """active보다 최신 archive가 있으면 최신 archive verdict을 기준으로 인계한다."""
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path)
    review_path = tmp_path / "pre_review_theory.md"
    review_path.write_text("active PASS\n최종 판정: PASS\n", encoding="utf-8")
    archived_review = tmp_path / "pre_review_theory_round0.md"
    archived_review.write_text("newer archive FAIL\n최종 판정: FAIL\n", encoding="utf-8")
    os.utime(review_path, (1_000, 1_000))
    os.utime(archived_review, (2_000, 2_000))

    fail_summary, skip = pipeline._consume_previous_review(
        review_path,
        round_num=1,
        archive_basename_template="pre_review_theory_round{}.md",
        pass_skip_precondition=lambda: True,
    )

    assert skip is False
    assert "newer archive FAIL" in fail_summary
    assert review_path.exists()
    assert archived_review.exists()


def test_consume_previous_review_round1_archive_pass_can_skip(
    tmp_path: Path, monkeypatch
) -> None:
    """최신 archive review가 PASS이고 섹션 guard가 통과하면 phase를 건너뛴다."""
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path)
    review_path = tmp_path / "pre_review_theory.md"
    archived_review = tmp_path / "pre_review_theory_round0.md"
    archived_review.write_text("최종 판정: PASS\n", encoding="utf-8")

    fail_summary, skip = pipeline._consume_previous_review(
        review_path,
        round_num=1,
        archive_basename_template="pre_review_theory_round{}.md",
        pass_skip_precondition=lambda: True,
    )

    assert fail_summary == ""
    assert skip is True
    assert archived_review.exists()


def test_consume_previous_review_round2_archives_as_round1(
    tmp_path: Path, monkeypatch
) -> None:
    """round 2 이상: 기존 동작 유지 — review_path를 _round{N-1}로 archive."""
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path)
    review_path = tmp_path / "pre_review_theory.md"
    review_path.write_text("최종 판정: FAIL\n발견된 오류 본문\n", encoding="utf-8")

    fail_summary, skip = pipeline._consume_previous_review(
        review_path,
        round_num=2,
        archive_basename_template="pre_review_theory_round{}.md",
    )

    assert skip is False
    assert "발견된 오류 본문" in fail_summary
    assert not review_path.exists()
    assert (tmp_path / "pre_review_theory_round1.md").exists()


def test_format_rework_extra_round1_signals_inheritance() -> None:
    extra = pipeline._format_rework_extra(
        1, "이전 이론 검토에서 발견된 문제", "FAIL 본문 내용"
    )
    assert "이전 실행에서 인계" in extra
    assert "이전 이론 검토에서 발견된 문제" in extra
    assert "FAIL 본문 내용" in extra
    assert "번째 시도" not in extra


def test_format_rework_extra_round2_signals_attempt_count() -> None:
    extra = pipeline._format_rework_extra(2, "이전 KVL/KCL 오류", "내용")
    assert "2번째 시도" in extra
    assert "이전 KVL/KCL 오류" in extra
    assert "내용" in extra


def test_pre_generator_rework_prompt_uses_latest_review_for_pass_sections(
    tmp_path: Path, monkeypatch
) -> None:
    """재작업 prompt도 active/archive 중 mtime 최신 review로 PASS 섹션을 추출한다."""
    monkeypatch.setattr(prompts, "OUTPUT_DIR", tmp_path)
    active_review = tmp_path / "pre_review_theory.md"
    active_review.write_text(
        "### 실험 목적\n- 판정: PASS\n### 발견된 문제점\n최종 판정: FAIL\n",
        encoding="utf-8",
    )
    archived_review = tmp_path / "pre_review_theory_round0.md"
    archived_review.write_text(
        "### 실험 준비물\n- 판정: PASS\n### 발견된 문제점\n최종 판정: FAIL\n",
        encoding="utf-8",
    )
    os.utime(active_review, (1_000, 1_000))
    os.utime(archived_review, (2_000, 2_000))

    prompt = prompts._build_pre_generator_prompt("이전 실행 FAIL 본문")

    assert "  - 실험 준비물" in prompt
    assert "  - 실험 목적" not in prompt


def test_result_skills_distinguish_measured_derived_values_from_theory() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    report_skill = (project_dir / "skills" / "result-report" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    review_skill = (project_dir / "skills" / "result-review" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "측정 기반 산출값과 이론 기준값 구분" in report_skill
    assert "측정값에서 좌표나 파생값을 산출" in report_skill
    assert "`X = R`, `V = E/√2`, `τ = RC` 같은 이상식" in report_skill
    assert "측정 기반 산출값과 이론 기준값 검증" in review_skill
    assert "관계식만으로 채웠으면 FAIL" in review_skill
    assert "소자 오차, 계측 한계, 그래프 판독 오차" in review_skill
