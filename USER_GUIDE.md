# Eng-Essay-QGen 사용자 가이드

중고등학교 영어 서술형 평가를 처음 만드는 교사와 운영자를 위한 실전 안내서입니다.
설치부터 문제 생성, 검수, 교안·PDF 제작, 학생 답안 채점, 이미지 답안의 사람 검수,
수업 결과 집계까지 한 번에 따라 할 수 있도록 설명합니다.

이 프로젝트는 두 가지 방식으로 사용할 수 있습니다.

1. Codex에서 슬래시 명령(`/auto-essay`, `/essay-qgen` 등)으로 AI 생성 워크플로우를 실행합니다.
2. 터미널에서 `uv run python scripts/...` 명령으로 검증·렌더링·배치 운영을 직접 실행합니다.

처음에는 0장과 1장의 빠른 시작만 따라 한 뒤, 실제 목적에 맞는 장으로 이동하면 됩니다.

## 0. 가장 짧은 사용 순서

### 새 문제를 처음부터 만들 때

Codex 대화창에 다음처럼 입력합니다.

```text
/auto-essay "기후 변화가 지역사회에 미치는 영향" 중3 type2
```

`/auto-essay`는 지문 생성부터 지문 검수, 문제 조건 설계, assessment package 생성,
학생용·교사용 분리 렌더링, 교안, PDF까지 순서대로 진행하는 오케스트레이터입니다.

### 이미 지문이 있을 때

```text
/essay-qgen passages/20260801_122000-type2-climate_change.txt type2 중3
```

그 다음 교안이 필요하면 다음을 실행합니다.

```text
/lesson-plan output/lesson-plans/_packages/<assessment-id>/assessment.json config/teacher_profile.example.yaml
```

### 학생 답안을 채점할 때

```text
/essay-grade output/lesson-plans/_packages/<assessment-id>/assessment.json "Students should save energy because it protects the environment."
```

이미지 답안은 전사 결과를 사람이 승인하기 전까지 채점하지 않습니다. 이 규칙은 8장에서
자세히 설명합니다.

## 1. 먼저 알아둘 개념

### 1.1 assessment package란 무엇인가

문제지 Markdown을 먼저 만들고 교안에서 답안을 추측하는 방식이 아닙니다. 하나의
private `assessment.json`이 문제·조건·루브릭·모범답안의 단일 원본(source of truth)이
됩니다. 이 원본에서 학생용과 교사용 파일을 각각 안전하게 파생합니다.

| 산출물 | 들어 있는 내용 | 배포 대상 |
| --- | --- | --- |
| `assessment.json` | 지문, 과제, 조건, 루브릭, 모범답안, 언어 감점 정책 | 시스템·교사만 |
| 학생용 Markdown/PDF | 지시문, 지문, 학생이 따라야 할 조건, 답안 작성란 | 학생 |
| 교사용 Markdown/PDF | 성취기준, 모범답안, 루브릭, 수업 지도 내용 | 교사 |
| `lesson-plan.json` | 수업 순서, 발문, 예상 반응, 수준별 지원, 오개념 대응 | 시스템·교사 |
| `qa-report.json` | 결정론적 검증 결과와 경고 | 운영자·교사 |
| `manifest.json` | 입력·출력 파일, 해시, 상태, 생성 메타데이터 | 운영자 |

학생용 파일에는 `모범 답안`, `Sample Answer`, `Rubric`, `채점 기준`, `배점표`가 들어가면
안 됩니다. 렌더러와 검수기가 이를 자동으로 차단하지만, 배포 전에 사람이 PDF도 한 번
확인하는 것이 좋습니다.

### 1.2 문제 유형

