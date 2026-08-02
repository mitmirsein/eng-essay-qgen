---
name: slash-essay-qgen
description: 지문과 학년을 분석해 적응형 영어 서술형 assessment package를 생성하고 결정론적 검증까지 수행합니다.
---

# /essay-qgen 워크플로우

`/essay-qgen <지문_파일_경로> [type1|type2|type3] [학년]`을 실행한다. `고2`와 `고3`은
`고2/3`으로 정규화한다.

## 처리 순서

1. 지문 파일을 UTF-8로 읽고 유형, 문단 구조, 정보량, 어휘·문장 난이도를 확인한다.
2. `templates/question_prompt.j2`를 사용해 assessment JSON을 생성한다. 조건은 지문과
   학년에 맞춰 3~4개를 적응형으로 설계하며, 인용·상징·특정 문법을 지문 근거 없이 강제하지 않는다.
3. JSON의 단일 원본을 `output/lesson-plans/_packages/<assessment-id>/assessment.json`에
   저장한다. 저장 시 `save_assessment`로 schema 검증을 통과시키고 기존 파일은 명시적
   overwrite 없이는 덮어쓰지 않는다.
4. 다음 결정론적 검증을 통과시킨다.

   ```bash
   uv run python scripts/validate_assessment.py \
     output/lesson-plans/_packages/<assessment-id>/assessment.json
   ```

   단어 수, 표면 패턴, 필수 문자열, 5-gram 복사, 형식, rubric 합계, 조건 연결, 모든
   deterministic 모범답안을 확인하고 semantic/manual 항목은 검수 대기 상태로 남긴다.
5. `scripts/render_package.py`로 학생용과 교사용 Markdown을 각각 렌더한다. 학생용에는
   조건·지시문·지문만 전달하며 루브릭과 답안은 전달하지 않는다.

   ```bash
   uv run python scripts/render_package.py \
     output/lesson-plans/_packages/<assessment-id>/assessment.json \
     --target all --output output/lesson-plans/_packages/<assessment-id>/rendered
   ```

6. `manifest.json`과 `qa-report.json`을 확인한다. PDF가 필요하면 학생용은 `--profile exam`,
   교사용은 `--profile teacher`로 만든다. PDF 실패는 성공으로 간주하지 않는다.

## 출력 보안

- 학생용 파일은 `output/essay-questions/` 또는 패키지의 `student.md`로만 배포한다.
- 모범답안, 채점 기준, 배점표, `Rubric`, 내부 QA를 학생용 텍스트에 넣지 않는다.
- 모범답안과 rubric은 private package 및 교사용 렌더에만 둔다.
- 임시 생성물은 프로젝트 루트에 두지 않고 허용된 `output/` 하위 또는 `/tmp`에 둔다.
