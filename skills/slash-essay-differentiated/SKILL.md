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
2. 학생용 문제부(모범 답안 제외)와 교사용 정답부(답안 및 채점 기준)를 각각 분리하여 2개의 마크다운 텍스트 블록으로 생성한다.

## 에이전트 행동 수칙
1. 파일 경로를 읽어 지문 텍스트를 추출한다.
2. `templates/differentiated_prompt.j2`의 지시사항을 준수하여 2개의 마크다운(문제지, 지도안) 내용을 생성한다.
3. **학생용 문제지 저장**: 학생용 마크다운 내용을 `output/essay-questions/` 폴더 내에 `YYYYMMDD_HHMMSS-diff-키워드.md` 파일로 저장한다.
4. **교사용 지도안 저장**: 정답이 포함된 교사용 마크다운을 `output/lesson-plans/` 폴더 내에 `YYYYMMDD_HHMMSS-diff-키워드_lesson.md` 파일로 저장한다.
5. **품질/보안 검수 강제**: 두 파일이 저장된 직후, 각 파일에 대해 `/essay-review` 스킬을 호출하여 검증한다.
   - 학생용: 모범 답안 유출(Format Security)이 없는지 검증.
   - 교사용: 모범 답안과 채점 기준이 누락 없이 완벽한지 검증.
   - Fail 판정이 나올 경우 지적 사항을 반영하여 파일을 수정한 뒤 덮어쓴다.
6. **PDF 렌더링**: 검수를 모두 통과한 후, 두 파일 각각에 대해 `tools/exam-pdf/make_exam_pdf.py`를 호출하여 PDF로 변환한다.
   - 학생용: `python3 tools/exam-pdf/make_exam_pdf.py [학생용_경로] --title "수준별 영어 서술형 평가" --subtitle "[학년] 대비"`
   - 교사용: `python3 tools/exam-pdf/make_exam_pdf.py [교사용_경로] --title "수준별 서술형 교사용 지도안" --subtitle "[학년] 대비"`
7. 모든 변환이 완료되면 사용자에게 두 파일의 경로를 보고한다.