| 유형 | 적합한 과제 | 예시 |
| --- | --- | --- |
| `type1` | 이야기·일화의 원인, 심리, 변화 추론 | 인물의 행동이 바뀐 이유 설명 |
| `type2` | 설명문·두 정보 묶음의 요약, 비교, 원인·해결책 | 기후 변화의 원인과 해결책 요약 |
| `type3` | 편지, 조언, 의견, 실용문 | 친구에게 스마트폰 사용 조언 |
| differentiated | 같은 지문을 Level 1·2·3으로 조절 | 문장틀·핵심·확장형 과제 |

유형을 지정하지 않으면 `/auto-essay`가 주제와 지문 특성에 맞춰 선택할 수 있습니다.
조건은 고정 목록에서 복사하지 않고 지문·학년·과제 목적에 맞춰 동적으로 설계합니다.

### 1.3 학년 표기

사용자는 `고2` 또는 `고3`을 입력할 수 있지만 내부 저장 시 두 학년을 `고2/3`으로
정규화합니다. 지원되는 표준값은 다음과 같습니다.

`중1`, `중2`, `중3`, `고1`, `고2/3`

## 2. 설치와 첫 점검

### 2.1 저장소 받기

```bash
git clone https://github.com/mitmirsein/eng-essay-qgen.git
cd eng-essay-qgen
```

### 2.2 필수 프로그램

Python 3.11 이상과 `uv`가 필요합니다. Markdown만 다룰 때는 Python 의존성만으로 충분하지만,
PDF를 만들려면 `pandoc`, `xelatex`, `pdfinfo`도 필요합니다.

macOS에서는 다음처럼 설치할 수 있습니다.

```bash
brew install uv pandoc poppler
brew install --cask mactex-no-gui
```

설치 확인:

```bash
python3 --version
uv --version
pandoc --version
xelatex --version
pdfinfo -v
```

`xelatex`가 처음 설치된 직후에는 터미널을 다시 열어 PATH가 반영되었는지 확인합니다.

### 2.3 Python 의존성 설치

```bash
uv sync
```

`uv sync`는 `pyproject.toml`과 `uv.lock`에 맞는 가상환경을 만들고 의존성을 설치합니다.
이 프로젝트에서는 별도로 `pip install`할 필요가 없습니다.

### 2.4 설치가 올바른지 확인

```bash
uv run ruff check .
uv run pytest -q
```

정상 상태라면 lint 검사에 `All checks passed!`, 테스트에 `passed`가 표시됩니다. PDF 도구까지
확인하려면 6장의 PDF 예제를 실행합니다.

## 3. 폴더와 파일을 읽는 법

```text
passages/                         원문 지문(.txt)
schemas/                          JSON 계약과 검증 기준
templates/                        생성 prompt와 Markdown 렌더 template
references/                       2022 개정 교육과정 reference
skills/                           Codex 슬래시 명령의 실행 규칙
config/teacher_profile.example.yaml 기본 교사 설정 예시
output/essay-questions/           학생용 문제지(.md/.pdf)
output/lesson-plans/              교사용 교안·채점·코칭 결과
output/lesson-plans/_packages/    private assessment package
input/answer-sheets/              학생 답안 이미지 입력
tools/exam-pdf/                   PDF 변환기와 profile별 preamble
```

실제 package 한 개는 보통 다음처럼 보입니다.

```text
output/lesson-plans/_packages/<assessment-id>/
├── assessment.json
├── lesson-plan.json       # 교안을 생성한 경우
├── qa-report.json
├── manifest.json
└── rendered/
    ├── student.md
    └── teacher.md
```

`render_package.py`로 직접 렌더하면 `student.md`, `teacher.md`가 지정한 폴더에 생성됩니다.
배포용 이름을 명확히 하고 싶다면 다음 규칙을 사용합니다.

```text
output/essay-questions/<assessment-id>.md
output/essay-questions/<assessment-id>.pdf
output/lesson-plans/<assessment-id>_lesson.md
output/lesson-plans/<assessment-id>_lesson.pdf
```

