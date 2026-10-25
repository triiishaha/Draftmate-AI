"""Context and token optimisation: normalise Markdown, chunk by structure, retrieve only what the
task needs, keep citations, compress chat history, and score prompts. No heavy dependencies."""
import math, re
from collections import Counter

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
except Exception:  # tiktoken missing or no network for its vocab
    _enc = None

def count_tokens(text: str) -> int:
    if not text: return 0
    return len(_enc.encode(text)) if _enc else max(1, len(text) // 4)  # ~4 chars/token estimate

CITATION_RE = re.compile(
    r"\(\d{4}\)\s*\d+\s*SCC\s*\d+|\bAIR\s*\d{4}\s*[A-Z]{2,5}\s*\d+|\b\d{4}\s*SCC\s*OnLine\s*[A-Za-z]+\s*\d+|"
    r"\b\d+\s+U\.S\.\s+\d+|\b[A-Z][\w.&' ]+\s+v\.?\s+[A-Z][\w.&' ]+|"
    r"\b(?:Section|Sec\.|Article|Art\.|Rule|Order)\s+\d+[A-Za-z]?(?:\(\d+\))?(?:\s+of\s+the\s+[A-Z][\w ]+?(?:Act|Code)(?:,?\s*\d{4})?)?", re.I)

def find_citations(text): return sorted({m.group(0).strip() for m in CITATION_RE.finditer(text or "")})

def normalise_markdown(text: str) -> str:
    """Lossless-for-meaning cleanup: whitespace, page numbers, repeated headers/footers."""
    lines = [l.rstrip() for l in (text or "").replace("\r", "").split("\n")]
    freq = Counter(l.strip() for l in lines if 3 < len(l.strip()) < 80)
    out = []
    for l in lines:
        s = l.strip()
        if re.fullmatch(r"(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?", s, re.I): continue          # page numbers
        if freq.get(s, 0) >= 4 and not s.startswith("#") and not re.match(r"\d+[.)]", s) \
           and not CITATION_RE.search(s): continue                                              # running header/footer
        out.append(l)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()

def chunk_markdown(text: str, max_tokens: int = 350):
    """Split on headings, then paragraphs. Each chunk carries its heading path."""
    chunks, path, buf = [], [], []
    def flush():
        body = "\n\n".join(buf).strip()
        if body: chunks.append({"heading": " > ".join(path), "text": body})
        buf.clear()
    for block in re.split(r"\n\s*\n", text or ""):
        h = re.match(r"(#{1,6})\s+(.*)", block.strip())
        if h:
            flush(); level = len(h.group(1)); path[:] = path[: level - 1] + [h.group(2).strip()]
            continue
        if buf and count_tokens("\n\n".join(buf + [block])) > max_tokens: flush()
        buf.append(block)
    flush()
    return chunks

def _tok(s): return re.findall(r"[a-z0-9]{2,}", s.lower())
STOP = set("the and for that with this from are was were has have not but any all shall may will can its their there which".split())

def _rank(chunks, query):
    docs = [[t for t in _tok(c["heading"] + " " + c["text"]) if t not in STOP] for c in chunks]
    q = [t for t in _tok(query) if t not in STOP]
    n, avg = len(docs), (sum(map(len, docs)) / max(1, len(docs)))
    df = Counter(t for d in docs for t in set(d))
    scores = []
    for d in docs:
        tf, s = Counter(d), 0.0
        for t in q:
            if t in tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * len(d) / max(1, avg)))
        scores.append(s)
    return scores

