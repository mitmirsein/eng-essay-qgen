---
name: slash-essay-differentiated
description: 동일한 지문에서 상/중/하 난이도별 3개의 서술형 문제를 동시 출제하는 수준별 맞춤 출제(Differentiated Instruction) 워크플로우를 실행합니다.
status: active
version: 1.0.0
---

# /essay-differentiated 워크플로우

이 스킬은 학교 현장의 '수준별 수업'을 지원하기 위해, 단일 지문을 바탕으로 하위권(Level 1), 중위권(Level 2), 상위권(Level 3) 맞춤형 서술형 문항 3세트를 동시에 출제하고 채점 기준까지 한 번에 생성하는 고급 워크플로우입니다.

## 사용법
`/essay-differentiated <지문_파일_경로> [학년]`
- `<지문_파일_경로>`: 출제의 바탕이 될 지문 텍스트 파일 (.txt)
- `[학년]`: (옵션) 중1, 중2, 중3, 고1, 고2/3 등 대상 학년.

## 실행 단계 (프롬프트 엔진)

사용자가 `/essay-differentiated`를 호출하면, 에이전트는 입력받은 지문 텍스트를 읽고 `templates/differentiated_prompt.j2` 프롬프트를 바탕으로 수준별 문항을 생성합니다.

### 지시사항 (가이드라인)
1. 프롬프트 로직에 따라 Level 1(기초), Level 2(심화), Level 3(종합)의 3문항 세트를 설계한다.
2. 예시 답안과 채점 기준을 한 문서 안에 모두 통합하여 마크다운을 작성한다.

## 에이전트 행동 수칙
1. 파일 경로를 읽어 지문 텍스트를 추출한다.
2. `templates/differentiated_prompt.j2`의 지시사항을 정확히 준수하여 마크다운 포맷으로 출제 데이터를 생성한다.
3. **결과물 저장**: 파일 쓰기 도구를 사용하여 `projects/eng-essay-qgen/output/essay-questions/` 폴더 내에 `YYYYMMDD_HHMMSS-diff-키워드.md` 형태의 파일로 저장한다. (예: `20260801_130000-diff-climate_change.md`)
4. 파일 저장이 완료되면, `tools/exam-pdf`를 사용하여 PDF로 변환한다.
   - 실행 명령어: `python3 tools/exam-pdf/make_exam_pdf.py [저장된_마크다운_경로] --title "수준별 영어 서술형 평가" --subtitle "[학년] 대비"`
5. PDF 변환까지 완료되면 사용자에게 "수준별 3종 세트 문항이 생성되어 [파일명] 경로에 저장되었습니다."라고 보고한다.
