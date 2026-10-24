"""
Citation verification module for DraftMate / Legal Drafting Studio.

Pipeline:
  draft text -> extract_citations() -> verify_citation() per item -> VerificationReport

Status meanings (match the PS):
  verified           - found in an external legal source AND key details match
  partially_verified - found something close, but some detail differs (year, court, name)
  unverified         - nothing found; never invent an authority

Sources are pluggable adapters. Order of lookup:
  1. LOCAL_CACHE  (pre-fetched demo data, works offline, guarantees a clean demo)
  2. IndianKanoonSource (needs INDIANKANOON_API_TOKEN env var)
"""
from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass, field, asdict
from difflib import SequenceMatcher
from typing import Callable, Protocol

import requests

# ----------------------------------------------------------------------------
# 1. Data models
# ----------------------------------------------------------------------------

@dataclass
class Citation:
    raw: str                    # exact text found in the draft
    kind: str                   # "case" | "statute"
    name: str | None = None     # e.g. "Kesavananda Bharati v. State of Kerala"
    year: str | None = None
    reporter: str | None = None  # e.g. "AIR", "SCC", "SCR"
    court: str | None = None
    section: str | None = None   # for statutes
    act: str | None = None
    span: tuple[int, int] = (0, 0)  # char offsets so the UI can highlight


@dataclass
class SourceHit:
    title: str
    url: str
    year: str | None = None
    court: str | None = None
    snippet: str = ""


@dataclass
class Verdict:
    citation: Citation
    status: str                  # verified | partially_verified | unverified
    score: float                 # 0..1 confidence
    reasons: list[str] = field(default_factory=list)
    source: SourceHit | None = None
    # For partial matches: what the closest real authority says, and (when safe) a one-click fix.
    # {"message": str, "replace_with": str | None, "source_url": str}
    suggestion: dict | None = None


# ----------------------------------------------------------------------------
# 2. Extraction (regex first; cheap, deterministic, explainable)
#    Optional: add an LLM pass for citations regex misses.
# ----------------------------------------------------------------------------

PARTY = r"[A-Z][A-Za-z0-9&.'\-]*(?:\s+(?:[A-Z][A-Za-z0-9&.'\-]*|of|and|the|for|vs?\.?))*"
V = r"(?:v\.?|vs\.?|versus)"

# "Kesavananda Bharati v. State of Kerala (1973) 4 SCC 225" / "... AIR 1973 SC 1461"
CASE_WITH_CITE = re.compile(
    rf"(?P<name>{PARTY}\s+{V}\s+{PARTY})\s*,?\s*"
    r"(?:\(\s*(?P<y1>\d{4})\s*\)\s*\d+\s*(?P<rep1>SCC|SCR|SCALE)\s*\d+"
    r"|(?P<rep2>AIR)\s*(?P<y2>\d{4})\s*(?P<ct>SC|[A-Z]{2,4})\s*\d+"
    r"|\(\s*(?P<y3>\d{4})\s*\)\s*\d+\s*(?P<rep3>SCC\s*OnLine\s*[A-Za-z]+)\s*\d+)"
)

# Bare case name, no reporter: "Maneka Gandhi v. Union of India"
CASE_NAME_ONLY = re.compile(rf"(?P<name>{PARTY}\s+{V}\s+{PARTY})")

# "Section 138 of the Negotiable Instruments Act, 1881"  /  "Sec. 420 IPC"
STATUTE = re.compile(
    r"(?:Section|Sec\.?|S\.|Article|Art\.?)\s*(?P<sec>\d+[A-Za-z]?(?:\(\d+\))?)"
    r"\s*(?:of\s+(?:the\s+)?)?"
    r"(?P<act>(?:[A-Z][A-Za-z&]*\s+){1,8}(?:Act|Code|Constitution)(?:,?\s*(?P<yr>\d{4}))?|IPC|CrPC|CPC|BNS|BNSS|BSA)",
)


