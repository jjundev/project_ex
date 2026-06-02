from __future__ import annotations

from pathlib import Path

from .config import EXERCISE_DIR, OUTPUT_DIR, STT_DIR, TEMPLATE_PATH
from .io_state import (
    _exercise_files_present,
    _find_measurements,
    _find_pre_reports,
    _find_result_reports,
    _has_discussion_section,
    _has_exercise_section,
    _latest_result_report,
    _latest_review_file,
    collect_docx_files,
    extract_pass_sections,
    parse_review_verdict,
)


def _build_pre_generator_prompt(extra: str = "") -> str:
    files = collect_docx_files()
    book_list = "\n".join(f"  - {f}" for f in files["book"]) or "  (없음)"
    note_list = "\n".join(f"  - {f}" for f in files["note"]) or "  (없음)"
    exp_list = "\n".join(f"  - {f}" for f in files["stt"]) or "  (없음)"

    rework_section = ""
    retry_section = ""
    if extra:
        rework_section = f"\n## 재작업 지시사항\n{extra}\n"

        pre_reports = _find_pre_reports(output_dir=OUTPUT_DIR)
        pre_list = "\n".join(f"  - {f}" for f in pre_reports) or "  (없음)"

        latest_review = _latest_review_file(
            OUTPUT_DIR / "pre_review_theory.md",
            "pre_review_theory_round*.md",
        )
        pass_sections = extract_pass_sections(latest_review) if latest_review else []
        pass_list = "\n".join(f"  - {s}" for s in pass_sections) or "  (없음)"

        retry_section = f"""
## 재작업 모드 (Phase 1 FAIL 후 재시도)

처음부터 새로 작성하지 마세요. 기존 예비보고서를 읽고 FAIL 항목만 수정하세요.

### 기존 예비보고서 (수정 대상)
{pre_list}

### 이전 검토에서 PASS된 섹션 (변경 금지)
{pass_list}

### 작업 방식
1. 위 기존 예비보고서를 Read로 먼저 읽으세요.
2. 위에 나열된 PASS 섹션은 절대 수정하지 마세요. 그대로 보존합니다.
3. `재작업 지시사항`의 FAIL 항목만 해당 섹션에서 Edit으로 수정하세요.
4. 수정에 필요한 경우에만 아래 입력 자료에서 관련 파일을 선택적으로 다시 읽으세요 (전체 재독 불필요).
5. 같은 파일에 덮어쓰기로 저장하세요.
"""

    return f"""아래 자료를 사용하여 예비보고서 **Phase 1** (실험 목적·준비물·이론)을 생성하세요.

> **주의**: 이번 단계에서는 `## 예상 결과 값` 섹션을 작성하지 마세요.
> 예상 결과 값은 이론 검토 통과 후 Phase 2에서 별도로 작성합니다.
{rework_section}{retry_section}
## 입력 자료

### 교재 스캔본 (input/book/) — 이미지 파일
{book_list}

### 강의노트 (input/note/) — PDF 파일
{note_list}

### 실험 영상 STT (input/stt/) — 텍스트 파일, 검증용
{exp_list}

### 템플릿
  - {TEMPLATE_PATH}

## 파일 읽기 방법

- **이미지 (book/)**: Read 도구로 각 파일을 순서대로 읽으세요. 회로도, Table, Procedure가 보입니다.
- **PDF (note/)**: Read 도구로 읽으세요. 10페이지 초과 시 pages 파라미터로 범위를 지정하세요 (예: "1-10").
- **텍스트 (stt/)**: Read 도구로 읽으세요.

## 지시사항

1. 위 자료를 **모두** 읽으세요. 파일을 건너뛰지 마세요. (재작업 모드인 경우 위 "작업 방식" 우선)
2. STT는 보조 자료로만 사용하세요. STT에 강의노트·교재와 다른 실험 변형(전압 설정 변경, 추가 소자 결합 등)이 있어도 본문에 인용하거나 변형 표를 추가하지 마세요. 강의노트 기준으로 통일하여 작성합니다 (자세한 정책은 SKILL.md Step 1-4 참조).
3. system prompt의 **Step 2-1 (실험 목적)**, **Step 2-2 (실험 준비물)**, **Step 2-3 (실험 이론)** 만 작성하세요.
4. `## 예상 결과 값` 섹션은 작성하지 마세요 (Phase 2에서 작성).
5. `## 보드 연결도` 섹션 헤더는 작성하세요 (내용 없이).
6. 최종 보고서는 `{OUTPUT_DIR}` 경로에 Markdown 파일로 저장하세요.
7. 파일명 형식: `{{N}}주차_예비보고서.md` (N은 주차 번호).
8. 저장 후 검토 결과를 출력하세요.
"""


