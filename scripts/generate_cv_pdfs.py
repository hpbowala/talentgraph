# /// script
# requires-python = ">=3.12"
# dependencies = ["fpdf2>=2.8"]
# ///
"""Render the authored CV sources in data/cv_sources/ to PDFs in data/sample_cvs/.

The .txt originals live outside the indexed corpus, which holds one document
per person.

Run with: uv run scripts/generate_cv_pdfs.py
"""

from pathlib import Path

from fpdf import FPDF

SOURCE_DIR = Path(__file__).parent.parent / "data" / "cv_sources"
CV_DIR = Path(__file__).parent.parent / "data" / "sample_cvs"


def render_pdf(txt_path: Path) -> Path:
    lines = txt_path.read_text(encoding="utf-8").splitlines()
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(18, 18, 18)

    for i, line in enumerate(lines):
        text = line.replace("—", "-").replace("–", "-").replace("’", "'")
        if i == 0:
            pdf.set_font("Helvetica", "B", 16)
        elif text and text == text.upper() and len(text) > 3 and not text.startswith("-"):
            pdf.set_font("Helvetica", "B", 11)
        else:
            pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5.5, text if text else " ", new_x="LMARGIN", new_y="NEXT")

    out_path = CV_DIR / f"{txt_path.stem}.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path


def main() -> None:
    txt_files = sorted(SOURCE_DIR.glob("*.txt"))
    if not txt_files:
        raise SystemExit(f"No .txt CV sources found in {SOURCE_DIR}")
    for txt in txt_files:
        out = render_pdf(txt)
        print(f"wrote {out.relative_to(CV_DIR.parent.parent)}")


if __name__ == "__main__":
    main()
