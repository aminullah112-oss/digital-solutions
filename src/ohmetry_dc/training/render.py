"""Render the training suite: editable Markdown sources, PDF module notes, exercise workbook, answer key, question bank and certificate template."""
from __future__ import annotations

import csv
import io
from pathlib import Path
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas

from ohmetry_dc import __version__
from ohmetry_dc.models import ProjectConfig

from .content import Exercise, Module, build_modules, build_question_bank

INK = colors.HexColor("#0E171E")
DISCLAIMER = ("Ohmetry course material for engineering learning. It is not accredited training. Worked examples use preliminary assumptions, not manufacturer data. "
              "It does not replace the standards, manufacturer data or a qualified engineer.")
CERT_TEXT = ("This is an Ohmetry course completion certificate. It is not a government, university, professional-body or accredited certification, "
             "unless such accreditation is separately obtained and stated here.")


def _fmt(e: Exercise) -> str:
    if isinstance(e.answer, str):
        return e.answer
    a = e.answer
    return f"{a:,.4f}".rstrip("0").rstrip(".") if abs(a) < 10 else f"{a:,.1f}" if abs(a) < 1000 else f"{a:,.0f}"


def module_markdown(m: Module, stamp: str) -> str:
    L = [f"# Module {m.no:02d}: {m.title}", "", f"_Ohmetry engineering learning suite. Generated {stamp}. {DISCLAIMER}_", "", "## Learning objectives", ""] + [f"- {x}" for x in m.objectives]
    L += ["", "## Technical explanation", ""] + [p + "\n" for p in m.explanation]
    L += ["## Key formulas", "", "| Quantity | Formula | Units |", "|---|---|---|"] + [f"| {a} | `{b}` | {c} |" for a, b, c in m.formulas]
    L += ["", "## Worked example (reference project configuration)", ""] + [f"- {x}" for x in m.example if x]
    L += ["", "## Common engineering mistakes", ""] + [f"- {x}" for x in m.mistakes]
    L += ["", "## Practical design checklist", ""] + [f"- [ ] {x}" for x in m.checklist]
    L += ["", "## Exercise", ""] + [f"**{e.id}.** {e.prompt}\n" for e in m.exercises]
    L += ["_The answer key is a separate document._", "", "## References", ""] + [f"- {x}" for x in m.references]
    L += ["", "## Limitations and safety notes", ""] + [f"- {x}" for x in m.limits]
    return "\n".join(L) + "\n"


def answer_key_markdown(mods: list[Module], bank: list[dict], stamp: str) -> str:
    L = ["# Answer key", "", f"_Generated {stamp}. For instructors and self-checking after the exercise. {DISCLAIMER}_", "", "## Exercises", ""]
    for m in mods:
        L += [f"### Module {m.no:02d}: {m.title}", ""]
        for e in m.exercises:
            L += [f"**{e.id}** Answer: **{_fmt(e)} {e.unit}**".rstrip(), f"Working: {e.working}", ""]
    L += ["## Question bank answers", "", "| Id | Answer | Explanation |", "|---|---|---|"] + [f"| {q['id']} | {'ABCD'[q['answer_index']]}. {q['answer']} | {q['explanation']} |" for q in bank]
    return "\n".join(L) + "\n"


def question_bank_markdown(bank: list[dict], stamp: str) -> str:
    L = ["# Assessment question bank", "", f"_Generated {stamp}. {len(bank)} multiple-choice questions, four per module. Answers are in the answer key._", ""]
    for q in bank:
        L += [f"**{q['id']}.** {q['question']}", ""] + [f"- {'ABCD'[i]}. {o}" for i, o in enumerate(q["options"])] + [""]
    return "\n".join(L)


def bank_csv(bank: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "module", "question", "A", "B", "C", "D", "answer", "explanation"])
    for q in bank:
        w.writerow([q["id"], q["module"], q["question"], *q["options"], "ABCD"[q["answer_index"]], q["explanation"]])
    return buf.getvalue()


def certificate_markdown() -> str:
    return ("# Ohmetry course completion certificate (template)\n\nThis certifies that\n\n**[Participant name]**\n\nhas completed the Ohmetry engineering learning suite\n\n"
            "**Data Centre Electrical Design: 12 modules**\n\non **[date]**.   Certificate number: **[ID]**\n\nIssued by Ohmetry: [name of the person issuing]\n\n"
            f"_{CERT_TEXT}_\n\n_Completion of the course shows that the exercises were attempted. It does not certify competence and does not replace professional qualification, "
            "supervision or the verification of any design._\n")


