from __future__ import annotations

import sys
import time
from pathlib import Path

from .config import INPUT_DIR, MODEL_SONNET, OUTPUT_DIR, PROJECT_DIR, ROLE_MODELS, ROLE_ORDER, SKILL_PATHS
from .io_state import (
    _archive_if_exists,
    _find_measurements,
    _find_pre_reports,
    _find_result_reports,
    collect_docx_files,
    extract_fail_items,
    parse_review_verdict,
)
from .prompts import (
    _build_pre_generator_phase2_prompt,
    _build_pre_reviewer_phase1_prompt,
    _build_pre_reviewer_prompt,
    _build_result_generator_phase2_prompt,
    _build_result_reviewer_phase1_prompt,
    _build_result_reviewer_phase2_prompt,
    _select_result_reviewer_prompt,
    build_prompt,
)

try:
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, SystemMessage, query
except ModuleNotFoundError:
    ClaudeAgentOptions = None  # type: ignore[assignment]
    ResultMessage = None  # type: ignore[assignment]
    SystemMessage = None  # type: ignore[assignment]
    query = None  # type: ignore[assignment]


class HarnessError(Exception):
    """하네스 파이프라인 오류."""


def _log(msg: str) -> None:
    print(f"\033[36m[harness]\033[0m {msg}", flush=True)


def _log_error(msg: str) -> None:
    print(f"\033[31m[harness]\033[0m {msg}", file=sys.stderr, flush=True)


def _ensure_sdk_available() -> None:
    """claude_agent_sdk 의존성이 필요한 시점에 지연 확인한다."""
    global ClaudeAgentOptions, ResultMessage, SystemMessage, query

    if (
        ClaudeAgentOptions is not None
        and ResultMessage is not None
        and SystemMessage is not None
        and query is not None
    ):
        return

    try:
        from claude_agent_sdk import (
            ClaudeAgentOptions as _ClaudeAgentOptions,
            ResultMessage as _ResultMessage,
            SystemMessage as _SystemMessage,
            query as _query,
        )
    except ModuleNotFoundError as e:
        raise HarnessError(
            "claude-agent-sdk 가 설치되어 있지 않습니다. "
            "`pip install -r requirements.txt` 후 다시 실행하세요."
        ) from e

    ClaudeAgentOptions = _ClaudeAgentOptions
    ResultMessage = _ResultMessage
    SystemMessage = _SystemMessage
    query = _query


def load_skill(role: str) -> str:
    """역할에 해당하는 SKILL.md를 읽어 system_prompt로 반환한다."""
    path = SKILL_PATHS.get(role)
    if path is None or not path.exists():
        raise HarnessError(f"SKILL.md를 찾을 수 없습니다 — role: '{role}', path: {path}")
    return path.read_text(encoding="utf-8")


def make_options(role: str) -> ClaudeAgentOptions:
    """역할에 맞는 ClaudeAgentOptions를 반환한다."""
    _ensure_sdk_available()

    model = ROLE_MODELS.get(role, MODEL_SONNET)
    return ClaudeAgentOptions(
        model=model,
        system_prompt=load_skill(role),
        cwd=str(PROJECT_DIR),
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
        permission_mode="acceptEdits",
        max_turns=50,
    )


def _log_input_summary(files: dict[str, list[str]]) -> None:
    """발견된 입력 파일 목록을 로그로 출력한다."""
    total = sum(len(v) for v in files.values())
    _log(f"입력 자료 {total}개 발견")
    labels = {"book": "교재 스캔본(이미지)", "note": "강의노트(PDF)", "stt": "STT(텍스트)"}
    for key, paths in files.items():
        if paths:
            _log(f"  {labels[key]}: {len(paths)}개")
            for p in paths:
                _log(f"    · {Path(p).name}")
        else:
            _log(f"  {labels[key]}: 없음")


async def run_role(role: str, extra: str = "", prompt_override: str | None = None) -> str:
    """단일 역할을 claude_agent_sdk query()로 실행한다."""
    _ensure_sdk_available()

    try:
        prompt = prompt_override if prompt_override is not None else build_prompt(role, extra)
    except ValueError as e:
        raise HarnessError(str(e)) from e

    _log(f"▶ {role} 시작")
    start = time.monotonic()

    result_text = ""

    async for msg in query(prompt=prompt, options=make_options(role)):
        if isinstance(msg, SystemMessage) and msg.subtype == "init":
            pass
        elif isinstance(msg, ResultMessage):
            result_text = msg.result or ""
            elapsed = time.monotonic() - start
            if msg.is_error:
                _log_error(f"✗ {role} 실패 ({elapsed:.0f}s) — {msg.subtype}")
                if msg.errors:
                    for e in msg.errors:
                        _log_error(f"  {e}")
                raise HarnessError(f"{role} 실패: {msg.subtype}")
            _log(
                f"✓ {role} 완료 ({elapsed:.0f}s, "
                f"turns={msg.num_turns}, "
                f"cost=${msg.total_cost_usd or 0:.4f})"
            )

    return result_text


