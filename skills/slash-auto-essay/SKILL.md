---
name: slash-auto-essay
description: 주제와 학년을 받아 지문·assessment package·검수·교안·PDF를 순서대로 생성하는 오케스트레이터입니다.
---

# /auto-essay 오케스트레이터

`/auto-essay "주제 또는 대략적인 내용" [중1|중2|중3|고1|고2|고3] [type1|type2|type3]`
을 실행한다. `고2`와 `고3`은 내부적으로 `고2/3`으로 통합한다.

## 반드시 지키는 순서

1. 주제와 학년에 맞는 지문을 생성하고 `passages/`에 저장한다. type2라면 실제로 균형 잡힌
   A/B sections를 만든다.
2. `scripts/validate_passage.py`로 단어 수, 문단, 공백·문자, 문장 길이 통계, type2 A/B
   최소 정보량을 확인한다. 결정론적 검사 실패 시 문제 생성을 중단한다.
3. 의미 기반 지문 검수로 문체·시제 일관성, 근거 충분성, 사실성·편향·민감 표현, A/B 균형을
   확인한다. 불확실한 판정은 사람 검수 대기로 표시한다.
4. `/essay-qgen` 또는 `/essay-differentiated` 로 private `assessment.json`을 만들고
   schema를 검증한다.
5. 결정론적 answer validator를 실행한 후 의미 기반 package review를 실행한다.
6. 학생용 allowlist 렌더와 교사용 렌더를 분리하고 `manifest.json`을 완료한다. 학생용에는
   답안·rubric·QA·교안 데이터를 넣지 않는다.
7. `lesson-plan.json`을 `templates/lesson_plan_prompt.j2`로 만들고 교안 validator를
   통과시킨 뒤 교사용 Markdown을 재렌더한다.
8. 학생 PDF는 `--profile exam`, 교안 PDF는 `--profile teacher`로 빌드한다. Pandoc,
   XeLaTeX return code, Missing character, Overfull 기준을 모두 확인한다.

## 산출물 위치

```text
passages/<id>.txt
output/lesson-plans/_packages/<assessment-id>/assessment.json
output/lesson-plans/_packages/<assessment-id>/lesson-plan.json
output/essay-questions/<assessment-id>/student.md
output/lesson-plans/<assessment-id>/teacher.md
```

모든 생성물은 허용된 `output/` 하위에 두고, 기존 파일은 명시적 overwrite 없이 보존한다.