프로젝트 루트에 임시 JSON, PDF, 변환 중간 파일을 만들지 마세요. 임시 파일은 `/tmp`에,
최종 파일은 허용된 `output/` 하위에 저장합니다.

## 4. Codex 슬래시 명령 사용법

아래 명령은 일반 셸 명령이 아니라 Codex 대화창에 입력하는 작업 요청입니다. 터미널에서
그대로 실행하지 않습니다.

### 4.1 전체 자동 생성: `/auto-essay`

```text
/auto-essay "인공지능과 윤리" 고1 type2
```

형식:

```text
/auto-essay "주제 또는 대략적인 내용" [학년] [type1|type2|type3]
```

유형을 생략해도 됩니다.

```text
/auto-essay "학교에서 실천할 수 있는 탄소 절약 방법" 중2
```

자동 흐름은 다음과 같습니다.

1. 주제와 학년에 맞는 지문을 `passages/`에 생성합니다.
2. 단어 수, 문단, 문장 길이, type2 A/B 정보량을 검사합니다.
3. 사실성, 문체, 편향, 민감성 등 의미 검수를 진행합니다.
4. private `assessment.json`을 만들고 schema·답안 validator를 실행합니다.
5. 학생용과 교사용을 분리하여 렌더합니다.
6. 교안 JSON과 교사용 렌더를 만들고 검증합니다.
7. 학생 PDF와 교안 PDF를 각각 `exam`·`teacher` profile로 빌드합니다.

### 4.2 기존 지문으로 문제 만들기: `/essay-qgen`

```text
/essay-qgen passages/my_passage.txt type2 중3
```

지문 파일은 UTF-8 텍스트여야 합니다. type2 지문이라면 `(A)`, `(B)`처럼 구분되는 실제
정보 단위가 있어야 하며, A와 B가 형식적으로만 나뉘어 있으면 검수에서 멈출 수 있습니다.

### 4.3 수준별 문제 만들기: `/essay-differentiated`

```text
/essay-differentiated passages/my_passage.txt 중3
```

Level 1·2·3은 서로 다른 문제가 아니라 공통 학습 목표를 유지하면서 언어 지원과 인지
부담을 조절한 버전입니다. 각 수준은 자체 조건·루브릭·모범답안을 가집니다.

### 4.4 문제 검수: `/essay-review`

```text
/essay-review output/lesson-plans/_packages/<assessment-id>/assessment.json package
/essay-review output/essay-questions/<assessment-id>.md student
/essay-review output/lesson-plans/<assessment-id>_lesson.md teacher
```

`package` 검수는 schema, 조건, 답안, 루브릭, grade alias를 먼저 검사한 뒤 의미 검수로
넘어갑니다. `student` 검수에서 답안이나 rubric이 발견되면 실패로 처리합니다.

### 4.5 교안 만들기: `/lesson-plan`

```text
/lesson-plan output/lesson-plans/_packages/<assessment-id>/assessment.json config/teacher_profile.example.yaml
```

학생용 Markdown을 교안의 원본으로 사용하지 않습니다. assessment package, 교사 profile,
교육과정 reference를 함께 사용해야 조건·루브릭·성취기준이 서로 어긋나지 않습니다.

### 4.6 형성평가 코칭: `/essay-coach`

점수 없이 초안을 개선하고 싶을 때 사용합니다.

```text
/essay-coach "I think students should save energy because it helps our future." 중3
/essay-coach input/student_draft.txt 중3
/essay-coach output/essay-questions/<assessment-id>.md "학생 답안" 중3
/essay-coach input/answer-sheets/draft.png 중3
```

점수·감점을 요구하면 `/essay-coach`가 아니라 `/essay-grade`를 사용합니다. 이미지 초안은
전사 후 반드시 사람이 확인하고 승인해야 합니다.

## 5. 터미널에서 직접 검증하고 렌더하기

