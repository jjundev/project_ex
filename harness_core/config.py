from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# 경로 상수
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parents[1]
DOCX_DIR = PROJECT_DIR / "docx"
TEMPLATE_PATH = DOCX_DIR / "template_pre_report.md"
INPUT_DIR = PROJECT_DIR / "input"
BOOK_DIR = INPUT_DIR / "book"
NOTE_DIR = INPUT_DIR / "note"
STT_DIR = INPUT_DIR / "stt"
MEASURED_DIR = INPUT_DIR / "measured"
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
    "pre-generator": MODEL_OPUS,
    "result-generator": MODEL_OPUS,
}

SKILL_PATHS: dict[str, Path] = {
    "pre-generator": SKILLS_DIR / "pre-report" / "SKILL.md",
    "pre-reviewer": SKILLS_DIR / "pre-review" / "SKILL.md",
    "result-generator": SKILLS_DIR / "result-report" / "SKILL.md",
    "result-reviewer": SKILLS_DIR / "result-review" / "SKILL.md",
}

