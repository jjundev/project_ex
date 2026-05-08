from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
EXERCISE_DIR = INPUT_DIR / "exercise"
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

# ---------------------------------------------------------------------------
# 모델 프리셋
# ---------------------------------------------------------------------------

MODEL_GPT_DEFAULT = "gpt-5.5"


@dataclass(frozen=True)
class ModelPreset:
    """provider별 역할-모델 매핑 묶음."""

    provider: Literal["claude", "codex"]
    role_models: dict[str, str]
    role_reasoning: dict[str, str] | None = None  # codex 전용


MODEL_PRESETS: dict[str, ModelPreset] = {
    "claude-default": ModelPreset(
        provider="claude",
        role_models={
            "pre-generator": MODEL_OPUS,
            "pre-reviewer": MODEL_SONNET,
            "result-generator": MODEL_OPUS,
            "result-reviewer": MODEL_SONNET,
        },
    ),
    "gpt-quality": ModelPreset(
        provider="codex",
        role_models={r: MODEL_GPT_DEFAULT for r in ROLE_ORDER},
        role_reasoning={r: "high" for r in ROLE_ORDER},
    ),
}

DEFAULT_MODEL_PRESET = "gpt-quality"

