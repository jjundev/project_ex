#!/usr/bin/env python3
"""기초전기실험 보고서 자동화 하네스 — claude_agent_sdk 기반 파이프라인 실행기.

Usage:
    python harness.py [options]

Examples:
    python harness.py
    python harness.py --to pre-reviewer
    python harness.py --from result-generator
    python harness.py --auto --max-rounds 2
    python harness.py --from pre-generator --to pre-generator
    python harness.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, SystemMessage, query

# ---------------------------------------------------------------------------
# 경로 상수
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).parent.resolve()
DOCX_DIR = PROJECT_DIR / "docx"
BOOK_DIR = DOCX_DIR / "book"
NOTE_DIR = DOCX_DIR / "note"
EXPERIMENT_DIR = DOCX_DIR / "experiment"
TEMPLATE_PATH = DOCX_DIR / "template_pre_report.md"
INPUT_DIR = PROJECT_DIR / "input"
OUTPUT_DIR = PROJECT_DIR / "output"
SKILLS_DIR = PROJECT_DIR / "skills"

# ---------------------------------------------------------------------------
# 파이프라인 상수
# ---------------------------------------------------------------------------

ROLE_ORDER = [
    "pre-generator",
    "pre-reviewer",
    "result-generator",
    "result-reviewer",
]

MODEL_OPUS = "claude-opus-4-6"
MODEL_SONNET = "claude-sonnet-4-6"

ROLE_MODELS: dict[str, str] = {
    "pre-generator":    MODEL_OPUS,
    "result-generator": MODEL_OPUS,
}

HUMAN_GATES: dict[str, str] = {
    "pre-reviewer":    "예비보고서 검토 결과를 확인하였습니까? 계속하시겠습니까?",
    "result-reviewer": "결과보고서 검토 결과를 확인하였습니까? 배포를 진행하시겠습니까?",
}

SKILL_PATHS: dict[str, Path] = {
    "pre-generator":    SKILLS_DIR / "pre-report"    / "SKILL.md",
    "pre-reviewer":     SKILLS_DIR / "pre-review"    / "SKILL.md",
    "result-generator": SKILLS_DIR / "result-report" / "SKILL.md",
    "result-reviewer":  SKILLS_DIR / "result-review" / "SKILL.md",
}


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


class HarnessError(Exception):
    """하네스 파이프라인 오류."""


def _log(msg: str) -> None:
    print(f"\033[36m[harness]\033[0m {msg}", flush=True)


def _log_error(msg: str) -> None:
    print(f"\033[31m[harness]\033[0m {msg}", file=sys.stderr, flush=True)


def load_skill(role: str) -> str:
    """역할에 해당하는 SKILL.md를 읽어 system_prompt로 반환한다."""
    path = SKILL_PATHS.get(role)
    if path is None or not path.exists():
        raise HarnessError(f"SKILL.md를 찾을 수 없습니다 — role: '{role}', path: {path}")
    return path.read_text(encoding="utf-8")


def make_options(role: str) -> ClaudeAgentOptions:
    """역할에 맞는 ClaudeAgentOptions를 반환한다."""
    model = ROLE_MODELS.get(role, MODEL_SONNET)
    return ClaudeAgentOptions(
        model=model,
        system_prompt=load_skill(role),
        cwd=str(PROJECT_DIR),
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
        permission_mode="acceptEdits",
        max_turns=50,
    )


def collect_docx_files() -> dict[str, list[str]]:
    """docx/ 하위 파일 목록을 수집하여 반환한다."""
    result: dict[str, list[str]] = {"book": [], "note": [], "experiment": []}
    _IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}
    if BOOK_DIR.exists():
        result["book"] = sorted(
            str(f) for f in BOOK_DIR.glob("*")
            if f.is_file() and f.suffix.lower() in _IMAGE_EXTS
        )
    if NOTE_DIR.exists():
        result["note"] = sorted(str(f) for f in NOTE_DIR.glob("*") if f.is_file())
    if EXPERIMENT_DIR.exists():
        result["experiment"] = sorted(
            str(f) for f in EXPERIMENT_DIR.glob("*.txt") if f.is_file()
        )
    return result


def _log_input_summary(files: dict[str, list[str]]) -> None:
    """발견된 입력 파일 목록을 로그로 출력한다."""
    total = sum(len(v) for v in files.values())
    _log(f"입력 자료 {total}개 발견")
    labels = {"book": "교재 스캔본(이미지)", "note": "강의노트(PDF)", "experiment": "STT(텍스트)"}
    for key, paths in files.items():
        if paths:
            _log(f"  {labels[key]}: {len(paths)}개")
            for p in paths:
                _log(f"    · {Path(p).name}")
        else:
            _log(f"  {labels[key]}: 없음")


def _find_pre_reports() -> list[str]:
    """output/ 에서 예비보고서 파일을 찾는다."""
    if not OUTPUT_DIR.exists():
        return []
    return sorted(str(f) for f in OUTPUT_DIR.glob("*예비보고서.md"))


def _find_measurements() -> list[str]:
    """input/ 에서 측정값 파일을 찾는다."""
    if not INPUT_DIR.exists():
        return []
    return sorted(str(f) for f in INPUT_DIR.glob("*측정값.md"))


def parse_review_verdict(review_path: Path) -> str:
    """검토 파일에서 최종 판정 → PASS / FAIL / UNKNOWN 반환."""
    if not review_path.exists():
        return "UNKNOWN"
    for line in review_path.read_text(encoding="utf-8").splitlines():
        if "최종 판정" in line:
            if "PASS" in line:
                return "PASS"
            if "FAIL" in line:
                return "FAIL"
    return "UNKNOWN"


def extract_fail_items(review_path: Path) -> str:
    """검토 파일에서 FAIL 포함 줄만 추출하여 반환한다."""
    if not review_path.exists():
        return ""
    lines = review_path.read_text(encoding="utf-8").splitlines()
    return "\n".join(l for l in lines if "FAIL" in l)


def human_gate(role: str) -> bool:
    """인간 확인 게이트. True면 계속 진행."""
    prompt_msg = HUMAN_GATES.get(role)
    if not prompt_msg:
        return True
    try:
        print(f"__GATE__ {role}", flush=True)  # GUI 감지용 센티널
        if sys.stdin.isatty():
            resp = input(f"\033[33m[gate]\033[0m [{role}] 완료. {prompt_msg} [y/N] ")
        else:
            resp = input()  # GUI가 프롬프트를 표시하므로 여기선 입력만 받음
        return resp.strip().lower() == "y"
    except (EOFError, KeyboardInterrupt):
        print()
        return False


# ---------------------------------------------------------------------------
# 프롬프트 빌더
# ---------------------------------------------------------------------------


def _build_pre_generator_prompt() -> str:
    files = collect_docx_files()
    book_list = "\n".join(f"  - {f}" for f in files["book"]) or "  (없음)"
    note_list = "\n".join(f"  - {f}" for f in files["note"]) or "  (없음)"
    exp_list = "\n".join(f"  - {f}" for f in files["experiment"]) or "  (없음)"

    return f"""아래 자료를 사용하여 예비보고서를 생성하세요.

