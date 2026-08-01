#!/usr/bin/env python3
"""make_exam_pdf.py — render a Korean/English exam Markdown note into a clean,
two-column PDF (Pandoc + XeLaTeX).

Why this exists: theology-pdf-maker mangles exams (it rewrites ①②③ → (1)(2)(3),
uses a single column, and a scholarly preamble). This renderer is exam-tuned:

  • keeps circled numerals ①..⑳ as-is
  • balanced two columns via multicol (no rule running down an empty column)
  • light-shaded, non-breakable reading-passage / 보기 boxes
  • a proper exam header (title · subtitle · name field · total points)
  • fixes the source quirks that break Pandoc:
      - inserts the blank line a blockquote needs (kills stray literal '>')
      - turns &nbsp;-aligned answer matrices (e.g. Q8 [A]/[B]) into real tabulars
  • never alters question text.

Usage:
    python3 make_exam_pdf.py INPUT.md \
        --title "2025학년도 1학기 2차 지필평가" \
        --subtitle "용동중학교 3학년 · 영어" \
        [--field "3학년 ___반 ___번  이름 _______"] \
        [-o OUTPUT.pdf]

Requires: pandoc, xelatex (TeX Live), fonts Noto Serif / Noto Serif KR / Noto Sans KR.
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PREAMBLE = Path(__file__).resolve().parent / "exam-preamble.tex"


# ── Markdown cleaning (content-preserving) ────────────────────────────────
def _cell(s: str) -> str:
    """markdown emphasis -> LaTeX, for one tabular cell."""
    s = s.strip()
    s = re.sub(r'\\newline\s*$', '', s).strip()      # drop a literal \newline token
    s = re.sub(r'\*\*([^*]+)\*\*', r'\\textbf{\1}', s)
    s = re.sub(r'\*([^*]+)\*', r'\\textit{\1}', s)
    return s


def collapse_matrices(lines):
    """A run (>=2) of non-quote, &nbsp;-aligned lines -> a centred LaTeX tabular
    so columns line up under a proportional font and the block stays together."""
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        if ('&nbsp;' in line) and not line.lstrip().startswith('>'):
            j, run = i, []
            while j < n and ('&nbsp;' in lines[j]) and not lines[j].lstrip().startswith('>'):
                run.append(lines[j]); j += 1
            if len(run) >= 2:
                rows = []
                for r in run:
                    cells = [_cell(c) for c in re.split(r'(?:&nbsp;)+', r)]
                    rows.append([c for c in cells if c != ''])   # drop indent padding
                ncol = max(len(r) for r in rows)
                colspec = '@{}' + 'l@{\\hspace{3.2em}}' * (ncol - 1) + 'l@{}'
                body = ' \\\\\n'.join(
                    ' & '.join(r + [''] * (ncol - len(r))) for r in rows)
                out += ['', '```{=latex}',
                        '\\begin{center}\\setlength{\\extrarowheight}{2pt}',
                        f'\\begin{{tabular}}{{{colspec}}}', body,
                        '\\end{tabular}\\end{center}', '```', '']
                i = j
                continue
        out.append(line); i += 1
    return out


def clean(md: str) -> str:
    md = re.sub(r'^\#\s+.*\n', '', md, count=1)          # drop '# title'
    md = md.lstrip('\n')
    md = re.sub(r'^-{3,}\s*\n', '', md, count=1)         # drop redundant leading ---

    lines = collapse_matrices(md.split('\n'))
    out = []
    for line in lines:
        if line.strip() == '<br>':                       # inter-question gap
            out += ['', r'\vspace{1.5pt}', '']
            continue
        is_bq = line.lstrip().startswith('>')
        prev = out[-1].strip() if out else ''
        prev_bq = out[-1].lstrip().startswith('>') if out else False
        if is_bq and prev != '' and not prev_bq:         # blockquote needs a blank line
            if out[-1].rstrip().endswith(r'\newline'):
                out[-1] = out[-1].rstrip()[:-len(r'\newline')].rstrip()
            out.append('')
        out.append(line)

    text = re.sub(r'\n{3,}', '\n\n', '\n'.join(out))
    return ('```{=latex}\n\\begin{multicols}{2}\n```\n\n'
            + text.strip()
            + '\n\n```{=latex}\n\\end{multicols}\n```\n')


def total_points(md: str) -> str:
    pts = [float(x) for x in re.findall(r'\[(\d+(?:\.\d+)?)\s*점\]', md)]
    return f"{sum(pts):g}"


# ── Build ─────────────────────────────────────────────────────────────────
def build(src: Path, out_pdf: Path, title: str, subtitle: str,
          field: str | None, fontsize: str) -> bool:
    md = src.read_text(encoding='utf-8')
    total = total_points(md)

    work = Path(tempfile.mkdtemp(prefix="exampdf_"))
    clean_md = work / "clean.md"
    clean_md.write_text(clean(md), encoding='utf-8')

    # per-run preamble = base + header fields
    pre = work / "preamble.tex"
    base = PREAMBLE.read_text(encoding='utf-8')
    base += f"\n\\setexamsubtitle{{{subtitle}}}\n"
    base += f"\\setexammeta{{\\fontspec{{Noto Sans KR}}\\small 총 {total}점}}\n"
    if field:
        base += f"\\setexamfield{{{field}}}\n"
    pre.write_text(base, encoding='utf-8')

    tex = work / "exam.tex"
    pandoc = [
        "pandoc", str(clean_md), "-s", "-o", str(tex),
        "--metadata", f"title={title}",
        "-V", f"fontsize={fontsize}",
        "-V", "geometry=a4paper, top=1.7cm, bottom=1.7cm, left=1.5cm, right=1.5cm",
        "-V", "documentclass=article",
        "-H", str(pre),
        "-M", "csquotes=true",
    ]
    try:
        subprocess.run(pandoc, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        sys.stderr.write("pandoc failed:\n" + e.stderr + "\n")
        return False

    for _ in range(2):                                   # twice: balance + page refs
        subprocess.run(
            ["xelatex", "-interaction=nonstopmode", f"-output-directory={work}", str(tex)],
            capture_output=True, text=True)

    built = work / "exam.pdf"
    if not built.exists():
        log = (work / "exam.log")
        sys.stderr.write("xelatex produced no PDF. Tail of log:\n")
        if log.exists():
            sys.stderr.write("\n".join(log.read_text(errors="replace").splitlines()[-25:]))
        return False

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(built, out_pdf)

    log = (work / "exam.log").read_text(errors="replace")
    miss = len(re.findall(r"Missing character", log))
    over = len(re.findall(r"Overfull \\hbox", log))
    pages = "?"
    try:
        info = subprocess.run(["pdfinfo", str(out_pdf)], capture_output=True, text=True).stdout
        m = re.search(r"Pages:\s+(\d+)", info)
        pages = m.group(1) if m else "?"
    except Exception:
        pass
    print(f"✅ {out_pdf}  ({pages} pages · 총 {total}점 · "
          f"Missing char {miss} · Overfull {over})")
    shutil.rmtree(work, ignore_errors=True)
    return True


def main():
    ap = argparse.ArgumentParser(description="Render an exam Markdown note to a polished two-column PDF.")
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--field", default=None,
                    help="override the name/number field row (default: 이름 ___)")
    ap.add_argument("--fontsize", default="10pt")
    a = ap.parse_args()

    src = Path(a.input)
    out = Path(a.output) if a.output else src.with_suffix(".pdf")
    ok = build(src, out, a.title, a.subtitle, a.field, a.fontsize)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