슬래시 명령은 AI 생성과 의미 판단을 담당하고, 아래 스크립트는 재현 가능한 결정론적
검증·렌더링·운영 작업을 담당합니다.

### 5.1 지문 검증

```bash
uv run python scripts/validate_passage.py passages/my_passage.txt \
  --grade 중3 \
  --type type2 \
  --report /tmp/my-passage-report.json
```

검사 항목:

- 단어 수와 문단 수
- 비정상 공백·문자
- 문장 길이 통계
- type2의 A/B 최소 정보량
- 학년 alias와 유형 입력

문체 자연스러움, 사실성, 편향, 민감성은 이 명령만으로 확정하지 않습니다. AI 의미 검수나
교사 검수를 별도로 남겨야 합니다.

### 5.2 assessment 검증

```bash
uv run python scripts/validate_assessment.py \
  output/lesson-plans/_packages/<assessment-id>/assessment.json \
  --student-scan \
  --report /tmp/<assessment-id>-qa.json
```

결정론적 검사는 다음을 포함합니다.

- JSON schema와 필수 필드
- grade 정규화
- 조건의 deterministic 표면 패턴·필수 문자열·형식
- 답안 단어 수와 5-gram 복사 제한
- rubric 총점과 condition 연결
- 학생용 렌더의 모범답안·rubric 누출

`errors=0`이어도 semantic/manual 항목은 별도 확인이 필요할 수 있습니다. `warnings=1`은
대개 의미 검수 대기 항목이며, 보고서의 상세 내용을 확인하세요.

### 5.3 안전한 Markdown 렌더

```bash
uv run python scripts/render_package.py \
  output/lesson-plans/_packages/<assessment-id>/assessment.json \
  --target all \
  --output output/lesson-plans/_packages/<assessment-id>/rendered \
  --overwrite
```

교안 JSON이 있다면 함께 연결합니다.

```bash
uv run python scripts/render_package.py \
  output/lesson-plans/_packages/<assessment-id>/assessment.json \
  --lesson-plan output/lesson-plans/_packages/<assessment-id>/lesson-plan.json \
  --target teacher \
  --output output/lesson-plans/<assessment-id> \
  --overwrite
```

`--overwrite`는 같은 경로를 의도적으로 다시 만들 때만 사용합니다. 기본값은 기존 파일을
보호하기 위해 덮어쓰기를 거부합니다.

## 6. 교안과 PDF 만들기

### 6.1 교안 JSON 검증

```bash
uv run python scripts/validate_lesson_plan.py \
  output/lesson-plans/_packages/<assessment-id>/lesson-plan.json \
  --assessment output/lesson-plans/_packages/<assessment-id>/assessment.json \
  --report /tmp/<assessment-id>-lesson-qa.json
```

교안 validator는 수업 시간 합계, 교육과정 reference, 발문과 예상 반응, 확인 방법,
수준별 지원, 오개념 대응, 답안 계획, scoring anchor, placeholder와 이모지를 검사합니다.

### 6.2 학생용 시험지 PDF

```bash
uv run python tools/exam-pdf/make_exam_pdf.py \
  output/essay-questions/<assessment-id>.md \
  --profile exam \
  --title "영어 서술형 평가" \
  --subtitle "중3 대비" \
  --total-points 8 \
  --output output/essay-questions/<assessment-id>.pdf
```

`exam` profile은 2단 레이아웃, 이름란, 총점을 사용합니다. 총점은 assessment의 rubric과
일치해야 합니다.

### 6.3 교사용 교안 PDF

```bash
uv run python tools/exam-pdf/make_exam_pdf.py \
  output/lesson-plans/<assessment-id>_lesson.md \
  --profile teacher \
  --title "교사용 수업 지도안" \
  --subtitle "중3 영어 서술형 대비" \
  --output output/lesson-plans/<assessment-id>_lesson.pdf
```

`teacher` profile은 1단 레이아웃이며 학생 이름란과 시험 총점 필드를 넣지 않습니다.
`feedback` profile은 코칭·피드백 문서에 사용할 수 있습니다.