LEADING_NOISE = {"see", "also", "cf", "vide", "per", "in", "and", "but", "however",
                 "compare", "reliance", "held", "as", "thus", "hence", "further",
                 "refer", "relied", "rely", "note", "noted", "accordingly", "similarly",
                 "therefore", "moreover", "furthermore", "additionally", "finally", "here",
                 "then", "now", "following", "followed", "applying", "citing", "cited",
                 "recall", "consider", "considering", "examine", "observe", "observed"}


# Short forms that end in a full stop but do NOT end a sentence ("Mohd. Ahmed Khan", "Pvt. Ltd.")
ABBREV = {"mohd", "smt", "shri", "shrimati", "messrs", "prof", "govt", "addl", "dept", "corpn",
          "assn", "secy", "commr", "ltd", "pvt", "bros", "engg", "mfg", "co", "anr", "ors",
          "dr", "mr", "mrs", "ms", "sri", "md", "inc", "no", "vs", "ltd"}


def _is_sentence_end(word: str, nxt: str | None) -> bool:
    if not word.endswith(".") or not nxt or not nxt[:1].isupper():
        return False
    if re.fullmatch(r"(?:[A-Za-z]\.)+", word):          # initials: K.S.  U.O.I.
        return False
    stem = word.rstrip(".")
    return len(stem) >= 3 and stem.lower() not in ABBREV


def _clean_name(name: str) -> str:
    """Trim sentence words stuck to a case name: a lead-in ('See Maneka Gandhi v. ...'),
    the end of the PREVIOUS sentence ('...of India. Refer X v. Y'), or the start of the NEXT."""
    parts = re.split(rf"\s+({V})\s+", name.strip(), maxsplit=1)
    if len(parts) == 3:
        left, sep, right = parts
    else:
        left, sep, right = name, None, ""
    lw, rw = left.split(), right.split()
    cuts = [i for i in range(len(lw) - 1) if _is_sentence_end(lw[i], lw[i + 1])]
    if cuts:                                              # keep text after the LAST sentence break
        lw = lw[cuts[-1] + 1:]
    for i in range(len(rw) - 1):                          # keep text before the FIRST break
        if _is_sentence_end(rw[i], rw[i + 1]):
            rw = rw[:i + 1]
            break
    if rw and rw[-1].endswith(".") and not re.fullmatch(r"(?:[A-Za-z]\.)+", rw[-1]) \
            and rw[-1].rstrip(".").lower() not in ABBREV:
        rw[-1] = rw[-1].rstrip(".")                        # trailing full stop of the sentence
    while len(lw) >= 2 and lw[0].lower().strip(".,:;") in LEADING_NOISE:
        lw.pop(0)
    return " ".join(lw) if sep is None else f"{' '.join(lw)} {sep} {' '.join(rw)}"


def _locate(m: re.Match, name: str, keep_tail: bool) -> tuple[int, int]:
    """Span of the cleaned name inside the regex match (so highlights are exact)."""
    s, e = m.span()
    pat = r"\s+".join(re.escape(w) for w in name.split())
    mm = re.search(pat, m.group(0))
    if not mm:
        return s, e
    return s + mm.start(), (e if keep_tail else s + mm.end())


# "Article 21 of the Constitution of India" / "Article 19(1)(a) of the Constitution"
ARTICLE = re.compile(
    r"Article\s+(?P<sec>\d+[A-Z]?(?:\(\d+\))?(?:\([a-z]\))?)\s+of\s+the\s+Constitution(?:\s+of\s+India)?"
)


