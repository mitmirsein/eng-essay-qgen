# P0·P1·P2 세부 구현 계획 및 새 세션 핸드오프

- 작성일: 2026-08-02
- 기준 커밋: `d2dff50 feat: add adaptive essay coaching skill`
- 선행 문서: [프로젝트 점검 및 고도화 제안](PROJECT_REVIEW_FEEDBACK.md)
- 목표: 새 세션이 추가 구두 설명 없이 안전하게 구현을 시작하고, 단계별 완료 여부를 검증할 수 있게 한다.

## 0. 문서 사용법

이 문서는 세 가지 작업축을 다룬다.

- P0: 단일 원본, 검증, 보안, PDF 신뢰성
- P1: 교안 v2와 교육적 품질
- P2: 강사 운영 편의성, 학급 분석, 개인정보 보호

P0·P1·P2의 설계 작업은 병렬로 진행할 수 있지만 통합은 반드시 게이트를 통과한 순서대로 진행한다.

```text
P0 스키마·검증 ── Gate 1 ── P1 교안 통합 ── Gate 2 ── P2 운영 통합
       │                        │                       │
       ├─ P1 명세 설계          ├─ P2 UX 설계           └─ 통합 테스트
       └─ P2 개인정보 정책      └─ Golden 교안 작성
```

핵심 원칙은 다음과 같다.

1. 학생용 파일을 데이터 원본으로 사용하지 않는다.
2. 문제, 조건, 루브릭, 답안은 하나의 평가 원본에서 파생한다.
3. 생성형 검수와 결정론적 검증을 분리한다.
4. 학생용, 교사용, 피드백용 렌더링을 분리한다.
5. 교안의 상세화보다 정합성 검증을 먼저 완성한다.
6. 기존 사용자 산출물과 미커밋 변경을 임의로 덮어쓰지 않는다.

## 1. 새 세션 시작 전 필수 확인

### 1.1 작업 트리 보호

현재 작업 트리에는 사용자 소유의 문제지·교안 변경과 미추적 산출물이 존재한다. 새 세션은 먼저 다음을 실행한다.

```bash
git status --short
git log -1 --oneline
```

주의사항:

- `output/essay-questions/`와 `output/lesson-plans/`의 기존 변경을 reset, checkout, 삭제하지 않는다.
- 기존 PDF를 테스트 목적으로 덮어쓰지 않는다. 테스트 출력은 `/tmp`를 사용한다.
- `docs/`와 루트 `.gitignore`가 아직 미커밋일 수 있으므로 먼저 상태를 확인한다.
- 기존에 추적 중인 `*-grade-*` 파일은 `.gitignore` 추가만으로 추적 해제되지 않는다.
- 실제 학생 자료인지 샘플인지 확인하지 않은 상태에서 `git rm --cached`를 실행하지 않는다.

### 1.2 프로젝트 헌법

[AGENTS.md](../AGENTS.md)를 먼저 읽고 다음 규칙을 유지한다.

- 학생용 문제지에는 모범답안과 루브릭을 포함하지 않는다.
- 고2와 고3은 단일 난이도 `고2/3`으로 정규화한다.
- 이미지 답안은 VLM 전사 후 HITL 승인을 받아야 한다.
- 생성물은 허용된 `output/` 하위 경로에 저장한다.
- 적응형 조건 생성을 고정 조건으로 퇴행시키지 않는다.
- PDF 출력에는 XeLaTeX 취약 문자를 사용하지 않는다.

### 1.3 기준 상태에서 알려진 결함

구현 전에 다음 결함을 재현 가능한 기준으로 기록한다.

1. AI 윤리 문제는 50~70단어를 요구하지만 기본 답안은 40단어다.
2. AI 윤리 확장 답안은 51단어로 표기되어 있으나 실제 계산은 48단어다.
3. 수준별 Level 3 답안은 40~60단어 조건에 35단어다.
4. 루브릭 제거 후 일부 학생용 PDF 총점이 0점으로 표시된다.
5. 교안 PDF에 시험지 이름란·총점이 들어간다.
6. 교안 PDF의 이모지가 네모 문자로 깨진다.
7. PDF 빌드는 Missing character가 있어도 성공한다.
8. 현재 교안에는 수업 진행표, 발문, 예상 반응, 오개념 대응이 없다.
9. 기존 스킬 6개는 `status`, `version` frontmatter 때문에 공식 validator를 통과하지 못한다.
10. `essay-grade`는 학생용 문제지에 루브릭이 있다고 가정하지만 보안 규칙상 존재하지 않는다.

이 목록은 P0·P1 회귀 테스트의 출발점으로 사용한다.

## 2. 목표 아키텍처

### 2.1 내부 평가 패키지

학생용 Markdown을 원본으로 사용하지 않고 교사 전용 내부 패키지를 둔다.

```text
output/lesson-plans/_packages/<assessment-id>/
├── assessment.json        # 문제·조건·루브릭·모범답안 단일 원본
├── lesson-plan.json       # P1 교안 구조화 데이터
├── manifest.json          # 파일 경로·버전·해시·생성 상태
└── qa-report.json         # 결정론적·의미 기반 검수 결과

output/essay-questions/
├── <assessment-id>.md     # 학생 안전 필드만 렌더링
└── <assessment-id>.pdf

output/lesson-plans/
├── <assessment-id>_lesson.md
└── <assessment-id>_lesson.pdf
```