## 입력 자료

### 교재 스캔본 (docx/book/) — 이미지 파일
{book_list}

### 강의노트 (docx/note/) — PDF 파일
{note_list}

### 실험 영상 STT (docx/experiment/) — 텍스트 파일, 검증용
{exp_list}

### 템플릿
  - {TEMPLATE_PATH}

## 파일 읽기 방법

- **이미지 (book/)**: Read 도구로 각 파일을 순서대로 읽으세요. 회로도, Table, Procedure가 보입니다.
- **PDF (note/)**: Read 도구로 읽으세요. 10페이지 초과 시 pages 파라미터로 범위를 지정하세요 (예: "1-10").
- **텍스트 (experiment/)**: Read 도구로 읽으세요.

## 지시사항

1. 위 자료를 **모두** 읽으세요. 파일을 건너뛰지 마세요.
2. system prompt에 정의된 Step 1~5를 순서대로 수행하세요.
3. 최종 보고서는 `{OUTPUT_DIR}` 경로에 Markdown 파일로 저장하세요.
4. 파일명 형식: `{{N}}주차_예비보고서.md` (N은 주차 번호).
5. 저장 후 검토 결과를 출력하세요.
"""


def _build_pre_reviewer_prompt(extra: str = "") -> str:
    rework_section = ""
    if extra:
        rework_section = f"\n## 이전 검토 FAIL 항목 (재작업 반영 확인)\n{extra}\n"

    pre_reports = _find_pre_reports()
    pre_list = "\n".join(f"  - {f}" for f in pre_reports) or "  (없음)"

    return f"""생성된 예비보고서를 검토하고 KVL/KCL 검증을 수행하세요.
{rework_section}
## 검토 대상

다음 예비보고서를 읽으세요:
{pre_list}

## 검증 항목

