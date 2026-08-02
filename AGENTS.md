# Eng-Essay-QGen Project Constitution

Last updated: 2026-08-01

This file defines the project-specific rules for the `eng-essay-qgen` workspace. It overrides the global `MS_Dev` constitution where applicable.

## Project Purpose
`eng-essay-qgen`은 중고등학교 영어 서술형(에세이) 문제와 교사용 수업 지도안을 전자동으로 생성, 검수, 렌더링하는 파이프라인 시스템입니다.

## Core Architecture & Workflow
1. **Orchestrator (`/auto-essay`)**: 파이프라인의 진입점(Entry point)입니다. 주제와 학년이 주어지면 지문을 창작하고, 이후 출제 ➔ 검수 ➔ 교안 작성 ➔ PDF 컴파일 과정을 순차적으로 지휘합니다.
2. **Adaptive Condition Engine (`/essay-qgen`)**: 고정된 하드코딩 조건을 사용하지 않습니다. `templates/question_prompt.j2` 내의 중고등 교육과정 성취기준(어휘, 문법, 분량) 메타 지식을 바탕으로, 타겟 학년과 지문 특성에 가장 적합한 3~4개의 출제 조건을 동적(Dynamic)으로 설계합니다.
3. **Format Security (`/essay-review`)**: 학생용 문제지 본문에는 절대로 '모범 답안(Sample Answer)'이 포함되어서는 안 됩니다. 리뷰 스킬이 이를 적발하면 검수를 Fail 처리하고 즉시 수정해야 합니다.
4. **Teacher Guide (`/lesson-plan`)**: 교사용 지도안에만 모범 답안과 수업 지도 전략이 포함됩니다.
5. **Automated Grading (`/essay-grade`)**: 텍스트 및 이미지(학생 손글씨) 답안지 일괄 채점 파이프라인입니다. **VLM 추출 시 반드시 Human-in-the-loop(HITL) 검수를 거쳐야 합니다.** 인식 오류가 억울한 감점으로 이어지는 것을 방지하기 위함입니다.
6. **Formative Writing Coach (`/essay-coach`)**: 학생의 영어 초안을 점수 없이 분석하고, 오류 근거와 최소 수정본, 발전 수정본, 재작성 연습을 제공합니다. 이미지 답안은 `/essay-grade`와 동일하게 VLM 추출 후 반드시 HITL 검수를 거쳐야 합니다.
7. **PDF Rendering**: `tools/exam-pdf/make_exam_pdf.py`를 호출하여 최종 마크다운을 2단 시험지 형태의 PDF로 컴파일합니다. (부제목에는 학년 정보가 동적으로 기입됩니다.)

## Development Guidelines
- **Prompt Modifications**: `question_prompt.j2` 수정 시, 반드시 '적응형(Adaptive)' 로직을 보존해야 합니다. 정형화된 조건으로 퇴행시키지 마십시오.
- **Grade Definitions**: 고등학교 2학년과 3학년은 단일 난이도(`고2/3`)로 취급합니다.
- **LaTeX/PDF Guardrails**: `xelatex` 컴파일러는 이모지나 특수 기호 처리에 취약합니다. 템플릿 구조 내에서 치명적인 컴파일 에러를 유발할 수 있는 특수 문자는 가급적 피하십시오.
- **Paths**: 파이프라인의 모든 생성물은 `output/passages/`, `output/essay-questions/`, `output/lesson-plans/` 폴더에 격리 저장해야 합니다. 프로젝트 루트를 어지럽히지 마십시오.