`assessment.json`과 내부 패키지는 답안과 루브릭을 포함하므로 절대로 `output/essay-questions/`에 저장하지 않는다.

### 2.2 권장 코드 구조

```text
pyproject.toml
schemas/
├── assessment-package.schema.json
├── lesson-plan.schema.json
└── teacher-profile.schema.json
src/eng_essay_qgen/
├── __init__.py
├── package_io.py
├── text_metrics.py
├── validators.py
├── renderers.py
├── manifests.py
└── privacy.py
scripts/
├── validate_assessment.py
├── render_package.py
├── migrate_samples.py
└── build_teacher_index.py
templates/
├── question_prompt.j2
├── lesson_plan_prompt.j2
├── student_exam.md.j2
├── teacher_guide.md.j2
└── feedback_report.md.j2
tests/
├── fixtures/
├── golden/
├── test_text_metrics.py
├── test_validators.py
├── test_render_security.py
├── test_pdf_profiles.py
└── test_sample_packages.py
```

### 2.3 의존성 기본안

`pyproject.toml`을 추가하고 Python 3.11 이상을 기준으로 한다.

런타임 후보:

- `jinja2`: Markdown 및 프롬프트 렌더링
- `jsonschema`: 구조 검증
- `pyyaml`: 강사 프로필 입력

개발 후보:

- `pytest`: 단위·통합 테스트
- `ruff`: 정적 검사와 포맷

의존성을 추가하기 전 현재 실행 환경과 `uv` 사용 가능 여부를 확인한다. 잠금 파일 정책은 저장소 소유자와 맞추되, 새 세션이 임의로 전역 환경에 설치하지 않는다.

## 3. 데이터 계약

### 3.1 assessment.json 최소 스키마

다음 구조를 스키마 v1의 기준으로 삼는다.

```json
{
  "schema_version": "1.0.0",
  "assessment_id": "20260802_210000-type2-ai_ethics",
  "metadata": {
    "title": "영어 서술형 평가",
    "topic": "인공지능과 윤리",
    "grade": "고2/3",
    "question_type": "type2",
    "total_points": 8,
    "created_at": "2026-08-02T21:00:00+09:00",
    "source_passage_path": "passages/example.txt"
  },
  "passage": {
    "genre": "expository",
    "text": "...",
    "sections": [
      {"id": "A", "text": "..."},
      {"id": "B", "text": "..."}
    ]
  },
  "task": {
    "instruction_ko": "...",
    "audience": "teacher-assigned",
    "purpose": "synthesis",
    "response_format": "one-paragraph"
  },
  "conditions": [
    {
      "id": "C1",
      "category": "length",
      "text_ko": "총 50~70단어로 작성할 것.",
      "validation": {
        "kind": "word_count",
        "check_mode": "deterministic",
        "params": {"min": 50, "max": 70}
      }
    }
  ],
  "rubric": [
    {
      "id": "R1",
      "condition_ids": ["C1"],
      "points": 2,
      "full_credit_ko": "50~70단어 범위를 충족한다.",
      "partial_credit_ko": "교사 정책에 따라 부분점수를 적용한다."
    }
  ],
  "language_policy": {
    "error_penalty": 0.5,
    "max_language_penalty": 2.0,
    "repeated_error_policy": "same-root-once",
    "double_penalty_allowed": false
  },
  "model_answers": [
    {
      "id": "minimum",
      "level": "minimum-pass",
      "text": "..."
    },
    {
      "id": "strong",
      "level": "proficient",
      "text": "..."
    }
  ]
}
```

### 3.2 허용 enum

최소 enum은 다음과 같이 고정한다.

- `grade`: `중1`, `중2`, `중3`, `고1`, `고2/3`
- 입력 alias: `고2`, `고3`을 `고2/3`으로 정규화
- `question_type`: `type1`, `type2`, `type3`, `differentiated`
- `condition.category`: `length`, `grammar`, `content`, `restriction`, `format`, `citation`
- `check_mode`: `deterministic`, `semantic`, `manual`
- `model_answers.level`: `minimum-pass`, `proficient`, `alternative`, `common-error`

### 3.3 검증 규칙 표현

결정론적으로 검증 가능한 조건만 코드로 확정한다.

| kind | 용도 | 예시 |
|---|---|---|
| `word_count` | 단어 수 범위 | `min=40`, `max=60` |
| `surface_pattern` | 표면 문법 패턴 | 관계대명사 2회 이상 |
| `literal_required` | 필수 문자열 | 지정 인용구 포함 |
| `ngram_limit` | 지문 연속 복사 제한 | 5단어 이상 금지 |
| `format` | 편지 시작·끝 등 | `Dear Jimin`, `From, Minho` |
| `semantic` | 내용·추론 판단 | 두 지문의 문제점 포함 |

문법 전체의 정확성을 정규식으로 판정하지 않는다. `surface_pattern`은 요구 형식의 존재 여부만 확인하고, 적절성은 의미 기반 검수가 판단한다.

### 3.4 단어 수 정책

단어 수는 모델이 작성한 괄호 표기를 신뢰하지 않고 코드로 다시 계산한다.

권장 기본 정책:

