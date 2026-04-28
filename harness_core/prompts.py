from __future__ import annotations

from pathlib import Path

from .config import OUTPUT_DIR, STT_DIR, TEMPLATE_PATH
from .io_state import (
    _find_measurements,
    _find_pre_reports,
    _find_result_reports,
    _has_discussion_section,
    _latest_result_report,
    collect_docx_files,
)


def _build_pre_generator_prompt(extra: str = "") -> str:
    files = collect_docx_files()
    book_list = "\n".join(f"  - {f}" for f in files["book"]) or "  (없음)"
    note_list = "\n".join(f"  - {f}" for f in files["note"]) or "  (없음)"
    exp_list = "\n".join(f"  - {f}" for f in files["stt"]) or "  (없음)"

    rework_section = ""
    if extra:
        rework_section = f"\n## 재작업 지시사항\n{extra}\n"

    return f"""아래 자료를 사용하여 예비보고서 **Phase 1** (실험 목적·준비물·이론)을 생성하세요.

> **주의**: 이번 단계에서는 `## 예상 결과 값` 섹션을 작성하지 마세요.
> 예상 결과 값은 이론 검토 통과 후 Phase 2에서 별도로 작성합니다.
{rework_section}
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

1. 위 자료를 **모두** 읽으세요. 파일을 건너뛰지 마세요.
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


def _build_result_generator_prompt(extra: str = "") -> str:
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
    if extra:
        rework_section = f"\n## 재작업 지시사항\n{extra}\n"

    return f"""아래 자료를 사용하여 결과보고서 **Phase 1** (실험 결과)을 생성하세요.

> **주의**: 이번 단계에서는 `# 고찰` 섹션을 작성하지 마세요.
> 고찰은 실험 결과 검토 통과 후 Phase 2에서 별도로 작성합니다.
> `# 연습 문제` 섹션도 작성하지 마세요.
{rework_section}
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

1. 예비보고서를 읽어 예상값 테이블 구조를 파악하세요.
2. `input/book/` 이미지를 다시 읽어 각 교재 Table의 원래 행/열 구조와 작성 요구사항을 확인하세요.
3. 측정값 파일이 있으면 읽고, 없으면 사용자에게 각 Table별 측정값을 질문하세요.
4. 교재 Table 원형 구조를 최상위 기준으로 삼으세요. 교재에 없는 `Calculated`, `Measured`, `%(Difference)` 열을 임의로 추가하지 마세요.
5. 교재가 `v_R = E - v_C`처럼 표 안의 파생값 작성을 요구하면, 그 값을 원래 Table 행/열에 채우세요.
6. system prompt의 **Step 1~3** (예비보고서 로드, 실측값 입력, 실험 결과 작성)을 수행하세요.
7. `# 실험 결과` 섹션만 작성하세요 (`# 고찰`, `# 연습 문제` 미작성).
8. 최종 보고서는 `{OUTPUT_DIR}` 경로에 Markdown 파일로 저장하세요.
9. 파일명 형식: `{{N}}주차_결과보고서.md`
"""


def _build_result_generator_phase2_prompt(extra: str = "") -> str:
    result_reports = _find_result_reports()
    report_list = "\n".join(f"  - {f}" for f in result_reports) or "  (없음)"

    rework_section = ""
    if extra:
        rework_section = f"\n## 재작업 지시사항\n{extra}\n"

    return f"""결과보고서에 **고찰 섹션만** 추가하세요 (Phase 2).

> `# 연습 문제` 섹션은 작성하지 마세요.
{rework_section}
## 현재 결과보고서 (Phase 1에서 작성된 파일)

{report_list}

## 지시사항

1. 현재 결과보고서를 읽어 `# 실험 결과` 섹션의 모든 Table 데이터와 %(Difference) 수치를 파악하세요.
2. system prompt의 **Step 4 (고찰 작성)** 지침에 따라 고찰을 작성하세요.
   - 결과 분석, 오차 원인, 개선 방안, 결론 소섹션 포함
   - 구체적인 %(Difference) 수치 인용 필수
   - 정량적 오차 원인 분석 필수
3. 기존 결과보고서 파일을 **수정**하여 `# 고찰` 섹션을 반영하세요.
   - 파일에 `# 고찰` 섹션이 **이미 있으면 교체**하고, 없으면 파일 끝에 **추가**하세요.
   - `# 실험 결과` 섹션은 변경하지 마세요.
4. 저장 후 완료를 보고하세요.
"""


def _build_result_reviewer_phase1_prompt(
    extra: str = "",
    output_dir: Path = OUTPUT_DIR,
) -> str:
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

    return f"""생성된 결과보고서의 **실험 결과 섹션**을 검증하세요 (Phase 1 검토).
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

`# 실험 결과` 섹션만 검토하세요 (고찰 섹션은 아직 없습니다):