PDF 도구는 다음을 모두 확인합니다.

- Pandoc return code
- XeLaTeX return code
- PDF 파일 생성 여부
- `Missing character` 개수
- `Overfull \\hbox` 개수

하나라도 실패하면 성공으로 처리하지 않습니다. PDF에 이모지나 장식용 특수 기호를 넣지
말고, 실패 로그에 표시된 임시 경로의 `exam.log`를 확인하세요.

## 7. 샘플로 전체 파이프라인 연습하기

처음부터 새 내용을 만들기 전에 기존 6개 샘플로 설치를 확인하는 것이 안전합니다.

### 7.1 샘플을 임시 package로 마이그레이션

```bash
uv run python scripts/migrate_samples.py \
  --output /tmp/essay-qgen-migration \
  --sample 20260801_123100-type2-ai_ethics
```

성공하면 다음 파일이 생깁니다.

```text
/tmp/essay-qgen-migration/20260801_123100-type2-ai_ethics/assessment.json
```

6개 전체를 확인하려면 `--sample all`을 사용합니다.

```bash
uv run python scripts/migrate_samples.py \
  --output /tmp/essay-qgen-migration \
  --sample all
```

### 7.2 검증과 렌더

```bash
SAMPLE=/tmp/essay-qgen-migration/20260801_123100-type2-ai_ethics/assessment.json

uv run python scripts/validate_assessment.py "$SAMPLE" --student-scan
uv run python scripts/render_package.py "$SAMPLE" \
  --target all \
  --output /tmp/essay-qgen-migration/rendered \
  --overwrite
```

`/tmp`를 사용하면 기존 `output/` 파일을 덮어쓰지 않고도 전체 흐름을 확인할 수 있습니다.

### 7.3 오늘 날짜의 샘플 산출물 만들기

샘플을 실제 `output/`에 날짜가 붙은 이름으로 내보낼 때 사용합니다.

```bash
uv run python scripts/export_sample_outputs.py --date 20260802
```

이 명령은 6개 샘플에 대해 다음을 만듭니다.

- `output/essay-questions/20260802_*.md/.pdf`
- `output/lesson-plans/20260802_*_lesson.md/.pdf`
- `output/lesson-plans/_packages/20260802_*/assessment.json`
- 각 package의 `qa-report.json`, `manifest.json`

같은 날짜 파일이 이미 있으면 기본적으로 중단합니다. 정말 다시 만들 때만 다음처럼
명시적으로 덮어씁니다.

```bash
uv run python scripts/export_sample_outputs.py \
  --date 20260802 \
  --sample 20260801_123100-type2-ai_ethics \
  --overwrite
```

## 8. 학생 답안 채점과 이미지 HITL

### 8.1 텍스트 답안

```text
/essay-grade output/lesson-plans/_packages/<assessment-id>/assessment.json "학생의 영어 답안"
```

채점 기준은 학생용 문제지에서 읽지 않고 private assessment package의 rubric에서 읽습니다.
학생용 파일에 rubric이 없더라도 정상 동작해야 합니다.

### 8.2 이미지 답안 한 장

```text
/essay-grade output/lesson-plans/_packages/<assessment-id>/assessment.json input/answer-sheets/student-001.png
```

이미지에서는 먼저 VLM 전사만 수행합니다. 다음 문구로 사용자에게 확인을 요청하기 전에는
채점하지 않습니다.

```text
텍스트가 올바르게 추출되었는지 확인해주세요. 수정할 부분이 없다면 '진행'이라고 승인해주세요.
```

사람이 확인할 때는 다음을 특히 봅니다.

- `l`과 `I`, `a`와 `o` 같은 글자 혼동
- 문장부호와 대문자
- 줄바꿈 때문에 단어가 붙거나 나뉜 부분
- 판독이 불확실한 단어