- 영문자와 내부 apostrophe를 하나의 단어로 처리한다.
- `mirror's`, `don't`는 각각 한 단어다.
- 편지의 `Dear`, 이름, `From` 포함 여부는 조건 데이터에 명시한다.
- 숫자와 하이픈 단어 처리 규칙을 테스트로 고정한다.
- 계산값은 `qa-report.json`에 기록하고 렌더러가 표시한다.

## 4. 병렬 작업축과 통합 게이트

### 4.1 작업축 소유권

| 작업축 | 초기 소유 파일 | 초기 산출물 |
|---|---|---|
| P0 Core | `schemas/`, `src/...validators`, `scripts/validate_*` | 스키마 v1, validator, QA 보고서 |
| P1 Content | `templates/lesson_plan_prompt.j2`, 교육과정 reference, golden 교안 | 교안 v2 명세와 예제 |
| P2 Teacher UX | 강사 프로필 명세, 개인정보 정책, 인덱스 설계 | 프로필 예제, 화면·출력 계약 |
| Integration | 공유 스킬, `README`, `AGENTS`, PDF 도구 | 통합 PR 또는 통합 커밋 |

다음 공유 파일은 여러 작업축이 동시에 수정하지 않는다.

- `skills/slash-auto-essay/SKILL.md`
- `skills/slash-essay-review/SKILL.md`
- `skills/slash-lesson-plan/SKILL.md`
- `templates/question_prompt.j2`
- `tools/exam-pdf/make_exam_pdf.py`
- `README.md`
- `AGENTS.md`

### 4.2 Gate 1: 데이터 계약 동결

다음이 완료되면 스키마 v1을 동결한다.

- JSON Schema가 유효하다.
- 기존 5개 일반 문제와 1개 수준별 문제를 표현할 수 있다.
- 조건, 루브릭, 답안 관계를 표현할 수 있다.
- 학생 안전 렌더링에 필요한 필드가 확정됐다.
- 학년과 유형 enum이 확정됐다.
- 단어 수와 n-gram 정책이 테스트로 고정됐다.

Gate 1 전에는 P1이 실제 파이프라인 필드명에 의존하는 코드를 작성하지 않는다.

### 4.3 Gate 2: P0 end-to-end 통과

다음이 완료되어야 P1·P2 통합을 시작한다.

- 샘플 패키지 6개가 스키마를 통과한다.
- 학생용 렌더링에 답안·루브릭이 없다.
- 모범답안이 모든 결정론적 조건을 통과한다.
- 루브릭 합계가 총점과 일치한다.
- exam PDF 총점이 0이 아니다.
- Missing character가 0이다.
- 실패 시 프로세스가 non-zero로 종료된다.

### 4.4 Gate 3: 교안 v2 승인

다음이 완료되면 P2 운영 기능이 교안 데이터를 소비할 수 있다.

- 교안 JSON 스키마가 확정됐다.
- 교안의 수업 시간 합계가 설정 시간과 일치한다.
- 유형별 golden 교안 3개가 사람 검토를 통과했다.
- 교육과정 코드는 검증된 reference에 존재한다.
- 최소·우수·경계 답안이 평가 조건과 일치한다.

## 5. P0 세부 구현

### P0-1. 프로젝트 실행 기반 추가

작업:

1. `pyproject.toml`을 추가한다.
2. `src/eng_essay_qgen/` 패키지를 생성한다.
3. `pytest`와 `ruff` 실행 경로를 마련한다.
4. 기존 PDF 스크립트의 import 가능한 함수와 CLI를 분리한다.

완료 조건:

- 깨끗한 환경에서 의존성을 설치할 수 있다.
- `python -c "import eng_essay_qgen"`이 성공한다.
- 최소 단위 테스트가 실행된다.

### P0-2. 스키마와 package I/O

대상 파일:

- `schemas/assessment-package.schema.json`
- `src/eng_essay_qgen/package_io.py`
- `src/eng_essay_qgen/manifests.py`

작업:

1. assessment 스키마 v1을 작성한다.
2. UTF-8 JSON 읽기·쓰기 함수를 구현한다.
3. 쓰기 전 스키마 검증을 강제한다.
4. `assessment_id`와 파일명 slug를 검증한다.
5. manifest에 schema version, 입력 파일, 출력 파일, SHA-256, QA 상태를 기록한다.
6. 기존 파일을 덮어쓸 때는 명시적 `--overwrite`가 없으면 실패한다.

완료 조건:

- 잘못된 grade, 중복 condition ID, 음수 점수를 거부한다.
- 출력 패키지 경로가 허용된 루트 밖으로 벗어나지 않는다.
- JSON 재저장 시 의미 없는 필드 손실이 없다.

### P0-3. 텍스트 지표와 validator

대상 파일:

- `src/eng_essay_qgen/text_metrics.py`
- `src/eng_essay_qgen/validators.py`
- `scripts/validate_assessment.py`

필수 검사:

1. 단어 수 범위
2. 필수 문자열과 형식
3. surface pattern 개수
4. 지문과 답안의 n-gram 중복
5. rubric point 합계
6. condition ID와 rubric 연결
7. 답안별 모든 deterministic condition
8. 학생용 금지 문자열
9. 비어 있는 placeholder와 `TODO`
10. grade·type 정규화

