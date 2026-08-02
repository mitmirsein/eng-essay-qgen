import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "tools" / "exam-pdf" / "make_exam_pdf.py"
SPEC = importlib.util.spec_from_file_location("make_exam_pdf", MODULE_PATH)
assert SPEC and SPEC.loader
PDF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PDF)


def test_pdf_profiles_only_wrap_exam_in_two_columns():
    markdown = "# Title\n\nBody.\n"
    assert "begin{multicols}" in PDF.clean(markdown, "exam")
    assert "begin{multicols}" not in PDF.clean(markdown, "teacher")
    assert "begin{multicols}" not in PDF.clean(markdown, "feedback")


def test_tex_escape_covers_user_controlled_special_characters():
    escaped = PDF.tex_escape(r"A&B 50% $x$ #tag _name {x} ~ ^")
    assert r"A\&B 50\% \$x\$ \#tag \_name \{x\} \textasciitilde{} \textasciicircum{}" == escaped


def test_exam_profile_rejects_zero_total_before_external_tools(tmp_path: Path):
    source = tmp_path / "student.md"
    output = tmp_path / "student.pdf"
    source.write_text("# Student\n\nNo point metadata.\n", encoding="utf-8")
    assert PDF.build(source, output, "Title", "Subtitle", None, "10pt", profile="exam") is False
    assert not output.exists()
