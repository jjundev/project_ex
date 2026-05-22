from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Callable

from .config import (
    DEFAULT_MODEL_PRESET,
    INPUT_DIR,
    MODEL_ALIASES,
    MODEL_PRESETS,
    ModelAlias,
    ModelPreset,
    OUTPUT_DIR,
    PROJECT_DIR,
    ROLE_ORDER,
    SKILL_PATHS,
    alias_for_role,
    role_to_category,
)
from .io_state import (
    _archive_if_exists,
    _find_measurements,
    _find_pre_reports,
    _find_result_reports,
    _has_discussion_section,
    _has_exercise_section,
    _has_expected_values_section,
    _has_pre_phase1_sections,
    _has_result_data_section,
    _latest_pre_report,
    _latest_result_report,
    _latest_review_file,
    collect_docx_files,
    extract_fail_items,
    parse_review_verdict,
)
from .prompts import (
    _build_pre_generator_phase2_prompt,
    _build_pre_reviewer_phase1_prompt,
    _build_pre_reviewer_prompt,
    _build_result_generator_phase1_prompt,
    _build_result_generator_phase2_prompt,
    _build_result_generator_phase3_prompt,
    _build_result_reviewer_phase1_prompt,
    _build_result_reviewer_phase2_prompt,
    _build_result_reviewer_phase3_prompt,
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

# 활성 preset (run_pipeline 진입 시 설정)
_ACTIVE_PRESET: ModelPreset = MODEL_PRESETS[DEFAULT_MODEL_PRESET]


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


def make_options(role: str, model: str) -> ClaudeAgentOptions:
    """역할에 맞는 ClaudeAgentOptions를 반환한다."""
    _ensure_sdk_available()

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
    labels = {
        "book": "교재 스캔본(이미지)",
        "note": "강의노트(PDF)",
        "stt": "STT(텍스트)",
        "exercise": "연습 문제(이미지/PDF/MD)",
    }
    for key, paths in files.items():
        label = labels.get(key, key)
        if paths:
            _log(f"  {label}: {len(paths)}개")
            for p in paths:
                _log(f"    · {Path(p).name}")
        else:
            _log(f"  {label}: 없음")


async def run_role(role: str, extra: str = "", prompt_override: str | None = None) -> str:
    """활성 preset에서 role의 카테고리를 보고 provider를 결정해 분기한다."""
    try:
        prompt = prompt_override if prompt_override is not None else build_prompt(role, extra)
    except ValueError as e:
        raise HarnessError(str(e)) from e

    try:
        alias = alias_for_role(_ACTIVE_PRESET, role)
    except ValueError as e:
        raise HarnessError(str(e)) from e

    if alias.provider == "claude":
        return await _run_role_claude(role, prompt, alias.model_id)
    if alias.provider == "codex":
        return await _run_role_codex(role, prompt, alias.model_id, alias.reasoning or "high")
    raise HarnessError(f"알 수 없는 provider: {alias.provider}")


async def _run_role_claude(role: str, prompt: str, model: str) -> str:
    """Claude Agent SDK 경로로 단일 역할을 실행한다."""
    _ensure_sdk_available()

    _log(f"▶ {role} 시작")
    start = time.monotonic()

    result_text = ""

    async for msg in query(prompt=prompt, options=make_options(role, model)):
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


async def _run_role_codex(role: str, prompt: str, model: str, reasoning: str) -> str:
    """Codex Python SDK 경로로 단일 역할을 실행한다."""
    try:
        from codex_app_server import AppServerConfig, AskForApproval, AsyncCodex, SandboxMode
    except ModuleNotFoundError as e:
        raise HarnessError(_codex_install_help()) from e

    _log(f"▶ {role} 시작")
    start = time.monotonic()

    cfg = AppServerConfig(codex_bin=_resolve_codex_bin())
    async with AsyncCodex(config=cfg) as codex:
        thread = await codex.thread_start(
            model=model,
            cwd=str(PROJECT_DIR),
            developer_instructions=load_skill(role),
            approval_policy=AskForApproval.model_validate("never"),
            sandbox=SandboxMode.workspace_write,
            config={"model_reasoning_effort": reasoning},
        )
        result = await thread.run(prompt)

    elapsed = time.monotonic() - start
    final = (result.final_response or "").strip()

    usage = result.usage
    usage_str = ""
    if usage is not None and usage.total is not None:
        usage_str = f", in:{usage.total.input_tokens} out:{usage.total.output_tokens}"

    _log(f"✓ {role} 완료 ({elapsed:.0f}s, codex{usage_str})")
    return final


def _codex_install_help() -> str:
    return (
        "Codex Python SDK를 import할 수 없습니다. 다음을 확인하세요:\n"
        "  1. Python 3.10+ 사용\n"
        "  2. pip install -r requirements-codex.txt\n"
        "  3. codex login (ChatGPT 로그인)\n"
        "  4. 우회 옵션: --model-preset claude-default"
    )


def _resolve_codex_bin() -> str:
    """시스템 codex CLI 바이너리 경로를 검출한다.

    검출 우선순위:
      1. 환경변수 CODEX_BIN
      2. %LOCALAPPDATA%\\OpenAI\\Codex\\bin\\codex.exe (Windows 표준 설치 위치)
      3. PATH 에서 'codex' 검색
    """
    import os
    import shutil

    env = os.environ.get("CODEX_BIN")
    if env and Path(env).exists():
        return env

    if sys.platform.startswith("win"):
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            candidate = Path(local_app) / "OpenAI" / "Codex" / "bin" / "codex.exe"
            if candidate.exists():
                return str(candidate)

    on_path = shutil.which("codex")
    if on_path:
        return on_path

    raise HarnessError(
        "Codex CLI 바이너리를 찾을 수 없습니다. 다음 중 하나로 해결:\n"
        "  1. Codex Desktop 또는 codex CLI 설치 (https://github.com/openai/codex)\n"
        "  2. CODEX_BIN 환경변수에 codex.exe 절대 경로 지정\n"
        "  3. PATH 에 codex 가 보이도록 설정\n"
        "  4. 우회 옵션: --model-preset claude-default"
    )


async def _codex_healthcheck(
    preset: ModelPreset,
    roles: list[str],
    *,
    timeout: float = 30.0,
) -> None:
    """활성 roles 중 codex provider가 하나라도 있으면 환경을 짧게 검증한다."""
    codex_aliases = [
        alias_for_role(preset, r) for r in roles
        if alias_for_role(preset, r).provider == "codex"
    ]
    if not codex_aliases:
        return

    try:
        from codex_app_server import AppServerConfig, AskForApproval, AsyncCodex, SandboxMode
    except ModuleNotFoundError as e:
        raise HarnessError(_codex_install_help()) from e

    # 첫 codex role의 모델로 ping
    model = codex_aliases[0].model_id
    cfg = AppServerConfig(codex_bin=_resolve_codex_bin())

    async def _ping() -> None:
        async with AsyncCodex(config=cfg) as codex:
            thread = await codex.thread_start(
                model=model,
                cwd=str(PROJECT_DIR),
                approval_policy=AskForApproval.model_validate("never"),
                sandbox=SandboxMode.read_only,
            )
            await thread.run("Reply with the single word: ok")

    try:
        await asyncio.wait_for(_ping(), timeout=timeout)
    except asyncio.TimeoutError as e:
        raise HarnessError(
            f"Codex preflight 30초 timeout. {_codex_install_help()}"
        ) from e
    except HarnessError:
        raise
    except Exception as e:
        raise HarnessError(
            f"Codex preflight 실패: {type(e).__name__}: {e}\n{_codex_install_help()}"
        ) from e

    _log(f"Codex preflight OK (model={model})")


def _consume_previous_review(
    review_path: Path,
    round_num: int,
    archive_basename_template: str,
    pass_skip_precondition: Callable[[], bool] | None = None,
) -> tuple[str, bool]:
    """라운드 시작 시 이전 review 파일을 처리한다.

    Round 1 (새 실행의 첫 라운드):
      - active/archive review 파일 없음 → ("", False), fresh start (기존 동작과 동일).
      - PASS + precondition() True → ("", True), phase 전체 skip 신호 (이전 실행에서 완료).
      - PASS + precondition() False → 보고서 상태가 review와 불일치 (상위 phase 재실행 등).
                                       active는 archive 후, archive는 유지 후 ("", False)로 진행.
      - FAIL / UNKNOWN → active는 archive (_round0) 후, archive는 유지 후 review 본문을
                         FAIL summary로 반환.

    Round ≥ 2: 기존 동작. review_path를 `_round{N-1}.md`로 archive하고 본문을 반환.

    archive_basename_template: e.g. ``"pre_review_theory_round{}.md"``.
    pass_skip_precondition: PASS-skip을 허용하기 전에 보고서가 해당 phase 결과물(섹션)을
        실제로 가지고 있는지 확인하는 콜러블. None이면 항상 허용.
    """
    if round_num == 1:
        archive_glob = archive_basename_template.format("*")
        previous_review = _latest_review_file(review_path, archive_glob)
        if previous_review is None:
            return ("", False)

        verdict = parse_review_verdict(previous_review)

        if verdict == "PASS":
            if pass_skip_precondition is None or pass_skip_precondition():
                _log(f"{previous_review.name}: 이전 실행 PASS — phase 건너뜀 (인계)")
                return ("", True)
            archived = previous_review
            if previous_review == review_path:
                archive_path = OUTPUT_DIR / archive_basename_template.format(0)
                archived = _archive_if_exists(review_path, archive_path)
            if archived is not None:
                action = (
                    f"{archived.name}로 보관"
                    if previous_review == review_path
                    else f"{archived.name} 유지"
                )
                _log(
                    f"{previous_review.name}: PASS이지만 보고서 섹션 누락 — "
                    f"{action} 후 fresh start"
                )
            return ("", False)

        # FAIL or UNKNOWN: archive and feed body back as rework guidance
        archived = previous_review
        if previous_review == review_path:
            archive_path = OUTPUT_DIR / archive_basename_template.format(0)
            archived = _archive_if_exists(review_path, archive_path)
        if archived is not None:
            if previous_review == review_path:
                _log(
                    f"{review_path.name} → {archived.name} "
                    f"(이전 실행 인계, verdict={verdict})"
                )
            else:
                _log(f"{archived.name} 인계 (verdict={verdict})")
        fail_summary = extract_fail_items(archived).strip() if archived else ""
        return (fail_summary, False)

    # round_num >= 2: archive current active review as _round{N-1} (existing behavior)
    archive_path = OUTPUT_DIR / archive_basename_template.format(round_num - 1)
    archived = _archive_if_exists(review_path, archive_path)
    if archived is not None:
        _log(f"{review_path.name} → {archived.name}")
    fail_summary = extract_fail_items(archived).strip() if archived else ""
    return (fail_summary, False)


def _format_rework_extra(round_num: int, label: str, fail_summary: str) -> str:
    """rework 모드용 generator/reviewer extra 문자열을 만든다."""
    if round_num == 1:
        prefix = "재작업 모드 (이전 실행에서 인계)."
    else:
        prefix = f"재작업 모드. {round_num}번째 시도."
    return f"{prefix} {label}:\n{fail_summary}"


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
        phase1_skipped_from_pass = False
        for round_num in range(1, max_rounds + 1):
            fail_summary, skip_phase = _consume_previous_review(
                review_theory_path,
                round_num,
                "pre_review_theory_round{}.md",
                pass_skip_precondition=lambda: (
                    (latest := _latest_pre_report(output_dir=OUTPUT_DIR)) is not None
                    and _has_pre_phase1_sections(latest)
                ),
            )
            if skip_phase:
                phase1_skipped_from_pass = True
                break

            _log(f"── Phase 1 라운드 {round_num}/{max_rounds} ──")

            p1_extra = (
                _format_rework_extra(round_num, "이전 이론 검토에서 발견된 문제", fail_summary)
                if fail_summary
                else ""
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

        if phase1_skipped_from_pass:
            _log("Phase 1 — 이전 실행에서 PASS 인계, 건너뜀")
    else:
        _log("── Phase 1 건너뜀 (start_step: {start_step}) ──".format(start_step=start_step))

    # ── Phase 2: 예상 결과 값 ──────────────────────────────────────────
    _log("── Phase 2: 예상 결과 값 ──")

    def _pre_phase2_precondition() -> bool:
        latest = _latest_pre_report(output_dir=OUTPUT_DIR)
        return latest is not None and _has_expected_values_section(latest)

    for round_num in range(1, max_rounds + 1):
        fail_summary, skip_phase = _consume_previous_review(
            review_calc_path,
            round_num,
            "pre_review_round{}.md",
            pass_skip_precondition=_pre_phase2_precondition,
        )
        if skip_phase:
            _log("Phase 2 — 이전 실행에서 PASS 인계, 건너뜀")
            _log("GAN 루프 PASS — 예비보고서 확정 (Phase 1+2)")
            return True

        _log(f"── Phase 2 라운드 {round_num}/{max_rounds} ──")

        p2_extra = (
            _format_rework_extra(round_num, "이전 검토에서 발견된 KVL/KCL 오류", fail_summary)
            if fail_summary
            else ""
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
    """result-generator ↔ result-reviewer 3단계 루프. PASS 시 True 반환.

    Phase 1 = 실험 결과 (result_review_data.md)
    Phase 2 = 연습 문제 (result_review_exercise.md), input/exercise/ 비어있으면 skip
    Phase 3 = 고찰 (result_review.md)

    start_step 값:
      p1g  Phase 1 생성부터 (기본값)
      p1r  Phase 1 검토부터 (1라운드에서 result-generator 건너뜀)
      p2g  Phase 2 생성부터 (Phase 1 전체 건너뜀)
      p2r  Phase 2 검토부터 (Phase 1 전체 건너뜀, 1라운드에서 result-generator 건너뜀)
      p3g  Phase 3 생성부터 (Phase 1·2 전체 건너뜀)
      p3r  Phase 3 검토부터 (Phase 1·2 전체 건너뜀, 1라운드에서 result-generator 건너뜀)
    """
    review_data_path = OUTPUT_DIR / "result_review_data.md"
    review_exercise_path = OUTPUT_DIR / "result_review_exercise.md"
    review_path = OUTPUT_DIR / "result_review.md"

    # ── Phase 1: 실험 결과 ──────────────────────────────────────────────
    if start_step in ("p1g", "p1r"):
        _log("── 결과보고서 Phase 1: 실험 결과 ──")
        phase1_skipped_from_pass = False
        for round_num in range(1, max_rounds + 1):
            fail_summary, skip_phase = _consume_previous_review(
                review_data_path,
                round_num,
                "result_review_data_round{}.md",
                pass_skip_precondition=lambda: (
                    (latest := _latest_result_report(output_dir=OUTPUT_DIR)) is not None
                    and _has_result_data_section(latest)
                ),
            )
            if skip_phase:
                phase1_skipped_from_pass = True
                break

            _log(f"── Phase 1 라운드 {round_num}/{max_rounds} ──")

            p1_extra = (
                _format_rework_extra(round_num, "이전 검토에서 발견된 오류", fail_summary)
                if fail_summary
                else ""
            )

            skip_gen = (start_step == "p1r") and round_num == 1
            if not skip_gen:
                await run_role("result-generator", prompt_override=_build_result_generator_phase1_prompt(p1_extra))
            await run_role("result-reviewer", prompt_override=_build_result_reviewer_phase1_prompt(p1_extra))

            verdict = parse_review_verdict(review_data_path)
            _log(f"Phase 1 판정: {verdict}")

            if verdict == "PASS":
                _log("Phase 1 PASS — 실험 결과 확정")
                break

            if round_num == max_rounds:
                _log_error(f"Phase 1 {max_rounds}라운드 후 FAIL — 수동 검토 필요")
                return False

        if phase1_skipped_from_pass:
            _log("결과보고서 Phase 1 — 이전 실행에서 PASS 인계, 건너뜀")
    else:
        _log(f"── 결과보고서 Phase 1 건너뜀 (start_step: {start_step}) ──")

    # ── Phase 2: 연습 문제 ─────────────────────────────────────────────
    exercise_files = collect_docx_files()["exercise"]
    if start_step in ("p3g", "p3r"):
        _log(f"── 결과보고서 Phase 2 건너뜀 (start_step: {start_step}) ──")
    elif not exercise_files:
        if start_step in ("p2g", "p2r"):
            _log_error(
                f"--start-step {start_step}로 Phase 2(연습 문제) 진입을 요청했지만 "
                f"input/exercise/ 폴더에 자료가 없습니다."
            )
            return False
        _log("── 연습 문제 자료 없음 — Phase 2 건너뜀 (exercise-skip) ──")
    else:
        _log("── 결과보고서 Phase 2: 연습 문제 ──")

        def _result_phase2_precondition() -> bool:
            latest = _latest_result_report(output_dir=OUTPUT_DIR)
            return latest is not None and _has_exercise_section(latest)

        phase2_skipped_from_pass = False
        for round_num in range(1, max_rounds + 1):
            fail_summary, skip_phase = _consume_previous_review(
                review_exercise_path,
                round_num,
                "result_review_exercise_round{}.md",
                pass_skip_precondition=_result_phase2_precondition,
            )
            if skip_phase:
                phase2_skipped_from_pass = True
                break

            _log(f"── Phase 2 라운드 {round_num}/{max_rounds} ──")

            p2_extra = (
                _format_rework_extra(round_num, "이전 연습 문제 검토에서 발견된 문제", fail_summary)
                if fail_summary
                else ""
            )

            skip_gen = (start_step == "p2r") and round_num == 1
            if not skip_gen:
                await run_role("result-generator", prompt_override=_build_result_generator_phase2_prompt(p2_extra))
            await run_role("result-reviewer", prompt_override=_build_result_reviewer_phase2_prompt(p2_extra))

            verdict = parse_review_verdict(review_exercise_path)
            _log(f"Phase 2 판정: {verdict}")

            if verdict == "PASS":
                _log("Phase 2 PASS — 연습 문제 확정")
                break

            if round_num == max_rounds:
                _log_error(f"Phase 2 {max_rounds}라운드 후 FAIL — 수동 검토 필요")
                return False

        if phase2_skipped_from_pass:
            _log("결과보고서 Phase 2 — 이전 실행에서 PASS 인계, 건너뜀")

    # ── Phase 3: 고찰 ──────────────────────────────────────────────────
    _log("── 결과보고서 Phase 3: 고찰 ──")

    def _result_phase3_precondition() -> bool:
        latest = _latest_result_report(output_dir=OUTPUT_DIR)
        return latest is not None and _has_discussion_section(latest)

    for round_num in range(1, max_rounds + 1):
        fail_summary, skip_phase = _consume_previous_review(
            review_path,
            round_num,
            "result_review_round{}.md",
            pass_skip_precondition=_result_phase3_precondition,
        )
        if skip_phase:
            _log("결과보고서 Phase 3 — 이전 실행에서 PASS 인계, 건너뜀")
            _log("결과보고서 루프 PASS — 결과보고서 확정 (Phase 1+2+3)")
            return True

        _log(f"── Phase 3 라운드 {round_num}/{max_rounds} ──")

        p3_extra = (
            _format_rework_extra(round_num, "이전 고찰 검토에서 발견된 문제", fail_summary)
            if fail_summary
            else ""
        )

        skip_gen = (start_step == "p3r") and round_num == 1
        if not skip_gen:
            await run_role("result-generator", prompt_override=_build_result_generator_phase3_prompt(p3_extra))
        await run_role("result-reviewer", prompt_override=_build_result_reviewer_phase3_prompt(p3_extra))

        verdict = parse_review_verdict(review_path)
        _log(f"Phase 3 판정: {verdict}")

        if verdict == "PASS":
            _log("결과보고서 루프 PASS — 결과보고서 확정 (Phase 1+2+3)")
            return True

        if round_num == max_rounds:
            _log_error(f"Phase 3 {max_rounds}라운드 후 FAIL — 수동 검토 필요")
            return False

    return False


def _validate_start_step_against_roles(start_step: str, roles: list[str]) -> None:
    """start_step이 활성 roles의 첫 GAN loop에 의미있는 값인지 검증한다.

    p3g/p3r 은 result-side 전용 phase로, pre-side가 먼저 도는 chain에서는 무효.
    """
    first_gan_loop_kind: str | None = None
    if "pre-generator" in roles and "pre-reviewer" in roles:
        first_gan_loop_kind = "pre"
    elif "result-generator" in roles and "result-reviewer" in roles:
        first_gan_loop_kind = "result"

    if first_gan_loop_kind == "pre" and start_step in ("p3g", "p3r"):
        raise HarnessError(
            f"--start-step {start_step} 은 result-loop 전용입니다. "
            f"예비보고서 loop는 p1/p2 단계만 가집니다."
        )


def _format_alias_line(category: str, alias_name: str, alias: ModelAlias) -> str:
    """카테고리별 모델 alias 한 줄 포맷."""
    pad = "generator" if category == "generator" else "reviewer "
    suffix = f", reasoning={alias.reasoning}" if alias.reasoning else ""
    return f"  {pad}: {alias_name:<8} [{alias.provider}/{alias.model_id}{suffix}]"


def _print_dry_run_summary(
    *,
    roles: list[str],
    preset: ModelPreset,
    preset_name: str,
    overrides: dict[str, str],
    max_rounds: int,
    start_step: str,
) -> None:
    """dry-run 모드에서 카테고리 단위 요약을 출력한다."""
    print("실행 경로:", " → ".join(roles))

    if overrides:
        ov_str = ", ".join(f"{k}={v}" for k, v in overrides.items())
        print(f"preset: {preset_name} (overrides: {ov_str})")
    else:
        print(f"preset: {preset_name}")

    categories_in_play = {role_to_category(r) for r in roles}
    if "generator" in categories_in_play:
        gen_alias = MODEL_ALIASES[preset.generator]
        print(_format_alias_line("generator", preset.generator, gen_alias))
    if "reviewer" in categories_in_play:
        rev_alias = MODEL_ALIASES[preset.reviewer]
        print(_format_alias_line("reviewer", preset.reviewer, rev_alias))

    has_pre_gan = "pre-generator" in roles and "pre-reviewer" in roles
    has_result_gan = "result-generator" in roles and "result-reviewer" in roles
    if has_pre_gan:
        print("예비보고서 2단계: Phase 1 (이론) + Phase 2 (예상 결과 값)")
    if has_result_gan:
        print("결과보고서 3단계: Phase 1 (실험 결과) + Phase 2 (연습 문제) + Phase 3 (고찰)")
    if has_pre_gan or has_result_gan:
        print(f"최대 GAN 라운드 (Phase당): {max_rounds}")
        print(f"시작 스텝: {start_step}")


async def run_pipeline(
    from_role: str,
    to_role: str,
    max_rounds: int,
    dry_run: bool,
    start_step: str = "p1g",
    preset: ModelPreset | None = None,
    preset_name: str | None = None,
    overrides: dict[str, str] | None = None,
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

    _validate_start_step_against_roles(start_step, roles)

    # 활성 preset 설정 (모듈 전역)
    global _ACTIVE_PRESET
    active_preset = preset if preset is not None else MODEL_PRESETS[DEFAULT_MODEL_PRESET]
    active_name = preset_name or DEFAULT_MODEL_PRESET
    _ACTIVE_PRESET = active_preset

    if dry_run:
        _print_dry_run_summary(
            roles=roles,
            preset=active_preset,
            preset_name=active_name,
            overrides=overrides or {},
            max_rounds=max_rounds,
            start_step=start_step,
        )
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

    # Codex 환경 preflight — 활성 roles 중 codex provider가 하나라도 있을 때만
    codex_aliases = [
        alias_for_role(active_preset, r) for r in roles
        if alias_for_role(active_preset, r).provider == "codex"
    ]
    if codex_aliases:
        _log(f"Codex preflight 실행 중 (model={codex_aliases[0].model_id})...")
        await _codex_healthcheck(active_preset, roles)

    _log(f"파이프라인 시작: {' → '.join(roles)}")
    pipeline_start = time.monotonic()

    # pre-generator 또는 result-generator가 포함된 경우 입력 파일 목록 출력
    if "pre-generator" in roles or "result-generator" in roles:
        _log_input_summary(collect_docx_files())

    # start_step은 활성 chain의 *첫* GAN loop에만 적용한다.
    # 두 loop가 모두 활성이면 두번째 loop는 항상 p1g로 시작 (이전 loop가 완료된 직후).
    start_step_for_next_loop = start_step

    i = 0
    while i < len(roles):
        role = roles[i]

        # pre GAN 루프 구간: pre-generator와 pre-reviewer가 모두 포함된 경우
        if role == "pre-generator" and "pre-reviewer" in roles[i:]:
            success = await run_gan_loop(max_rounds=max_rounds, start_step=start_step_for_next_loop)
            start_step_for_next_loop = "p1g"
            if not success:
                _log_error("예비보고서 GAN 루프 실패. 파이프라인 중단.")
                sys.exit(1)
            reviewer_idx = roles.index("pre-reviewer", i)
            i = reviewer_idx + 1
            continue

        # result 루프 구간: result-generator와 result-reviewer가 모두 포함된 경우
        if role == "result-generator" and "result-reviewer" in roles[i:]:
            success = await run_result_loop(max_rounds=max_rounds, start_step=start_step_for_next_loop)
            start_step_for_next_loop = "p1g"
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

