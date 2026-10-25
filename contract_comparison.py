"""Smart redlining + key-term comparison between two contract versions."""
import difflib
import re
from contract_analysis import split_clauses, analyze_risks

KEY_TERMS = {
    "Salary / fees": r"(?:salary|ctc|compensation|remuneration|fees?|consideration)[^.\n]{0,80}?((?:₹|rs\.?|inr|\$)\s?[\d,]+(?:\.\d+)?(?:\s?(?:lakhs?|lpa|crores?|per (?:month|annum|year)))?)",
    "Notice period": r"((?:\d{1,3})\s*(?:\(\w+\)\s*)?(?:business |working )?(?:days?|weeks?|months?))['’]?\s*(?:prior |written )?notice|notice period[^.\n]{0,40}?(\d{1,3}\s*(?:days?|weeks?|months?))",
    "Probation": r"probation[^.\n]{0,60}?(\d{1,2}\s*(?:days?|weeks?|months?))",
    "Non-compete": r"(non-?compete[^.\n]{0,120})",
    "Termination": r"(terminat\w+[^.\n]{0,120})",
    "Governing law": r"governed by (?:the )?laws? of ([A-Za-z ]{3,40})",
    "Working hours": r"(\d{1,2}\s*hours?\s*(?:per|a|each)\s*(?:day|week))",
    "Leave": r"(\d{1,2}\s*days?[^.\n]{0,20}(?:leave|vacation))",
    "Renewal": r"((?:auto(?:matic(?:ally)?)?[- ]?renew\w*)[^.\n]{0,80})",
}

def extract_terms(text):
    out = {}
    for name, pat in KEY_TERMS.items():
        m = re.search(pat, text or "", re.I)
        if m:
            out[name] = next((g for g in m.groups() if g), m.group(0)).strip()
    return out

def compare_terms(a, b):
    ta, tb = extract_terms(a), extract_terms(b)
    rows = []
    for name in KEY_TERMS:
        va, vb = ta.get(name), tb.get(name)
        if va is None and vb is None:
            continue
        status = "same" if va and vb and va.lower() == vb.lower() else "added" if vb and not va else "removed" if va and not vb else "changed"
        rows.append({"term": name, "a": va, "b": vb, "status": status})
    return rows

def _word_diff(x, y):
    xs, ys = x.split(), y.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, xs, ys).get_opcodes():
        if op == "equal":
            out.append({"op": "equal", "t": " ".join(xs[i1:i2])})
        else:
            if i2 > i1: out.append({"op": "delete", "t": " ".join(xs[i1:i2])})
            if j2 > j1: out.append({"op": "insert", "t": " ".join(ys[j1:j2])})
    return out

def redline(a, b):
    ca, cb = split_clauses(a), split_clauses(b)
    changes, stats = [], {"added": 0, "removed": 0, "changed": 0, "unchanged": 0}
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ca, cb, autojunk=False).get_opcodes():
        if op == "equal":
            stats["unchanged"] += i2 - i1
            continue
        if op == "replace" and (i2 - i1) == (j2 - j1):
            for x, y in zip(ca[i1:i2], cb[j1:j2]):
                changes.append({"type": "changed", "a": x, "b": y, "words": _word_diff(x, y)})
                stats["changed"] += 1
            continue
        for x in ca[i1:i2]:
            changes.append({"type": "removed", "a": x, "b": None, "words": [{"op": "delete", "t": x}]}); stats["removed"] += 1
        for y in cb[j1:j2]:
            changes.append({"type": "added", "a": None, "b": y, "words": [{"op": "insert", "t": y}]}); stats["added"] += 1
    # flag changed/added clauses that trip a risk rule in the new version
    for ch in changes:
        if ch["b"]:
            r = analyze_risks(ch["b"])["flags"]
            ch["review"] = [{"title": f["title"], "severity": f["severity"], "why": f["why"]} for f in r]
        else:
            ch["review"] = []
    return {"stats": stats, "changes": changes, "terms": compare_terms(a, b),
            "needs_review": sum(1 for c in changes if c["review"])}