def _build_pre_reviewer_prompt(extra: str = "") -> str:
    rework_section = ""
    if extra:
        rework_section = f"\n## 이전 검토 FAIL 항목 (재작업 반영 확인)\n{extra}\n"

    pre_reports = _find_pre_reports()
    pre_list = "\n".join(f"  - {f}" for f in pre_reports) or "  (없음)"

    return f"""생성된 예비보고서를 검토하고 KVL/KCL 검증을 수행하세요.
{rework_section}
## 검토 대상

다음 예비보고서를 읽으세요:
{pre_list}

## 검증 항목

1. **KVL 검증**: 각 폐회로의 전압 합 = 전원전압 확인
2. **KCL 검증**: 각 노드의 전류 보존 확인
3. **단위 일관성**: mA, V, kΩ, μF, s 단위 명시 여부
4. **계산 정확도**: 예상값 Table의 수식 및 수치 검토
5. **STT 교차검증**: `{STT_DIR}` 에 STT 파일이 있으면 측정값과 비교

## 출력 형식

검토 결과를 `{OUTPUT_DIR}/pre_review.md` 에 저장하세요.
파일 형식:

```
## KVL/KCL 검증 결과

### 회로 1
- KVL: [결과]
- KCL: [결과]

### 발견된 오류
- [오류 항목 목록, 없으면 "없음"]

## 최종 판정: PASS
```

마지막 줄은 반드시 `최종 판정: PASS` 또는 `최종 판정: FAIL` 형식으로 끝내세요.
"""


def _build_pre_generator_phase2_prompt(extra: str = "") -> str:
    pre_reports = _find_pre_reports()
    pre_list = "\n".join(f"  - {f}" for f in pre_reports) or "  (없음)"
    files = collect_docx_files()
    book_list = "\n".join(f"  - {f}" for f in files["book"]) or "  (없음)"
    note_list = "\n".join(f"  - {f}" for f in files["note"]) or "  (없음)"

    rework_section = ""
    if extra:
        rework_section = f"\n## 재작업 지시사항\n{extra}\n"

    return f"""예비보고서에 **예상 결과 값 섹션만** 추가하세요 (Phase 2).
{rework_section}
## 현재 예비보고서 (Phase 1에서 작성된 파일)

{pre_list}

## 입력 자료 (회로도·이론 확인용)

### 교재 스캔본 (input/book/) — 이미지 파일
{book_list}

### 강의노트 (input/note/) — PDF 파일
{note_list}

## 지시사항

1. 현재 예비보고서를 읽으세요.
2. `input/book/` 이미지를 읽어 회로도와 Table 구조를 파악하세요.
3. `input/note/` PDF를 읽어 이론을 확인하세요.
4. system prompt의 **Step 2-4 (예상 결과 값)** 지침에 따라 각 Table의 예상값을 계산하세요.
5. 기존 예비보고서 파일을 **수정**하여 `## 예상 결과 값` 섹션을 반영하세요.
   - 파일에 `## 예상 결과 값` 섹션이 **이미 있으면 교체**하고, 없으면 `## 보드 연결도` 바로 앞에 **삽입**하세요.
   - `## 실험 목적`, `## 실험 준비물`, `## 실험 이론` 섹션은 변경하지 마세요.
6. 저장 후 KVL/KCL 자동 검토 결과를 출력하세요.
"""


def _build_pre_reviewer_phase1_prompt(extra: str = "") -> str:
    rework_section = ""
    if extra:
        rework_section = f"\n## 이전 검토 FAIL 항목 (재작업 반영 확인)\n{extra}\n"

    pre_reports = _find_pre_reports()
    pre_list = "\n".join(f"  - {f}" for f in pre_reports) or "  (없음)"

    return f"""생성된 예비보고서의 **이론 섹션 완성도**를 검토하세요 (Phase 1 검토).
{rework_section}
## 검토 대상

다음 예비보고서를 읽으세요:
{pre_list}

## 검증 항목

이 단계에서는 `## 예상 결과 값` 섹션이 아직 없습니다. 아래 3개 섹션만 검토하세요:

1. **실험 목적**: 교재·강의노트의 실험 목표와 일치하는지, 각 챕터별로 구체적으로 서술되었는지
2. **실험 준비물**: 교재 Equipment + Procedure에서 사용되는 소자가 모두 포함되었는지, 한글명·용도·주의사항이 기재되었는지
3. **실험 이론**: 해당 주차 핵심 이론이 빠짐없이 포함되었는지, 개념과 적용 방법이 올바르게 서술되었는지

## 출력 형식

검토 결과를 `{OUTPUT_DIR}/pre_review_theory.md` 에 저장하세요.
파일 형식:

```
## 이론 섹션 검토 결과

### 실험 목적
- 판정: PASS 또는 FAIL (이유)

### 실험 준비물
- 판정: PASS 또는 FAIL (누락 항목 등)

### 실험 이론
- 판정: PASS 또는 FAIL (누락/오류 이론 항목)

### 발견된 문제점
- [구체적 항목, 없으면 "없음"]

최종 판정: PASS
```

마지막 줄은 반드시 `최종 판정: PASS` 또는 `최종 판정: FAIL` 형식으로 끝내세요.
"""