n-gram 검사 정책:

- 소문자화 후 문장부호를 제거한다.
- 기본 금지 길이는 5단어다.
- 문제에서 요구한 정확 인용은 whitelist로 제외한다.
- 발견 시 일치 구절과 지문 위치를 QA 보고서에 기록한다.

CLI 목표:

```bash
uv run python scripts/validate_assessment.py \
  output/lesson-plans/_packages/<id>/assessment.json
```

종료 코드:

- `0`: 모든 필수 검사 통과
- `1`: 평가 데이터 오류
- `2`: 사용법·파일 오류

### P0-4. 안전한 학생·교사 렌더러

대상 파일:

- `templates/student_exam.md.j2`
- `templates/teacher_guide.md.j2`
- `src/eng_essay_qgen/renderers.py`
- `scripts/render_package.py`

학생 렌더러는 allowlist 방식으로 다음만 받는다.

- 제목·학년·총점
- 지문
- 지시문
- 학생용 조건

학생 렌더러에는 assessment 전체 객체를 넘기지 않는다. 답안과 루브릭 필드를 템플릿 컨텍스트에 포함하지 않는 것이 핵심이다.

교사 렌더러는 다음을 사용한다.

- 학생용 문제 전체
- 루브릭
- 검증된 모범답안
- P1 교안 데이터
- QA 요약

렌더 후 학생용 보안 스캔을 다시 수행한다.

금지 기본어:

- 모범 답안
- Sample Answer
- 채점 기준
- 채점기준
- Rubric
- 배점표

완료 조건:

- 악의적으로 assessment에 답안 필드가 추가되어도 학생 출력에 나타나지 않는다.
- 학생 출력에 금지어가 있으면 파일 저장과 PDF 생성을 중단한다.
- 렌더 결과의 총점은 assessment metadata에서 가져온다.

### P0-5. 프롬프트 및 스킬 데이터 흐름 정리

대상:

- `templates/question_prompt.j2`
- `templates/differentiated_prompt.j2`
- `skills/slash-essay-qgen/SKILL.md`
- `skills/slash-essay-differentiated/SKILL.md`
- `skills/slash-essay-review/SKILL.md`
- `skills/slash-essay-grade/SKILL.md`
- `skills/slash-auto-essay/SKILL.md`

작업:

1. 생성 프롬프트 출력 계약을 Markdown이 아닌 assessment JSON으로 변경한다.
2. `essay-qgen`의 고정된 인용·상징 조건을 제거하고 적응형 프롬프트를 단일 기준으로 삼는다.
3. `essay-review`를 `package`, `student`, `teacher` 모드로 분리한다.
4. 결정론적 validator를 의미 검수보다 먼저 실행한다.
5. `essay-grade`는 학생 문제지가 아니라 assessment package 또는 teacher package에서 루브릭을 읽는다.
6. `auto-essay`는 passage review, package validation, safe render, PDF QA 순서로 실행한다.
7. 모든 기존 스킬 frontmatter에서 공식 validator가 허용하지 않는 `status`, `version`을 제거하거나 허용 필드로 이전한다.

권장 실행 순서:

```text
passage generation
→ passage deterministic checks
→ passage semantic review
→ assessment JSON generation
→ schema validation
→ model answer validation
→ semantic package review
→ student safe render
→ teacher render
→ PDF render and QA
→ manifest completion
```

### P0-6. PDF 프로필 분리

대상:

- `tools/exam-pdf/make_exam_pdf.py`
- `tools/exam-pdf/exam-preamble.tex`
- 새 `tools/exam-pdf/teacher-preamble.tex`
- 새 `tools/exam-pdf/feedback-preamble.tex`

CLI 목표:

```bash
python3 tools/exam-pdf/make_exam_pdf.py student.md \
  --profile exam --title "영어 서술형 평가" --total-points 8

python3 tools/exam-pdf/make_exam_pdf.py teacher.md \
  --profile teacher --title "교사용 수업 지도안"
```

프로필 요구사항:

| profile | 레이아웃 | 이름란 | 총점 | 용도 |
|---|---|---:|---:|---|
| exam | 2단 | 있음 | 있음 | 학생 시험지 |
| teacher | 1단 | 없음 | 없음 | 수업 지도안 |
| feedback | 1단 | 선택 | 선택 | 채점·첨삭 리포트 |

오류 정책:

- pandoc와 xelatex의 return code를 모두 확인한다.
- Missing character가 기본 0이 아니면 실패한다.
- Overfull 기준치를 CLI 옵션으로 받되 기본은 엄격하게 둔다.
- PDF가 존재하는지만으로 성공 처리하지 않는다.
- 실패 로그와 임시 디렉터리 경로를 보고하되 성공 시 임시 파일은 정리한다.
- 제목, 부제목, 이름 필드의 TeX 특수 문자를 안전하게 escape한다.

### P0-7. 지문 검수

새 `skills/slash-passage-review/SKILL.md` 또는 package review의 passage 모드를 추가한다.

결정론적 검사:

- 단어 수
- 문단 수
- 비정상 공백·문자
- 대상 학년 대비 문장 길이 통계
- type2의 A/B 존재와 최소 정보량

의미 기반 검사:

