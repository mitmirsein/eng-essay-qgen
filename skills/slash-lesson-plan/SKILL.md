---
name: slash-lesson-plan
description: 검증된 assessment package와 교육과정 reference로 구조화된 교안 JSON과 교사용 렌더를 생성합니다.
---

# /lesson-plan 워크플로우

`/lesson-plan <assessment.json> [teacher_profile.yaml]`을 실행한다. 학생용 Markdown을
원본으로 사용하지 않는다.

## 생성 절차

1. assessment schema와 deterministic validator가 통과했는지 확인한다.
2. `config/teacher_profile.example.yaml` 또는 명시된 profile을 읽고 CLI override를 적용한다.
3. `references/curriculum-2022.json`에서 대상 학년·수업 목표에 맞는 성취기준을 고른다.
   reference에 없는 코드는 사용하지 않는다.
4. `templates/lesson_plan_prompt.j2`에 assessment, profile, curriculum reference, 수업
   시간, 수업 모드를 주입한다. prompt의 출력은 JSON 하나뿐이며 assessment의 조건·rubric·
   답안을 복제하거나 변경하지 않는다.
5. `lesson-plan.json`을 다음 경로에 저장하고 validator를 실행한다.

   ```bash
   uv run python scripts/validate_lesson_plan.py \
     output/lesson-plans/_packages/<assessment-id>/lesson-plan.json \
     --assessment output/lesson-plans/_packages/<assessment-id>/assessment.json
   ```

   수업 시간 합계, 발문별 예상 반응·확인 방법, condition 계획, 성취기준 코드, 수준별
   지원, 오개념, scoring anchors, placeholder·emoji를 검사한다.
6. 교사용 렌더에 lesson plan JSON을 연결한다.

   ```bash
   uv run python scripts/render_package.py \
     output/lesson-plans/_packages/<assessment-id>/assessment.json \
     --lesson-plan output/lesson-plans/_packages/<assessment-id>/lesson-plan.json \
     --target teacher --output output/lesson-plans/<assessment-id>
   ```

## 교육적 품질

- type1은 지문 근거와 해석을, type2는 A/B 정보 조직과 패러프레이징을, type3은 독자·목적·
  실행 가능한 조언 또는 의견을 중심으로 지도한다.
- differentiated는 공통 목표를 유지하면서 support, core, extension의 접근 방식만 조절한다.
- 모든 목표는 관찰 가능한 학생 행동으로 쓰고, 실제 지문에 없는 어휘·문법·상징을 만들지 않는다.
- 장식용 이모지와 XeLaTeX 취약 문자는 교안 데이터와 PDF 입력에서 사용하지 않는다.
