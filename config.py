from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

# 프로젝트 경로
PROJECT_DIR = Path(__file__).parent.resolve()
DOCX_DIR = PROJECT_DIR / "docx"
BOOK_DIR = DOCX_DIR / "book"
NOTE_DIR = DOCX_DIR / "note"
EXPERIMENT_DIR = DOCX_DIR / "experiment"
TEMPLATE_PATH = DOCX_DIR / "template_pre_report.md"
INPUT_DIR = PROJECT_DIR / "input"
OUTPUT_DIR = PROJECT_DIR / "output"
SKILLS_DIR = PROJECT_DIR / "skills"


def get_agent_options(system_prompt: str) -> ClaudeAgentOptions:
    """공통 에이전트 옵션을 반환한다."""
    return ClaudeAgentOptions(
        system_prompt=system_prompt,
        cwd=str(PROJECT_DIR),
        permission_mode="acceptEdits",
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
        max_turns=50,
    )


def collect_docx_files() -> dict[str, list[str]]:
    """docx/ 하위 파일 목록을 수집하여 반환한다."""
    result: dict[str, list[str]] = {
        "book": [],
        "note": [],
        "experiment": [],
    }

    if BOOK_DIR.exists():
        result["book"] = sorted(str(f) for f in BOOK_DIR.glob("*") if f.is_file())

    if NOTE_DIR.exists():
        result["note"] = sorted(str(f) for f in NOTE_DIR.glob("*") if f.is_file())

    if EXPERIMENT_DIR.exists():
        result["experiment"] = sorted(
            str(f) for f in EXPERIMENT_DIR.glob("*.txt") if f.is_file()
        )

    return result
