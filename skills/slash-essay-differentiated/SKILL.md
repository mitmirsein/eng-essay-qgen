---
name: slash-essay-differentiated
description: 하나의 지문에서 공통 목표를 유지한 수준별 assessment package를 생성합니다.
---

# /essay-differentiated 워크플로우

`/essay-differentiated <지문_파일_경로> [학년]`을 실행한다. `고2`와 `고3`은 `고2/3`으로
정규화한다.

## 생성 규칙

1. 지문과 학년을 먼저 분석하고 Level 1·2·3의 공통 학습 목표를 정한다.
2. `templates/differentiated_prompt.j2`에 따라 각 수준의 인지 부담, 언어 지원, 답안
   독립성을 조절한다. 고정된 단어 수·문법 목록을 복사하지 않는다.
3. 각 수준에 자체 `conditions`, `rubric`, `model_answers`를 둔다. 결정론적 조건은 모든
   해당 수준의 모범답안이 통과해야 하며, 의미 판단은 semantic/manual 검수로 남긴다.
4. 다음 private package에 JSON을 저장한다.

   `output/lesson-plans/_packages/<assessment-id>/assessment.json`

5. 스키마와 answer validator를 실행한 뒤 안전한 렌더러로 학생용과 교사용을 분리한다.

   ```bash
   uv run python scripts/validate_assessment.py \
     output/lesson-plans/_packages/<assessment-id>/assessment.json --student-scan
   uv run python scripts/render_package.py \
     output/lesson-plans/_packages/<assessment-id>/assessment.json \
     --target all --output output/lesson-plans/_packages/<assessment-id>/rendered
   ```

## 보안 및 PDF

- 학생용에는 세 수준의 지시문·지문·조건만 표시한다. 답안, rubric, 배점 기준은 절대 표시하지 않는다.
- 교사용에는 각 수준의 답안과 rubric을 표시한다.
- 학생 PDF는 `--profile exam`, 교안 PDF는 `--profile teacher`로 만들고, Missing character와
  Overfull 오류가 있으면 수정 후 다시 빌드한다.
- Level 3 분량 같은 수치는 지문·학년·과제 목적에서 도출하고 임의로 고정하지 않는다.