1. **KVL 검증**: 각 폐회로의 전압 합 = 전원전압 확인
2. **KCL 검증**: 각 노드의 전류 보존 확인
3. **단위 일관성**: mA, V, kΩ, μF, s 단위 명시 여부
4. **계산 정확도**: 예상값 Table의 수식 및 수치 검토
5. **STT 교차검증**: `{EXPERIMENT_DIR}` 에 STT 파일이 있으면 측정값과 비교

## 출력 형식

검토 결과를 `{OUTPUT_DIR}/pre_review.md` 에 저장하세요.
파일 형식:

```
## KVL/KCL 검증 결과

### 회로 1
- KVL: [결과]
- KCL: [결과]

### 발견된 오류
- [오류 항목 목록, 없으면 "없음"]

## 최종 판정: PASS
```

마지막 줄은 반드시 `최종 판정: PASS` 또는 `최종 판정: FAIL` 형식으로 끝내세요.
"""


def _build_result_generator_prompt() -> str:
    pre_reports = _find_pre_reports()
    measurements = _find_measurements()
    docx_files = collect_docx_files()

    pre_list = "\n".join(f"  - {f}" for f in pre_reports)
    meas_list = (
        "\n".join(f"  - {f}" for f in measurements)
        if measurements
        else "  (없음 - 사용자에게 입력 요청 필요)"
    )
    exp_list = (
        "\n".join(f"  - {f}" for f in docx_files["experiment"])
        if docx_files["experiment"]
        else "  (없음)"
    )

    return f"""아래 자료를 사용하여 결과보고서를 생성하세요.

## 입력 자료

### 예비보고서
{pre_list}

### 측정값 파일 (input/)
{meas_list}

### 실험 영상 STT (참고용)
{exp_list}

## 지시사항

1. 예비보고서를 읽어 예상값 테이블 구조를 파악하세요.
2. 측정값 파일이 있으면 읽고, 없으면 사용자에게 각 Table별 측정값을 질문하세요.
3. system prompt에 정의된 Step 1~5를 순서대로 수행하세요.
4. 최종 보고서는 `{OUTPUT_DIR}` 경로에 Markdown 파일로 저장하세요.
5. 파일명 형식: `{{N}}주차_결과보고서.md`
"""


def _build_result_reviewer_prompt(extra: str = "") -> str:
    rework_section = ""
    if extra:
        rework_section = f"\n## 이전 검토 FAIL 항목\n{extra}\n"

    return f"""생성된 결과보고서의 오차율 계산을 검증하세요.
{rework_section}
## 검토 대상

`{OUTPUT_DIR}` 경로의 최신 결과보고서 (`*주차_결과보고서.md`)를 읽으세요.

## 검증 항목

1. **오차율 공식**: `|예상값 - 측정값| / 예상값 × 100 (%)` 계산 정확성
2. **예상값 일치**: 결과보고서의 예상값이 예비보고서와 동일한지 확인
3. **오차 원인 분석**: 저항 ±5%, 커패시터 ±10~20% 허용 오차 범위 고려 여부

## 출력 형식