- 시제와 문체 일관성
- 문법적 자연스러움
- 문제 해결에 필요한 근거 존재
- 사실성·편향·민감 표현
- 복수 지문의 균형

실패한 지문으로는 문제를 생성하지 않는다.

### P0-8. 기존 샘플 마이그레이션

대상 샘플:

- Snow White
- White lie
- Climate change
- AI ethics
- Smartphone
- Differentiated climate change

`scripts/migrate_samples.py`는 원본을 덮어쓰지 않고 `/tmp` 또는 새 `_packages/` 경로에 먼저 결과를 생성한다.

완료 조건:

- AI ethics 모범답안이 50~70단어를 충족한다.
- Differentiated Level 3 답안이 40~60단어를 충족한다.
- 학생용 총점이 8점으로 표시된다.
- 학생용에 루브릭이 없다.
- 모든 패키지가 validator를 통과한다.

## 6. P1 세부 구현

### P1-1. lesson-plan.json 스키마

권장 구조:

```json
{
  "schema_version": "1.0.0",
  "assessment_id": "...",
  "overview": {
    "grade": "중3",
    "duration_minutes": 45,
    "lesson_mode": "writing-workshop",
    "materials": ["학생용 문제지", "근거 표시용 형광펜"],
    "objectives": ["..."]
  },
  "standards": [
    {
      "code": "verified-code",
      "statement_ko": "...",
      "performance_verb": "요약한다",
      "lesson_evidence": "두 지문의 핵심을 한 문단으로 통합한다.",
      "condition_ids": ["C2", "C3"]
    }
  ],
  "passage_analysis": {
    "flow": ["..."],
    "key_vocabulary": ["..."],
    "target_grammar": ["..."],
    "background_knowledge": ["..."]
  },
  "sequence": [
    {
      "phase": "guided-writing",
      "minutes": 10,
      "teacher_actions": ["..."],
      "student_actions": ["..."],
      "questions": ["..."],
      "expected_responses": ["..."],
      "checks_for_understanding": ["..."]
    }
  ],
  "differentiation": {
    "support": {"sentence_frames": ["..."], "word_bank": ["..."]},
    "core": {"organizer": ["..."]},
    "extension": {"prompts": ["..."]}
  },
  "misconceptions": [
    {
      "pattern": "...",
      "diagnostic_question": "...",
      "teacher_response": "...",
      "mini_lesson": "..."
    }
  ],
  "answer_planning": {
    "condition_to_sentence_map": ["..."],
    "self_checklist": ["..."]
  },
  "scoring_anchors": [
    {"score": 8, "answer_id": "strong", "rationale_ko": "..."},
    {"score": 6, "text": "...", "rationale_ko": "..."}
  ],
  "formative_assessment": {
    "mid_lesson_check": "...",
    "exit_ticket": "...",
    "follow_up": "..."
  }
}
```

### P1-2. 교안 프롬프트 분리

새 `templates/lesson_plan_prompt.j2`를 만들고 SKILL.md 안의 장문 출력 예시를 템플릿으로 이동한다.

입력:

- 검증된 assessment JSON
- teacher profile
- 검증된 교육과정 reference
- 요청 수업 시간
- 수업 모드

출력:

- `lesson-plan.json`만 출력
- Markdown은 renderer가 생성

프롬프트 규칙:

1. assessment의 조건·루브릭·답안을 복제하거나 변경하지 않는다.
2. 모든 수업 목표는 관찰 가능한 학생 행동으로 쓴다.
3. sequence의 minutes 합계가 전체 수업 시간과 같아야 한다.
4. 발문마다 예상 학생 반응과 확인 방법을 제공한다.
5. 실제 글에 근거한 어휘·문법만 다룬다.
6. type에 맞지 않는 상징·인용 지도법을 강제하지 않는다.
7. 지원 활동과 심화 활동이 같은 핵심 목표를 유지하게 한다.

### P1-3. 유형별 지도 전략

type1:

- 사건·심리 근거 표시
- 인용과 해석 구분
- 상징 추론을 위한 단계적 발문
- 근거 없는 해석 방지

type2:

- A/B 정보 표
- 공통점·차이점·인과관계 조직자
- 핵심어 치환과 문장 구조 변경
- 패러프레이징과 표절 경계

type3:

- 독자, 목적, 문체 분석
- 주장·이유·구체적 행동 계획
- 편지·조언·의견문의 형식
- 공손성, 실행 가능성, 일관성

differentiated:

- 공통 목표 유지
- 지원 수준만 단계화
- 그룹 배치 기준
- 그룹 이동 기준
- 공통 출구 티켓

### P1-4. 교육과정 reference

권장 파일:

- `references/curriculum-2022.json`
- `references/curriculum-2022-sources.md`

주의:

- 성취기준 코드를 기억에 의존해 작성하지 않는다.
- 구현 시 공식 NCIC 자료를 확인한다.
- 코드, 학교급, 영역, 공식 또는 검증된 요약, 출처 URL, 마지막 확인일을 저장한다.
- lesson plan validator는 reference에 없는 코드를 거부한다.
- 고2와 고3 난이도는 프로젝트 규칙상 `고2/3`으로 통합하되 성취기준 학교급 표기는 정확히 유지한다.

### P1-5. 모범답안과 채점 앵커

교사용 패키지에는 최소 다음을 둔다.

