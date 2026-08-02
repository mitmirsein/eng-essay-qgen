# eng-essay-qgen

중고등학교 영어 서술형 평가를 지문 분석, 적응형 조건 설계, 결정론적 검증, 안전한 렌더링,
교안 생성까지 연결하는 파이프라인입니다. `assessment.json`이 문제·조건·rubric·모범답안의
private source of truth이며, 학생용 파일은 이 원본에서 allowlist로 파생됩니다.

## 핵심 원칙

- `고2`와 `고3`은 내부에서 `고2/3`으로 정규화합니다.
- 조건은 지문·학년·유형에 맞춰 동적으로 설계하며 고정된 인용·상징·문법 목록을 강제하지 않습니다.
- 학생용 렌더에는 모범답안, rubric, 배점표, 내부 QA가 들어가지 않습니다.
- 이미지 답안은 VLM 전사 후 `pending-review`를 거쳐 사람이 승인한 경우에만 채점합니다.
- 기존 파일은 기본적으로 덮어쓰지 않으며 생성물은 `output/` 하위에 격리합니다.

## 기본 실행

의존성은 `uv`로 관리합니다.

```bash
uv sync
uv run pytest -q
uv run ruff check .
```

### 지문 gate

```bash
uv run python scripts/validate_passage.py passages/example.txt \
  --grade 중3 --type type2 --report /tmp/passage-report.json
```

단어 수, 문단 수, 문장 길이 통계, 비정상 공백·문자, type2 A/B 정보량을 검사합니다.
문체·사실성·편향·민감성은 별도 semantic 또는 사람 검수로 남습니다.

### Assessment package

`/essay-qgen` 또는 `/essay-differentiated` 스킬은 다음 구조를 만듭니다.

```text
output/lesson-plans/_packages/<assessment-id>/
├── assessment.json
├── lesson-plan.json              # 선택
├── qa-report.json
├── manifest.json
└── rendered/
    ├── student.md
    └── teacher.md
```

직접 검증·렌더링할 때:

```bash
uv run python scripts/validate_assessment.py <assessment.json> --student-scan
uv run python scripts/render_package.py <assessment.json> \
  --target all --output /tmp/essay-qgen-render
uv run python scripts/render_package.py <assessment.json> \
  --lesson-plan <lesson-plan.json> --target teacher \
  --output /tmp/essay-qgen-teacher
```

`render_package.py`는 렌더 후 manifest와 QA 보고서를 기록합니다. private package는
`output/lesson-plans/_packages/` 밖에 저장하지 않습니다.

### 교안

```bash
uv run python scripts/validate_lesson_plan.py <lesson-plan.json> \
  --assessment <assessment.json>
```

교안은 `templates/lesson_plan_prompt.j2`가 JSON을 생성하고, validator가 수업 시간 합계,
교육과정 reference, 발문·예상 반응·확인 방법, 수준별 지원, 오개념, 답안 계획을 검사합니다.

### 교사 운영

```bash
uv run python scripts/validate_teacher_profile.py config/teacher_profile.example.yaml
uv run python scripts/build_teacher_index.py output/lesson-plans/_packages \
  --output /tmp/teacher-index.md
uv run python scripts/mark_stale.py <manifest.json> passage
uv run python scripts/build_class_insights.py <grading-rows.json> \
  --output output/lesson-plans/class-insights/<batch-id>
uv run python scripts/export_sample_outputs.py --date 20260802
```

배치 전사/HITL 상태는 다음 CLI로 관리합니다.

```bash
uv run python scripts/manage_batch.py init batch-001 \
  --output-root output/lesson-plans/grading \
  --source input/answer-sheets/example.png
uv run python scripts/manage_batch.py transition <batch-dir> <anonymous-id> pending-review
uv run python scripts/manage_batch.py eligible <batch-dir>
```

학생 이름은 기본 출력에 사용하지 않고, 원본 경로 매핑은 `source_map.local.json`으로 분리합니다.

## PDF

```bash
python3 tools/exam-pdf/make_exam_pdf.py <student.md> \
  --profile exam --title "영어 서술형 평가" --total-points 8 -o <student.pdf>
python3 tools/exam-pdf/make_exam_pdf.py <teacher.md> \
  --profile teacher --title "교사용 수업 지도안" -o <teacher.pdf>
```

`exam`은 2단·이름란·총점, `teacher`는 1단·이름란 없음, `feedback`은 선택적 필드와 총점을
사용합니다. Pandoc/XeLaTeX return code, Missing character, Overfull hbox를 확인하며 실패 시
non-zero로 종료합니다.

## 프로젝트 경로

- `schemas/`: assessment, lesson plan, teacher profile 계약
- `src/eng_essay_qgen/`: I/O, metric, validator, renderer, 운영 로직
- `templates/`: assessment·교안 생성 및 Markdown 렌더 prompt
- `references/`: 2022 개정 교육과정 reference와 출처
- `skills/`: `/auto-essay`, `/essay-qgen`, `/essay-review`, `/lesson-plan`, `/essay-grade` 흐름
- `output/`: 생성물 전용 경로

교육과정 코드는 [references/curriculum-2022-sources.md](references/curriculum-2022-sources.md)에
기록된 공식 교육자료를 확인한 reference만 사용합니다.
