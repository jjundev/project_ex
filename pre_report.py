import anyio
from claude_agent_sdk import AssistantMessage, ResultMessage, query

from config import (
    OUTPUT_DIR,
    SKILLS_DIR,
    TEMPLATE_PATH,
    collect_docx_files,
    get_agent_options,
)


def _build_prompt(files: dict[str, list[str]]) -> str:
    """예비보고서 생성을 위한 프롬프트를 구성한다."""
    book_list = "\n".join(f"  - {f}" for f in files["book"]) or "  (없음)"
    note_list = "\n".join(f"  - {f}" for f in files["note"]) or "  (없음)"
    exp_list = "\n".join(f"  - {f}" for f in files["experiment"]) or "  (없음)"

    return f"""아래 자료를 사용하여 예비보고서를 생성하세요.

## 입력 자료

### 교재 스캔본 (docx/book/)
{book_list}

### 강의노트 (docx/note/)
{note_list}

### 실험 영상 STT (docx/experiment/) - 검증용
{exp_list}

### 템플릿
  - {TEMPLATE_PATH}

## 지시사항

1. 위 자료를 **모두** 읽으세요 (이미지, PDF, 텍스트 파일).
2. system prompt에 정의된 Step 1~5를 순서대로 수행하세요.
3. 최종 보고서는 `{OUTPUT_DIR}` 경로에 Markdown 파일로 저장하세요.
4. 파일명 형식: `{{N}}주차_예비보고서.md` (N은 주차 번호).
5. 저장 후 검토 결과를 출력하세요.
"""


async def generate_pre_report() -> None:
    """예비보고서를 생성한다."""
    # SKILL.md를 system prompt로 로드
    skill_path = SKILLS_DIR / "pre-report" / "SKILL.md"
    system_prompt = skill_path.read_text(encoding="utf-8")

    # 입력 자료 수집
    files = collect_docx_files()
    total = sum(len(v) for v in files.values())
    print(f"입력 자료 {total}개 발견")
    for category, paths in files.items():
        if paths:
            print(f"  {category}: {len(paths)}개")

    # 출력 디렉토리 확인
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 프롬프트 구성
    prompt = _build_prompt(files)

    # 에이전트 실행
    options = get_agent_options(system_prompt)
    print("\n예비보고서 생성을 시작합니다...\n")

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "text") and block.text:
                    print(block.text)

        elif isinstance(message, ResultMessage):
            if message.subtype == "success":
                print("\n예비보고서 생성 완료!")
                if message.result:
                    print(message.result)
            else:
                print(f"\n생성 중단: {message.subtype}")

            if hasattr(message, "total_cost_usd") and message.total_cost_usd:
                print(f"비용: ${message.total_cost_usd:.4f}")
            if hasattr(message, "num_turns") and message.num_turns:
                print(f"턴 수: {message.num_turns}")


if __name__ == "__main__":
    anyio.run(generate_pre_report)
