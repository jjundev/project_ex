# 기초전기실험 보고서 자동화 하네스

## 개요
교재 스캔본, 강의노트, 실험 영상 STT를 기반으로 예비보고서/결과보고서를 자동 생성한다.

## 첫 셋업

```bash
# 1. 의존성 설치 (Claude + Codex 양쪽)
pip install -r requirements.txt -r requirements-codex.txt

# 2. Codex CLI 로그인 (gpt-quality preset 사용 시)
codex login
```

기본 preset은 `gpt-quality` (Codex Python SDK + gpt-5.5)다. Claude Opus/Sonnet으로 강제하려면 매 실행에 `--model-preset claude-default` 를 붙인다.

## 사용 가능 커맨드

```bash
# 전체 파이프라인 (예비 → 결과)
python harness.py

# 예비보고서만 (GAN 루프 포함)
python harness.py --to pre-reviewer

# 결과보고서만 (예비보고서 선행 필요)
python harness.py --from result-generator

# GAN 루프 최대 횟수 지정
python harness.py --to pre-reviewer --max-rounds 2

# 실행 경로 미리보기 (실제 실행 안 함)
python harness.py --dry-run

# Claude (Opus/Sonnet) 강제 사용
python harness.py --model-preset claude-default
```

### 파이프라인 역할 순서
`pre-generator` → `pre-reviewer` → `result-generator` → `result-reviewer`

예비보고서는 **2단계 GAN 루프**로 작성된다:

| 단계 | 역할 | 내용 | 모델 |
|---|---|---|---|
| Phase 1 생성 | `pre-generator` | 실험 목적·준비물·이론 작성 | Opus |
| Phase 1 검토 | `pre-reviewer` | 이론 섹션 완성도 검증 → `pre_review_theory.md` | Sonnet |
| Phase 2 생성 | `pre-generator` | 예상 결과 값 추가 | Opus |
| Phase 2 검토 | `pre-reviewer` | KVL/KCL 계산 검증 → `pre_review.md` | Sonnet |
| Phase 1 생성 | `result-generator` | 실험 결과 섹션 + 연습 문제 섹션 작성 (`input/exercise/` 있을 때) | Opus |
| Phase 1 검토 | `result-reviewer` | %(Difference) 수치 검증 + 연습 문제 9개 항목 검증 → `result_review_data.md` | Sonnet |
| Phase 2 생성 | `result-generator` | 고찰 섹션 추가 | Opus |
| Phase 2 검토 | `result-reviewer` | 고찰 품질 검토 → `result_review.md` | Sonnet |

## 디렉토리 구조
- `docx/` : 보고서 템플릿
  - `template_pre_report.md` : 예비보고서 마크다운 템플릿
  - `template_result_report.md` : 결과보고서 마크다운 템플릿
- `input/` : 주차별 입력 자료
  - `book/` : 교재 스캔본 이미지 (회로도, Table, 실험 절차)
  - `note/` : 강의노트 PDF (이론, 공식)
  - `stt/` : 실험 영상 STT (`{ch}-{part}.txt`)
  - `measured/` : 실제 실험에서 측정한 값 (`{N}주차_측정값.md`)
  - `exercise/` : 연습 문제 자료 (선택, KakaoTalk 이미지/PDF/MD/텍스트). 폴더 비어있으면 # 연습 문제 섹션 자동 생략.
- `output/` : 생성된 보고서 (Markdown + PDF)

## 보고서 품질 기준
- 모든 예상값 Table에 **풀이 과정** 필수 포함
- **KVL/KCL 검증** 수행 (폐회로 전압합 = 전원전압, 노드 전류 보존)
- **단위 명시**: mA, V, kΩ, Ω, μF, s
- 연립방정식은 크래머 공식으로 풀이하고 중간 과정을 생략하지 않는다
- 실험 주제에 해당하는 분석 방법 적용 (옴의 법칙, 직병렬, 중첩, 테브난/노튼, 메쉬/노드 해석, DC 정상상태, 과도응답 등)

## input/ 자료 준비 규칙
1. `book/` 에 해당 주차 교재 페이지를 순서대로 스캔하여 저장
2. `note/` 에 해당 주차 강의노트 PDF 저장
3. `stt/` 에 실험 영상 STT 저장 (선택, 검증용)
   - 파일명 형식: `{챕터번호}-{파트번호}.txt` (예: `15-1.txt`)
4. `measured/` 에 실험 측정값 저장 (결과보고서 작성 시 필요)
   - 파일명 형식: `{N}주차_측정값.md`
5. `exercise/` 에 연습 문제 자료 저장 (선택)
   - 허용 형식: `.jpg`, `.png`, `.jpeg`, `.gif`, `.bmp`, `.tiff`, `.webp`, `.pdf`, `.md`, `.txt`
   - 파일명 자유 (KakaoTalk 타임스탬프 그대로 OK). agent가 vision으로 내용을 파싱하여 Ch 그룹 자동 추론.
   - 폴더가 없거나 비어있으면 결과보고서에 `# 연습 문제` 섹션이 생성되지 않는다.