불확실한 부분은 추측해서 채우지 않고 후보와 함께 기록합니다.

### 8.3 이미지 답안 배치

먼저 입력 이미지를 익명화된 batch로 등록합니다.

```bash
uv run python scripts/manage_batch.py init batch-001 \
  --output-root output/lesson-plans/grading \
  --source input/answer-sheets/student-001.png \
  --source input/answer-sheets/student-002.png
```

생성된 디렉터리의 `approvals.json`에서 익명 ID를 확인합니다.

```bash
cat output/lesson-plans/grading/batch-001/approvals.json
```

상태 흐름은 다음과 같습니다.

```text
pending-extraction
        ↓ VLM 전사
pending-review
        ├─ 오류 없음 → approved
        └─ 수정 필요 → corrected → approved
approved/corrected
        ↓
eligible → 채점
```

상태를 전이할 때는 이름이 아니라 익명 ID를 사용합니다.

```bash
uv run python scripts/manage_batch.py transition \
  output/lesson-plans/grading/batch-001 \
  stu-xxxxxxxxxxxx \
  approved \
  --transcript "확인한 영어 답안 원문" \
  --note "전사 결과 확인 완료"
```

수정한 전사라면 `corrected`로 먼저 저장합니다.

```bash
uv run python scripts/manage_batch.py transition \
  output/lesson-plans/grading/batch-001 \
  stu-xxxxxxxxxxxx \
  corrected \
  --transcript "사람이 수정한 전사 원문" \
  --uncertain-span "원래 판독: enviroment → environment"
```

채점 가능한 항목만 확인합니다.

```bash
uv run python scripts/manage_batch.py eligible \
  output/lesson-plans/grading/batch-001
```

`approved` 또는 `corrected`만 eligible 목록에 포함됩니다. 이미지 원본은 기본적으로 보존하지
않으며, 꼭 필요할 때만 `init`에 `--retain-handwriting-images`를 추가합니다.

### 8.4 개인정보 규칙

- 리포트에는 학생 이름 대신 `stu-...` 익명 ID를 사용합니다.
- 실제 경로와 익명 ID의 연결은 `source_map.local.json`에만 보관합니다.
- `source_map.local.json`, 원본 이미지, 학생 이름 매핑을 Git에 커밋하지 않습니다.
- 채점 결과는 `output/lesson-plans/grading/<batch-id>/reports/`에 저장합니다.

## 9. 코칭 결과 만들기

`/essay-coach`는 점수를 매기지 않고 다음 글을 더 잘 쓰게 하는 피드백을 만듭니다.

```text
/essay-coach output/essay-questions/<assessment-id>.md "I think this is good because people can use it." 중3
```

기본 분석 영역은 과제·내용, 구성, 문법, 어휘, 표기입니다. 결과에는 보통 다음이 포함됩니다.

- 명백한 오류와 원문 근거
- 한국어 설명과 최소 수정본
- 의미를 유지한 발전 수정본
- 학생이 다시 써 볼 문장과 확인 질문

코칭 결과는 `output/lesson-plans/YYYYMMDD_HHMMSS-coach-식별자.md`에 저장합니다. 학생용
문제지 폴더에는 답안·수정본을 저장하지 않습니다.

## 10. 교사 profile과 수업 운영

### 10.1 profile 검증

기본 예시를 확인합니다.

```bash
uv run python scripts/validate_teacher_profile.py \
  config/teacher_profile.example.yaml
```

학교별 설정은 예시 파일을 복사해 local 파일로 관리합니다.

```bash
cp config/teacher_profile.example.yaml config/teacher_profile.local.yaml
```

`teacher_profile.local.yaml`에는 학교명, 학급 정보, 보존 기간처럼 개인·기관별 값이 들어갈
수 있으므로 커밋하지 않습니다. 주요 설정은 다음과 같습니다.

