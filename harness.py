#!/usr/bin/env python3
"""기초전기실험 보고서 자동화 하네스 — claude_agent_sdk 기반 파이프라인 실행기.

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
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from harness_core import config as _config
from harness_core import io_state as _io_state
from harness_core import prompts as _prompts
from harness_core.cli import main, parse_args
from harness_core.pipeline import HarnessError, run_pipeline

# ---------------------------------------------------------------------------
# 경로 상수 (호환 재노출)
# ---------------------------------------------------------------------------

PROJECT_DIR = _config.PROJECT_DIR
DOCX_DIR = _config.DOCX_DIR
BOOK_DIR = _config.BOOK_DIR
NOTE_DIR = _config.NOTE_DIR
EXPERIMENT_DIR = _config.EXPERIMENT_DIR
TEMPLATE_PATH = _config.TEMPLATE_PATH
INPUT_DIR = _config.INPUT_DIR
OUTPUT_DIR = _config.OUTPUT_DIR
SKILLS_DIR = _config.SKILLS_DIR

# ---------------------------------------------------------------------------
# 파이프라인 상수 (호환 재노출)
# ---------------------------------------------------------------------------

ROLE_ORDER = _config.ROLE_ORDER
MODEL_OPUS = _config.MODEL_OPUS
MODEL_SONNET = _config.MODEL_SONNET
ROLE_MODELS = _config.ROLE_MODELS
SKILL_PATHS = _config.SKILL_PATHS


def parse_review_verdict(review_path: Path) -> str:
    return _io_state.parse_review_verdict(review_path)


def extract_fail_items(review_path: Path) -> str:
    return _io_state.extract_fail_items(review_path)


def _reserve_archive_path(base_archive_path: Path) -> Path:
    return _io_state._reserve_archive_path(base_archive_path, now=datetime.now)


def _archive_if_exists(src_path: Path, base_archive_path: Path) -> Path | None:
    return _io_state._archive_if_exists(src_path, base_archive_path, now=datetime.now)


def _select_result_reviewer_prompt(extra: str = "") -> tuple[str, Path, str]:
    latest_report = _io_state._latest_result_report(output_dir=OUTPUT_DIR)
    if latest_report is not None and _io_state._has_discussion_section(latest_report):
        return (
            _prompts._build_result_reviewer_phase2_prompt(extra, output_dir=OUTPUT_DIR),
            OUTPUT_DIR / "result_review.md",
            "phase2",
        )
    return (
        _prompts._build_result_reviewer_phase1_prompt(extra, output_dir=OUTPUT_DIR),
        OUTPUT_DIR / "result_review_data.md",
        "phase1",
    )


if __name__ == "__main__":
    main()