async def run_gan_loop(max_rounds: int = 3, start_step: str = "p1g") -> bool:
    """Generator ↔ Reviewer 2단계 루프 (Phase 1: 이론 / Phase 2: 예상 결과 값). PASS 시 True 반환.

    start_step 값:
      p1g  Phase 1 생성부터 (기본값)
      p1r  Phase 1 검토부터 (1라운드에서 pre-generator 건너뜀)
      p2g  Phase 2 생성부터 (Phase 1 전체 건너뜀)
      p2r  Phase 2 검토부터 (Phase 1 전체 건너뜀, 2라운드에서 pre-generator 건너뜀)
    """
    review_theory_path = OUTPUT_DIR / "pre_review_theory.md"
    review_calc_path = OUTPUT_DIR / "pre_review.md"

    # ── Phase 1: 실험 목적·준비물·이론 ─────────────────────────────────
    if start_step not in ("p2g", "p2r"):
        _log("── Phase 1: 실험 목적·준비물·이론 ──")
        for round_num in range(1, max_rounds + 1):
            _log(f"── Phase 1 라운드 {round_num}/{max_rounds} ──")

            p1_extra = ""
            if round_num > 1:
                archive = OUTPUT_DIR / f"pre_review_theory_round{round_num - 1}.md"
                archived_path = _archive_if_exists(review_theory_path, archive)
                if archived_path is not None:
                    _log(f"pre_review_theory.md → {archived_path.name}")
                fail_summary = extract_fail_items(archived_path).strip() if archived_path is not None else ""
                p1_extra = (
                    f"재작업 모드. {round_num}번째 시도. "
                    f"이전 이론 검토에서 발견된 문제:\n{fail_summary}"
                )

            skip_gen = (start_step == "p1r") and round_num == 1
            if not skip_gen:
                await run_role("pre-generator", p1_extra)
            await run_role("pre-reviewer", prompt_override=_build_pre_reviewer_phase1_prompt(p1_extra))

            verdict = parse_review_verdict(review_theory_path)
            _log(f"Phase 1 판정: {verdict}")

            if verdict == "PASS":
                _log("Phase 1 PASS — 이론 섹션 확정")
                break

            if round_num == max_rounds:
                _log_error(f"Phase 1 {max_rounds}라운드 후 FAIL — 수동 검토 필요")
                return False
    else:
        _log("── Phase 1 건너뜀 (start_step: {start_step}) ──".format(start_step=start_step))

    # ── Phase 2: 예상 결과 값 ──────────────────────────────────────────
    _log("── Phase 2: 예상 결과 값 ──")
    for round_num in range(1, max_rounds + 1):
        _log(f"── Phase 2 라운드 {round_num}/{max_rounds} ──")

        p2_extra = ""
        if round_num > 1:
            archive = OUTPUT_DIR / f"pre_review_round{round_num - 1}.md"
            archived_path = _archive_if_exists(review_calc_path, archive)
            if archived_path is not None:
                _log(f"pre_review.md → {archived_path.name}")
            fail_summary = extract_fail_items(archived_path).strip() if archived_path is not None else ""
            p2_extra = (
                f"재작업 모드. {round_num}번째 시도. "
                f"이전 검토에서 발견된 KVL/KCL 오류:\n{fail_summary}"
            )

        skip_gen = (start_step == "p2r") and round_num == 1
        if not skip_gen:
            await run_role("pre-generator", prompt_override=_build_pre_generator_phase2_prompt(p2_extra))
        await run_role("pre-reviewer", prompt_override=_build_pre_reviewer_prompt(p2_extra))

        verdict = parse_review_verdict(review_calc_path)
        _log(f"Phase 2 판정: {verdict}")

        if verdict == "PASS":
            _log("GAN 루프 PASS — 예비보고서 확정 (Phase 1+2)")
            return True

        if round_num == max_rounds:
            _log_error(f"Phase 2 {max_rounds}라운드 후 FAIL — 수동 검토 필요")
            return False

    return False