def _build_result_generator_phase1_prompt(extra: str = "") -> str:
    """Phase 1: # 실험 결과 섹션만 작성. 연습 문제·고찰은 후속 phase에서 처리."""
    pre_reports = _find_pre_reports()
    measurements = _find_measurements()
    docx_files = collect_docx_files()

    pre_list = "\n".join(f"  - {f}" for f in pre_reports) or "  (없음)"
    book_list = "\n".join(f"  - {f}" for f in docx_files["book"]) or "  (없음)"
    meas_list = (
        "\n".join(f"  - {f}" for f in measurements)
        if measurements
        else "  (없음 - 사용자에게 입력 요청 필요)"
    )
    exp_list = (
        "\n".join(f"  - {f}" for f in docx_files["stt"])
        if docx_files["stt"]
        else "  (없음)"
    )

    rework_section = ""
    retry_section = ""
    if extra:
        rework_section = f"\n## 재작업 지시사항\n{extra}\n"

        result_reports = _find_result_reports()
        result_list = "\n".join(f"  - {f}" for f in result_reports) or "  (없음)"

        retry_section = f"""
## 재작업 모드 (Phase 1 FAIL 후 재시도)

처음부터 새로 작성하지 마세요. 기존 결과보고서를 읽고 FAIL 항목만 수정하세요.

### 기존 결과보고서 (수정 대상)
{result_list}

### 작업 방식
1. 위 기존 결과보고서를 Read로 먼저 읽으세요.
2. `재작업 지시사항`에 명시된 FAIL 항목만 Edit으로 수정하세요. FAIL 목록에 없는 Table/항목은 변경하지 마세요.
3. 수정에 필요한 경우에만 아래 입력 자료(교재 Table 원형, 측정값)를 선택적으로 다시 읽으세요.
4. 같은 파일에 덮어쓰기로 저장하세요.
5. **`# 연습 문제` 섹션이 보고서에 이미 존재하면 절대 수정하지 마세요.** Phase 2에서 작성된 영역이며 Phase 1 재생성 시 보존 대상입니다.
6. **`# 고찰` 섹션이 보고서에 이미 존재하면 절대 수정하지 마세요.** Phase 3에서 작성된 영역이며 Phase 1 재생성 시 보존 대상입니다.
"""

    return f"""아래 자료를 사용하여 결과보고서 **Phase 1** (실험 결과)을 생성하세요.

> **주의**: 이번 단계에서는 `# 실험 결과` 섹션만 작성합니다.
> `# 연습 문제` 섹션은 Phase 2에서, `# 고찰` 섹션은 Phase 3에서 별도로 작성합니다.
> 이번 단계에 `# 연습 문제`나 `# 고찰` 섹션을 작성하지 마세요.
{rework_section}{retry_section}
## 입력 자료

### 예비보고서
{pre_list}

### 교재 스캔본 (input/book/) — Table 원형 확인용
{book_list}

### 측정값 파일 (input/measured/)
{meas_list}

### 실험 영상 STT (참고용)
{exp_list}

## 지시사항

> 재작업 모드인 경우 위 "작업 방식"을 우선 적용하고, 아래 단계는 신규 작성 시에만 따르세요.

1. 예비보고서를 읽어 예상값 테이블 구조를 파악하세요.
2. `input/book/` 이미지를 다시 읽어 각 교재 Table의 원래 행/열 구조와 작성 요구사항을 확인하세요.
3. 측정값 파일이 있으면 읽고, 없으면 사용자에게 각 Table별 측정값을 질문하세요.
4. 교재 Table 원형 구조를 최상위 기준으로 삼으세요. 교재에 없는 `Calculated`, `Measured`, `%(Difference)` 열을 임의로 추가하지 마세요.
5. 교재가 `v_R = E - v_C`처럼 표 안의 파생값 작성을 요구하면, 그 값을 원래 Table 행/열에 채우세요.
6. 교재가 그래프 판독값, 측정 교차점, 특정 임계점, 특정 주파수/시간의 실측 데이터 기반 값을 요구하면 먼저 측정값에서 좌표나 파생값을 산출하세요. `X = R`, `V = E/√2`, `τ = RC` 같은 이론식은 이론 기준값 또는 비교·해석용 값으로 분리하고, 측정 기반 산출값을 덮어쓰지 마세요.
7. 표의 값이 측정 기반 산출값인지, 명판값 기반 이론 계산인지, 실측 소자값 기반 재계산인지 Table 앞 설명에 구분해 명시하세요.
8. system prompt의 **Step 1~3** (예비보고서 로드, 실측값 입력, 실험 결과 작성)을 수행하세요.
9. `# 실험 결과` 섹션만 작성하세요. `# 연습 문제` (Phase 2 영역) 와 `# 고찰` (Phase 3 영역) 은 작성하지 마세요.
10. 최종 보고서는 `{OUTPUT_DIR}` 경로에 Markdown 파일로 저장하세요.
11. 파일명 형식: `{{N}}주차_결과보고서.md`
"""


