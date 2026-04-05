from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
HARNESS = PROJECT_DIR / "harness.py"
NOTION_DEPLOY = PROJECT_DIR / "harness_core" / "notion_deploy.py"
PYTHON = sys.executable
DEFAULT_PORT = 7788

ROLE_ORDER = ["pre-generator", "pre-reviewer", "result-generator", "result-reviewer"]
ROLE_LABEL = {
    "pre-generator": "예비 생성",
    "pre-reviewer": "예비 검토",
    "result-generator": "결과 생성",
    "result-reviewer": "결과 검토",
}
ROLE_MODEL = {
    "pre-generator": "Opus",
    "pre-reviewer": "Sonnet",
    "result-generator": "Opus",
    "result-reviewer": "Sonnet",
}

ANSI = re.compile(r"\033\[[0-9;]*m")
PHASE_START_RE = re.compile(r"── ((?:결과보고서 )?Phase \d+): (.+?) ──")
PHASE_ROUND_RE = re.compile(r"── Phase (\d+) 라운드 (\d+)/(\d+) ──")
NOTION_STEP_RE = re.compile(r"\[deploy:step\] (.+)")
NOTION_UPLOAD_RE = re.compile(r"\[deploy\] 블록 업로드 (\d+)/(\d+)")

_STEP_CLI_ARGS = {
    "pre": {"from": "pre-generator", "to": "pre-reviewer"},
    "result": {"from": "result-generator", "to": "result-reviewer"},
}