def _styles():
    ss = getSampleStyleSheet()
    return {"title": ParagraphStyle("t", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=INK, alignment=0),
            "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=INK, spaceBefore=10, spaceAfter=4),
            "body": ParagraphStyle("b", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13, spaceAfter=4),
            "small": ParagraphStyle("s", parent=ss["BodyText"], fontName="Helvetica-Oblique", fontSize=8, leading=10, textColor=colors.HexColor("#555555")),
            "cell": ParagraphStyle("c", parent=ss["BodyText"], fontName="Helvetica", fontSize=8.5, leading=11),
            "bul": ParagraphStyle("bl", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13, leftIndent=12, bulletIndent=2)}


def _p(t, st):
    return Paragraph(escape(str(t)), st)


def _footer(c, doc):
    c.saveState()
    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.HexColor("#555555"))
    c.drawString(18 * mm, 10 * mm, "Ohmetry learning suite. Preliminary educational material, not accredited training.")
    c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    c.restoreState()


def module_pdf(m: Module, path: Path, stamp: str) -> None:
    st = _styles()
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm, title=f"Module {m.no:02d} {m.title}", author="Ohmetry")
    S = [_p(f"Module {m.no:02d}: {m.title}", st["title"]), _p(f"Ohmetry engineering learning suite. Generated {stamp}. Package version {__version__}. {DISCLAIMER}", st["small"]), Spacer(1, 4)]
    S += [_p("Learning objectives", st["h1"])] + [Paragraph("• " + escape(x), st["bul"]) for x in m.objectives]
    S += [_p("Technical explanation", st["h1"])] + [_p(x, st["body"]) for x in m.explanation]
    t = Table([[_p(h, st["cell"]) for h in ("Quantity", "Formula", "Units")]] + [[_p(a, st["cell"]), _p(b, st["cell"]), _p(c, st["cell"])] for a, b, c in m.formulas], colWidths=[45 * mm, 80 * mm, 49 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D2DA")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEFF1")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    S += [_p("Key formulas", st["h1"]), t, _p("Worked example (reference project configuration)", st["h1"])] + [Paragraph("• " + escape(x), st["bul"]) for x in m.example if x]
    S += [_p("Common engineering mistakes", st["h1"])] + [Paragraph("• " + escape(x), st["bul"]) for x in m.mistakes]
    S += [_p("Practical design checklist", st["h1"])] + [Paragraph("[  ] " + escape(x), st["bul"]) for x in m.checklist]
    S += [_p("Exercise", st["h1"])] + [_p(f"{e.id}. {e.prompt}", st["body"]) for e in m.exercises] + [_p("The answer key is a separate document.", st["small"])]
    S += [_p("References", st["h1"])] + [Paragraph("• " + escape(x), st["bul"]) for x in m.references]
    S += [_p("Limitations and safety notes", st["h1"])] + [Paragraph("• " + escape(x), st["bul"]) for x in m.limits]
    doc.build(S, onFirstPage=_footer, onLaterPages=_footer)


def answer_key_pdf(mods: list[Module], bank: list[dict], path: Path, stamp: str) -> None:
    st = _styles()
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm, title="Answer key", author="Ohmetry")
    S = [_p("Answer key", st["title"]), _p(f"Generated {stamp}. {DISCLAIMER}", st["small"])]
    for m in mods:
        S.append(_p(f"Module {m.no:02d}: {m.title}", st["h1"]))
        for e in m.exercises:
            S.append(_p(f"{e.id}: {_fmt(e)} {e.unit}".strip() + f".  Working: {e.working}", st["body"]))
    S += [PageBreak(), _p("Question bank answers", st["h1"])]
    t = Table([[_p(h, st["cell"]) for h in ("Id", "Answer", "Explanation")]] + [[_p(q["id"], st["cell"]), _p(f"{'ABCD'[q['answer_index']]}. {q['answer']}", st["cell"]), _p(q["explanation"], st["cell"])] for q in bank], colWidths=[18 * mm, 70 * mm, 86 * mm], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D2DA")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEFF1")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    S.append(t)
    doc.build(S, onFirstPage=_footer, onLaterPages=_footer)