def _build_result_generator_phase2_prompt(extra: str = "") -> str:
    """Phase 2: # 연습 문제 섹션만 추가. Phase 1 섹션은 read-only."""
    result_reports = _find_result_reports()
    docx_files = collect_docx_files()

    report_list = "\n".join(f"  - {f}" for f in result_reports) or "  (없음)"
    exercise_list = (
        "\n".join(f"  - {f}" for f in docx_files["exercise"])
        if docx_files["exercise"]
        else "  (없음 — Phase 2를 호출해서는 안 됩니다)"
    )

    rework_section = ""
    if extra:
        rework_section = f"\n## 재작업 지시사항\n{extra}\n"

    return f"""결과보고서에 **`# 연습 문제` 섹션만** 추가하세요 (Phase 2).

> **Phase 1에서 작성된 `# 실험 결과` 섹션은 절대 수정하지 마세요** (헤더·표·계산·수치·sub-bullet 모두 읽기 전용).
> Phase 1 검증이 이미 PASS된 상태이며, Phase 2에서 손대면 Phase 1 reviewer가 잡지 못해 라운드 무한 반복 위험이 있습니다.
{rework_section}
## 현재 결과보고서 (Phase 1에서 작성된 파일)

{report_list}

## 연습 문제 자료 (input/exercise/) — 이미지/PDF/MD/텍스트

{exercise_list}

## 삽입 위치 규칙 (필수)

1. 보고서를 Read한다.
2. 보고서에 `# 고찰` 헤더가 있으면 그 줄 *앞*에 `# 연습 문제` 섹션을 Edit으로 insert한다.
3. `# 고찰` 헤더가 없으면 파일 *맨 끝*에 `# 연습 문제` 섹션을 append한다.
4. 절대 `# 실험 결과` 내부의 `## Ch X` 섹션 사이나 그 위쪽에 끼우지 마라.

## 지시사항

1. 위 결과보고서를 Read하세요.
2. `input/exercise/` 자료를 모두 읽으세요. 이미지는 vision으로 직접 파싱하여 *문제 본문·조건·그림(Fig X.Y)* 을 추출하세요.
3. system prompt의 **Step 4 (연습 문제 작성, Phase 2)** 지침을 따르세요.
   - Ch 그룹화 자동 추론 (파일명 무시, 문제 *내용*에서 추론)
   - 헤더 구조: `# 연습 문제` → `## AC Ch X` (또는 `DC Ch X`) → `### Exercise N` (제목·괄호 금지)
   - 풀이 단계는 ① ② ③ 원숫자 번호 사용
   - 단위 변환 (p-p ↔ rms 등) 명시
   - **Type 3 Calculated/Experimental Table의 Experimental 칸은 *항상* "실험 측정값" placeholder 유지** (측정값 파일에서 자동 매핑 금지)
4. 위 "삽입 위치 규칙"대로 Edit insert / append 하세요.
5. 저장 후 작업 완료를 보고하세요.
6. 스타일 규칙: 헤더·bold label·① step·HTML 주석·표 앞뒤는 빈 줄 1개, 같은 목록의 연속 bullet 사이에는 빈 줄 없음, 긴 문장/수식/표 행은 임의 hard-wrap 금지, `**결론**`/`**판정**`/문장형 `**정답**` 아래 문단은 top-level bullet `-` 사용, `*italic*` 강조 금지, `✓`/`✗`/`❌`/`✅` 등 시각 기호 금지. 자세한 사항은 system prompt §4-4 8~12번 참조.

## 재작업 모드 (Phase 2 FAIL 후 재시도)

`재작업 지시사항`이 위에 있으면 해당 FAIL 항목만 `# 연습 문제` 섹션 안에서 Edit으로 수정하세요. Phase 1 영역(`# 실험 결과`)은 절대 손대지 마세요.
"""


