import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

docx = pytest.importorskip("docx")
reportlab = pytest.importorskip("reportlab")

from pipeline_service import process_document_command
from document_service import extract_document, extract_document_details
from markdown_converter import to_structured_markdown
from structure_parser import parse_document


def make_docx(sections=4, filler=25, word_levels=False):
    d = docx.Document()
    d.add_heading("SERVICE AGREEMENT", 1)
    names = ["Payment Terms", "Termination", "Confidentiality", "Governing Law", "Liability", "Notices"]
    for i in range(sections):
        # word_levels=True: the author used Heading 1 for every numbered heading, a common mistake
        d.add_heading(f"{i+1}. {names[i]}", 1 if word_levels else 2)
        d.add_paragraph(f"General terms about {names[i].lower()}. " + "Standard filler wording applies here. " * filler)
        d.add_heading(f"{i+1}.1 {names[i]} details", 1 if word_levels else 3)
        d.add_paragraph(f"Detail for {names[i].lower()}: the client must pay Rs. 50,000 within 30 days.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text, t.cell(1, 0).text, t.cell(1, 1).text = "Item", "Amount", "Fee", "50,000"
    d.add_paragraph("See Section 27 of the Indian Contract Act, 1872.")
    b = io.BytesIO(); d.save(b)
    return b.getvalue()


def make_pdf(pages=6, scanned=False):
    from reportlab.pdfgen import canvas
    b = io.BytesIO(); c = canvas.Canvas(b)
    for i in range(pages):
        if scanned:
            c.rect(50, 50, 100, 100)
        else:
            c.drawString(72, 800, "ACME CONFIDENTIAL")
            c.drawString(72, 760, f"{i+1}. Clause number {i+1}")
            c.drawString(72, 740, "The client must pay within 30 days of the invoice date.")
            c.drawString(300, 30, str(i + 1))
        c.showPage()
    c.save()
    return b.getvalue()


def test_old_behaviour_still_works():
    md = to_structured_markdown("SERVICE AGREEMENT\n\n1. Payment Terms\nPay in 30 days.\n\n1.1 Late Fees\nFees may apply.\n")
    p = parse_document(md)
    assert p["title"] == "SERVICE AGREEMENT" and p["sections"][0]["clauses"][0]["clause_id"] == "1.1"
    assert "SERVICE AGREEMENT" in extract_document("a.docx", make_docx())


def test_docx_headings_tables_and_levels():
    md = to_structured_markdown(extract_document("a.docx", make_docx(word_levels=True)))
    assert "## 1. Payment Terms" in md and "### 1.1 Payment Terms details" in md      # re-levelled
    assert "| Item | Amount |" in md                                                  # table kept in place
    p = parse_document(md)
    assert p["title"] == "SERVICE AGREEMENT"                                          # not overwritten by a numbered heading
    assert len(p["sections"]) == 4


def test_pdf_headers_and_page_numbers_removed_by_pipeline():
    r = process_document_command("a.pdf", make_pdf(), "Summarise this agreement", generate_ai=False)
    text = r["context"]["text"]
    assert "ACME CONFIDENTIAL" not in text and "Clause number 3" in text
    assert any("repeated header" in s for s in r["optimization"]["cleaning"])


def test_scanned_pdf_and_bad_types_raise_clear_errors():
    with pytest.raises(ValueError, match="OCR"):
        extract_document("scan.pdf", make_pdf(scanned=True))
    with pytest.raises(ValueError, match="Only PDF and DOCX"):
        extract_document("a.exe", b"MZ")


def test_clause_command_sends_only_the_clause_and_reports_savings():
    r = process_document_command("a.docx", make_docx(), "Explain clause 2.1", generate_ai=False)
    o = r["optimization"]
    assert r["context"]["found"] and "Termination" in r["context"]["heading"]
    assert o["strategy"] == "clause" and o["sent_tokens"] < o["full_document_tokens"] and o["saved_pct"] > 50
    assert r["estimated_tokens"] == o["sent_tokens"]


def test_long_summary_is_cut_to_budget_and_keeps_citations():
    big = make_docx(sections=6, filler=120)
    full = process_document_command("a.docx", big, "Summarise this agreement", max_tokens=100000, generate_ai=False)
    cut = process_document_command("a.docx", big, "Summarise this agreement", max_tokens=1200, generate_ai=False)
    assert cut["estimated_tokens"] < full["estimated_tokens"] and cut["optimization"]["saved_pct"] > 40
    assert cut["estimated_tokens"] <= 1300
    assert cut["optimization"]["citations"]["kept"] == cut["optimization"]["citations"]["total"] >= 1
    assert any(not s["kept"] for s in cut["optimization"]["sections"])


def test_general_instruction_prefers_matching_sections():
    big = make_docx(sections=6, filler=120)
    r = process_document_command("a.docx", big, "What happens on termination?", max_tokens=1200, generate_ai=False)
    kept = [s["title"] for s in r["optimization"]["sections"] if s["kept"]]
    assert any("Termination" in k for k in kept)


def test_works_without_gemini_key_until_ai_is_needed(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = process_document_command("a.docx", make_docx(), "Explain clause 1.1", generate_ai=False)
    assert r["ai_response"] is None and r["conversion"]["engine"] in {"built-in", "MarkItDown"}


def test_ai_is_called_with_the_reduced_context(monkeypatch):
    seen = {}
    fake = type(sys)("ai_service")
    fake.generate_document_response = lambda action, context, transcript: seen.update(action=action, text=context["text"], heading=context.get("heading", "")) or "ok"
    monkeypatch.setitem(sys.modules, "ai_service", fake)
    r = process_document_command("a.docx", make_docx(), "Rewrite clause 1.1 in simpler language")
    assert r["ai_response"] == "ok" and seen["action"] == "rewrite_clause" and "Payment Terms" in seen["heading"] and "50,000" in seen["text"]
    assert "Governing Law" not in seen["text"]          # the rest of the document was not sent


def test_unknown_clause_is_not_invented():
    r = process_document_command("a.docx", make_docx(), "Explain clause 9.9", generate_ai=False)
    assert r["context"]["found"] is False and r["ai_response"] is None