def extract_citations(text: str) -> list[Citation]:
    found: list[Citation] = []
    taken: list[tuple[int, int]] = []

    def overlaps(a: int, b: int) -> bool:
        return any(not (b <= s or a >= e) for s, e in taken)

    for m in CASE_WITH_CITE.finditer(text):
        year = m.group("y1") or m.group("y2") or m.group("y3")
        rep = m.group("rep1") or m.group("rep2") or m.group("rep3")
        name = _clean_name(m.group("name").strip())
        span = _locate(m, name, keep_tail=True)          # keeps the reporter citation
        found.append(Citation(
            raw=text[span[0]:span[1]].strip(), kind="case", name=name,
            year=year, reporter=rep, court="SC" if m.group("ct") == "SC" or rep in ("SCC", "SCR") else m.group("ct"),
            span=span,
        ))
        taken.append(span)

    for m in CASE_NAME_ONLY.finditer(text):
        name = _clean_name(m.group("name").strip())
        span = _locate(m, name, keep_tail=False)         # name only, no neighbouring sentences
        if overlaps(*span):
            continue
        found.append(Citation(raw=text[span[0]:span[1]].strip(), kind="case", name=name, span=span))
        taken.append(span)

    for m in ARTICLE.finditer(text):
        if overlaps(*m.span()):
            continue
        found.append(Citation(raw=m.group(0).strip(), kind="statute", section=m.group("sec"),
                              act="Constitution of India", span=m.span()))
        taken.append(m.span())

    for m in STATUTE.finditer(text):
        if overlaps(*m.span()):
            continue
        found.append(Citation(
            raw=m.group(0).strip(), kind="statute", section=m.group("sec"),
            act=m.group("act").strip(), year=m.group("yr"), span=m.span(),
        ))
        taken.append(m.span())

    return sorted(found, key=lambda c: c.span[0])


# ----------------------------------------------------------------------------
# 3. Sources
# ----------------------------------------------------------------------------

class Source(Protocol):
    def search(self, c: Citation) -> list[SourceHit]: ...


class LocalCacheSource:
    """Pre-fetched hits stored in a JSON file. Guarantees demo works offline.

    File format: [{"title": ..., "url": ..., "year": ..., "court": ..., "snippet": ...}, ...]
    Build it by running real Indian Kanoon searches for the cases in your demo draft.
    """
    def __init__(self, path: str = "legal_cache.json"):
        self.entries: list[SourceHit] = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.entries = [SourceHit(**e) for e in json.load(f)]

    def search(self, c: Citation) -> list[SourceHit]:
        if c.kind == "case" and c.name:
            return [h for h in self.entries if _name_sim(c.name, h.title) >= 0.55]
        if c.kind == "statute" and c.act:
            return [h for h in self.entries if _name_sim(c.act, h.title) >= 0.55]
        return []


class IndianKanoonSource:
    """Official API: https://api.indiankanoon.org/documentation/
    Auth header: 'Authorization: Token <token>'. Search is a POST to /search/.
    Paid per call (small), signup gives trial credit. Token via INDIANKANOON_API_TOKEN.
    """
    BASE = "https://api.indiankanoon.org"

    def __init__(self, token: str | None = None, timeout: int = 15):
        self.token = token or os.getenv("INDIANKANOON_API_TOKEN")
        self.timeout = timeout

    def search(self, c: Citation) -> list[SourceHit]:
        if not self.token:
            return []
        # Try the precise query first; only fall back (a 2nd paid call) if it finds nothing.
        for q in self._queries(c):
            docs = self._call(q)
            if docs:
                return [self._to_hit(d) for d in docs[:8]]
        return []

    @staticmethod
    def _queries(c: Citation) -> list[str]:
        if c.kind == "case" and c.name:
            toks = [t for t in _norm(c.name).split() if t not in PARTY_STOPWORDS and len(t) > 1]
            qs = []
            if toks:
                qs.append("title: " + " ".join(toks[:4]))   # title filter = fewer noisy hits
            qs.append(f'"{c.name}"')
            return qs
        if c.kind == "statute" and c.act and c.section:
            act = re.sub(r",?\s*\d{4}$", "", c.act)          # drop trailing year
            w = _provision_word(c)
            return [f"{w} {c.section} {act} doctypes: laws",
                    f"{act} {w} {c.section}"]
        return []

    def _call(self, query: str) -> list[dict]:
        try:
            r = requests.post(
                f"{self.BASE}/search/",
                params={"formInput": query, "pagenum": 0},
                headers={"Authorization": f"Token {self.token}"},
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json().get("docs", [])
        except (requests.RequestException, ValueError):
            return []   # network failure => unverified, never a fake pass

    @staticmethod
    def _to_hit(d: dict) -> SourceHit:
        clean = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s or ""))
        title = clean(d.get("title"))
        return SourceHit(
            title=title,
            url=f"https://indiankanoon.org/doc/{d.get('tid')}/",
            year=_year_from(title) or _year_from(d.get("docsource", "")),
            court=d.get("docsource"),
            snippet=clean(d.get("headline"))[:300],
        )


