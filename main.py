"""기초전기실험 보고서 자동화 하네스 CLI."""

import argparse
import sys

import anyio


def main() -> None:
    parser = argparse.ArgumentParser(
        description="기초전기실험 보고서 자동화 하네스",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "pre-report",
        help="예비보고서 생성",
    )
    subparsers.add_parser(
        "result-report",
        help="결과보고서 생성 (예비보고서 선행 필요)",
    )

    args = parser.parse_args()

    if args.command == "pre-report":
        from pre_report import generate_pre_report

        anyio.run(generate_pre_report)

    elif args.command == "result-report":
        from result_report import generate_result_report

        anyio.run(generate_result_report)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
