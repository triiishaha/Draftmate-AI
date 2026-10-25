"""
Context and token optimisation (no AI, no network).

Goal from the problem statement: send the model less text while keeping what matters legally.
Steps:
  1. clean     - normalise whitespace, drop repeated page headers/footers and bare page numbers, drop exact duplicate paragraphs
  2. split     - cut into sections at headings or clause numbers (keeps clause numbering and structure)
  3. select    - keep the sections that best match the task (query), plus sections holding citations, within a token budget
  4. report    - tokens before/after, which sections were kept or left out, and how many citations survived

Token counts are ESTIMATES (about 4 characters per token). Real model tokenisers differ a little.
Nothing is rewritten or summarised: kept text is the original wording, in the original order.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Optional

MAX_CHARS = 2_000_000
SECTION_TARGET_CHARS = 1200

STOP = set("""a an the and or of to in on for with by at from as is are was were be been being this that these those it its
shall will may must should can could would not no any all each such under upon into than then there their they them his her
he she we our you your i if but so do does did has have had which who whom whose what when where how about between within""".split())

HEADING = re.compile(
    r"^(?:#{1,6}\s+\S.*"                                        # markdown heading
    r"|(?:ARTICLE|Article|CLAUSE|Clause|SECTION|Section|SCHEDULE|Schedule|PART|Part)\s+[IVXLC\d]+[.:)]?\s*.*"
    r"|\d{1,2}(?:\.\d{1,2})*[.)]\s+[A-Z][^\n]{0,80}"            # 1. Termination   /  2.1 Payment
    r"|[A-Z][A-Z &/,\-]{3,60})$"                                # ALL CAPS HEADING
)
# Same as HEADING but without the ALL CAPS rule: an unnumbered ALL CAPS line that repeats on many pages is a page header, not a heading.
HEADING_STRICT = re.compile(HEADING.pattern.replace(r'|[A-Z][A-Z &/,\-]{3,60})$', ')$'))
PAGE_NO = re.compile(r"^\s*(?:page\s+)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?\s*$", re.I)
CITATION = re.compile(
    r"(?:\bAIR\s+\d{4}\s+[A-Z.]+\s+\d+|\(\d{4}\)\s*\d+\s*SCC\s*\d+|\b\d{4}\s+SCC\s+OnLine\s+[A-Za-z]+\s+\d+"
    r"|\b\d{4}\s*\(\d+\)\s*SCC\s*\d+|\bSCC\s+\d+|\b[Ss]ection\s+\d+[A-Za-z]?(?:\(\d+\))?(?:\s+of\s+the\s+[A-Z][A-Za-z ,]+?Act(?:,?\s*\d{4})?)?"
    r"|\b[Aa]rticle\s+\d+[A-Za-z]?\b|\b[A-Z][A-Za-z ]+ Act,?\s+\d{4})"
)
SIGNALS = re.compile(r"\b(shall|must|terminat\w*|liab\w*|indemn\w*|penalt\w*|damages|notice|payment|fee|governing law|jurisdiction|arbitrat\w*|confiden\w*)\b|Rs\.?\s?[\d,]+|\d+\s*(?:days?|months?|years?)", re.I)


def est_tokens(text: str) -> int:
    """Rough token estimate: about 4 characters or 0.75 words per token, whichever is larger."""
    if not text:
        return 0
    return max(math.ceil(len(text) / 4), math.ceil(len(text.split()) * 1.33))


def _words(s: str) -> list:
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 1]


# ------------------------------------------------------------------ 1. clean
def clean(text: str) -> tuple:
    steps = []
    t = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "").replace("\f", "\n\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    lines = t.split("\n")

    counts = Counter(l.strip() for l in lines if 3 <= len(l.strip()) <= 80)
    repeated = {l for l, n in counts.items() if n >= 3 and not HEADING_STRICT.match(l) and not re.match(r"^\s*(?:[-*]|\d+[.)])\s", l)}
    kept, dropped_repeat, dropped_pages = [], 0, 0
    for l in lines:
        s = l.strip()
        if s in repeated:
            dropped_repeat += 1
            continue
        if s and PAGE_NO.match(s) and len(lines) > 30:
            dropped_pages += 1
            continue
        kept.append(l)
    if dropped_repeat:
        steps.append(f"Removed {dropped_repeat} repeated header/footer lines")
    if dropped_pages:
        steps.append(f"Removed {dropped_pages} bare page numbers")
    t = "\n".join(kept)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()

    paras, seen, dup = [], set(), 0
    for p in re.split(r"\n\s*\n", t):
        key = " ".join(p.split()).lower()
        if len(key) > 40 and key in seen:
            dup += 1
            continue
        seen.add(key)
        paras.append(p.strip())
    if dup:
        steps.append(f"Removed {dup} duplicate paragraphs")
    return "\n\n".join(p for p in paras if p), steps


# ------------------------------------------------------------------ 2. split
def split_sections(text: str) -> list:
    blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
    sections, cur_title, cur = [], "", []

    def flush():
        nonlocal cur, cur_title
        if cur:
            body = "\n\n".join(cur)
            sections.append({"title": cur_title or " ".join(body.split())[:50], "text": body})
        cur, cur_title = [], ""

    for b in blocks:
        first = b.strip().split("\n", 1)[0].strip()
        is_head = bool(HEADING.match(first))
        size = sum(len(x) for x in cur)
        if is_head or size + len(b) > SECTION_TARGET_CHARS * 2:
            if is_head or size >= SECTION_TARGET_CHARS:
                flush()
            if is_head and not cur_title:
                cur_title = first.lstrip("# ").strip()[:80]
        cur.append(b.strip())
    flush()
    for i, s in enumerate(sections):
        s["id"] = i + 1
        s["tokens"] = est_tokens(s["text"])
    return sections


# ------------------------------------------------------------------ 3. select
def _score(sections: list, query: str) -> list:
    q = set(_words(query)) if query else set()
    n = len(sections)
    df = Counter()
    toks = []
    for s in sections:
        w = _words(s["title"] + " " + s["text"])
        toks.append(w)
        df.update(set(w))
    out = []
    for i, (s, w) in enumerate(zip(sections, toks)):
        tf = Counter(w)
        length = max(len(w), 1)
        if q:
            sc = 0.0
            for term in q:
                if tf[term]:
                    idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
                    sc += idf * (tf[term] * 2.2) / (tf[term] + 1.2 * (0.25 + 0.75 * length / 120))
                if term in _words(s["title"]):
                    sc += 1.5
        else:
            sc = min(len(SIGNALS.findall(s["text"])), 12) / 3.0
        if CITATION.search(s["text"]):
            sc += 0.8                              # never let authorities fall out first
        if i == 0:
            sc += 0.6                              # parties / preamble
        out.append(sc)
    return out


def _truncate(text: str, budget: int) -> str:
    """Cut text to about `budget` tokens at a sentence boundary (hard cut only if one sentence is too long)."""
    out, used = [], 0
    for sent in re.split(r"(?<=[.!?])\s+", text):
        t = est_tokens(sent)
        if used + t > budget:
            break
        out.append(sent)
        used += t
    if not out:
        out = [text[: max(budget * 4 - 8, 0)].rstrip()]
    return " ".join(out).strip() + " [...]"


def select(sections: list, query: str, budget: int) -> tuple:
    scores = _score(sections, query)
    order = sorted(range(len(sections)), key=lambda i: (-scores[i], i))
    keep, used = set(), 0
    for i in order:
        t = sections[i]["tokens"]
        if used + t <= budget:
            keep.add(i)
            used += t
    if not keep and sections:                      # budget smaller than any one section: keep the best one, cut to fit later
        keep.add(order[0])
    return keep, scores


# ------------------------------------------------------------------ 4. report
def optimize(text: str, query: str = "", max_tokens: int = 4000, outline: bool = True) -> dict:
    text = text or ""
    if not text.strip():
        raise ValueError("The text is empty.")
    if len(text) > MAX_CHARS:
        raise ValueError(f"The text is too long (max {MAX_CHARS} characters).")
    max_tokens = max(100, min(int(max_tokens), 200_000))
    original = est_tokens(text)
    cleaned, steps = clean(text)
    cleaned_tokens = est_tokens(cleaned)
    secs = split_sections(cleaned)

    cites_all = [m.group(0).strip() for m in CITATION.finditer(cleaned)]
    cites_unique = list(dict.fromkeys(cites_all))

    if cleaned_tokens <= max_tokens:
        keep = set(range(len(secs)))
        scores = _score(secs, query)
        steps.append("Fits in the budget, so no sections were left out")
    else:
        reserve = 60 if outline else 0
        keep, scores = select(secs, query, max_tokens - reserve)
        steps.append(f"Kept {len(keep)} of {len(secs)} sections that best match the task, within {max_tokens} tokens")

    cut = {}
    if cleaned_tokens > max_tokens and len(keep) == 1:
        only = next(iter(keep))
        room = max_tokens - (60 if outline else 0)
        if secs[only]["tokens"] > room:
            cut[only] = _truncate(secs[only]["text"], max(room, 20))
            steps.append(f"Section {secs[only]['id']} is longer than the budget, so it was cut at a sentence boundary")

    def assemble(with_outline: bool) -> str:
        parts, run = [], []

        def flush():
            if run:
                plural = "s" if len(run) > 1 else ""
                if with_outline:
                    names = "; ".join(f"{x['id']}. {x['title']}" for x in run[:6]) + (" …" if len(run) > 6 else "")
                    parts.append(f"[Omitted {len(run)} section{plural}: {names}]")
                else:
                    parts.append(f"[Omitted {len(run)} section{plural}]")
                run.clear()

        for i, sec in enumerate(secs):
            if i in keep:
                flush()
                parts.append(cut.get(i, sec["text"]))
            else:
                run.append(sec)
        flush()
        return "\n\n".join(parts)

    final_text = assemble(outline)
    if outline and est_tokens(final_text) > max_tokens:      # the list of omitted titles must not break the budget
        final_text = assemble(False)
    final = est_tokens(final_text)
    kept_cites = [c for c in cites_unique if c in final_text]

    return {
        "text": final_text,
        "original_tokens": original,
        "cleaned_tokens": cleaned_tokens,
        "final_tokens": final,
        "saved_tokens": max(original - final, 0),
        "saved_pct": round(100 * max(original - final, 0) / original) if original else 0,
        "budget": max_tokens,
        "within_budget": final <= max_tokens,
        "query_terms": sorted(set(_words(query))) if query else [],
        "sections": [{"id": s["id"], "title": s["title"], "tokens": s["tokens"], "kept": i in keep,
                      "cut": i in cut, "score": round(scores[i], 2)} for i, s in enumerate(secs)],
        "citations": {"total": len(cites_unique), "kept": len(kept_cites),
                      "lost": [c for c in cites_unique if c not in final_text][:20]},
        "steps": steps,
        "note": "Token counts are estimates. Kept text is the original wording in the original order; nothing is rewritten.",
    }


try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field

    router = APIRouter(prefix="/context")

    class OptReq(BaseModel):
        text: str = Field(..., max_length=MAX_CHARS)
        query: Optional[str] = Field("", max_length=1000)
        max_tokens: int = Field(4000, ge=100, le=200_000)
        outline: bool = True

    @router.post("/optimize")
    def optimize_endpoint(req: OptReq):
        try:
            return optimize(req.text, req.query or "", req.max_tokens, req.outline)
        except ValueError as e:
            raise HTTPException(422, str(e))
except ImportError:
    router = None
