"""
Reference-style adaptation.

Reads a reference document (an earlier draft, a firm template) and measures HOW it is written:
tone, obligation verbs, numbering, heading style, defined terms, recurring phrases and a short sample.
The result becomes a plain-English style guide that is added to a drafting prompt. It copies style, not facts:
the guide tells the model to keep the user's facts and meaning and never to reuse names, amounts or dates from the reference.
No model is called here, so it is fast, free and testable.
"""
from __future__ import annotations

import re
from collections import Counter

FORMAL_MARKERS = ["hereby", "hereinafter", "whereas", "witnesseth", "notwithstanding", "thereof", "herein", "hereto",
                  "aforesaid", "pursuant to", "inter alia", "forthwith", "in witness whereof", "without prejudice"]
OPENERS = [r"this agreement is made", r"this (deed|agreement|contract) of", r"whereas", r"know all men", r"to whom it may concern",
           r"under instructions from", r"i, .{3,60}, (aged|son|daughter|do hereby)", r"dear (sir|madam|sirs)"]
CLOSERS = [r"in witness whereof", r"yours (faithfully|sincerely)", r"verified (at|that)", r"thanking you", r"signed and delivered"]


def _sentences(text: str) -> list:
    return [s for s in re.split(r"(?<=[.;:])\s+|\n+", text) if len(s.split()) >= 3]


def _headings(text: str) -> list:
    out = []
    for line in text.split("\n"):
        t = line.strip().lstrip("#").strip()
        if not t or len(t) > 80 or len(t.split()) > 9 or t.endswith((",", ";", ".")):
            continue
        numbered = re.match(r"^(\d+(\.\d+)*[.)]|\(?[a-z]\)|[IVX]+\.|Article\s+\w+|Clause\s+\w+)\s+\S", t, re.I) and len(t.split()) <= 7
        upper = t.isupper() and len(t) > 3
        if line.lstrip().startswith("#") or upper or numbered:
            out.append(t)
    return out[:25]


def _numbering(text: str) -> str:
    c = Counter()
    for line in text.split("\n"):
        s = line.strip()
        if re.match(r"^\d+\.\d+(\.\d+)?\s", s): c["decimal sub-clauses (1.1, 1.2)"] += 1
        elif re.match(r"^\d+[.)]\s", s): c["numbered clauses (1., 2.)"] += 1
        elif re.match(r"^\([a-z]\)\s", s): c["lettered sub-paragraphs ((a), (b))"] += 1
        elif re.match(r"^\([ivx]+\)\s", s, re.I): c["roman sub-paragraphs ((i), (ii))"] += 1
        elif re.match(r"^(article|clause|section)\s+\w+", s, re.I): c["article/clause headings"] += 1
    return ", ".join(k for k, _ in c.most_common(3)) or "unnumbered paragraphs"


def _defined_terms(text: str) -> list:
    terms = re.findall(r"[\"“]([A-Z][A-Za-z ]{2,30})[\"”]", text)
    seen, out = set(), []
    for t in terms:
        if t not in seen:
            seen.add(t); out.append(t)
    return out[:15]


def _phrases(text: str, patterns: list) -> list:
    low = text.lower()
    out = []
    for p in patterns:
        m = re.search(p, low)
        if m:
            out.append(text[m.start():m.end()].strip())
    return out


def _sample(text: str, limit: int = 900) -> str:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if 120 < len(p.strip()) < 700]
    if not paras:
        return text.strip()[:limit]
    best = max(paras, key=lambda p: sum(p.lower().count(m) for m in FORMAL_MARKERS) + p.lower().count("shall"))
    return best[:limit]


