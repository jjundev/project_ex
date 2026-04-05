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


def test_result_reviewer_precheck_requires_result_report(tmp_path: Path) -> None:
    isolated = tmp_path / "isolated"
    isolated.mkdir()

    isolated_harness = isolated / "harness.py"
    shutil.copy2(HARNESS_PATH, isolated_harness)

    proc = subprocess.run(
        [sys.executable, str(isolated_harness), "--from", "result-reviewer", "--to", "result-reviewer"],
        cwd=str(isolated),
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 1
    assert "결과보고서가 없습니다" in proc.stderr
