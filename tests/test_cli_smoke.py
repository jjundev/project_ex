from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_DIR = Path(__file__).resolve().parents[1]
HARNESS_PATH = PROJECT_DIR / "harness.py"


def _run_harness(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HARNESS_PATH), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    "args,expected_text",
    [
        (["--dry-run"], "실행 경로:"),
        (["--to", "pre-reviewer", "--dry-run"], "예비보고서 2단계"),
        (["--from", "result-generator", "--dry-run"], "결과보고서 2단계"),
    ],
)
def test_cli_dry_run_smoke(args: list[str], expected_text: str) -> None:
    proc = _run_harness(args, PROJECT_DIR)

    assert proc.returncode == 0
    assert expected_text in proc.stdout


def test_cli_dry_run_includes_full_pipeline_and_phase_guides() -> None:
    proc = _run_harness(["--dry-run"], PROJECT_DIR)

    assert proc.returncode == 0
    assert "실행 경로: pre-generator → pre-reviewer → result-generator → result-reviewer" in proc.stdout
    assert "예비보고서 2단계: Phase 1 (이론) + Phase 2 (예상 결과 값)" in proc.stdout
    assert "결과보고서 2단계: Phase 1 (실험 결과) + Phase 2 (고찰)" in proc.stdout


def test_result_reviewer_precheck_requires_result_report(tmp_path: Path) -> None:
    isolated = tmp_path / "isolated"
    isolated.mkdir()

    isolated_harness = isolated / "harness.py"
    shutil.copy2(HARNESS_PATH, isolated_harness)
    shutil.copytree(PROJECT_DIR / "harness_core", isolated / "harness_core")

    proc = subprocess.run(
        [sys.executable, str(isolated_harness), "--from", "result-reviewer", "--to", "result-reviewer"],
        cwd=str(isolated),
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 1
    assert "결과보고서가 없습니다" in proc.stderr
