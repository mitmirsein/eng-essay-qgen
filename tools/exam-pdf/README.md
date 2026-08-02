# exam-pdf

Markdown을 학생 시험지, 교사용 지도안, 피드백 PDF로 변환하는 도구입니다.

## 프로필

| profile | 레이아웃 | 이름란 | 총점 |
| --- | --- | --- | --- |
| `exam` | 2단 | 있음 | 있음 |
| `teacher` | 1단 | 없음 | 없음 |
| `feedback` | 1단 | 선택 | 선택 |

```bash
python3 tools/exam-pdf/make_exam_pdf.py student.md \
  --profile exam --title "영어 서술형 평가" \
  --subtitle "고2/3 대비" --total-points 8 -o student.pdf

python3 tools/exam-pdf/make_exam_pdf.py teacher.md \
  --profile teacher --title "교사용 수업 지도안" -o teacher.pdf
```

## 실패 정책

- Pandoc과 XeLaTeX의 return code를 모두 확인합니다.
- `Missing character`는 기본 0개만 허용합니다.
- `Overfull hbox`는 기본 0개만 허용하며 `--max-overfull`로 명시적으로 완화할 수 있습니다.
- 시험 프로필은 양수 총점이 없으면 실패합니다.
- 실패 시 임시 작업 디렉터리 경로를 출력해 로그를 보존하고, 성공 시 임시 파일을 정리합니다.
- 제목·부제목·필드의 TeX 특수 문자를 escape합니다.

## 의존성

- `pandoc`
- `xelatex`
- 시각 검수용 `gs` 또는 `pdftoppm` 권장

기본 preamble은 현재 macOS에서 확인된 `Times New Roman`, `Arial`, `Apple SD Gothic Neo`를
사용합니다. 다른 환경에서는 해당 preamble의 폰트를 설치된 한글 폰트로 바꾼 뒤 Missing character와
Overfull 검사를 다시 실행해야 합니다.