# ----------------------------------------------------------------------------
# 4. Scoring
# ----------------------------------------------------------------------------

def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\b(vs?\.?|versus)\b", "v", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\b(the|of|and|on|its)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


PARTY_STOPWORDS = {"v", "state", "union", "india", "ors", "anr", "another", "others", "vs",
                   "pvt", "ltd", "limited", "co", "company", "in", "for", "by", "to", "a"}


def _name_sim(a: str, b: str) -> float:
    """a = name from the draft, b = title from the source.
    Real titles are longer ('Kesavananda Bharati Sripadagalvaru ... vs State Of Kerala And Anr
    on 24 April, 1973'), so plain string ratio fails. We use the share of the draft's
    words that appear in the title, and demand the key (non-generic) words all match.
    """
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    ratio = SequenceMatcher(None, a, b).ratio()
    contain = 1.0 if a in b or b in a else 0.0
    # initials ("K.S.", "U.O.I") are written differently everywhere, so ignore 1-letter tokens
    ta = {t for t in a.split() if len(t) > 1}
    tb = {t for t in b.split() if len(t) > 1}
    if not ta:
        return 0.0
    coverage = len(ta & tb) / len(ta)
    key = {t for t in ta if t not in PARTY_STOPWORDS}
    key_cov = len(key & tb) / len(key) if key else coverage
    # distinctive words decide; generic words ('union', 'india') only nudge the score
    token_score = 0.95 * key_cov * (0.85 + 0.15 * coverage)
    if key_cov < 0.5:
        return 0.0       # titles sharing only generic words ("India", "Union") never count
    return max(ratio, 0.9 * contain, token_score)


def _provision_word(c: Citation) -> str:
    """Constitution has 'Articles'; Acts and Codes have 'Sections'."""
    return "article" if c.act and "constitution" in c.act.lower() else "section"


def _year_from(s: str | None) -> str | None:
    m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", s or "")
    return m.group(1) if m else None


def verify_citation(c: Citation, sources: list[Source]) -> Verdict:
    best: tuple[float, SourceHit, list[str], str | None, float] | None = None

    for src in sources:
        for hit in src.search(c):
            key = c.name if c.kind == "case" else (c.act or "")
            sim = _name_sim(key, hit.title)
            reasons = [f"name similarity {sim:.2f} with '{hit.title}'"]
            score = sim
            flag: str | None = None       # why this match is not perfect (drives the suggestion)

            if c.kind == "case" and c.year:
                if hit.year and hit.year == c.year:
                    reasons.append(f"year {c.year} matches")
                    score = min(1.0, score + 0.1)
                elif hit.year:
                    reasons.append(f"year mismatch: draft says {c.year}, source says {hit.year}")
                    score -= 0.25
                    flag = "year_mismatch"
                else:
                    reasons.append("source gave no year to compare")
                    score -= 0.05
            elif c.kind == "case":
                reasons.append("draft gave no year, so only the name could be checked")
                score -= 0.1
                flag = "no_year"

            if c.kind == "statute" and c.section:
                w = _provision_word(c)
                if re.search(rf"\b{w}\s+{re.escape(c.section)}\b", hit.title, re.I):
                    reasons.append(f"{w} {c.section} found in source title")
                    score = min(1.0, score + 0.1)
                else:
                    reasons.append(f"Act found but {w} {c.section} not confirmed in title")
                    score -= 0.2
                    flag = "section_unconfirmed"

            if best is None or score > best[0]:
                best = (score, hit, reasons, flag, sim)
        if best and best[0] >= 0.85:
            break  # good enough, skip slower/paid sources

    if best is None:
        return Verdict(c, "unverified", 0.0,
                       ["no matching authority found in any accessible source; do not rely on it"])

    score, hit, reasons, flag, sim = best
    score = max(0.0, min(1.0, score))
    if score >= 0.85:
        status = "verified"
    elif score >= 0.55:
        status = "partially_verified"
    else:
        status = "unverified"
    suggestion = _suggest(c, hit, flag, sim) if status == "partially_verified" else None
    return Verdict(c, status, round(score, 2), reasons, hit if status != "unverified" else None,
                   suggestion)


