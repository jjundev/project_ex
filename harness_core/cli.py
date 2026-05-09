from __future__ import annotations

import argparse
import asyncio
import sys

from .config import (
    DEFAULT_MODEL_PRESET,
    MODEL_ALIASES,
    MODEL_PRESETS,
    ModelPreset,
    ROLE_ORDER,
)
from .pipeline import HarnessError, _log, _log_error, run_pipeline

DOC = """기초전기실험 보고서 자동화 하네스 — claude_agent_sdk 기반 파이프라인 실행기.

Usage:
    python harness.py [options]

Examples:
    python harness.py
    python harness.py --to pre-reviewer
    python harness.py --from result-generator
    python harness.py --max-rounds 2
    python harness.py --from pre-generator --to pre-generator
    python harness.py --dry-run
    python harness.py --generator-model opus --reviewer-model gpt-5.5
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="기초전기실험 보고서 자동화 하네스",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=DOC,
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
    parser.add_argument(
        "--start-step",
        dest="start_step",
        default="p1g",
        choices=["p1g", "p1r", "p2g", "p2r"],
        help="GAN 루프 시작 스텝 (p1g: Phase1 생성부터, p1r: Phase1 검토부터, "
             "p2g: Phase2 생성부터, p2r: Phase2 검토부터). default: p1g",
    )
    parser.add_argument(
        "--model-preset",
        dest="model_preset",
        default=DEFAULT_MODEL_PRESET,
        choices=list(MODEL_PRESETS.keys()),
        help=f"모델 프리셋 (default: {DEFAULT_MODEL_PRESET})",
    )
    parser.add_argument(
        "--generator-model",
        dest="generator_model",
        default=None,
        choices=list(MODEL_ALIASES.keys()),
        help="generator 카테고리(pre-generator + result-generator)에 적용할 모델 alias. "
             "지정 시 --model-preset의 generator 항목을 덮어씀.",
    )
    parser.add_argument(
        "--reviewer-model",
        dest="reviewer_model",
        default=None,
        choices=list(MODEL_ALIASES.keys()),
        help="reviewer 카테고리(pre-reviewer + result-reviewer)에 적용할 모델 alias. "
             "지정 시 --model-preset의 reviewer 항목을 덮어씀.",
    )
    return parser.parse_args()


def resolve_preset(args: argparse.Namespace) -> tuple[ModelPreset, str, dict[str, str]]:
    """args에서 base preset + 카테고리별 override를 합쳐 최종 ModelPreset을 만든다.

    Returns:
        (final_preset, base_preset_name, overrides) — overrides는 명시된 카테고리만 담은 dict.
    """
    base = MODEL_PRESETS[args.model_preset]
    overrides: dict[str, str] = {}
    if args.generator_model is not None and args.generator_model != base.generator:
        overrides["generator"] = args.generator_model
    if args.reviewer_model is not None and args.reviewer_model != base.reviewer:
        overrides["reviewer"] = args.reviewer_model

    final = ModelPreset(
        generator=args.generator_model or base.generator,
        reviewer=args.reviewer_model or base.reviewer,
    )
    return final, args.model_preset, overrides


def main() -> None:
    args = parse_args()
    final_preset, base_name, overrides = resolve_preset(args)

    try:
        asyncio.run(
            run_pipeline(
                from_role=args.from_role,
                to_role=args.to_role,
                max_rounds=args.max_rounds,
                dry_run=args.dry_run,
                start_step=args.start_step,
                preset=final_preset,
                preset_name=base_name,
                overrides=overrides,
            )
        )
    except HarnessError as e:
        _log_error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        _log("중단됨.")
        sys.exit(130)
