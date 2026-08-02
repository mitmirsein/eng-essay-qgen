#!/usr/bin/env python3
"""Render Markdown into a profile-specific Korean/English PDF.

The exam profile keeps the original two-column layout. Teacher and feedback
documents use separate one-column preambles so a lesson guide never inherits a
student name field or exam total by accident.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PREAMBLES = {
    "exam": Path(__file__).resolve().parent / "exam-preamble.tex",
    "teacher": Path(__file__).resolve().parent / "teacher-preamble.tex",
    "feedback": Path(__file__).resolve().parent / "feedback-preamble.tex",
}
PREAMBLE = PREAMBLES["exam"]


def _cell(value: str) -> str:
    """Convert Markdown emphasis in one matrix cell to simple LaTeX."""

    value = value.strip()
    value = re.sub(r"\\newline\s*$", "", value).strip()
    value = re.sub(r"\*\*([^*]+)\*\*", r"\\textbf{\1}", value)
    value = re.sub(r"\*([^*]+)\*", r"\\textit{\1}", value)
    return value


def collapse_matrices(lines: list[str]) -> list[str]:
    """Convert runs of ``&nbsp;``-aligned rows to a real tabular."""

    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if "&nbsp;" in line and not line.lstrip().startswith(">"):
            end = index
            run: list[str] = []
            while (
                end < len(lines)
                and "&nbsp;" in lines[end]
                and not lines[end].lstrip().startswith(">")
            ):
                run.append(lines[end])
                end += 1
            if len(run) >= 2:
                rows = []
                for row in run:
                    cells = [_cell(cell) for cell in re.split(r"(?:&nbsp;)+", row)]
                    rows.append([cell for cell in cells if cell])
                column_count = max(len(row) for row in rows)
                column_spec = "@{}" + "l@{\\hspace{3.2em}}" * (column_count - 1) + "l@{}"
                body = " \\\\\n".join(
                    " & ".join(row + [""] * (column_count - len(row))) for row in rows
                )
                output.extend(
                    [
                        "",
                        "```{=latex}",
                        r"\begin{center}\setlength{\extrarowheight}{2pt}",
                        f"\\begin{{tabular}}{{{column_spec}}}",
                        body,
                        r"\end{tabular}\end{center}",
                        "```",
                        "",
                    ]
                )
                index = end
                continue
        output.append(line)
        index += 1
    return output


def clean(md: str, profile: str = "exam") -> str:
    """Apply content-preserving Markdown fixes for the selected profile."""

    md = re.sub(r"^\#\s+.*\n", "", md, count=1)
    md = md.lstrip("\n")
    md = re.sub(r"^-{3,}\s*\n", "", md, count=1)
    md = re.sub(
        r">\s*\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(.*)",
        r"> **\1**",
        md,
        flags=re.IGNORECASE,
    )
    md = md.replace("<조건>", "[조건]")

    output: list[str] = []
    for line in collapse_matrices(md.split("\n")):
        if line.strip() == "<br>":
            output.extend(["", r"\vspace{1.5pt}", ""])
            continue
        is_blockquote = line.lstrip().startswith(">")
        previous = output[-1].strip() if output else ""
        previous_is_blockquote = output[-1].lstrip().startswith(">") if output else False
        if is_blockquote and previous and not previous_is_blockquote:
            if output[-1].rstrip().endswith(r"\newline"):
                output[-1] = output[-1].rstrip()[: -len(r"\newline")].rstrip()
            output.append("")
        output.append(line)

    text = re.sub(r"\n{3,}", "\n\n", "\n".join(output)).strip()
    if profile == "exam":
        return (
            "```{=latex}\n\\begin{multicols}{2}\n```\n\n"
            + text
            + "\n\n```{=latex}\n\\end{multicols}\n```\n"
        )
    return text + "\n"


def total_points(md: str) -> str:
    points = [float(value) for value in re.findall(r"\[(\d+(?:\.\d+)?)\s*점\]", md)]
    return f"{sum(points):g}"


def tex_escape(value: str) -> str:
    """Escape user-controlled text interpolated into a TeX preamble."""

    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def _failure(message: str, work: Path | None = None) -> bool:
    suffix = f" (temporary files: {work})" if work else ""
    sys.stderr.write(f"{message}{suffix}\n")
    return False


def build(
    src: Path,
    out_pdf: Path,
    title: str,
    subtitle: str,
    field: str | None,
    fontsize: str,
    profile: str = "exam",
    total_points_override: float | None = None,
    max_overfull: int = 0,
) -> bool:
    """Build a PDF and fail closed on tool or PDF QA errors."""

    if profile not in PREAMBLES:
        return _failure(f"unsupported profile: {profile}")
    try:
        md = src.read_text(encoding="utf-8")
    except OSError as exc:
        return _failure(f"cannot read Markdown input: {exc}")

    total = total_points_override if total_points_override is not None else float(total_points(md))
    total_label = f"{total:g}"
    if profile == "exam" and total <= 0:
        return _failure("exam profile requires a positive total point value")

    work = Path(tempfile.mkdtemp(prefix="exampdf_"))
    clean_md = work / "clean.md"
    clean_md.write_text(clean(md, profile=profile), encoding="utf-8")

    preamble = work / "preamble.tex"
    base = PREAMBLES[profile].read_text(encoding="utf-8")
    if profile == "exam":
        base += f"\n\\setexamsubtitle{{{tex_escape(subtitle)}}}\n"
        base += f"\\setexammeta{{\\fontspec{{Apple SD Gothic Neo}}\\small 총 {total_label}점}}\n"
        if field:
            base += f"\\setexamfield{{{tex_escape(field)}}}\n"
    elif profile == "feedback":
        if field:
            base += f"\n\\setfeedbackfield{{{tex_escape(field)}}}\n"
        if total_points_override is not None:
            base += (
                "\\setfeedbackmeta{\\fontspec{Apple SD Gothic Neo}"
                f"\\small 총 {total_label}점}}\n"
            )
    preamble.write_text(base, encoding="utf-8")

    tex = work / "exam.tex"
    pandoc = [
        "pandoc",
        str(clean_md),
        "-s",
        "-o",
        str(tex),
        "--metadata",
        f"title={title}",
        "-V",
        f"fontsize={fontsize}",
        "-V",
        "geometry=a4paper, top=1.7cm, bottom=1.7cm, left=1.5cm, right=1.5cm",
        "-V",
        "documentclass=article",
        "-H",
        str(preamble),
    ]
    pandoc_result = subprocess.run(pandoc, capture_output=True, text=True)
    if pandoc_result.returncode != 0:
        return _failure("pandoc failed:\n" + pandoc_result.stderr, work)

    latex_results = []
    for _ in range(2):
        latex_results.append(
            subprocess.run(
                ["xelatex", "-interaction=nonstopmode", f"-output-directory={work}", str(tex)],
                capture_output=True,
                text=True,
            )
        )
    failed_latex = next((result for result in latex_results if result.returncode != 0), None)
    if failed_latex:
        return _failure("xelatex failed:\n" + failed_latex.stdout[-4000:], work)

    built = work / "exam.pdf"
    if not built.exists():
        log = work / "exam.log"
        tail = ""
        if log.exists():
            tail = "\n".join(log.read_text(errors="replace").splitlines()[-25:])
        return _failure("xelatex produced no PDF. Tail of log:\n" + tail, work)

    log = (work / "exam.log").read_text(errors="replace")
    missing_characters = len(re.findall(r"Missing character", log))
    overfull = len(re.findall(r"Overfull \\hbox", log))
    if missing_characters > 0:
        return _failure(f"PDF QA failed: Missing character count is {missing_characters}", work)
    if overfull > max_overfull:
        return _failure(
            f"PDF QA failed: Overfull hbox count is {overfull}, allowed {max_overfull}", work
        )

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(built, out_pdf)
    pages = "?"
    try:
        info = subprocess.run(["pdfinfo", str(out_pdf)], capture_output=True, text=True).stdout
        match = re.search(r"Pages:\s+(\d+)", info)
        pages = match.group(1) if match else "?"
    except OSError:
        pass
    total_text = f" · 총 {total_label}점" if profile in {"exam", "feedback"} else ""
    print(
        f"{out_pdf} ({pages} pages · profile={profile}{total_text} · "
        f"Missing char {missing_characters} · Overfull {overfull})"
    )
    shutil.rmtree(work, ignore_errors=True)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Markdown to a profile-specific PDF.")
    parser.add_argument("input")
    parser.add_argument("-o", "--output")
    parser.add_argument("--title", required=True)
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--profile", choices=sorted(PREAMBLES), default="exam")
    parser.add_argument("--total-points", type=float, default=None)
    parser.add_argument("--max-overfull", type=int, default=0)
    parser.add_argument(
        "--field",
        default=None,
        help="override the exam name/number field or set a feedback student identifier",
    )
    parser.add_argument("--fontsize", default="10pt")
    args = parser.parse_args()

    source = Path(args.input)
    output = Path(args.output) if args.output else source.with_suffix(".pdf")
    ok = build(
        source,
        output,
        args.title,
        args.subtitle,
        args.field,
        args.fontsize,
        profile=args.profile,
        total_points_override=args.total_points,
        max_overfull=args.max_overfull,
    )
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
