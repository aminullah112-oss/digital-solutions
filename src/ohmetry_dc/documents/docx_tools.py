"""Small python-docx helpers: a document-control block, headings, tables and bullet lists, plus DOCX to PDF through LibreOffice."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor


def new_document(title: str, doc_no: str, revision: str, status_line: str, header_text: str) -> Document:
    d = Document()
    st = d.styles["Normal"]
    st.font.name, st.font.size = "Arial", Pt(10)
    for s in d.sections:
        s.header.paragraphs[0].text = header_text
        s.header.paragraphs[0].runs[0].font.size = Pt(8)
        s.footer.paragraphs[0].text = f"{doc_no}  Revision {revision}.  {status_line}"
        s.footer.paragraphs[0].runs[0].font.size = Pt(8)
    return d


def shade(cell, hexcolor: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def title(d: Document, text: str, sub: str = "") -> None:
    p = d.add_paragraph()
    r = p.add_run(text)
    r.bold, r.font.size = True, Pt(18)
    if sub:
        q = d.add_paragraph()
        r2 = q.add_run(sub)
        r2.italic, r2.font.size = True, Pt(9)
        r2.font.color.rgb = RGBColor(0x55, 0x55, 0x55)


def banner(d: Document, text: str) -> None:
    t = d.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    c = t.rows[0].cells[0]
    c.text = text
    shade(c, "FFE9A8")
    for r in c.paragraphs[0].runs:
        r.bold, r.font.size = True, Pt(9)
    d.add_paragraph()


def table(d: Document, header: list[str], rows: list[list], widths: list[float] | None = None, head_fill: str = "0E171E") -> None:
    t = d.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = str(h)
        shade(c, head_fill)
        for r in c.paragraphs[0].runs:
            r.bold, r.font.size, r.font.color.rgb = True, Pt(9), RGBColor(255, 255, 255)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = "" if v is None else str(v)
            for p in cells[i].paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
    d.add_paragraph()


def bullets(d: Document, items: list[str]) -> None:
    for it in items:
        d.add_paragraph(it, style="List Bullet")


def numbered(d: Document, items: list[str], prefix: str) -> None:
    for i, it in enumerate(items, 1):
        p = d.add_paragraph(f"{prefix}.{i}  {it}")
        p.paragraph_format.left_indent = Pt(18)
        p.paragraph_format.first_line_indent = Pt(-18)


def to_pdf(docx: Path, outdir: Path) -> Path | None:
    """Convert with LibreOffice when available. Returns the PDF path or None."""
    if not shutil.which("soffice"):
        return None
    outdir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(docx)], capture_output=True, timeout=240)
    pdf = outdir / (docx.stem + ".pdf")
    return pdf if pdf.exists() else None