1. **교재 Table 구조 대조**: `input/book/` 원본의 Table 번호, 행/열 라벨, 작성 요구사항과 결과보고서 Table 구조가 일치하는지 확인
2. **임의 열 추가/누락 검증**: 교재에 없는 `Calculated`, `Measured`, `%(Difference)` 열이 추가되었거나, 교재에 있는 행/열이 빠졌으면 FAIL
3. **파생값 검증**: 교재가 `v_R = E - v_C`처럼 요구한 표 안의 파생값이 원래 행/열에 채워졌는지 확인
4. **Measured 열 원본 대조**: `input/measured/` 의 측정값 파일이 있으면 읽고, 결과보고서 Table의 Measured 열 값이 원본 측정값과 일치하는지 1:1 비교 (옮겨 적기 누락·오기·단위 변환 오류 발견 시 FAIL). 측정값 파일이 없으면 "측정값 파일 없음 — 원본 대조 생략"으로 표기하고 PASS 판정을 막지 않음
5. **Calculated 값 재계산**: 교재 Table이 계산값 비교 구조를 요구하는 경우에만, 실측 소자값으로 직접 재계산하여 Calculated 열과 일치하는지 확인
6. **%(Difference) 검증**: 교재 Table이 계산값 비교 구조를 요구하는 경우에만 `|Calculated - Measured| / Calculated × 100` 공식으로 재계산
7. **단위 일관성**: mA, V, kΩ, Ω, μF, s 등 단위 표기 여부

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
    rework_section = ""
    if extra:
        rework_section = f"\n## 이전 검토 FAIL 항목 (재작업 반영 확인)\n{extra}\n"

    result_reports = _find_result_reports(output_dir=output_dir)
    report_list = "\n".join(f"  - {f}" for f in result_reports) or "  (없음)"

    return f"""생성된 결과보고서의 **고찰 섹션**을 검토하세요 (Phase 2 검토).
{rework_section}
## 검토 대상

결과보고서:
{report_list}

## 검증 항목

`# 고찰` 섹션만 검토하세요:

1. **결과 분석**: 각 Table의 %(Difference) 수치가 구체적으로 인용되었는지, 분석 기법별로 그룹화되었는지 확인
2. **오차 원인**: 각 원인에 정량적 근거(공칭값 vs 실측값 등)가 포함되었는지 확인
3. **개선 방안**: 오차 원인과 1:1 대응하는 구체적 방법이 서술되었는지 확인
4. **결론**: 오차율 범위의 정량적 요약, 실험 목적 달성 여부가 포함되었는지 확인
5. **형식**: 모든 소섹션이 문단(paragraph) 형식인지 확인 (bullet point 사용 여부)

## 출력 형식

검토 결과를 `{output_dir}/result_review.md` 에 저장하세요.
파일 형식:

```
## 고찰 검토 결과

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


def _build_result_reviewer_prompt(extra: str = "", output_dir: Path = OUTPUT_DIR) -> str:
    rework_section = ""
    if extra:
        rework_section = f"\n## 이전 검토 FAIL 항목\n{extra}\n"
    docx_files = collect_docx_files()
    book_list = "\n".join(f"  - {f}" for f in docx_files["book"]) or "  (없음)"
    measurements = _find_measurements()
    meas_list = (
        "\n".join(f"  - {f}" for f in measurements)
        if measurements
        else "  (없음 - Measured 열 원본 대조 생략)"
    )

    return f"""생성된 결과보고서의 오차율 계산을 검증하세요.
{rework_section}
## 검토 대상

`{output_dir}` 경로의 최신 결과보고서 (`*주차_결과보고서.md`)를 읽으세요.

교재 스캔본 (input/book/) — Table 원형 확인용:
{book_list}

측정값 파일 (input/measured/) — Measured 열 원본 대조용:
{meas_list}

## 검증 항목

1. **교재 Table 구조 대조**: 원본 Table의 행/열 라벨과 결과보고서 Table 구조가 일치하는지 확인
2. **임의 열 추가/누락 검증**: 교재에 없는 `Calculated`, `Measured`, `%(Difference)` 열이 추가되었거나, 교재에 있는 행/열이 빠졌으면 FAIL
3. **Measured 열 원본 대조**: `input/measured/` 의 측정값 파일이 있으면 읽고, 결과보고서 Table의 Measured 열 값이 원본 측정값과 일치하는지 1:1 비교 (옮겨 적기 누락·오기·단위 변환 오류 발견 시 FAIL). 측정값 파일이 없으면 "측정값 파일 없음 — 원본 대조 생략"으로 표기
4. **오차율 공식**: 교재 Table이 계산값 비교 구조를 요구하는 경우에만 `|Calculated - Measured| / Calculated × 100 (%)` 계산 정확성 확인
5. **Calculated 재계산**: 교재 Table이 계산값 비교 구조를 요구하는 경우에만 실측 소자값으로 올바르게 재계산되었는지 확인
6. **오차 원인 분석**: 저항 ±5% 등 허용 오차 범위 고려 여부

## 출력 형식

검토 결과를 `{output_dir}/result_review.md` 에 저장하세요.
마지막 줄은 반드시 `최종 판정: PASS` 또는 `최종 판정: FAIL` 형식으로 끝내세요.
측정값 파일이 존재하지 않는 것은 FAIL 사유가 아닙니다. 단, 파일이 있는데 보고서 Measured 값과 다르면 FAIL입니다.
"""


def _select_result_reviewer_prompt(
    extra: str = "",
    output_dir: Path = OUTPUT_DIR,
) -> tuple[str, Path, str]:
    """result-reviewer 단독 실행 시 Phase를 자동 판별한다."""
    latest_report = _latest_result_report(output_dir=output_dir)
    if latest_report is not None and _has_discussion_section(latest_report):
        return _build_result_reviewer_phase2_prompt(extra, output_dir=output_dir), output_dir / "result_review.md", "phase2"
    return _build_result_reviewer_phase1_prompt(extra, output_dir=output_dir), output_dir / "result_review_data.md", "phase1"


def build_prompt(role: str, extra: str = "") -> str:
    if role == "pre-generator":
        return _build_pre_generator_prompt(extra)
    if role == "pre-reviewer":
        return _build_pre_reviewer_prompt(extra)
    if role == "result-generator":
        return _build_result_generator_prompt(extra)
    if role == "result-reviewer":
        return _build_result_reviewer_phase1_prompt(extra)
    raise ValueError(f"알 수 없는 역할: {role}")

