from __future__ import annotations

import argparse
import asyncio
import sys

from .config import ROLE_ORDER
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        asyncio.run(
            run_pipeline(
                from_role=args.from_role,
                to_role=args.to_role,
                max_rounds=args.max_rounds,
                dry_run=args.dry_run,
                start_step=args.start_step,
            )
        )
    except HarnessError as e:
        _log_error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        _log("중단됨.")
        sys.exit(130)

