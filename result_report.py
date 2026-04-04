import anyio
from claude_agent_sdk import AssistantMessage, ResultMessage, query

from config import (
    INPUT_DIR,
    OUTPUT_DIR,
    SKILLS_DIR,
    collect_docx_files,
    get_agent_options,
)


def _find_pre_report() -> list[str]:
    """output/ 에서 예비보고서 파일을 찾는다."""
    if not OUTPUT_DIR.exists():
        return []
    return sorted(str(f) for f in OUTPUT_DIR.glob("*예비보고서.md"))


def _find_measurements() -> list[str]:
    """input/ 에서 측정값 파일을 찾는다."""
    if not INPUT_DIR.exists():
        return []
    return sorted(str(f) for f in INPUT_DIR.glob("*측정값.md"))


def _build_prompt(
    pre_reports: list[str],
    measurements: list[str],
    docx_files: dict[str, list[str]],
) -> str:
    """결과보고서 생성을 위한 프롬프트를 구성한다."""
    pre_list = "\n".join(f"  - {f}" for f in pre_reports)
    meas_list = (
        "\n".join(f"  - {f}" for f in measurements)
        if measurements
        else "  (없음 - 사용자에게 입력 요청 필요)"
    )
    exp_list = (
        "\n".join(f"  - {f}" for f in docx_files["experiment"])
        if docx_files["experiment"]
        else "  (없음)"
    )

    return f"""아래 자료를 사용하여 결과보고서를 생성하세요.

## 입력 자료

### 예비보고서
{pre_list}

### 측정값 파일 (input/)
{meas_list}

### 실험 영상 STT (참고용)
{exp_list}

## 지시사항

1. 예비보고서를 읽어 예상값 테이블 구조를 파악하세요.
2. 측정값 파일이 있으면 읽고, 없으면 사용자에게 각 Table별 측정값을 질문하세요.
3. system prompt에 정의된 Step 1~5를 순서대로 수행하세요.
4. 최종 보고서는 `{OUTPUT_DIR}` 경로에 Markdown 파일로 저장하세요.
5. 파일명 형식: `{{N}}주차_결과보고서.md`
"""


async def generate_result_report() -> None:
    """결과보고서를 생성한다."""
    # 전제조건: 예비보고서 존재 확인
    pre_reports = _find_pre_report()
    if not pre_reports:
        print("예비보고서가 없습니다.")
        print("먼저 'python main.py pre-report'를 실행하세요.")
        return

    print(f"예비보고서 {len(pre_reports)}개 발견:")
    for f in pre_reports:
        print(f"  - {f}")

    # 측정값 파일 확인
    measurements = _find_measurements()
    if measurements:
        print(f"\n측정값 파일 {len(measurements)}개 발견:")
        for f in measurements:
            print(f"  - {f}")
    else:
        print("\n측정값 파일 없음 - 에이전트가 사용자에게 입력을 요청합니다.")

    # SKILL.md 로드
    skill_path = SKILLS_DIR / "result-report" / "SKILL.md"
    system_prompt = skill_path.read_text(encoding="utf-8")

    # 입력 자료 수집
    docx_files = collect_docx_files()

    # 출력 디렉토리 확인
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 프롬프트 구성
    prompt = _build_prompt(pre_reports, measurements, docx_files)

    # 에이전트 실행
    options = get_agent_options(system_prompt)
    print("\n결과보고서 생성을 시작합니다...\n")

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "text") and block.text:
                    print(block.text)

        elif isinstance(message, ResultMessage):
            if message.subtype == "success":
                print("\n결과보고서 생성 완료!")
                if message.result:
                    print(message.result)
            else:
                print(f"\n생성 중단: {message.subtype}")

            if hasattr(message, "total_cost_usd") and message.total_cost_usd:
                print(f"비용: ${message.total_cost_usd:.4f}")
            if hasattr(message, "num_turns") and message.num_turns:
                print(f"턴 수: {message.num_turns}")


if __name__ == "__main__":
    anyio.run(generate_result_report)