async def run_result_loop(max_rounds: int = 3, start_step: str = "p1g") -> bool:
    """result-generator ↔ result-reviewer 2단계 루프 (Phase 1: 실험 결과 / Phase 2: 고찰). PASS 시 True 반환.

    start_step 값:
      p1g  Phase 1 생성부터 (기본값)
      p1r  Phase 1 검토부터 (1라운드에서 result-generator 건너뜀)
      p2g  Phase 2 생성부터 (Phase 1 전체 건너뜀)
      p2r  Phase 2 검토부터 (Phase 1 전체 건너뜀, 1라운드에서 result-generator 건너뜀)
    """
    review_data_path = OUTPUT_DIR / "result_review_data.md"
    review_path = OUTPUT_DIR / "result_review.md"

    # ── Phase 1: 실험 결과 ──────────────────────────────────────────────
    if start_step not in ("p2g", "p2r"):
        _log("── 결과보고서 Phase 1: 실험 결과 ──")
        for round_num in range(1, max_rounds + 1):
            _log(f"── Phase 1 라운드 {round_num}/{max_rounds} ──")

            p1_extra = ""
            if round_num > 1:
                archive = OUTPUT_DIR / f"result_review_data_round{round_num - 1}.md"
                archived_path = _archive_if_exists(review_data_path, archive)
                if archived_path is not None:
                    _log(f"result_review_data.md → {archived_path.name}")
                fail_summary = extract_fail_items(archived_path).strip() if archived_path is not None else ""
                p1_extra = (
                    f"재작업 모드. {round_num}번째 시도. "
                    f"이전 검토에서 발견된 오류:\n{fail_summary}"
                )

            skip_gen = (start_step == "p1r") and round_num == 1
            if not skip_gen:
                await run_role("result-generator", p1_extra)
            await run_role("result-reviewer", prompt_override=_build_result_reviewer_phase1_prompt(p1_extra))

            verdict = parse_review_verdict(review_data_path)
            _log(f"Phase 1 판정: {verdict}")

            if verdict == "PASS":
                _log("Phase 1 PASS — 실험 결과 확정")
                break

            if round_num == max_rounds:
                _log_error(f"Phase 1 {max_rounds}라운드 후 FAIL — 수동 검토 필요")
                return False
    else:
        _log("── 결과보고서 Phase 1 건너뜀 (start_step: {start_step}) ──".format(start_step=start_step))

    # ── Phase 2: 고찰 ──────────────────────────────────────────────────
    _log("── 결과보고서 Phase 2: 고찰 ──")
    for round_num in range(1, max_rounds + 1):
        _log(f"── Phase 2 라운드 {round_num}/{max_rounds} ──")

        p2_extra = ""
        if round_num > 1:
            archive = OUTPUT_DIR / f"result_review_round{round_num - 1}.md"
            archived_path = _archive_if_exists(review_path, archive)
            if archived_path is not None:
                _log(f"result_review.md → {archived_path.name}")
            fail_summary = extract_fail_items(archived_path).strip() if archived_path is not None else ""
            p2_extra = (
                f"재작업 모드. {round_num}번째 시도. "
                f"이전 고찰 검토에서 발견된 문제:\n{fail_summary}"
            )

        skip_gen = (start_step == "p2r") and round_num == 1
        if not skip_gen:
            await run_role("result-generator", prompt_override=_build_result_generator_phase2_prompt(p2_extra))
        await run_role("result-reviewer", prompt_override=_build_result_reviewer_phase2_prompt(p2_extra))

        verdict = parse_review_verdict(review_path)
        _log(f"Phase 2 판정: {verdict}")

        if verdict == "PASS":
            _log("결과보고서 루프 PASS — 결과보고서 확정 (Phase 1+2)")
            return True

        if round_num == max_rounds:
            _log_error(f"Phase 2 {max_rounds}라운드 후 FAIL — 수동 검토 필요")
            return False

    return False


