"""
Contract Intelligence (Member 3): Smart Redlining, Contract Comparison, Deadline & Obligation Tracker.

Everything here is deterministic text analysis. No AI model is used, so nothing can be invented:
every item points back to the exact words of the contract it came from. A lawyer must still review.

Mount:
    from contract_intel import router as contract_router
    app.include_router(contract_router)

Routes (all POST, JSON):
    /contract/redline    {old, new}                    -> clause-by-clause changes with word-level diff
    /contract/compare    {a, b}                        -> key terms side by side
    /contract/deadlines  {text, start_date?, today?}   -> dates, relative deadlines, obligations
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from typing import Optional
from difflib import SequenceMatcher

MAX_CHARS = 200_000

# ----------------------------------------------------------------------------
# Shared helpers: numbers, money, durations, percentages
# ----------------------------------------------------------------------------
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTHS["sept"] = 9

NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
    "thirty": 30, "forty-five": 45, "forty five": 45, "sixty": 60, "ninety": 90,
}
_WORDS_RE = "|".join(sorted((re.escape(w) for w in NUM_WORDS), key=len, reverse=True))

_DURATION = re.compile(
    r"\b(?:(?P<num>\d+)|(?P<word>" + _WORDS_RE + r"))(?:\s*\((?P<paren>\d+)\))?[\s-]+"
    r"(?P<kind>business\s+|working\s+|calendar\s+)?(?P<unit>day|week|month|year)s?\b", re.I)

_MONEY = re.compile(
    r"(?:(?P<cur>₹|Rs\.?|INR|USD|\$)\s?(?P<amt>\d[\d,]*(?:\.\d+)?)(?:\s*(?P<mult>lakhs?|lacs?|crores?|cr|million|thousand)\b)?"
    r"|(?P<amt2>\d[\d,]*(?:\.\d+)?)\s*(?P<mult2>LPA|lakhs?|lacs?|crores?)\b)", re.I)
_MULT = {"lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "lpa": 1e5, "crore": 1e7, "crores": 1e7,
         "cr": 1e7, "million": 1e6, "thousand": 1e3}

_PERCENT = re.compile(r"\b(?P<p>\d+(?:\.\d+)?)\s?(?:%|per\s?cent\b|percent\b)", re.I)


def _duration_key(m: re.Match) -> tuple:
    n = int(m.group("paren") or m.group("num") or NUM_WORDS[m.group("word").lower()])
    return ("duration", n, m.group("unit").lower(), (m.group("kind") or "").strip().lower())


def values_in(text: str, kinds=("money", "duration", "percent")) -> list[dict]:
    """Money, durations and percentages found in `text`, each with a canonical key for comparison."""
    out: list[tuple[int, dict]] = []
    taken: list[tuple[int, int]] = []

    def free(m):  # do not report a number twice (e.g. the amount inside "Rs. 5 lakh")
        return not any(m.start() < e and m.end() > s for s, e in taken)

    if "money" in kinds:
        for m in _MONEY.finditer(text):
            amt = float((m.group("amt") or m.group("amt2")).replace(",", "").rstrip("."))
            mult = (m.group("mult") or m.group("mult2") or "").lower()
            val = amt * _MULT.get(mult, 1)
            cur = (m.group("cur") or "INR").upper().replace("RS.", "INR").replace("RS", "INR").replace("₹", "INR")
            if cur == "$":
                cur = "USD"
            out.append((m.start(), {"kind": "money", "text": m.group(0).strip(), "key": ("money", cur, round(val))}))
            taken.append((m.start(), m.end()))
    if "duration" in kinds:
        for m in _DURATION.finditer(text):
            if free(m):
                out.append((m.start(), {"kind": "duration", "text": m.group(0).strip(), "key": _duration_key(m)}))
                taken.append((m.start(), m.end()))
    if "percent" in kinds:
        for m in _PERCENT.finditer(text):
            if free(m):
                out.append((m.start(), {"kind": "percent", "text": m.group(0).strip(), "key": ("percent", float(m.group("p")))}))
    out.sort(key=lambda t: t[0])
    return [v for _, v in out]


_ABBREV = ("Rs", "No", "Nos", "Mr", "Mrs", "Ms", "Dr", "M/s", "St", "vs", "v", "Inc", "Ltd", "Pvt", "Co",
           "Art", "Sec", "Cl", "approx", "etc", "i.e", "e.g")
_SPLIT = re.compile(r"(?<=[.;])" + "".join(r"(?<!\b%s\.)" % re.escape(x) for x in _ABBREV) + r"\s+(?=[A-Z0-9(])")
_LEAD_NUM = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.)]?|\([a-zA-Z0-9]{1,4}\)|[A-Z][.)])\s+")


def _sentences(text: str) -> list[str]:
    """Sentences, without cutting at 'Rs. 5,000' or 'No. 7', and with 'Salary.' headings joined to their clause."""
    parts: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = _LEAD_NUM.sub("", line.strip(), count=1) if _LEAD_NUM.match(line) else line.strip()
        if line:
            parts += _SPLIT.split(line)
    out: list[str] = []
    carry = ""
    for p in (re.sub(r"\s+", " ", x).strip() for x in parts):
        if len(p) <= 3:
            continue
        if len(p.split()) <= 3 and p.endswith(".") and not carry:
            carry = p + " "          # a heading such as "Governing Law."
            continue
        out.append(carry + p)
        carry = ""
    if carry:
        out.append(carry.strip())
    return out


def _clip(text: str | None) -> str:
    return (text or "")[:MAX_CHARS]


# ----------------------------------------------------------------------------
# 1. Smart Redlining
# ----------------------------------------------------------------------------
_NUMBERED = re.compile(
    r"^\s*(?:\d+(?:\.\d+)+\.?|\d+[.)]|\([a-zA-Z0-9]{1,4}\)|[A-Z][.)]|(?:Article|Section|Clause)\s+\d+)\s+", re.I)

# What a change is "about". High-risk topics are flagged for legal review when they change.
TOPICS = [
    ("Notice period", r"\bnotice\b", True),
    ("Termination", r"terminat", True),
    ("Salary / payment", r"salary|remuneration|compensation|\bCTC\b|\bfees?\b|\brent\b|payable|\bpayment", True),
    ("Non-compete", r"non-?compete|shall not,?\s*(?:directly or indirectly,?\s*)?(?:compete|engage)|restrain", True),
    ("Penalty / interest", r"penalt|liquidated damages|late fee|\binterest\b", True),
    ("Indemnity / liability", r"indemn|liabilit", True),
    ("Governing law / disputes", r"governing law|governed by|jurisdiction|arbitrat", True),
    ("Confidentiality", r"confidential", False),
    ("Probation", r"probation", False),
    ("Leave", r"\bleave\b", False),
    ("Security deposit", r"\bdeposit\b", False),
]


def split_clauses(text: str) -> list[str]:
    """Split a contract into clauses: blank-line blocks, then numbered lines (1., 1.1, (a), Clause 3)."""
    out: list[str] = []
    for block in re.split(r"\n\s*\n", _clip(text).replace("\r\n", "\n")):
        cur: list[str] = []
        for line in block.split("\n"):
            if not line.strip():
                continue
            if cur and _NUMBERED.match(line):
                out.append(" ".join(cur))
                cur = []
            cur.append(line.strip())
        if cur:
            out.append(" ".join(cur))
    return [re.sub(r"\s+", " ", c).strip() for c in out if c.strip()]


def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def _tok_key(w: str) -> str:
    return w.lower().strip(".,;:()\"'")


def word_diff(old: str, new: str) -> list[dict]:
    """[{op: equal|delete|insert, text}] at word level. Punctuation-only changes are ignored."""
    a, b = old.split(), new.split()
    sm = SequenceMatcher(None, [_tok_key(w) for w in a], [_tok_key(w) for w in b], autojunk=False)
    segs: list[dict] = []

    def add(op, words):
        if not words:
            return
        text = " ".join(words)
        if segs and segs[-1]["op"] == op:
            segs[-1]["text"] += " " + text
        else:
            segs.append({"op": op, "text": text})

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            add("equal", b[j1:j2])
        else:
            add("delete", a[i1:i2])
            add("insert", b[j1:j2])
    return segs


def _topics(text: str) -> list[tuple[str, bool]]:
    return [(label, risky) for label, pat, risky in TOPICS if re.search(pat, text, re.I)]


def _pairs(segs: list[dict]) -> list[str]:
    """'Delhi → Mumbai', 'adds ...', 'removes ...' from the word diff (short ones only)."""
    out, i = [], 0
    short = lambda t: t if len(t) <= 60 else t[:57] + "..."
    while i < len(segs):
        sg = segs[i]
        if sg["op"] == "delete" and i + 1 < len(segs) and segs[i + 1]["op"] == "insert":
            out.append(f"{short(sg['text'])} → {short(segs[i + 1]['text'])}")
            i += 2
            continue
        if sg["op"] == "delete":
            out.append(f"removes: {short(sg['text'])}")
        elif sg["op"] == "insert":
            out.append(f"adds: {short(sg['text'])}")
        i += 1
    return out[:4]


def _describe(old: str, new: str, segs: list[dict]) -> tuple[list[str], list[str], bool]:
    """Topics touched, plain-English details, and whether this change needs legal review."""
    topics = _topics(old + " " + new)
    label = topics[0][0] if topics else "Clause"
    ov, nv = values_in(old), values_in(new)
    details: list[str] = []
    for kind in ("money", "duration", "percent"):
        a_ = [v for v in ov if v["kind"] == kind]
        b_ = [v for v in nv if v["kind"] == kind]
        for x, y in zip(a_, b_):
            if x["key"] != y["key"]:
                details.append(f"{label}: {x['text']} → {y['text']}")
        details += [f"{label}: adds {y['text']}" for y in b_[len(a_):]]
        details += [f"{label}: removes {x['text']}" for x in a_[len(b_):]]
    if not details:
        details = [f"{label}: {p}" for p in _pairs(segs)]
    review = bool(details) and any(r for _, r in topics)
    return [t for t, _ in topics], details, review


def _change(kind: str, old: str | None, new: str | None) -> dict:
    if kind == "unchanged":
        return {"kind": kind, "old": old, "new": new, "segments": [{"op": "equal", "text": new}],
                "topics": [], "details": [], "review": False}
    if kind == "added":
        t = _topics(new)
        return {"kind": kind, "old": None, "new": new, "segments": [{"op": "insert", "text": new}],
                "topics": [x for x, _ in t],
                "details": [f"New clause added: {t[0][0].lower()}"] if t else [],
                "review": any(r for _, r in t)}
    if kind == "removed":
        t = _topics(old)
        return {"kind": kind, "old": old, "new": None, "segments": [{"op": "delete", "text": old}],
                "topics": [x for x, _ in t],
                "details": [f"Clause removed: {t[0][0].lower()}"] if t else [],
                "review": any(r for _, r in t)}
    po, pn = _LEAD_NUM.match(old), _LEAD_NUM.match(new)     # clause numbers (6. -> 7.) are not a change
    body_o, body_n = old[po.end():] if po else old, new[pn.end():] if pn else new
    segs = word_diff(body_o, body_n)
    if pn:
        segs.insert(0, {"op": "equal", "text": new[:pn.end()].strip()})
        if len(segs) > 1 and segs[1]["op"] == "equal":
            segs[0]["text"] += " " + segs.pop(1)["text"]
    topics, details, review = _describe(body_o, body_n, segs[1:] if pn else segs)
    return {"kind": "modified", "old": old, "new": new, "segments": segs,
            "topics": topics, "details": details, "review": review}


def _pair(olds: list[str], news: list[str]) -> list[dict]:
    """Match leftover old and new clauses by similarity (>= 0.5 means 'same clause, edited')."""
    out, j0 = [], 0
    for o in olds:
        best, bj = 0.0, None
        for j in range(j0, len(news)):
            r = SequenceMatcher(None, _norm(o), _norm(news[j]), autojunk=False).ratio()
            if r > best:
                best, bj = r, j
        if bj is not None and best >= 0.5:
            out += [_change("added", None, news[j]) for j in range(j0, bj)]
            out.append(_change("modified", o, news[bj]))
            j0 = bj + 1
        else:
            out.append(_change("removed", o, None))
    out += [_change("added", None, news[j]) for j in range(j0, len(news))]
    return out


def redline(old: str, new: str) -> dict:
    a, b = split_clauses(old), split_clauses(new)
    sm = SequenceMatcher(None, [_norm(x) for x in a], [_norm(x) for x in b], autojunk=False)
    changes: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            changes += [_change("unchanged", a[i1 + k], b[j1 + k]) for k in range(i2 - i1)]
        elif tag == "delete":
            changes += [_change("removed", x, None) for x in a[i1:i2]]
        elif tag == "insert":
            changes += [_change("added", None, x) for x in b[j1:j2]]
        else:
            changes += _pair(a[i1:i2], b[j1:j2])
    summary = {k: sum(1 for c in changes if c["kind"] == k) for k in ("added", "removed", "modified", "unchanged")}
    summary["review"] = sum(1 for c in changes if c["review"])
    return {"summary": summary, "changes": changes}


# ----------------------------------------------------------------------------
# 2. Contract Comparison (key terms side by side)
# ----------------------------------------------------------------------------
# label, keyword regex, value kinds to extract, flag for review when it differs
COMPARE_TOPICS = [
    ("Salary / compensation", r"salary|remuneration|compensation|\bCTC\b|per annum|\bLPA\b|\bfees?\b|\brent\b", ("money",), True),
    ("Notice period", r"\bnotice\b", ("duration",), True),
    ("Probation", r"probation", ("duration",), False),
    ("Contract term", r"\bterm of (?:this|the)\b|period of (?:this )?(?:agreement|contract|employment)|valid for|shall continue for|fixed term", ("duration",), False),
    ("Termination", r"terminat", ("duration",), True),
    ("Non-compete", r"non-?compete|shall not,?\s*(?:directly or indirectly,?\s*)?(?:compete|engage)|restrain", ("duration",), True),
    ("Confidentiality", r"confidential", (), False),
    ("Penalty / interest", r"penalt|liquidated damages|late fee|\binterest\b", ("percent", "money"), True),
    ("Security deposit", r"security deposit|\bdeposit\b", ("money",), False),
    ("Payment due", r"payable within|due within|paid on or before|within .{0,25}of (?:the )?invoice", ("duration",), False),
    ("Leave", r"\bleave\b", ("duration",), False),
    ("Governing law", r"governed by|governing law", (), True),
    ("Jurisdiction / arbitration", r"jurisdiction|arbitrat", (), True),
    ("Indemnity / liability", r"indemn|limitation of liability|\bliable\b", ("money",), True),
]
_PLACE = {
    "Governing law": re.compile(r"laws? of\s+(?:the\s+)?(?P<p>[A-Z][A-Za-z]+(?:\s[A-Z][A-Za-z]+)?)"),
    "Jurisdiction / arbitration": re.compile(
        r"(?:courts? (?:at|of|in)|seat (?:of arbitration )?(?:is|shall be)(?: at| in)?|arbitration (?:at|in)|jurisdiction of(?: the)?(?: courts)?(?: at| in| of)?)"
        r"\s+(?:the\s+)?(?P<p>[A-Z][A-Za-z]+(?:\s[A-Z][A-Za-z]+)?)"),
}


def _find_term(sentences: list[str], pattern: str, kinds: tuple, place) -> dict | None:
    rx = re.compile(pattern, re.I)
    fallback = None
    for s in sentences:
        if not rx.search(s):
            continue
        vals = values_in(s, kinds) if kinds else []
        if place:
            vals = [{"kind": "place", "text": m.group("p"), "key": ("place", m.group("p").lower())}
                    for m in place.finditer(s)]
        if vals or not (kinds or place):
            return {"quote": s, "values": vals}
        fallback = fallback or {"quote": s, "values": []}
    return fallback


def _status(a: dict | None, b: dict | None) -> str:
    if a and not b:
        return "only_a"
    if b and not a:
        return "only_b"
    ka, kb = [v["key"] for v in a["values"]], [v["key"] for v in b["values"]]
    if ka or kb:
        return "same" if ka == kb else "changed"
    sim = SequenceMatcher(None, _norm(a["quote"]), _norm(b["quote"]), autojunk=False).ratio()
    return "same" if sim >= 0.9 else "changed"


def compare(a_text: str, b_text: str) -> dict:
    sa, sb = _sentences(_clip(a_text)), _sentences(_clip(b_text))
    rows = []
    for label, pat, kinds, risky in COMPARE_TOPICS:
        place = _PLACE.get(label)
        a, b = _find_term(sa, pat, kinds, place), _find_term(sb, pat, kinds, place)
        if not a and not b:
            continue
        st = _status(a, b)
        rows.append({
            "topic": label, "status": st,
            "a": a and {"value": ", ".join(v["text"] for v in a["values"]) or None, "quote": a["quote"]},
            "b": b and {"value": ", ".join(v["text"] for v in b["values"]) or None, "quote": b["quote"]},
            "review": risky and st != "same",
        })
    summary = {k: sum(1 for r in rows if r["status"] == k) for k in ("same", "changed", "only_a", "only_b")}
    summary["review"] = sum(1 for r in rows if r["review"])
    return {"summary": summary, "rows": rows}


# ----------------------------------------------------------------------------
# 3. Deadline & Obligation Tracker
# ----------------------------------------------------------------------------
_DATE_PATTERNS = [
    re.compile(r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?(?P<m>[A-Za-z]{3,9})\.?,?\s+(?P<y>\d{4})\b"),
    re.compile(r"\b(?P<m>[A-Za-z]{3,9})\.?\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<y>\d{4})\b"),
    re.compile(r"\b(?P<d>\d{1,2})[/.-](?P<mn>\d{1,2})[/.-](?P<y>\d{4})\b"),       # DD/MM/YYYY (Indian style)
    re.compile(r"\b(?P<y>\d{4})-(?P<mn>\d{2})-(?P<d>\d{2})\b"),
]
_MODAL = re.compile(r"\b(shall|must|agrees? to|undertakes? to|is required to|are required to|will pay|liable to|obliged to)\b", re.I)
_REL_BEFORE = re.compile(r"(?:within|not later than|no later than|notice(?: period)?(?: of)?(?: at least)?)\s+(?:a period of\s+)?$", re.I)
_REL_AFTER = re.compile(r"(?:'s?)?\s+(?:prior\s+|written\s+|advance\s+)?notice", re.I)


def _relative(sentence: str):
    """First duration used as a time limit. Returns (match, kind): kind is 'notice' for
    "30 days' notice" / "notice of 30 days" (a length of time) or 'deadline' for "within 15 days"."""
    for m in _DURATION.finditer(sentence):
        before = sentence[max(0, m.start() - 40):m.start()]
        b = _REL_BEFORE.search(before)
        if _REL_AFTER.match(sentence[m.end():m.end() + 30]) or (b and "notice" in b.group(0).lower()):
            return m, "notice"
        if b:
            return m, "deadline"
    return None, None


# a trigger like "of joining" is measured from the contract's effective date; "of receipt of invoice" is not
_START_EVENT = re.compile(r"join|effective|commence|execut|signing|signature|date of (?:this )?(?:agreement|contract)|start|begin", re.I)


_RECUR = re.compile(r"\b(monthly|quarterly|annually|yearly|weekly|fortnightly|every\s+(?:month|quarter|year|week)|"
                    r"(?:on or before|by)\s+the\s+\d{1,2}(?:st|nd|rd|th)?\s+(?:day\s+)?of\s+(?:each|every)\s+month)\b", re.I)
_TRIGGER = re.compile(r"\b(?:of|from|after|following|before|prior to|upon)\s+([^,.;]{3,70})", re.I)
_PARTY = re.compile(r"^(?:\d+(?:\.\d+)*[.)]?\s*)?(?:The\s+)?([A-Z][A-Za-z&.' -]{2,40}?)\s+(?:shall|must|agrees?|undertakes?|is required|are required|will|is obliged)\b")
_TYPES = [
    ("Payment", r"\bpay|salary|rent|fee|invoice|instal|remit|reimburs"),
    ("Notice", r"\bnotice\b"),
    ("Renewal / expiry", r"renew|expire|expiry|\bterm\b"),
    ("Termination", r"terminat"),
    ("Delivery / performance", r"deliver|complete|submit|provide|furnish|perform"),
    ("Confidentiality", r"confidential"),
]


def _classify(sentence: str) -> str:
    for label, pat in _TYPES:
        if re.search(pat, sentence, re.I):
            return label
    return "Other"


def _find_dates(sentence: str) -> list[tuple[date, str]]:
    found: list[tuple[date, str]] = []
    spans: list[tuple[int, int]] = []
    for rx in _DATE_PATTERNS:
        for m in rx.finditer(sentence):
            if any(m.start() < e and m.end() > s for s, e in spans):
                continue
            g = m.groupdict()
            try:
                if g.get("m"):
                    mo = MONTHS.get(g["m"].lower().rstrip("."))
                    if not mo:
                        continue
                else:
                    mo = int(g["mn"])
                d, y = int(g["d"]), int(g["y"])
                if mo > 12 and d <= 12:      # 03/25/2026 style: swap
                    d, mo = mo, d
                found.append((date(y, mo, d), m.group(0)))
                spans.append((m.start(), m.end()))
            except ValueError:
                continue
    return found


def _add(start: date, n: int, unit: str) -> date:
    if unit == "day":
        return start + timedelta(days=n)
    if unit == "week":
        return start + timedelta(weeks=n)
    months = n * (12 if unit == "year" else 1)
    idx = start.month - 1 + months
    y, mo = start.year + idx // 12, idx % 12 + 1
    return date(y, mo, min(start.day, calendar.monthrange(y, mo)[1]))


def _parse_date(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def extract_deadlines(text: str, start_date: str | None = None, today: str | None = None) -> dict:
    """Dates, 'within N days' deadlines, recurring duties and plain obligations, each with its source sentence."""
    t0 = _parse_date(today) or date.today()
    start = _parse_date(start_date)
    items: list[dict] = []
    for sent in _sentences(_clip(text)):
        dates = _find_dates(sent)
        rel = None
        dm, rkind = _relative(sent)
        if dm:
            trig = _TRIGGER.search(sent[dm.end():])
            rel = {"amount": _duration_key(dm)[1], "unit": dm.group("unit").lower(), "text": dm.group(0).strip(),
                   "trigger": trig.group(0).strip() if trig else None, "kind": rkind}
        rec = _RECUR.search(sent)
        modal = _MODAL.search(sent)
        if not (dates or rel or rec or modal):
            continue
        pm = _PARTY.match(sent)
        item = {
            "type": _classify(sent),
            "party": pm.group(1).strip() if pm else None,
            "text": sent,
            "date": None, "date_text": None,
            "relative": rel,
            "recurring": rec.group(0) if rec else None,
            "has_deadline": bool(dates or rel or rec),
            "is_obligation": bool(modal),
            "due_from_start": False,
            "days_left": None, "status": "undated",
        }
        if dates:
            item["date"], item["date_text"] = dates[0][0].isoformat(), dates[0][1]
        elif rel and start and rel["kind"] == "deadline" and (not rel["trigger"] or _START_EVENT.search(rel["trigger"])):
            item["date"] = _add(start, rel["amount"], rel["unit"]).isoformat()
            item["due_from_start"] = True
        if item["date"]:
            days = (date.fromisoformat(item["date"]) - t0).days
            item["days_left"] = days
            item["status"] = "overdue" if days < 0 else "due_soon" if days <= 30 else "upcoming"
        elif rel and rel["kind"] == "notice":
            item["status"] = "notice_period"          # a length of time, not a calendar date
        elif rel and not start:
            item["status"] = "needs_start_date"
        elif rel:
            item["status"] = "event_based"            # runs from an event (e.g. receipt of invoice)
        elif rec:
            item["status"] = "recurring"
        items.append(item)

    order = {"overdue": 0, "due_soon": 1, "upcoming": 2, "needs_start_date": 3, "event_based": 4,
             "notice_period": 5, "recurring": 6, "undated": 7}
    items.sort(key=lambda i: (order[i["status"]], i["date"] or "9999"))
    items = items[:100]
    for n, it in enumerate(items, 1):
        it["id"] = n
    summary = {k: sum(1 for i in items if i["status"] == k) for k in order}
    summary["total"] = len(items)
    return {"today": t0.isoformat(), "start_date": start.isoformat() if start else None,
            "summary": summary, "items": items}


# ----------------------------------------------------------------------------
# FastAPI routes
# ----------------------------------------------------------------------------
try:
    from fastapi import APIRouter
    from pydantic import BaseModel, Field

    router = APIRouter()

    class RedlineReq(BaseModel):
        old: str = Field(..., max_length=MAX_CHARS)
        new: str = Field(..., max_length=MAX_CHARS)

    class CompareReq(BaseModel):
        a: str = Field(..., max_length=MAX_CHARS)
        b: str = Field(..., max_length=MAX_CHARS)

    class DeadlineReq(BaseModel):
        text: str = Field(..., max_length=MAX_CHARS)
        start_date: Optional[str] = None  # effective date (YYYY-MM-DD): turns "within 30 days" into a due date
        today: Optional[str] = None       # for tests/demos; defaults to the server's date

    @router.post("/contract/redline")
    def redline_endpoint(req: RedlineReq):
        return redline(req.old, req.new)

    @router.post("/contract/compare")
    def compare_endpoint(req: CompareReq):
        return compare(req.a, req.b)

    @router.post("/contract/deadlines")
    def deadlines_endpoint(req: DeadlineReq):
        return extract_deadlines(req.text, req.start_date, req.today)
except ImportError:
    router = None