검토 결과를 `{OUTPUT_DIR}/result_review.md` 에 저장하세요.
마지막 줄은 반드시 `최종 판정: PASS` 또는 `최종 판정: FAIL` 형식으로 끝내세요.
"""


def build_prompt(role: str, extra: str = "") -> str:
    if role == "pre-generator":
        return _build_pre_generator_prompt()
    elif role == "pre-reviewer":
        return _build_pre_reviewer_prompt(extra)
    elif role == "result-generator":
        return _build_result_generator_prompt()
    elif role == "result-reviewer":
        return _build_result_reviewer_prompt(extra)
    else:
        raise HarnessError(f"알 수 없는 역할: {role}")


# ---------------------------------------------------------------------------
# 단일 역할 실행
# ---------------------------------------------------------------------------


async def run_role(role: str, extra: str = "") -> str:
    """단일 역할을 claude_agent_sdk query()로 실행한다."""
    prompt = build_prompt(role, extra)
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


# ---------------------------------------------------------------------------
# GAN 루프: pre-generator ↔ pre-reviewer
# ---------------------------------------------------------------------------


async def run_gan_loop(max_rounds: int = 3) -> bool:
    """Generator ↔ Reviewer 루프. PASS 시 True 반환."""
    review_path = OUTPUT_DIR / "pre_review.md"

    for round_num in range(1, max_rounds + 1):
        _log(f"── GAN 라운드 {round_num}/{max_rounds} ──")

        extra = ""
        if round_num > 1:
            archive = OUTPUT_DIR / f"pre_review_round{round_num - 1}.md"
            if review_path.exists():
                review_path.rename(archive)
                _log(f"pre_review.md → {archive.name}")
            fail_summary = extract_fail_items(archive)
            extra = (
                f"재작업 모드. {round_num}번째 시도. "
                f"이전 검토에서 발견된 KVL/KCL 오류:\n{fail_summary}"
            )

        await run_role("pre-generator", extra)
        await run_role("pre-reviewer")

        verdict = parse_review_verdict(review_path)
        _log(f"검토 판정: {verdict}")

        if verdict == "PASS":
            _log("GAN 루프 PASS — 예비보고서 확정")
            return True

        if round_num == max_rounds:
            _log_error(f"GAN 루프 {max_rounds}라운드 후 FAIL — 수동 검토 필요")
            return False

    return False


# ---------------------------------------------------------------------------
# 파이프라인
# ---------------------------------------------------------------------------


async def run_pipeline(
    from_role: str,
    to_role: str,
    auto: bool,
    max_rounds: int,
    dry_run: bool,
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
        if auto:
            print("모드: 완전 자동 (인간 게이트 없음)")
        else:
            gates = [r for r in roles if r in HUMAN_GATES]
            if gates:
                print(f"인간 게이트: {', '.join(gates)}")
        has_gan = "pre-generator" in roles and "pre-reviewer" in roles
        if has_gan:
            print(f"최대 GAN 라운드: {max_rounds}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    # result-side 시작 시 예비보고서 선행 확인
    if from_role in ("result-generator", "result-reviewer"):
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

    _log(f"파이프라인 시작: {' → '.join(roles)}")
    pipeline_start = time.monotonic()

    # pre-generator가 포함된 경우 입력 파일 목록 출력
    if "pre-generator" in roles:
        _log_input_summary(collect_docx_files())

    i = 0
    while i < len(roles):
        role = roles[i]

        # GAN 루프 구간: pre-generator와 pre-reviewer가 모두 포함된 경우
        if role == "pre-generator" and "pre-reviewer" in roles[i:]:
            success = await run_gan_loop(max_rounds=max_rounds)
            if not success:
                _log_error("GAN 루프 실패. 파이프라인 중단.")
                sys.exit(1)
            reviewer_idx = roles.index("pre-reviewer", i)
            i = reviewer_idx + 1
            # GAN 루프 PASS 후 human gate (result-generator 진입 전 확인)
            if not auto and "pre-reviewer" in HUMAN_GATES:
                if not human_gate("pre-reviewer"):
                    _log("사용자에 의해 중단됨.")
                    return
            continue

        await run_role(role)

        # result-reviewer: 판정 파싱 후 FAIL 경고
        if role == "result-reviewer":
            verdict = parse_review_verdict(OUTPUT_DIR / "result_review.md")
            if verdict == "FAIL":
                _log_error("result-reviewer FAIL — 결과보고서에 오류가 있습니다. result_review.md를 확인하세요.")
            elif verdict == "UNKNOWN":
                _log_error("result-reviewer 판정 미확인 — result_review.md에 '최종 판정' 줄이 없습니다.")

        if role in HUMAN_GATES and not auto:
            if not human_gate(role):
                _log("사용자에 의해 중단됨.")
                return

        i += 1

    elapsed = time.monotonic() - pipeline_start
    _log(f"파이프라인 완료 ({elapsed:.0f}s)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="기초전기실험 보고서 자동화 하네스",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--from",
        dest="from_role",
        default=ROLE_ORDER[0],
        choices=ROLE_ORDER,
        help=f"시작 역할 (default: {ROLE_ORDER[0]})",
    )
    parser.add_argument(
        "--to",
        dest="to_role",
        default=ROLE_ORDER[-1],
        choices=ROLE_ORDER,
        help=f"종료 역할 (default: {ROLE_ORDER[-1]})",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="인간 게이트 없이 완전 자동 실행",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=3,
        help="GAN 루프 최대 반복 횟수 (default: 3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실행 경로만 출력하고 실제 실행하지 않음",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        asyncio.run(
            run_pipeline(
                from_role=args.from_role,
                to_role=args.to_role,
                auto=args.auto,
                max_rounds=args.max_rounds,
                dry_run=args.dry_run,
            )
        )
    except HarnessError as e:
        _log_error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        _log("중단됨.")
        sys.exit(130)


if __name__ == "__main__":
    main()
