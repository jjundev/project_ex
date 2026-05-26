from __future__ import annotations

import pytest

from harness_core.notion_deploy import _normalize_code_language, parse_markdown


def _single_code_language(markdown: str) -> str:
    blocks = parse_markdown(markdown)
    code_blocks = [block for block in blocks if block["type"] == "code"]
    assert len(code_blocks) == 1
    return code_blocks[0]["code"]["language"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", "plain text"),
        ("text", "plain text"),
        ("txt", "plain text"),
        ("plaintext", "plain text"),
        ("plain text", "plain text"),
        ("md", "markdown"),
        ("js", "javascript"),
        ("ts", "typescript"),
        ("py", "python"),
        ("ps1", "powershell"),
        ("sh", "shell"),
        ("yml", "yaml"),
        ("dockerfile", "docker"),
        ("make", "makefile"),
        ("rb", "ruby"),
        ("rs", "rust"),
        ("csharp", "c#"),
        ("cpp", "c++"),
        ("objectivec", "objective-c"),
        ("unknown-lang", "plain text"),
    ],
)
def test_normalize_code_language_aliases(raw: str, expected: str) -> None:
    assert _normalize_code_language(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "python",
        "bash",
        "json",
        "mermaid",
        "c++",
        "c#",
        "java/c/c++/c#",
        "notion formula",
    ],
)
def test_normalize_code_language_keeps_notion_values(raw: str) -> None:
    assert _normalize_code_language(raw) == raw


@pytest.mark.parametrize(
    "fence,expected",
    [
        ("text", "plain text"),
        ("", "plain text"),
        ("plain text", "plain text"),
        ("{.python}", "python"),
        ("python title=foo", "python"),
        ("js linenums", "javascript"),
        ("dockerfile", "docker"),
        ("unknown-lang", "plain text"),
    ],
)
def test_parse_markdown_normalizes_code_block_language(fence: str, expected: str) -> None:
    markdown = f"```{fence}\nhello\n```"
    assert _single_code_language(markdown) == expected