def certificate_pdf(path: Path) -> None:
    w, h = landscape(A4)
    c = canvas.Canvas(str(path), pagesize=(w, h))
    c.setStrokeColor(INK)
    c.setLineWidth(2)
    c.rect(15 * mm, 15 * mm, w - 30 * mm, h - 30 * mm)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(w / 2, h - 45 * mm, "Ohmetry Course Completion Certificate")
    c.setFont("Helvetica", 13)
    c.drawCentredString(w / 2, h - 65 * mm, "This certifies that")
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(w / 2, h - 82 * mm, "[Participant name]")
    c.setFont("Helvetica", 13)
    c.drawCentredString(w / 2, h - 100 * mm, "has completed the Ohmetry engineering learning suite")
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(w / 2, h - 112 * mm, "Data Centre Electrical Design: 12 modules")
    c.setFont("Helvetica", 12)
    c.drawCentredString(w / 2, h - 128 * mm, "Date: [date]        Certificate number: [ID]        Issued by: [name]")
    c.setFont("Helvetica-Oblique", 9.5)
    for i, line in enumerate(["This is an Ohmetry course completion certificate. It is not a government, university, professional-body or accredited certification,", "unless such accreditation is separately obtained and stated here."]):
        c.drawCentredString(w / 2, 40 * mm - i * 5 * mm, line)
    c.save()


def exercise_workbook(mods: list[Module], path: Path, stamp: str) -> None:
    """Exercises without answers: a blue cell per exercise for the learner's answer. The answers are in the answer key."""
    wb = Workbook()
    ws = wb.active
    ws.title = "EXERCISES"
    ws["A1"].value, ws["A1"].font = "Ohmetry learning suite: exercise workbook", Font(name="Arial", size=14, bold=True)
    ws["A2"].value = f"Generated {stamp}. {DISCLAIMER}"
    hdr = ["Id", "Module", "Exercise", "Your answer", "Unit", "Notes / working"]
    for i, (h, wd) in enumerate(zip(hdr, [8, 40, 100, 16, 10, 50]), 1):
        c = ws.cell(4, i, h)
        c.font, c.fill = Font(name="Arial", bold=True, color="FFFFFF"), PatternFill("solid", fgColor="0E171E")
        ws.column_dimensions[chr(64 + i)].width = wd
    r = 5
    for m in mods:
        for e in m.exercises:
            for col, v in zip("ABCEF", (e.id, f"{m.no:02d} {m.title}", e.prompt, e.unit, None)):
                ws[f"{col}{r}"].value = v
            ws[f"C{r}"].alignment = __import__("openpyxl").styles.Alignment(wrap_text=True, vertical="top")
            ws[f"D{r}"].fill = PatternFill("solid", fgColor="DCEBFF")
            ws[f"D{r}"].font = Font(name="Arial", color="0000FF")
            r += 1
    ws.freeze_panes = "A5"
    wb.save(path)


def build_training(cfg: ProjectConfig, out: Path, stamp: str) -> list[Path]:
    mods = build_modules(cfg)
    bank = build_question_bank(mods)
    for d in ("modules", "exercises", "assessments", "answer_keys"):
        (out / d).mkdir(parents=True, exist_ok=True)
    (out / "modules" / "source").mkdir(exist_ok=True)
    written: list[Path] = []
    for m in mods:
        stem = f"{m.no:02d}_{m.title.replace(' ', '_').replace(',', '').replace('/', '_')}"
        md = out / "modules" / "source" / f"{stem}.md"
        md.write_text(module_markdown(m, stamp), encoding="utf-8")
        pdf = out / "modules" / f"{stem}.pdf"
        module_pdf(m, pdf, stamp)
        written += [md, pdf]
    ex = out / "exercises" / "Exercise_Workbook.xlsx"
    exercise_workbook(mods, ex, stamp)
    qb_md, qb_csv = out / "assessments" / "Question_Bank.md", out / "assessments" / "Question_Bank.csv"
    qb_md.write_text(question_bank_markdown(bank, stamp), encoding="utf-8")
    qb_csv.write_text(bank_csv(bank), encoding="utf-8")
    ak_md, ak_pdf = out / "answer_keys" / "Answer_Key.md", out / "answer_keys" / "Answer_Key.pdf"
    ak_md.write_text(answer_key_markdown(mods, bank, stamp), encoding="utf-8")
    answer_key_pdf(mods, bank, ak_pdf, stamp)
    cert_md, cert_pdf = out / "Completion_Certificate_Template.md", out / "Completion_Certificate_Template.pdf"
    cert_md.write_text(certificate_markdown(), encoding="utf-8")
    certificate_pdf(cert_pdf)
    return written + [ex, qb_md, qb_csv, ak_md, ak_pdf, cert_md, cert_pdf]