async def run_pipeline(
    from_role: str,
    to_role: str,
    max_rounds: int,
    dry_run: bool,
    start_step: str = "p1g",
) -> None:
    """from_role 부터 to_role 까지 하네스 파이프라인을 실행한다."""
    if from_role not in ROLE_ORDER:
        raise HarnessError(f"알 수 없는 역할: {from_role}")
    if to_role not in ROLE_ORDER:
        raise HarnessError(f"알 수 없는 역할: {to_role}")

    start_idx = ROLE_ORDER.index(from_role)
    end_idx = ROLE_ORDER.index(to_role)
    if start_idx > end_idx:
        raise HarnessError(f"--from ({from_role})이 --to ({to_role}) 이후입니다")

    roles = ROLE_ORDER[start_idx : end_idx + 1]

    if dry_run:
        print("실행 경로:", " → ".join(roles))
        has_pre_gan = "pre-generator" in roles and "pre-reviewer" in roles
        has_result_gan = "result-generator" in roles and "result-reviewer" in roles
        if has_pre_gan:
            print("예비보고서 2단계: Phase 1 (이론) + Phase 2 (예상 결과 값)")
        if has_result_gan:
            print("결과보고서 2단계: Phase 1 (실험 결과) + Phase 2 (고찰)")
        if has_pre_gan or has_result_gan:
            print(f"최대 GAN 라운드 (Phase당): {max_rounds}")
            print(f"시작 스텝: {start_step}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    # result-side 사전 검증
    if "result-generator" in roles:
        pre_reports = _find_pre_reports()
        if not pre_reports:
            raise HarnessError(
                "예비보고서가 없습니다. 먼저 pre-generator 또는 pre-reviewer를 실행하세요."
            )
        measurements = _find_measurements()
        if not measurements:
            raise HarnessError(
                f"측정값 파일이 없습니다. {INPUT_DIR}/ 에 *측정값.md 파일을 추가하세요."
            )
    elif roles == ["result-reviewer"]:
        result_reports = _find_result_reports()
        if not result_reports:
            raise HarnessError(
                "결과보고서가 없습니다. 먼저 result-generator를 실행하여 결과보고서를 생성하세요."
            )

    _log(f"파이프라인 시작: {' → '.join(roles)}")
    pipeline_start = time.monotonic()

    # pre-generator가 포함된 경우 입력 파일 목록 출력
    if "pre-generator" in roles:
        _log_input_summary(collect_docx_files())

    i = 0
    while i < len(roles):
        role = roles[i]

        # pre GAN 루프 구간: pre-generator와 pre-reviewer가 모두 포함된 경우
        if role == "pre-generator" and "pre-reviewer" in roles[i:]:
            success = await run_gan_loop(max_rounds=max_rounds, start_step=start_step)
            if not success:
                _log_error("예비보고서 GAN 루프 실패. 파이프라인 중단.")
                sys.exit(1)
            reviewer_idx = roles.index("pre-reviewer", i)
            i = reviewer_idx + 1
            continue

        # result 루프 구간: result-generator와 result-reviewer가 모두 포함된 경우
        if role == "result-generator" and "result-reviewer" in roles[i:]:
            success = await run_result_loop(max_rounds=max_rounds, start_step=start_step)
            if not success:
                _log_error("결과보고서 루프 실패. 파이프라인 중단.")
                sys.exit(1)
            reviewer_idx = roles.index("result-reviewer", i)
            i = reviewer_idx + 1
            continue

        prompt_override = None
        result_review_path = OUTPUT_DIR / "result_review.md"

        if role == "result-reviewer" and roles == ["result-reviewer"]:
            prompt_override, result_review_path, mode = _select_result_reviewer_prompt()
            _log(f"result-reviewer 단독 실행 자동 모드: {mode} ({result_review_path.name})")

        await run_role(role, prompt_override=prompt_override)

        # 단독 실행 시 판정 파싱 (GAN 루프 외부)
        if role == "pre-reviewer":
            verdict = parse_review_verdict(OUTPUT_DIR / "pre_review.md")
            if verdict == "FAIL":
                _log_error("pre-reviewer FAIL — 예비보고서에 오류가 있습니다. pre_review.md를 확인하세요.")
                sys.exit(1)
            if verdict == "UNKNOWN":
                _log_error("pre-reviewer 판정 미확인 — pre_review.md에 '최종 판정' 줄이 없습니다.")
                sys.exit(1)

        if role == "result-reviewer":
            verdict = parse_review_verdict(result_review_path)
            if verdict == "FAIL":
                _log_error(
                    f"result-reviewer FAIL — 결과보고서에 오류가 있습니다. {result_review_path.name}를 확인하세요."
                )
                sys.exit(1)
            if verdict == "UNKNOWN":
                _log_error(
                    f"result-reviewer 판정 미확인 — {result_review_path.name}에 '최종 판정' 줄이 없습니다."
                )
                sys.exit(1)

        i += 1

    elapsed = time.monotonic() - pipeline_start
    _log(f"파이프라인 완료 ({elapsed:.0f}s)")

