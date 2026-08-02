---
name: slash-essay-review
description: assessment package와 학생·교사용 렌더를 결정론적·의미 기반으로 교차 검수합니다.
---

# /essay-review 워크플로우

`/essay-review <경로> [package|student|teacher]`를 사용한다. 경로가 없으면 현재 작업의
명시된 package를 먼저 찾고, 파일명을 추측해 학생용 파일을 원본으로 삼지 않는다.

## 검수 순서

1. `package` 모드에서는 먼저 schema와 결정론적 validator를 실행한다.

   ```bash
   uv run python scripts/validate_assessment.py <assessment.json> --student-scan
   ```

   단어 수, surface pattern, literal, n-gram, format, rubric 합계, condition 연결,
   placeholder, grade alias를 확인한다. 이 단계가 실패하면 의미 검수나 렌더를 진행하지 않는다.
2. 통과한 package에 대해 지문 근거, 조건의 명확성, 답안의 의미 충족, rubric의 공정성,
   사실성·편향·민감 표현을 semantic 검수한다. 결정론적 도구가 판단하지 못하는 항목은
   `deferred` 또는 사람 검수로 명시한다.
3. `student` 모드에서는 금지어와 답안 누출을 검사한다. 다음 중 하나라도 있으면 Fail이다:
   `모범 답안`, `Sample Answer`, `채점 기준`, `채점기준`, `배점표`, `Rubric`.
4. `teacher` 모드에서는 private package의 rubric과 모범답안이 교사용 출력에 존재하는지,
   학생용 출력에는 존재하지 않는지 확인한다.

## 출력 정책

- 검수 리포트는 `qa-report.json` 또는 지정된 review 파일에 저장한다.
- 학생용 파일을 검수하면서 답안이나 rubric을 보충하지 않는다.
- Fail이면 원인을 고친 새 package를 만들고 validator부터 다시 실행한다.
- 사람이 확인해야 하는 의미·문체·민감성 판정은 자동 Pass로 위장하지 않는다.
