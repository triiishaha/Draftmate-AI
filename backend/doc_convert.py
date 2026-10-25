"""
Document to Markdown conversion.

Order of attempts:
  1. Microsoft MarkItDown, if installed (pip install "markitdown[all]"; it needs Python 3.10 or newer).
  2. Built-in converters: PDF (pypdf), DOCX (python-docx), HTML, CSV, TXT, MD.
The response says which engine was used. Files are read in memory and never saved to disk.
Scanned PDFs (pictures of pages) have no text to extract. We say so instead of guessing: OCR is needed.
"""
from __future__ import annotations

import csv
import io
import os
import re
from html.parser import HTMLParser

from context_opt import est_tokens

MAX_BYTES = 10 * 1024 * 1024
MAX_CHARS = 2_000_000
BUILTIN = {".txt", ".md", ".pdf", ".docx", ".html", ".htm", ".csv"}
EXTRA = {".pptx", ".xlsx"}                     # only with MarkItDown
ALLOWED = BUILTIN | EXTRA


class ConvertError(ValueError):
    pass


def _normalise(md: str) -> str:
    md = md.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    md = re.sub(r"[ \t]+\n", "\n", md)
    return re.sub(r"\n{3,}", "\n\n", md).strip()


# ---------------------------------------------------------------- built-in converters
def _pdf(data: bytes) -> tuple:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                if not reader.decrypt(""):
                    raise ConvertError("This PDF is password protected.")
            except ConvertError:
                raise
            except Exception:
                raise ConvertError("This PDF is password protected.")
        pages = [(p.extract_text() or "").strip() for p in reader.pages]
    except ConvertError:
        raise
    except Exception:
        raise ConvertError("Could not read this PDF. It may be damaged.")
    text = "\n\n".join(p for p in pages if p)
    warn = []
    if len(pages) and len(text) < 20 * len(pages):
        warn.append("This PDF has little or no selectable text. It may be scanned pictures, which needs OCR. Nothing was guessed.")
    return text, warn, len(pages)


def _docx(data: bytes) -> tuple:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    try:
        d = docx.Document(io.BytesIO(data))
    except Exception:
        raise ConvertError("Could not read this DOCX. It may be damaged or not a Word file.")
    out = []
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, d)
            t = p.text.strip()
            if not t:
                continue
            style = (p.style.name or "") if p.style is not None else ""
            m = re.match(r"Heading (\d)", style)
            if style == "Title":
                out.append("# " + t)
            elif m:
                out.append("#" * min(int(m.group(1)), 6) + " " + t)
            elif "List" in style:
                out.append("- " + t)
            else:
                out.append(t)
        elif tag == "tbl":
            rows = [[" ".join(c.text.split()).replace("|", "/") for c in r.cells] for r in Table(child, d).rows]
            if rows:
                w = max(len(r) for r in rows)
                rows = [r + [""] * (w - len(r)) for r in rows]
                md = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * w]
                md += ["| " + " | ".join(r) + " |" for r in rows[1:]]
                out.append("\n".join(md))
    return "\n\n".join(out), [], None


class _Html(HTMLParser):
    SKIP = {"script", "style", "head", "noscript"}

    def __init__(self):
        super().__init__()
        self.out, self.skip, self.href = [], 0, None

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in {"p", "div", "br", "tr", "section", "article"}:
            self.out.append("\n\n" if tag != "br" else "\n")
        elif tag == "li":
            self.out.append("\n- ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in {"td", "th"}:
            self.out.append(" | ")

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)


def _html(data: bytes) -> tuple:
    p = _Html()
    p.feed(_decode(data))
    return "".join(p.out), [], None


def _csv(data: bytes) -> tuple:
    rows = list(csv.reader(io.StringIO(_decode(data))))[:2000]
    if not rows:
        return "", [], None
    w = max(len(r) for r in rows)
    rows = [[c.replace("|", "/").strip() for c in r] + [""] * (w - len(r)) for r in rows]
    md = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * w] + ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(md), [], None


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("utf-8", errors="replace")


def _markitdown(ext: str, data: bytes):
    try:
        from markitdown import MarkItDown, StreamInfo
    except Exception:
        return None
    try:
        res = MarkItDown(enable_plugins=False).convert_stream(io.BytesIO(data), stream_info=StreamInfo(extension=ext))
        return (res.markdown or res.text_content or "").strip()
    except Exception:
        return None


# ---------------------------------------------------------------- public
def convert_bytes(filename: str, data: bytes, prefer_markitdown: bool = True) -> dict:
    name = os.path.basename(filename or "document")
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED:
        raise ConvertError(f"Files of type '{ext or 'unknown'}' are not supported. Use PDF, DOCX, HTML, CSV, TXT or MD.")
    if not data:
        raise ConvertError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise ConvertError(f"The file is too large (max {MAX_BYTES // (1024 * 1024)} MB).")

    engine, warnings, pages, md = None, [], None, ""
    if ext in {".txt", ".md"}:
        md, engine = _decode(data), "plain text"
    else:
        if prefer_markitdown:
            got = _markitdown(ext, data)
            if got:
                md, engine = got, "MarkItDown"
        if not md:
            if ext in EXTRA:
                raise ConvertError("PPTX and XLSX need MarkItDown. Install it with: pip install \"markitdown[all]\" (Python 3.10 or newer).")
            fn = {".pdf": _pdf, ".docx": _docx, ".html": _html, ".htm": _html, ".csv": _csv}[ext]
            md, warnings, pages = fn(data)
            engine = "built-in"
        elif ext == ".pdf":
            try:
                _, w2, pages = _pdf(data)
                warnings = w2
            except ConvertError:
                pass
    md = _normalise(md)
    if len(md) > MAX_CHARS:
        md, warnings = md[:MAX_CHARS], warnings + [f"The text was cut at {MAX_CHARS} characters."]
    if not md:
        warnings.append("No text could be extracted from this file.")
    return {"filename": name, "markdown": md, "engine": engine, "pages": pages, "chars": len(md),
            "words": len(md.split()), "tokens_estimate": est_tokens(md), "warnings": warnings}


try:
    import importlib.util
    from fastapi import APIRouter, HTTPException

    router = APIRouter(prefix="/doc")

    if importlib.util.find_spec("multipart") or importlib.util.find_spec("python_multipart"):
        from fastapi import File, UploadFile

        @router.post("/convert")
        async def convert_endpoint(file: UploadFile = File(...)):
            data = await file.read(MAX_BYTES + 1)
            try:
                return convert_bytes(file.filename or "", data)
            except ConvertError as e:
                raise HTTPException(422, str(e))
    else:
        @router.post("/convert")
        async def convert_unavailable():
            raise HTTPException(501, "File upload needs python-multipart. Run: python3 -m pip install python-multipart")
except ImportError:
    router = None