def _suggest(c: Citation, hit: SourceHit, flag: str | None, sim: float) -> dict:
    """Turn a partial match into advice. A text replacement is offered ONLY when the case name
    clearly matches and the year is the single problem; everything else is advice to a human."""
    url = hit.url
    if flag == "year_mismatch" and c.kind == "case" and sim >= 0.8 and c.year and hit.year:
        fixed = c.raw.replace(c.year, hit.year, 1) if c.year in c.raw else None
        return {
            "message": (f"The case exists, but the source dates it {hit.year}, not {c.year}. "
                        f"Closest authority: {hit.title}. Check the reporter reference too."),
            "replace_with": fixed,
            "source_url": url,
        }
    if flag == "no_year":
        return {"message": f"Found a likely match: {hit.title}. Add the year and reporter citation "
                           f"so the authority can be fully confirmed.",
                "replace_with": None, "source_url": url}
    if flag == "section_unconfirmed":
        w = _provision_word(c)
        return {"message": f"The Act was found, but {w} {c.section} could not be confirmed from "
                           f"the source. Open the source and check the provision number.",
                "replace_with": None, "source_url": url}
    return {"message": f"Closest match found: {hit.title}. Please check it against your draft.",
            "replace_with": None, "source_url": url}


# ----------------------------------------------------------------------------
# 5. Report + entry point
# ----------------------------------------------------------------------------

#
# LLM extraction pass (optional). The LLM only FINDS citations; it never judges them.
# Every item must quote the draft word-for-word, or it is thrown away, so the model
# cannot add authorities that are not in the text.
#
Completer = Callable[[str], str]      # any function: prompt in, model text out

EXTRACT_PROMPT = """You are a citation finder for Indian legal drafts. Find EVERY legal authority \
cited in the text: court cases (with or without a reporter citation) and statutory provisions \
(sections, articles, rules, orders).

Rules:
- Do NOT judge whether a citation is correct or real. Only report what the text contains.
- "quote" must be copied EXACTLY, character for character, from the text.
- Never invent or complete a citation. Use null for anything the text does not say.
- Return ONLY a JSON array, no other text. Each item:
  {"quote": str, "kind": "case" or "statute", "name": str or null, "year": str or null,
   "reporter": str or null, "act": str or null, "section": str or null}
  For a case, "name" is the parties ("A v. B"). For a statute, "act" is the Act/Code/Constitution
  and "section" is the section/article/rule number.

TEXT:
\"\"\"
{chunk}
\"\"\"
"""


def anthropic_completer(model: str = "claude-sonnet-5-5", api_key: str | None = None,
                        timeout: int = 40) -> Completer | None:
    """Ready-made completer for Claude. Returns None if no key, so the app still runs
    on regex alone. To use another LLM, pass any function(prompt) -> str instead."""
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None

    def complete(prompt: str) -> str:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": model, "max_tokens": 3000,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=timeout,
        )
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))
    return complete