- minimum-pass: 모든 필수 조건을 최소 수준으로 충족
- proficient: 자연스럽고 충분한 답안
- alternative: 다른 관점이나 표현의 허용 답안
- common-error: 대표적인 오류 답안

채점 앵커는 기본 8점 문항에서 8·6·4·2점 예시를 제공한다. 총점이 달라지면 비율에 맞게 조정한다.

루브릭 정책:

- 내용 조건과 언어 오류를 이중 감점하지 않는다.
- 동일한 원인의 반복 오류는 정책에 따라 한 번만 감점한다.
- 언어 감점 상한을 명시한다.
- 경계 사례와 허용 가능한 영미식 변이를 설명한다.

### P1-6. 교안 validator

필수 검사:

- duration과 sequence minutes 합계 일치
- 모든 condition이 answer planning 또는 sequence에서 다뤄짐
- 모든 성취기준 코드가 reference에 존재
- 발문에 expected response가 존재
- support, core, extension이 존재
- misconceptions가 최소 1개 이상 존재
- exit ticket이 수업 목표를 측정
- scoring anchor 점수가 rubric total 범위 내에 있음
- 모범답안이 P0 assessment validator를 통과
- Markdown placeholder와 장식용 emoji가 없음

### P1-7. Golden 교안

최소 세 유형을 사람 검토용 golden으로 만든다.

- type1: Snow White 또는 다른 검수된 서사 지문
- type2: Climate change 또는 AI ethics
- type3: Smartphone advice letter

각 golden은 다음 질문에 답할 수 있어야 한다.

- 강사가 10분 이내에 수업 준비를 파악할 수 있는가?
- 수업 순서를 그대로 따라갈 수 있는가?
- 예상 학생 반응과 대응이 충분한가?
- 하위권과 상위권을 동시에 지원할 수 있는가?
- 채점 경계 사례를 일관되게 처리할 수 있는가?

## 7. P2 세부 구현

### P2-1. 강사 프로필

추적 파일:

- `config/teacher_profile.example.yaml`
- `schemas/teacher-profile.schema.json`

로컬 파일:

- `config/teacher_profile.local.yaml`
- 루트 `.gitignore`에 추가

권장 필드:

```yaml
school_name: ""
default_grade: "중3"
lesson_duration_minutes: 45
class_size: 30
proficiency_profile: "mixed"
instruction_language_ratio:
  korean: 70
  english: 30
default_total_points: 8
language_penalty:
  per_error: 0.5
  maximum: 2.0
  repeated_error_policy: "same-root-once"
pdf_profile: "teacher"
output_formats:
  - markdown
  - pdf
privacy:
  use_anonymous_student_ids: true
  retain_handwriting_images: false
```

CLI 인자는 프로필보다 우선하며, 적용된 최종 설정을 manifest에 기록한다.

### P2-2. 강사용 인덱스

`scripts/build_teacher_index.py`가 manifest를 읽어 다음 정보를 제공한다.

- 주제, 학년, 유형
- 생성일과 schema version
- student PDF, teacher PDF 링크
- QA Pass/Fail
- 마지막 수정 시각
- 재생성 필요 여부
- 채점·첨삭·학급 분석 존재 여부

초기 구현은 Markdown 또는 정적 HTML로 충분하다. 원본 디렉터리를 직접 스캔해 파일명을 추측하지 말고 manifest를 사용한다.

### P2-3. 배치 HITL 상태 관리

학생별 순차 대화를 상태 파일로 바꾼다.

```text
output/lesson-plans/grading/<batch-id>/
├── batch-manifest.json
├── transcriptions.csv
├── approvals.json
├── reports/
└── class-summary.csv
```

상태 enum:

- `pending-extraction`
- `pending-review`
- `corrected`
- `approved`
- `graded`
- `failed`

규칙:

- `approved` 또는 `corrected` 상태만 채점한다.
- 중단 후 같은 batch ID로 재개할 수 있어야 한다.
- 판독 불확실 구간과 원본 이미지 경로를 함께 표시한다.
- 기본 출력에는 학생 이름 대신 익명 ID를 사용한다.

### P2-4. 학급 인사이트

개별 리포트에서 다음을 집계한다.

- 평균·중앙값·점수 분포
- 조건별 달성률
- 문법·어휘 오류 패턴
- 반복되는 패러프레이징 문제
- 재수업 추천 그룹
- 추천 미니 레슨
- 익명 우수 답안 후보

집계 결과가 새로운 학생 점수를 생성하거나 바꾸지 않게 한다. 개별 채점 결과의 읽기 전용 파생물이어야 한다.

### P2-5. 선택적 재생성

전체 패키지를 다시 생성하지 않고 다음 단위를 갱신할 수 있게 한다.

- passage
- task and conditions
- model answers
- lesson sequence
- differentiation
- scoring anchors
- PDFs only

의존성 규칙:

- passage 변경 시 모든 하위 산출물을 stale 처리한다.
- task·conditions 변경 시 rubric, answers, lesson, PDFs를 stale 처리한다.
- lesson sequence만 변경하면 학생용 파일은 그대로 유지한다.
- PDF만 다시 만들면 내용 해시는 유지한다.

manifest에 `stale_sections`와 원인 이벤트를 기록한다.

### P2-6. 개인정보와 Git 정책

