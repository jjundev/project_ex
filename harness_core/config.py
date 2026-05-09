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

MODEL_OPUS = "claude-opus-4-7"
MODEL_SONNET = "claude-sonnet-4-6"
MODEL_GPT_DEFAULT = "gpt-5.5"

SKILL_PATHS: dict[str, Path] = {
    "pre-generator": SKILLS_DIR / "pre-report" / "SKILL.md",
    "pre-reviewer": SKILLS_DIR / "pre-review" / "SKILL.md",
    "result-generator": SKILLS_DIR / "result-report" / "SKILL.md",
    "result-reviewer": SKILLS_DIR / "result-review" / "SKILL.md",
}

# ---------------------------------------------------------------------------
# 모델 alias 레지스트리 — provider별 모델 구성을 짧은 이름으로 묶는다.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelAlias:
    """provider, model_id, codex 전용 reasoning effort를 묶은 모델 구성."""

    provider: Literal["claude", "codex"]
    model_id: str
    reasoning: str | None = None  # codex 전용


MODEL_ALIASES: dict[str, ModelAlias] = {
    "opus": ModelAlias("claude", MODEL_OPUS),
    "sonnet": ModelAlias("claude", MODEL_SONNET),
    "gpt-5.5": ModelAlias("codex", MODEL_GPT_DEFAULT, reasoning="high"),
}

# ---------------------------------------------------------------------------
# 모델 프리셋 — generator/reviewer 2-카테고리로 alias 묶음.
# ---------------------------------------------------------------------------

Category = Literal["generator", "reviewer"]


@dataclass(frozen=True)
class ModelPreset:
    """generator/reviewer 카테고리별 alias 묶음."""

    generator: str  # alias name
    reviewer: str   # alias name


MODEL_PRESETS: dict[str, ModelPreset] = {
    "claude-default": ModelPreset(generator="opus", reviewer="sonnet"),
    "gpt-quality": ModelPreset(generator="gpt-5.5", reviewer="gpt-5.5"),
}

DEFAULT_MODEL_PRESET = "gpt-quality"


def role_to_category(role: str) -> Category:
    """role 이름에서 카테고리(generator/reviewer)를 도출한다."""
    if role.endswith("-generator"):
        return "generator"
    if role.endswith("-reviewer"):
        return "reviewer"
    raise ValueError(f"카테고리를 알 수 없는 role: {role}")


def alias_for_role(preset: ModelPreset, role: str) -> ModelAlias:
    """preset과 role에서 최종 ModelAlias를 해석한다."""
    category = role_to_category(role)
    alias_name = preset.generator if category == "generator" else preset.reviewer
    if alias_name not in MODEL_ALIASES:
        raise ValueError(f"알 수 없는 alias: {alias_name}")
    return MODEL_ALIASES[alias_name]
