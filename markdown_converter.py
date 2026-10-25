"""Document -> Markdown. Uses Microsoft MarkItDown when installed (pip install 'markitdown[all]'),
otherwise a lightweight fallback so the app still works. The 'engine' field says which one ran."""
import io, os, re, tempfile

SUPPORTED = {".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".html", ".htm", ".csv", ".json", ".xml", ".txt", ".md", ".epub", ".msg"}

def _markitdown(data, ext):
    from markitdown import MarkItDown  # raises ImportError if not installed
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(data); path = tmp.name
    try:
        return MarkItDown().convert(path).text_content
    finally:
        os.unlink(path)

def _fallback(data, ext):
    if ext in {".txt", ".md", ".csv", ".json", ".xml"}:
        return data.decode("utf-8", errors="ignore")
    if ext in {".html", ".htm"}:
        t = data.decode("utf-8", errors="ignore")
        t = re.sub(r"(?is)<(script|style).*?</\1>", "", t)
        t = re.sub(r"(?i)<h([1-6])[^>]*>", lambda m: "\n\n" + "#" * int(m.group(1)) + " ", t)
        t = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>|<br\s*/?>", "\n", t)
        return re.sub(r"<[^>]+>", "", t)
    if ext == ".pdf":
        from pypdf import PdfReader
        return "\n\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    if ext == ".docx":
        import docx
        out = []
        for p in docx.Document(io.BytesIO(data)).paragraphs:
            style = (p.style.name or "") if p.style is not None else ""
            m = re.match(r"Heading (\d)", style)
            out.append(("#" * int(m.group(1)) + " " + p.text) if m and p.text.strip() else p.text)
        return "\n\n".join(out)
    raise ValueError(f"Install markitdown to convert {ext} files: pip install 'markitdown[all]'")

def convert_bytes(data: bytes, filename: str):
    from token_optimizer import count_tokens, normalise_markdown
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED))}")
    try:
        md, engine = _markitdown(data, ext), "markitdown"
    except ImportError:
        md, engine = _fallback(data, ext), "fallback"
    raw_tokens = count_tokens(md)
    md = normalise_markdown(md)
    if not md.strip():
        raise ValueError("No text found. Scanned PDFs need OCR before conversion.")
    return {"filename": filename, "markdown": md, "engine": engine, "tokens": count_tokens(md), "raw_tokens": raw_tokens}