루트 `.gitignore`는 다음을 기본 제외한다.

- 학생별 grade·coach 결과
- grading, coaching, class-insights 디렉터리
- 로컬 teacher profile
- 임시 전사 및 승인 파일
- `.DS_Store`, Python cache, 로컬 가상환경

주의:

- `.gitignore`는 이미 추적 중인 파일을 자동 해제하지 않는다.
- 기존 학생명 샘플의 추적 해제는 실제 데이터 여부를 확인한 후 별도 승인 아래 수행한다.
- 로그와 manifest에도 원본 학생 이름을 기본 저장하지 않는다.
- 보존 기간과 삭제 정책은 teacher profile 또는 별도 privacy config로 둔다.

## 8. 테스트 전략

### 8.1 단위 테스트

`test_text_metrics.py`:

- apostrophe 단어
- 하이픈 단어
- 이름과 편지 형식
- 문장부호 제거
- 대소문자 정규화
- 5-gram 비교와 whitelist

`test_validators.py`:

- rubric 총점 불일치
- condition 미연결
- 중복 ID
- 범위 밖 답안
- 금지 복사
- surface pattern 부족

`test_render_security.py`:

- 답안·루브릭 필드 누출 방지
- 금지어 탐지
- 총점 metadata 반영
- 임의 추가 필드 무시

### 8.2 통합 테스트

기존 6개 샘플을 fixture로 변환하여 다음을 검증한다.

1. package 생성
2. schema validation
3. answer validation
4. student render
5. security scan
6. teacher render
7. PDF build
8. manifest completion

### 8.3 Golden 테스트

Golden Markdown 전체 문자열 비교는 사소한 문구 변경에 취약하므로 다음을 분리한다.

- 구조: 필수 heading과 section ID
- 데이터: 조건, 점수, 답안 metrics
- 보안: 금지 필드 부재
- PDF: 페이지 수, Missing character, Overfull, profile header
- 교육 품질: 사람 검토 체크리스트

### 8.4 목표 명령

구현 후 다음 명령이 성공해야 한다.

```bash
uv run ruff check .
uv run pytest
uv run python scripts/validate_assessment.py tests/fixtures/ai_ethics/assessment.json
uv run python scripts/render_package.py tests/fixtures/ai_ethics/assessment.json --target all --output /tmp/essay-qgen-smoke
python3 tools/exam-pdf/make_exam_pdf.py /tmp/essay-qgen-smoke/student.md --profile exam --title "영어 서술형 평가" --total-points 8 -o /tmp/essay-qgen-smoke/student.pdf
python3 tools/exam-pdf/make_exam_pdf.py /tmp/essay-qgen-smoke/teacher.md --profile teacher --title "교사용 수업 지도안" -o /tmp/essay-qgen-smoke/teacher.pdf
```

이 명령들은 목표 인터페이스이며 현재는 아직 존재하지 않을 수 있다. 구현 과정에서 문서와 실제 CLI가 일치하도록 함께 갱신한다.

## 9. Definition of Done

### P0 완료

- [ ] assessment schema v1이 존재한다.
- [ ] 기존 6개 샘플을 표현할 수 있다.
- [ ] 단어 수, n-gram, 총점, condition-rubric 연결 validator가 존재한다.
- [ ] 학생 렌더러가 allowlist 방식이다.
- [ ] 학생용 파일에 답안·루브릭이 없다.
- [ ] `essay-grade`가 package에서 루브릭을 읽는다.
- [ ] exam, teacher, feedback PDF 프로필이 분리됐다.
- [ ] Missing character 발생 시 빌드가 실패한다.
- [ ] 학생 PDF 총점이 정확하다.
- [ ] 기존 스킬이 공식 validator를 통과한다.
- [ ] 단위·통합 테스트가 통과한다.

### P1 완료

- [ ] lesson-plan schema v1이 존재한다.
- [ ] 독립 lesson plan prompt가 JSON을 생성한다.
- [ ] 검증된 교육과정 reference가 존재한다.
- [ ] sequence 시간 합계가 수업 시간과 일치한다.
- [ ] 교사·학생 활동, 발문, 예상 반응, 확인 방법이 있다.
- [ ] support, core, extension이 있다.
- [ ] 예상 오류와 교정 전략이 있다.
- [ ] 최소·우수·대안·오류 답안이 있다.
- [ ] 채점 앵커와 반복 오류 정책이 있다.
- [ ] type1, type2, type3 golden 교안이 승인됐다.

### P2 완료

- [ ] 강사 프로필과 override 규칙이 있다.
- [ ] 산출물 인덱스에서 QA 상태와 파일을 찾을 수 있다.
- [ ] 배치 HITL이 상태 기반으로 재개 가능하다.
- [ ] 성적 CSV와 학급 인사이트를 생성한다.
- [ ] 선택적 재생성과 stale 전파가 작동한다.
- [ ] 학생 식별 정보가 기본적으로 Git에서 제외된다.
- [ ] 실제 학생 이름 대신 익명 ID가 기본값이다.

## 10. 권장 커밋 단위

큰 단일 커밋을 피하고 다음 단위로 나눈다.