def _parse_json_list(raw: str) -> list[dict]:
    raw = re.sub(r"```(?:json)?", "", raw or "").strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(raw[start:end + 1])
    except ValueError:
        return []
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


def _chunks(text: str, size: int = 6000) -> list[str]:
    out, cur = [], ""
    for para in text.split("\n"):
        if len(cur) + len(para) > size and cur:
            out.append(cur)
            cur = ""
        cur += para + "\n"
    if cur.strip():
        out.append(cur)
    return out


def _s(v) -> str | None:
    return v.strip() if isinstance(v, str) and v.strip() else None


def llm_extract(text: str, completer: Completer) -> list[Citation]:
    found: dict[tuple[int, int], Citation] = {}
    for chunk in _chunks(text):
        try:
            raw = completer(EXTRACT_PROMPT.replace("{chunk}", chunk))
        except Exception:
            continue                      # LLM down or slow: regex results still work
        for d in _parse_json_list(raw):
            quote, kind = _s(d.get("quote")), d.get("kind")
            if not quote or kind not in ("case", "statute"):
                continue
            pos = text.find(quote)
            if pos == -1:
                continue                  # not word-for-word in the draft => dropped
            span = (pos, pos + len(quote))
            qlow = quote.lower()
            year, section = _s(d.get("year")), _s(d.get("section"))
            year = year if year and year in quote else None        # must appear in the quote
            section = section if section and section.lower() in qlow else None
            name, act = _s(d.get("name")), _s(d.get("act"))
            if kind == "case":
                if not name:
                    continue
                keys = [t for t in _norm(name).split() if t not in PARTY_STOPWORDS and len(t) > 2]
                if not keys or not all(t in _norm(quote) for t in keys):
                    continue              # name words not in the quote => model invented them
                found[span] = Citation(raw=quote, kind="case", name=_clean_name(name), year=year,
                                       reporter=_s(d.get("reporter")), span=span)
            else:
                if not act:
                    continue
                found[span] = Citation(raw=quote, kind="statute", act=act, section=section,
                                       year=year, span=span)
    return list(found.values())


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return not (a[1] <= b[0] or a[0] >= b[1])


def extract_citations_hybrid(text: str, completer: Completer | None = None) -> list[Citation]:
    """Regex first (fast, free, deterministic), then the LLM fills the gaps."""
    merged = extract_citations(text)
    if completer is None:
        return merged
    for new in llm_extract(text, completer):
        old = next((c for c in merged if _overlap(c.span, new.span)), None)
        if old is None:
            merged.append(new)
        elif old.kind == new.kind == "case":      # enrich e.g. a bare name with its year
            old.year = old.year or new.year
            old.reporter = old.reporter or new.reporter
            # the LLM often finds the true start of the name better than regex does
            if new.name and old.name and new.name != old.name and new.name in old.name:
                old.name = new.name
    return sorted(merged, key=lambda c: c.span[0])


def verify_draft(text: str, sources: list[Source] | None = None,
                 completer: Completer | None = None) -> dict:
    sources = sources or [LocalCacheSource(), IndianKanoonSource()]
    verdicts = [verify_citation(c, sources) for c in extract_citations_hybrid(text, completer)]
    summary = {"verified": 0, "partially_verified": 0, "unverified": 0}
    for v in verdicts:
        summary[v.status] += 1
    return {"summary": summary, "items": [asdict(v) for v in verdicts]}


# ----------------------------------------------------------------------------
# 6. FastAPI route (mount in your backend)
# ----------------------------------------------------------------------------
try:
    from fastapi import APIRouter
    from pydantic import BaseModel

    router = APIRouter()

    class VerifyRequest(BaseModel):
        text: str

    @router.post("/verify")
    def verify_endpoint(req: VerifyRequest):
        return verify_draft(req.text, completer=anthropic_completer())
except ImportError:
    router = None