def _build_result_generator_phase3_prompt(extra: str = "") -> str:
    """Phase 3: # 고찰 섹션만 추가. Phase 1 (실험 결과)·Phase 2 (연습 문제) 모두 read-only."""
    result_reports = _find_result_reports()
    report_list = "\n".join(f"  - {f}" for f in result_reports) or "  (없음)"

    rework_section = ""
    if extra:
        rework_section = f"\n## 재작업 지시사항\n{extra}\n"

    return f"""결과보고서에 **`# 고찰` 섹션만** 추가하세요 (Phase 3).

> **Phase 1에서 작성된 `# 실험 결과` 섹션과 Phase 2에서 작성된 `# 연습 문제` 섹션은 절대 수정하지 마세요** (헤더·표·계산·수치·sub-bullet 모두 읽기 전용).
> Phase 1·2 검증이 이미 PASS된 상태이며, Phase 3에서 손대면 Phase 1·2 reviewer가 잡지 못해 라운드 무한 반복 위험이 있습니다.
{rework_section}
## 현재 결과보고서 (Phase 1·2에서 작성된 파일)

{report_list}

## 지시사항

1. 현재 결과보고서를 읽어 `# 실험 결과` 섹션의 모든 Table 데이터와 %(Difference) 수치를 파악하세요. `# 연습 문제` 섹션이 있으면 그 내용도 파악(인용은 가능, 수정은 금지)하세요.
2. system prompt의 **Step 5 (고찰 작성, Phase 3)** 지침에 따라 고찰을 작성하세요.
   - 결과 분석, 오차 원인, 개선 방안, 결론 소섹션 포함
   - 구체적인 %(Difference) 수치 인용 필수
   - 정량적 오차 원인 분석 필수
   - 측정 기반 산출값과 이론 기준값이 다르면 단순 계산 오류로 단정하지 말고, 보간값·판독값·이론 기준값을 구분해 차이를 정량적으로 설명
   - 각 소섹션의 본문은 일반 문단이 아니라 top-level bullet `-` 로 시작하는 긴 bullet 문단 형식으로 작성
   - 각 `##` 소섹션 헤더 뒤에는 빈 줄 하나를 둔 뒤 bullet 문단을 시작하고, 연속 bullet 문단 사이에는 빈 줄을 넣지 않으며, 긴 bullet 문단은 임의 hard-wrap 하지 않음
3. 기존 결과보고서 파일을 **수정**하여 `# 고찰` 섹션을 반영하세요.
   - 파일에 `# 고찰` 섹션이 **이미 있으면 교체**하고, 없으면 파일 끝에 **추가**하세요.
   - 위치 규칙: `# 연습 문제` 섹션이 있으면 그 *뒤*에, 없으면 `# 실험 결과` *뒤*에 `# 고찰`이 옵니다. 절대 `# 실험 결과`와 `# 연습 문제` 사이에 끼워 넣지 마세요.
   - **append anchor 규칙**: Edit으로 추가할 때 anchor(old_string)는 *파일의 마지막 줄*이어야 합니다. `# 실험 결과` 섹션의 끝 줄을 anchor로 잡으면 `# 고찰`이 `# 실험 결과`와 `# 연습 문제` 사이에 끼워집니다 (14주차 사고 원인).
   - **삽입 후 self-check**: 저장 후 보고서를 다시 Read하여 `# 고찰`이 *마지막* top-level `#` 섹션이며, `# 연습 문제`가 있으면 그 *뒤*에 오는지 확인하세요. 어긋나면 잘못 삽입한 블록을 제거하고 파일 맨 끝에 다시 추가하세요.
   - `# 실험 결과` 섹션과 `# 연습 문제` 섹션은 변경하지 마세요.
4. 저장 후 완료를 보고하세요.
"""


