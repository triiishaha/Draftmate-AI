"""Export a draft as a real Word (.docx) file: POST /export/docx {text, title}."""
from __future__ import annotations

import io
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter(prefix="/export", tags=["export"])
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class ExportIn(BaseModel):
    text: str
    title: str = "DraftMate document"


def _is_heading(line: str) -> bool:
    t = line.strip()
    if not t or len(t) > 80 or t.endswith((".", ",", ";")):
        return False
    return t.isupper() or t.startswith("#") or bool(re.match(r"^(\d+[.)]|Article|Clause|Schedule)\s+[A-Z]", t) and len(t.split()) <= 7)


def _add_inline(paragraph, text: str, force_bold: bool = False):
    """Write text into a paragraph, turning **bold** and *italic* markdown into real formatting."""
    for part in re.split(r"(\*\*.+?\*\*)", text):
        if not part:
            continue
        bold = force_bold or (part.startswith("**") and part.endswith("**") and len(part) > 4)
        chunk = part[2:-2] if part.startswith("**") and part.endswith("**") and len(part) > 4 else part
        for sub in re.split(r"(?<!\*)(\*[^*\s][^*]*\*)(?!\*)", chunk):
            if not sub:
                continue
            italic = sub.startswith("*") and sub.endswith("*") and len(sub) > 2
            run = paragraph.add_run(sub[1:-1] if italic else sub)
            run.bold, run.italic = bold, italic


def build_docx(text: str, title: str) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt

    doc = Document()
    for sec in doc.sections:
        sec.top_margin = sec.bottom_margin = Cm(2.5)
        sec.left_margin = sec.right_margin = Cm(2.5)
    style = doc.styles["Normal"]
    style.font.name, style.font.size = "Times New Roman", Pt(12)
    style.paragraph_format.space_after = Pt(8)
    style.paragraph_format.line_spacing = 1.3
    doc.core_properties.title = title[:120]
    doc.core_properties.author = "DraftMate AI"

    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines or all(re.fullmatch(r"\s*(-{3,}|\*{3,}|_{3,})\s*", l) for l in lines):
            continue
        # a block that is just one heading line
        if len(lines) == 1:
            raw = lines[0].strip()
            m = re.match(r"^(#{1,6})\s+(.*)$", raw)
            if m or _is_heading(raw):
                label = (m.group(2) if m else raw).strip().strip("*").strip()
                p = doc.add_paragraph()
                r = p.add_run(label)
                r.bold = True
                if m and len(m.group(1)) <= 2:
                    r.font.size = Pt(14)
                p.paragraph_format.keep_with_next = True
                if label.isupper() or (m and len(m.group(1)) == 1):
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                continue
        p = None
        for line in lines:
            raw = line.strip()
            if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", raw):
                continue
            h = re.match(r"^(#{1,6})\s+(.*)$", raw)
            b = re.match(r"^[*\-\u2022]\s+(.*)$", raw)
            if h:
                hp = doc.add_paragraph()
                _add_inline(hp, h.group(2), force_bold=True)
                hp.paragraph_format.keep_with_next = True
                p = None
            elif b:
                bp = doc.add_paragraph(style="List Bullet")
                _add_inline(bp, b.group(1))
                p = None
            else:
                if p is None:
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                else:
                    p.runs[-1].add_break()
                _add_inline(p, raw)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@router.post("/docx")
def export_docx(body: ExportIn):
    if not body.text.strip():
        raise HTTPException(422, "There is nothing to export yet.")
    if len(body.text) > 500_000:
        raise HTTPException(413, "The draft is too long to export.")
    try:
        data = build_docx(body.text, body.title)
    except ImportError:
        raise HTTPException(501, "Word export needs python-docx. Run: python3 -m pip install python-docx")
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", body.title).strip("-") or "DraftMate"
    return Response(data, media_type=DOCX, headers={"Content-Disposition": f'attachment; filename="{name}.docx"'})


def build_pdf(text: str, title: str) -> bytes:
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    from xml.sax.saxutils import escape

    def inline(t: str) -> str:
        t = escape(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        return re.sub(r"(?<!\*)\*([^*\s][^*]*)\*(?!\*)", r"<i>\1</i>", t)

    body = ParagraphStyle("body", fontName="Times-Roman", fontSize=12, leading=17, alignment=TA_JUSTIFY, spaceAfter=8)
    head = ParagraphStyle("head", parent=body, fontName="Times-Bold", alignment=0, spaceBefore=6, keepWithNext=1)
    centre = ParagraphStyle("centre", parent=head, alignment=TA_CENTER, fontSize=14, leading=18)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=18, bulletIndent=6, alignment=0, spaceAfter=4)

    story = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        lines = [l for l in lines if not re.fullmatch(r"-{3,}|\*{3,}|_{3,}", l)]
        if not lines:
            continue
        para = []

        def flush():
            if para:
                story.append(Paragraph("<br/>".join(inline(x) for x in para), body))
                para.clear()
        for raw in lines:
            h = re.match(r"^(#{1,6})\s+(.*)$", raw)
            b = re.match(r"^[*\-\u2022]\s+(.*)$", raw)
            if h:
                flush(); story.append(Paragraph(inline(h.group(2)), centre if len(h.group(1)) == 1 else head))
            elif b:
                flush(); story.append(Paragraph(inline(b.group(1)), bullet, bulletText="\u2022"))
            elif len(lines) == 1 and _is_heading(raw):
                story.append(Paragraph(inline(raw.strip("*")), centre if raw.isupper() else head))
            else:
                para.append(raw)
        flush()
    if not story:
        story.append(Spacer(1, 1))
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=2.5 * cm, rightMargin=2.5 * cm, topMargin=2.5 * cm, bottomMargin=2.5 * cm,
                      title=title[:120], author="DraftMate AI").build(story)
    return buf.getvalue()


@router.post("/pdf")
def export_pdf(body: ExportIn):
    if not body.text.strip():
        raise HTTPException(422, "There is nothing to export yet.")
    if len(body.text) > 500_000:
        raise HTTPException(413, "The draft is too long to export.")
    try:
        data = build_pdf(body.text, body.title)
    except ImportError:
        raise HTTPException(501, "PDF export needs reportlab. Run: python3 -m pip install reportlab")
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", body.title).strip("-") or "DraftMate"
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})
