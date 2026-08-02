---
name: slash-essay-grade
description: private assessment package의 rubric으로 텍스트·이미지 답안을 안전하게 채점하고 익명 리포트를 생성합니다.
---

# /essay-grade 워크플로우

사용 예:

```text
/essay-grade <assessment.json> "학생 답안"
/essay-grade <assessment.json> <답안_이미지>
/essay-grade <assessment.json> --batch <답안_디렉터리>
```

## 입력과 채점 순서

1. 학생용 문제지에서 rubric을 추출하지 않는다. `assessment.json` 또는 검증된 교사용
   package에서 조건, rubric, language policy를 읽는다.
2. 텍스트 답안은 원문을 보존한다. 이미지 답안은 VLM으로 전사하되, 다음 문구로 HITL
   확인을 받기 전에는 절대 채점하지 않는다.

   `텍스트가 올바르게 추출되었는지 확인해주세요. 수정할 부분이 없다면 '진행'이라고 승인해주세요.`

3. 배치 이미지에는 `scripts/manage_batch.py init`을 사용하고, 각 항목을
   `pending-extraction -> pending-review -> corrected 또는 approved`로 전이한다.
   `approved` 또는 `corrected` 항목만 채점 대상이다.
4. `templates/grading_prompt.j2`와 package validator를 사용해 결정론적 조건을 먼저
   확인하고, 그 다음 의미 판단과 package의 언어 감점 정책을 적용한다. 같은 원인의 반복
   오류와 언어 감점 상한을 지키며 내용 조건과 이중 감점하지 않는다.

## 개인정보와 출력

- 저장 리포트에는 익명 학생 ID만 사용하고 학생 이름·원본 이미지 경로를 넣지 않는다.
- 배치 산출물은 `output/lesson-plans/grading/<batch-id>/reports/`에 저장한다.
- class summary는 개별 점수를 변경하지 않는 읽기 전용 집계다.
- 이미지 전사가 불확실하면 임의 보정하지 말고 불확실 구간을 기록한 뒤 사람 승인 대기 상태로 둔다.