def _build_result_reviewer_phase1_prompt(
    extra: str = "",
    output_dir: Path = OUTPUT_DIR,
) -> str:
    """Phase 1 검토: # 실험 결과 섹션의 데이터/수치 검증만. 연습 문제는 Phase 2 reviewer에서 별도 검증."""
    rework_section = ""
    if extra:
        rework_section = f"\n## 이전 검토 FAIL 항목 (재작업 반영 확인)\n{extra}\n"

    result_reports = _find_result_reports(output_dir=output_dir)
    report_list = "\n".join(f"  - {f}" for f in result_reports) or "  (없음)"
    pre_reports = _find_pre_reports(output_dir=output_dir)
    pre_list = "\n".join(f"  - {f}" for f in pre_reports) or "  (없음)"
    docx_files = collect_docx_files()
    book_list = "\n".join(f"  - {f}" for f in docx_files["book"]) or "  (없음)"
    measurements = _find_measurements()
    meas_list = (
        "\n".join(f"  - {f}" for f in measurements)
        if measurements
        else "  (없음 - Measured 열 원본 대조 생략)"
    )

    return f"""생성된 결과보고서의 **`# 실험 결과` 섹션**을 검증하세요 (Phase 1 검토).
{rework_section}
## 검토 대상

결과보고서:
{report_list}

예비보고서 (Predicted 값 참조용):
{pre_list}

교재 스캔본 (input/book/) — Table 원형 확인용:
{book_list}

측정값 파일 (input/measured/) — Measured 열 원본 대조용:
{meas_list}

## 검증 항목

`# 실험 결과` 섹션만 검토하세요. `# 연습 문제` 섹션과 `# 고찰` 섹션이 이미 보고서에 있더라도 이 단계에서는 *검증 대상이 아닙니다* (Phase 2·3 reviewer가 별도로 검증).

1. **교재 Table 구조 대조**: `input/book/` 원본의 Table 번호, 행/열 라벨, 작성 요구사항과 결과보고서 Table 구조가 일치하는지 확인
2. **임의 열 추가/누락 검증**: 교재에 없는 `Calculated`, `Measured`, `%(Difference)` 열이 추가되었거나, 교재에 있는 행/열이 빠졌으면 FAIL
3. **파생값 검증**: 교재가 `v_R = E - v_C`처럼 요구한 표 안의 파생값이 원래 행/열에 채워졌는지 확인
4. **Measured 열 원본 대조**: `input/measured/` 의 측정값 파일이 있으면 읽고, 결과보고서 Table의 Measured 열 값이 원본 측정값과 일치하는지 1:1 비교 (옮겨 적기 누락·오기·단위 변환 오류 발견 시 FAIL). 측정값 파일이 없으면 "측정값 파일 없음 — 원본 대조 생략"으로 표기하고 PASS 판정을 막지 않음
5. **Calculated 값 재계산**: 교재 Table이 계산값 비교 구조를 요구하는 경우에만, 실측 소자값으로 직접 재계산하여 Calculated 열과 일치하는지 확인
6. **측정 기반 산출값 검증**: 교재가 그래프 판독값, 측정 교차점, 특정 임계점, 특정 주파수/시간의 실측 데이터 기반 값을 요구하면 인접 측정점 보간 또는 명시된 판독 기준으로 산출했는지 확인. 측정 기반 표를 `X = R`, `V = E/√2`, `τ = RC` 같은 이론 기준값으로 단정하거나 관계식만으로 채웠으면 FAIL
7. **%(Difference) 검증**: 교재 Table이 계산값 비교 구조를 요구하는 경우에만 `|Calculated - Measured| / Calculated × 100` 공식으로 재계산
8. **단위 일관성**: mA, V, kΩ, Ω, μF, s 등 단위 표기 여부

## 출력 형식

검토 결과를 `{output_dir}/result_review_data.md` 에 저장하세요.
파일 형식:

```
## 실험 결과 검증

### [Table 번호]
- Table 구조: PASS 또는 FAIL (교재 원형 대비 행/열 누락, 임의 열 추가 여부)
- Measured 원본 대조: PASS 또는 FAIL (대조 불가 시 "측정값 파일 없음")
- Calculated 재계산: PASS 또는 FAIL (오류 내용)
- %(Difference) 계산: PASS 또는 FAIL (오류 내용 및 올바른 값)

### 발견된 오류 목록
- [구체적 오류 항목, 없으면 "없음"]

최종 판정: PASS
```

마지막 줄은 반드시 `최종 판정: PASS` 또는 `최종 판정: FAIL` 형식으로 끝내세요.
오류가 하나라도 있으면 FAIL, %(Difference) > 20%인 항목은 별도 표시하여 측정값 재확인을 권고하세요.
측정값 파일이 존재하지 않는 것은 FAIL 사유가 아닙니다. 단, 파일이 있는데 보고서 Measured 값과 다르면 FAIL입니다.
"""