def analyze(text: str) -> dict:
    text = (text or "").replace("\r\n", "\n").strip()
    words = text.split()
    if len(words) < 40:
        return {"ok": False, "error": "The reference is too short to learn a style from (need about 40 words)."}
    low = text.lower()
    n = max(len(words), 1)
    sents = _sentences(text)
    avg = round(sum(len(s.split()) for s in sents) / max(len(sents), 1), 1)
    markers = {m: low.count(m) for m in FORMAL_MARKERS if low.count(m)}
    modals = {m: len(re.findall(rf"\b{m}\b", low)) for m in ("shall", "will", "must", "may")}
    modal_main = max(("shall", "will", "must"), key=lambda m: modals[m]) if any(modals[m] for m in ("shall", "will", "must")) else None
    contractions = len(re.findall(r"\b\w+'(t|s|re|ve|ll|d)\b", low))
    first_person = len(re.findall(r"\b(i|we|my|our)\b", low))
    formality = sum(markers.values()) * 1000 / n + modals["shall"] * 400 / n - contractions * 600 / n - first_person * 150 / n
    tone = "highly formal, traditional legal" if formality > 12 else "formal" if formality > 4 else "plain, modern"
    heads = _headings(text)
    upper = sum(h.isupper() for h in heads)
    head_case = "ALL CAPS" if heads and upper / len(heads) > 0.6 else "Title Case or sentence case"
    profile = {
        "ok": True, "words": len(words), "tone": tone, "avg_sentence_words": avg,
        "obligation_verb": modal_main, "modal_counts": modals,
        "formal_markers": dict(sorted(markers.items(), key=lambda kv: -kv[1])[:8]),
        "numbering": _numbering(text), "heading_case": head_case, "headings": heads,
        "defined_terms": _defined_terms(text),
        "openers": _phrases(text, OPENERS), "closers": _phrases(text, CLOSERS),
        "sample": _sample(text),
    }
    profile["guide"] = guide_from(profile)
    return profile


def guide_from(p: dict) -> str:
    lines = [f"Tone: {p['tone']}. Average sentence length about {p['avg_sentence_words']} words."]
    if p.get("obligation_verb"):
        lines.append(f"Express obligations with \"{p['obligation_verb']}\" consistently.")
    if p.get("formal_markers"):
        lines.append("Use this formal vocabulary where natural: " + ", ".join(p["formal_markers"]) + ".")
    lines.append(f"Numbering: {p['numbering']}. Headings: {p['heading_case']}.")
    if p.get("headings"):
        lines.append("Typical headings in the reference: " + "; ".join(p["headings"][:10]) + ".")
    if p.get("defined_terms"):
        lines.append("Define terms in quotation marks with a capital letter, as the reference does, e.g. " + ", ".join(f"\"{t}\"" for t in p["defined_terms"][:6]) + ".")
    if p.get("openers"):
        lines.append("Opening pattern: " + "; ".join(p["openers"]) + ".")
    if p.get("closers"):
        lines.append("Closing pattern: " + "; ".join(p["closers"]) + ".")
    lines.append("Sample paragraph showing the clause style (imitate its wording style only):\n" + p["sample"])
    lines.append("IMPORTANT: copy the style only. Keep the user's own facts, parties, amounts, dates and legal meaning. "
                 "Never reuse names, amounts, dates or case details from the reference.")
    return "\n".join("- " + l if not l.startswith("IMPORTANT") else l for l in lines)


try:
    import importlib.util
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
    from doc_convert import ConvertError, MAX_BYTES, convert_bytes

    router = APIRouter(prefix="/style", tags=["style"])

    class TextIn(BaseModel):
        text: str

    @router.post("/analyze")
    def analyze_text(body: TextIn):
        r = analyze(body.text)
        if not r["ok"]:
            raise HTTPException(422, r["error"])
        return r

    if importlib.util.find_spec("multipart") or importlib.util.find_spec("python_multipart"):
        from fastapi import File, UploadFile

        @router.post("/profile")
        async def profile_from_file(file: UploadFile = File(...)):
            data = await file.read(MAX_BYTES + 1)
            try:
                conv = convert_bytes(file.filename or "", data)
            except ConvertError as e:
                raise HTTPException(422, str(e))
            r = analyze(conv["markdown"])
            if not r["ok"]:
                raise HTTPException(422, r["error"])
            r["filename"] = conv["filename"]
            return r
except ImportError:
    router = None