| 설정 | 의미 |
| --- | --- |
| `default_grade` | 학년 기본값 |
| `lesson_duration_minutes` | 기본 수업 시간 |
| `class_size` | 학급 규모 |
| `proficiency_profile` | `mixed` 등 학급 수준 |
| `language_penalty` | 오류당 감점·최대 감점·반복 오류 정책 |
| `privacy` | 익명 ID, 손글씨 원본 보존, 보존 기간 |
| `pdf_profile` | 기본 PDF profile |

### 10.2 교사 산출물 색인

여러 package의 manifest를 교사가 한눈에 볼 수 있는 Markdown 색인으로 만듭니다.

```bash
uv run python scripts/build_teacher_index.py \
  output/lesson-plans/_packages \
  --output output/lesson-plans/teacher-index.md
```

HTML 색인이 필요하면 `--format html`을 사용합니다.

### 10.3 학급 인사이트

개별 점수를 바꾸지 않는 읽기 전용 집계입니다. 입력은 JSON 배열 또는 CSV입니다.

```bash
uv run python scripts/build_class_insights.py \
  output/lesson-plans/grading/batch-001/rows.json \
  --output output/lesson-plans/class-insights/batch-001
```

결과에는 보통 JSON 요약과 CSV 요약이 함께 생깁니다. 개인별 원문이나 이름을 집계 파일에
추가하지 않습니다.

### 10.4 일부만 다시 생성하기

지문이나 조건이 바뀌면 모든 산출물을 무조건 다시 만들지 말고 manifest에 stale 상태를
표시합니다.

```bash
uv run python scripts/mark_stale.py \
  output/lesson-plans/_packages/<assessment-id>/manifest.json passage
```

지원되는 변경 영역은 `passage`, `task_conditions`, `rubric`, `model_answers`,
`lesson_sequence`, `differentiation`, `scoring_anchors`, `pdfs` 등입니다. stale 표시는
재생성이 필요하다는 뜻이며, 재생성 자체를 대신 수행하지는 않습니다.

## 11. 검수 결과를 해석하는 법

### `PASS`

결정론적 검사에서 오류가 없다는 뜻입니다. 지문 근거, 답안의 의미 적합성, 민감 표현,
교육적 타당성까지 자동으로 보증한다는 뜻은 아닙니다.

### `WARNING`

사람 또는 의미 기반 검수가 필요한 항목이 남아 있다는 뜻입니다. `qa-report.json`에서
`checks`, `warnings`, `deferred`의 세부 내용을 확인합니다.

### `ERROR`

다음 단계로 진행하지 않습니다. 먼저 원인을 고치고 같은 package를 덮어쓰기보다 새 버전
또는 명시적 `--overwrite`로 다시 생성한 뒤 validator를 재실행합니다.

### 학생용 검수가 실패하는 경우

다음 단어 또는 내용이 학생용 파일에 들어가면 실패로 봅니다.

`모범 답안`, `Sample Answer`, `채점 기준`, `채점기준`, `배점표`, `Rubric`

답안과 루브릭은 학생용 Markdown을 직접 편집해 삭제하지 말고, private package를 원본으로
안전한 renderer를 다시 실행합니다.