1. `chore: add python project and test scaffold`
2. `feat: add assessment package schema`
3. `feat: add deterministic assessment validators`
4. `feat: render secure student and teacher markdown`
5. `refactor: align qgen review and grade skills with packages`
6. `feat: add document-specific pdf profiles`
7. `feat: add lesson plan v2 schema and prompt`
8. `feat: add verified curriculum mapping reference`
9. `feat: add teacher profile and artifact index`
10. `feat: add resumable batch grading and class insights`

각 커밋은 관련 테스트를 포함하고 기존 사용자 산출물을 섞어 커밋하지 않는다.

## 11. 의사결정이 필요한 항목과 권장 기본값

| 항목 | 권장 기본값 | 이유 |
|---|---|---|
| 총점 | configurable, 기본 8점 | 기존 문항과 호환 |
| schema version | `1.0.0` | manifest와 migration 기준 필요 |
| 단어 수 | apostrophe 포함 형태를 한 단어로 계산 | 일반적 학교 word count와 일치 |
| 반복 오류 | 동일 원인 1회 감점 | 과도한 감점 방지 |
| 언어 감점 상한 | 기본 2점 | 내용 점수 압도 방지 |
| 교안 PDF | 1단 | 수업 순서표와 메모에 적합 |
| 학생 식별자 | 익명 ID | 개인정보 보호 |
| 실제 출력 덮어쓰기 | 기본 금지 | 사용자 산출물 보호 |
| 교육과정 코드 | 공식 자료 검증 후만 허용 | 환각 방지 |
| 생성 런타임 | 에이전트 생성 + 결정론적 로컬 검증 | 현재 프로젝트 구조와 호환 |

## 12. 위험과 대응

### 스키마가 너무 빨리 복잡해지는 위험

대응:

- 기존 6개 샘플을 표현하는 최소 필드로 v1을 시작한다.
- 선택 필드를 남발하지 않는다.
- 실제 두 번째 사용 사례가 나오기 전에는 추상화를 추가하지 않는다.

### P1이 P0 필드 변경을 따라가느라 재작업하는 위험

대응:

- Gate 1 전에는 P1이 JSON 통합 코드를 작성하지 않는다.
- P1은 교안 명세와 golden 예제만 먼저 작성한다.

### 생성형 검수를 결정론적 검사처럼 신뢰하는 위험

대응:

- 단어 수, 총점, ID, n-gram, 누출 검사는 코드가 판단한다.
- 내용 적합성과 문법 자연스러움만 의미 검수가 판단한다.
- QA 보고서에 검사 유형을 표시한다.

### 기존 산출물과 새 패키지의 혼재

대응:

- manifest 없는 파일은 `legacy`로 표시한다.
- migration은 복사 기반으로 수행한다.
- 새 패키지가 통과하기 전 기존 파일을 삭제하지 않는다.

### 강사 편의 기능이 개인정보 노출을 늘리는 위험

대응:

- 익명 ID를 기본값으로 한다.
- 학생별 결과와 학급 분석은 Git ignore한다.
- 이름 매핑 파일은 별도 로컬 파일로 둔다.
- export 단계에서 포함 필드를 교사가 선택하게 한다.

## 13. 새 세션용 실행 프롬프트

새 구현 세션에는 다음과 같이 요청하면 된다.

```text
docs/P0_P1_P2_IMPLEMENTATION_HANDOFF.md를 읽고 P0부터 구현하라.
먼저 AGENTS.md와 git status를 확인하고 기존 output 변경을 보존하라.
P0-1부터 P0-3까지 구현하고 테스트하되, assessment schema v1과 validator가
기존 6개 샘플을 표현하고 AI ethics 및 differentiated word-count 결함을
탐지하는 시점에서 중간 보고하라. 실제 output 파일은 덮어쓰지 말고
테스트 산출물은 /tmp를 사용하라.
```

P1 병렬 설계 세션에는 다음을 사용한다.

```text
docs/P0_P1_P2_IMPLEMENTATION_HANDOFF.md의 P1을 기준으로 교안 v2 JSON 명세,
lesson_plan_prompt.j2 초안, type1/type2/type3 golden 교안 평가 체크리스트를
설계하라. Gate 1 전에는 P0 공유 파일을 수정하지 말고 P1 소유 파일만 다뤄라.
성취기준 코드는 공식 자료 확인 없이 만들어내지 마라.
```

P2 병렬 설계 세션에는 다음을 사용한다.

```text
docs/P0_P1_P2_IMPLEMENTATION_HANDOFF.md의 P2를 기준으로 teacher profile,
산출물 인덱스, 배치 HITL 상태 모델, 개인정보 정책을 설계하라.
P0/P1 JSON 필드에 직접 결합되는 구현은 Gate 1 이후로 미루고,
기존 학생별 결과나 output 파일을 수정하지 마라.
```

## 14. 최종 인수 체크

새 세션이 작업을 마치면 다음 내용을 보고해야 한다.

1. 구현한 P0/P1/P2 항목 ID
2. 추가·변경한 파일 목록
3. 실행한 테스트와 결과
4. 기존 10개 결함 중 해결된 항목
5. 아직 남은 위험과 다음 Gate
6. 실제 output을 변경했는지 여부
7. 개인정보 파일을 생성하거나 추적했는지 여부
8. 커밋·푸시 여부와 커밋 해시

이 보고가 없으면 다음 작업축은 통합을 시작하지 않는다.