def _build_result_reviewer_phase2_prompt(
    extra: str = "",
    output_dir: Path = OUTPUT_DIR,
) -> str:
    """Phase 2 검토: # 연습 문제 섹션 전용 (11-항목 검증 + 섹션 위치)."""
    rework_section = ""
    if extra:
        rework_section = f"\n## 이전 검토 FAIL 항목 (재작업 반영 확인)\n{extra}\n"

    result_reports = _find_result_reports(output_dir=output_dir)
    report_list = "\n".join(f"  - {f}" for f in result_reports) or "  (없음)"
    docx_files = collect_docx_files()
    exercise_list = (
        "\n".join(f"  - {f}" for f in docx_files["exercise"])
        if docx_files["exercise"]
        else "  (없음 — Phase 2 검토를 호출해서는 안 됩니다)"
    )

    return f"""생성된 결과보고서의 **`# 연습 문제` 섹션**을 검증하세요 (Phase 2 검토).
{rework_section}
## 검토 대상

결과보고서:
{report_list}

연습 문제 자료 (input/exercise/):
{exercise_list}

## 검증 항목

`# 연습 문제` 섹션만 검토하세요. `# 실험 결과` 섹션은 Phase 1 reviewer가 이미 검증했으므로 이 단계에서는 검증하지 마세요.

### 섹션 존재 확인
- `input/exercise/` 자료가 있는데 보고서에 `# 연습 문제` 섹션이 *없으면* FAIL (Exercise 누락).
- `input/exercise/` 자료가 *없는데* 보고서에 `# 연습 문제` 섹션이 있으면 FAIL (환각 섹션).

### 섹션이 있을 때 11개 항목 (system prompt `result-review` SKILL.md Step 6 참조)

- **(a) 섹션 위치**: `# 연습 문제`가 `# 실험 결과` *뒤*, (있다면) `# 고찰` *앞*에 위치하는가. 아니면 FAIL.
- **(b) Exercise 누락**: 입력 폴더의 모든 Exercise(이미지/PDF/MD)가 보고서에 작성되었는가.
- **(c) 입력 파싱**: 입력 자료의 *조건*(주어진 R, V, f 등)이 보고서 풀이에 정확히 반영되었는가 (단위 혼동 포함).
- **(d) 단위 변환**: p-p ↔ rms 변환에서 ×2√2, ÷2√2가 정확히 적용되었는가.
- **(e) 단계별 계산 흐름**: ① 결과가 ② 입력으로 정확히 사용되었는가.
- **(f) 공식 정확성**: X_L = 2πfL, |Z| = √(R²+X²), θ = arctan(X/R) 등 공식이 회로 이론과 일치하는가 (부호·인자 포함).
- **(g) 재계산 일치**: 모든 수치를 직접 재계산하여 보고서 값과 일치하는가.
- **(h) 단위 표기**: 모든 수치에 단위(V/mA/Ω/μF/Hz/° 등)가 표기되었는가.
- **(i) 정답-본문 일관성**: "정답" 섹션의 값이 본문 마지막 단계 결과와 일치하는가.
- **(j) Calculated/Experimental Table 형식** (Type 3 Exercise 한정): 헤더가 `구분 | Calculated | Experimental` 형식인가. Calculated 열만 풀이값으로 채워졌고, **Experimental 칸은 *모두* "실험 측정값" placeholder를 유지하는가** (자동 채움 흔적이 있으면 FAIL).
- **(k) 스타일 규칙**: 헤더 단독, 블록 줄바꿈, 결론/요약 bullet, italic 금지, 시각 기호 금지를 모두 만족하는가.

Q5 중간 산술 오류 정책 (system prompt 참조): 중간 표기와 정확값이 *최종 정답에서 동일 자리수*에서 같으면 PASS + "미세 표기 불일치" 메모. 최종 정답이 다르면 FAIL.

## 출력 형식

검토 결과를 `{output_dir}/result_review_exercise.md` 에 저장하세요.
파일 형식:

```
## 연습 문제 검증

- 섹션 위치: PASS 또는 FAIL (# 실험 결과 뒤 / # 고찰 앞 위치 여부)
- Exercise 누락: PASS 또는 FAIL (누락 Exercise 식별자)
- 입력 파싱: PASS 또는 FAIL (조건 불일치 항목)
- 단위 변환: PASS 또는 FAIL (p-p ↔ rms 오류 위치)
- 단계별 계산 흐름: PASS 또는 FAIL (앞→뒤 단계 불일치 위치)
- 공식 정확성: PASS 또는 FAIL (잘못된 공식 위치)
- 재계산 일치: PASS 또는 FAIL (보고서 값 vs 정확값)
- 단위 표기: PASS 또는 FAIL (단위 누락 항목)
- 정답-본문 일관성: PASS 또는 FAIL (불일치 Exercise)
- Calculated/Experimental Table 형식 (해당 시): PASS 또는 FAIL (Experimental 자동 채움 흔적 시 FAIL — placeholder만 허용)
- 스타일 규칙 (헤더 단독·블록 줄바꿈·결론/요약 bullet·italic·시각 기호): PASS 또는 FAIL (위반 위치)

### 발견된 오류 목록
- [구체적 오류 항목, 없으면 "없음"]

최종 판정: PASS
```

마지막 줄은 반드시 `최종 판정: PASS` 또는 `최종 판정: FAIL` 형식으로 끝내세요.
오류가 하나라도 있으면 FAIL입니다.
"""