## 12. 자주 발생하는 문제

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| `uv: command not found` | `uv`가 설치되지 않았거나 PATH에 없음 | `brew install uv`, 새 터미널 실행 |
| `pandoc: command not found` | PDF 변환기 미설치 | `brew install pandoc` |
| `xelatex failed` | MacTeX 미설치 또는 PATH 문제 | `brew install --cask mactex-no-gui`, `xelatex --version` 확인 |
| `Missing character` | 이모지·특수 유니코드가 XeLaTeX에서 처리되지 않음 | 장식 문자를 제거하고 PDF 재생성 |
| `Overfull \\hbox` | 긴 문자열이나 표가 줄 너비를 초과 | 긴 URL·표·문장을 줄이고 재렌더 |
| `refusing to overwrite` | 같은 경로의 기존 파일을 보호하는 정상 동작 | 새 assessment ID를 쓰거나 정말 필요할 때만 `--overwrite` |
| `assessment schema validation failed` | 필수 필드, grade, 조건 구조가 schema와 다름 | 오류 경로를 읽고 JSON 원본 수정 후 재검증 |
| `student render blocked` | 학생용에 답안·rubric·금지어가 유입됨 | 학생 Markdown을 직접 고치지 말고 package를 재렌더 |
| `migrated rubric does not total 8` | 원본 조건과 루브릭 배점이 맞지 않음 | 교안의 루브릭 합계를 확인하고 package 재생성 |
| 이미지 답안이 채점되지 않음 | `pending-review` 상태에서 멈춤 | 전사 확인 후 `approved` 또는 `corrected`로 전이 |
| 오늘 날짜 파일이 없음 | 테스트를 `/tmp`에서 실행했거나 export 명령을 실행하지 않음 | `export_sample_outputs.py --date YYYYMMDD` 실행 |
| `고2`·`고3`이 거부됨 | 외부 입력 형식 문제 | 지원되는 입력으로 입력하고 내부 `고2/3` 정규화 확인 |

## 13. 커밋과 공유 전 체크리스트

### 생성 전

- [ ] 지문 파일이 UTF-8인가?
- [ ] 학년과 유형이 목적에 맞는가?
- [ ] type2라면 A/B 정보량이 균형적인가?
- [ ] 기존 파일을 덮어써도 되는가?

### 생성 후

- [ ] `validate_passage.py`가 통과했는가?
- [ ] `validate_assessment.py --student-scan`이 통과했는가?
- [ ] 의미·사실성·편향·민감성 검수를 사람이 확인했는가?
- [ ] 학생용에 답안·루브릭·배점표가 없는가?
- [ ] 교사용에 필요한 답안·루브릭·수업 지도 내용이 있는가?
- [ ] 교안 validator가 통과했는가?
- [ ] 학생 PDF는 `exam`, 교안 PDF는 `teacher` profile인가?
- [ ] PDF 로그의 Missing character와 Overfull이 0인가?
- [ ] 이미지 답안은 HITL 승인 후에만 채점했는가?
- [ ] 학생 이름과 원본 이미지 경로가 리포트에 남지 않았는가?

### Git 공유 전

- [ ] `uv run ruff check .` 통과
- [ ] `uv run pytest -q` 통과
- [ ] `git diff --check` 통과
- [ ] `source_map.local.json`, `approvals.json`, 학생 이름 매핑, 원본 손글씨 이미지를 확인
- [ ] private package와 개인별 grading/coaching 결과를 공개 저장소에 넣지 않았는가?

## 14. 더 읽을 문서

- 프로젝트 개요와 짧은 명령 모음: [`README.md`](README.md)
- P0/P1/P2 구현 인수인계 문서: [`P0_P1_P2_IMPLEMENTATION_HANDOFF.md`](docs/P0_P1_P2_IMPLEMENTATION_HANDOFF.md)
- 교육과정 reference 출처: [`references/curriculum-2022-sources.md`](references/curriculum-2022-sources.md)
- 학생용 문제 생성 규칙: [`skills/slash-essay-qgen/SKILL.md`](skills/slash-essay-qgen/SKILL.md)
- 채점과 이미지 HITL 규칙: [`skills/slash-essay-grade/SKILL.md`](skills/slash-essay-grade/SKILL.md)
- 코칭 규칙: [`skills/slash-essay-coach/SKILL.md`](skills/slash-essay-coach/SKILL.md)

문서와 실제 실행 결과가 다르면 먼저 `--help`, schema, validator 출력과 현재 package의
`manifest.json`을 확인하고, 프로젝트 규칙이 바뀐 경우 이 가이드도 함께 업데이트합니다.