def build_context(documents, query, budget_tokens=3000, keep_citations=True):
    """documents: [{'name','markdown'}]. Returns trimmed context plus savings stats."""
    all_chunks = []
    for d in documents:
        for i, c in enumerate(chunk_markdown(normalise_markdown(d.get("markdown", "")))):
            all_chunks.append({**c, "doc": d.get("name", "document"), "order": (len(all_chunks)), "tokens": count_tokens(c["text"]) + 8})
    original = sum(count_tokens(d.get("markdown", "")) for d in documents)
    if not all_chunks:
        return {"context": "", "stats": {"original_tokens": original, "final_tokens": 0, "saved_pct": 0, "chunks_used": 0, "chunks_total": 0}}
    scores = _rank(all_chunks, query)
    for c, s in zip(all_chunks, scores): c["score"] = s
    picked, used = [], 0
    for c in sorted(all_chunks, key=lambda c: -c["score"]):
        if c["score"] <= 0 and picked: break
        if used + c["tokens"] <= budget_tokens: picked.append(c); used += c["tokens"]
    if keep_citations:  # second pass: spend leftover budget on chunks that hold citations
        for c in all_chunks:
            if c not in picked and CITATION_RE.search(c["text"]) and used + c["tokens"] <= budget_tokens:
                picked.append(c); used += c["tokens"]
    picked.sort(key=lambda c: c["order"])
    context = "\n\n".join(f"[{c['doc']} | {c['heading'] or 'Start'}]\n{c['text']}" for c in picked)
    src_cites = {x for d in documents for x in find_citations(d.get("markdown", ""))}
    ctx_cites = set(find_citations(context))
    final = count_tokens(context)
    return {"context": context, "stats": {
        "original_tokens": original, "final_tokens": final, "saved_pct": round(100 * (1 - final / original), 1) if original else 0,
        "chunks_used": len(picked), "chunks_total": len(all_chunks),
        "citations_in_source": len(src_cites), "citations_kept": len(src_cites & ctx_cites),
        "citations_dropped": sorted(src_cites - ctx_cites)[:20]}}

def compress_history(messages, keep_last=6, summariser=None):
    """Keep the latest turns verbatim; replace older ones with a short summary
    (pass summariser(text)->str to use an LLM, otherwise a heuristic digest is used)."""
    if len(messages) <= keep_last: return messages
    old, recent = messages[:-keep_last], messages[-keep_last:]
    text = "\n".join(f"{m['role']}: {m['content']}" for m in old)
    if summariser:
        digest = summariser(text)
    else:
        goals = [m["content"].strip().split("\n")[0][:140] for m in old if m["role"] == "user"]
        cites = find_citations(text)[:10]
        digest = "Earlier user requests: " + "; ".join(goals) + (f". Authorities mentioned: {', '.join(cites)}." if cites else "")
    return [{"role": "user", "content": f"[Summary of {len(old)} earlier messages] {digest}"}] + recent

def prompt_score(prompt: str):
    """Real-time prompt quality meter + tips (the 'Prompt Strength' bar)."""
    p = prompt or ""
    checks = [
        ("purpose", 20, r"\b(draft|review|summari[sz]e|analy[sz]e|research|verify|compare|redline|prepare|write|explain|check|extract)\b", "Say what you want done (draft, review, summarise...)."),
        ("document type", 15, r"\b(notice|agreement|contract|petition|nda|affidavit|opinion|memo|reply|judgment|clause|policy|lease|deed)\b", "Name the document type."),
        ("jurisdiction", 20, r"\b(india|indian|delhi|mumbai|uttar pradesh|high court|supreme court|state of|act,? ?\d{4}|\bUK\b|\bUS\b|singapore)\b", "Add the jurisdiction or governing law."),
        ("parties", 15, r"\b(between|party|parties|client|employer|employee|landlord|tenant|buyer|seller|company|vendor|plaintiff|defendant|petitioner|respondent)\b", "Say who the parties are."),
        ("specifics", 15, r"(\d|₹|rs\.?|inr|\$|days?|months?|years?)", "Add specifics: amounts, dates, time limits."),
        ("format/constraints", 15, r"\b(format|tone|formal|short|concise|table|bullet|numbered|clauses?|pages?|words?|style)\b", "State the tone, format or length you want."),
    ]
    score, tips = 0, []
    for _, w, pat, tip in checks:
        if re.search(pat, p, re.I): score += w
        else: tips.append(tip)
    words = len(p.split())
    if words < 8: score = min(score, 40); tips.insert(0, "Write at least a full sentence of instructions.")
    return {"score": min(100, score), "words": words, "tips": tips[:4],
            "label": "Strong" if score >= 70 else "Fair" if score >= 40 else "Weak"}