def _build_result_reviewer_phase3_prompt(
    extra: str = "",
    output_dir: Path = OUTPUT_DIR,
) -> str:
    """Phase 3 검토: # 고찰 섹션 품질 검토."""
    rework_section = ""
    if extra:
        rework_section = f"\n## 이전 검토 FAIL 항목 (재작업 반영 확인)\n{extra}\n"

    result_reports = _find_result_reports(output_dir=output_dir)
    report_list = "\n".join(f"  - {f}" for f in result_reports) or "  (없음)"

    return f"""생성된 결과보고서의 **고찰 섹션**을 검토하세요 (Phase 3 검토).
{rework_section}
## 검토 대상

결과보고서:
{report_list}

## 검증 항목

`# 고찰` 섹션만 검토하세요:

0. **고찰 위치** (구조 우선): `# 고찰`이 보고서의 *마지막* top-level `#` 섹션이며 (그 뒤에 다른 `# ` 섹션 없음), `# 연습 문제`가 있으면 그 *뒤*에 오는지 확인. `# 실험 결과`와 `# 연습 문제` 사이 등 잘못된 위치면 구조 FAIL (끼어든 위치 인용)
1. **결과 분석**: 각 Table의 %(Difference) 수치가 구체적으로 인용되었는지, 분석 기법별로 그룹화되었는지 확인
2. **측정값-이론값 구분**: 측정 기반 산출값과 이론 기준값의 차이를 단순 오류로 처리하지 않고, 보간값·판독값·이론 기준값을 구분해 설명했는지 확인
3. **오차 원인**: 각 원인에 정량적 근거(공칭값 vs 실측값 등)가 포함되었는지 확인. 측정 기반 결과와 이론 기준값이 다르면 소자 오차, 계측 한계, 그래프 판독 오차 등 데이터에 근거한 가능한 원인을 제시했는지 확인
4. **개선 방안**: 오차 원인과 1:1 대응하는 구체적 방법이 서술되었는지 확인
5. **결론**: 오차율 범위의 정량적 요약, 실험 목적 달성 여부가 포함되었는지 확인
6. **형식**: `# 고찰` 아래 각 소섹션 본문 문단이 top-level bullet `-` 로 시작하는지 확인. 각 소섹션 헤더와 첫 bullet 사이에는 빈 줄이 정확히 하나 있어야 하고, 연속 bullet 문단 사이에는 빈 줄이 없어야 하며, 긴 bullet 문단은 임의 hard-wrap 되면 안 됨. 일반 문단, nested bullet, numbered list, table 사용 시 FAIL

## 출력 형식

검토 결과를 `{output_dir}/result_review.md` 에 저장하세요.
파일 형식:

```
## 고찰 검토 결과

### 고찰 위치
- 판정: PASS 또는 FAIL (# 고찰이 마지막 top-level 섹션이며 # 연습 문제 뒤인지)

### 고찰 서식
- 판정: PASS 또는 FAIL (각 본문 문단이 top-level bullet `-` 형식인지)

### 결과 분석
- 판정: PASS 또는 FAIL (이유)

### 오차 원인
- 판정: PASS 또는 FAIL (정량적 근거 누락 여부 등)

### 개선 방안
- 판정: PASS 또는 FAIL (1:1 대응 누락 여부)

### 결론
- 판정: PASS 또는 FAIL (정량적 요약 누락 여부)

### 발견된 문제점
- [구체적 항목, 없으면 "없음"]

최종 판정: PASS
```

마지막 줄은 반드시 `최종 판정: PASS` 또는 `최종 판정: FAIL` 형식으로 끝내세요.
"""


def _select_result_reviewer_prompt(
    extra: str = "",
    output_dir: Path = OUTPUT_DIR,
    exercise_dir: Path = EXERCISE_DIR,
) -> tuple[str, Path, str]:
    """result-reviewer 단독 실행 시 Phase를 자동 판별한다.

    분기 우선순위:
      1. 보고서에 `# 고찰` 있음 → phase3 (고찰 review).
      2. 보고서에 `# 연습 문제` 있음 → phase2 (연습 문제 review).
      3. result_review_data.md PASS + exercise dir 비어있음 → phase3 (exercise-skip 경로).
      4. 그 외 → phase1 (데이터 review).
    """
    latest_report = _latest_result_report(output_dir=output_dir)
    if latest_report is not None and _has_discussion_section(latest_report):
        return (
            _build_result_reviewer_phase3_prompt(extra, output_dir=output_dir),
            output_dir / "result_review.md",
            "phase3",
        )
    if latest_report is not None and _has_exercise_section(latest_report):
        return (
            _build_result_reviewer_phase2_prompt(extra, output_dir=output_dir),
            output_dir / "result_review_exercise.md",
            "phase2",
        )
    # exercise-skip path: Phase 1 이미 PASS + exercise dir 비었으면 phase3로 직행
    data_review = output_dir / "result_review_data.md"
    if (
        parse_review_verdict(data_review) == "PASS"
        and not _exercise_files_present(exercise_dir=exercise_dir)
    ):
        return (
            _build_result_reviewer_phase3_prompt(extra, output_dir=output_dir),
            output_dir / "result_review.md",
            "phase3",
        )
    return (
        _build_result_reviewer_phase1_prompt(extra, output_dir=output_dir),
        output_dir / "result_review_data.md",
        "phase1",
    )


def build_prompt(role: str, extra: str = "") -> str:
    if role == "pre-generator":
        return _build_pre_generator_prompt(extra)
    if role == "pre-reviewer":
        return _build_pre_reviewer_prompt(extra)
    if role == "result-generator":
        return _build_result_generator_phase1_prompt(extra)
    if role == "result-reviewer":
        return _build_result_reviewer_phase1_prompt(extra)
    raise ValueError(f"알 수 없는 역할: {role}")

