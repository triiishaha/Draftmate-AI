"""Voice command understanding. The browser does speech-to-text; this module turns the transcript
into an action the drafting workspace can run, and requires spoken confirmation for risky ones.
Swap in OpenWhispr / Whisper for transcription later without touching this file."""
import re, time, uuid
import skills_registry as registry

NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
STYLES = "formal|concise|shorter|simpler|simple|persuasive|polite|firm|professional|neutral|longer"
YES = re.compile(r"^(yes|yeah|yep|confirm(ed)?|go ahead|do it|proceed|sure|ok(ay)?|haan|ha)\b")
NO = re.compile(r"^(no|nope|cancel|stop|don'?t|never mind|nahi|nahin)\b")
TTL = 120  # seconds a pending confirmation stays valid
_pending = {}   # session_id -> action
_dictating = set()

def _num(s):
    s = s.lower(); return int(s) if s.isdigit() else NUM.get(s)

def _result(intent, status="ok", feedback="", params=None, confirm=False, **kw):
    return {"intent": intent, "status": status, "feedback": feedback, "params": params or {}, "requires_confirmation": confirm, **kw}

def _needs_confirm(session_id, intent, params, prompt):
    pid = uuid.uuid4().hex[:8]
    _pending[session_id] = {"id": pid, "intent": intent, "params": params, "expires": time.time() + TTL}
    return _result(intent, "awaiting_confirmation", prompt + " Say yes to confirm or no to cancel.", params, True, pending_id=pid)

def confirm(session_id, accept: bool):
    p = _pending.pop(session_id, None)
    if not p or p["expires"] < time.time():
        return _result("none", "error", "There is nothing waiting for confirmation.")
    if not accept:
        return _result(p["intent"], "cancelled", "Cancelled. Nothing was changed.", p["params"])
    return _result(p["intent"], "confirmed", "Done.", p["params"])

def parse(session_id: str, transcript: str):
    raw = (transcript or "").strip()
    t = re.sub(r"[.,!?]+$", "", raw.lower()).strip()
    if not t:
        return _result("none", "error", "I did not catch that. Please try again.")

    p = _pending.get(session_id)
    if p and p["expires"] < time.time():
        _pending.pop(session_id, None); p = None
    if p:  # a destructive action is waiting: only yes/no is accepted
        if YES.match(t): return confirm(session_id, True)
        if NO.match(t): return confirm(session_id, False)
        return _result(p["intent"], "awaiting_confirmation", "Please say yes to confirm or no to cancel.", p["params"], True, pending_id=p["id"])

    if session_id in _dictating:
        if re.search(r"\b(stop|end|finish)\s+dictat", t):
            _dictating.discard(session_id); return _result("stop_dictation", "ok", "Dictation stopped.")
        return _result("dictate_text", "ok", "", {"text": raw})
    if re.search(r"\b(start|begin)\s+dictat|\bdictate\b", t):
        _dictating.add(session_id)
        return _result("start_dictation", "ok", "Dictation on. Say stop dictation when you are done.")

    if re.search(r"\b(overwrite|start over|discard (the )?(draft|document))\b|replace the (whole|entire) (document|draft)", t):
        return _needs_confirm(session_id, "overwrite_document", {}, "This will overwrite the current document.")
    m = re.search(r"\b(delete|remove|erase|clear)\b\s*(the\s+)?(entire |whole |all )?(document|draft|everything|paragraph|section|clause)\s*(\w+)?", t)
    if m:
        target = m.group(4); n = _num(m.group(5) or "") if target in ("paragraph", "section", "clause") else None
        label = f"{target} {n}" if n else target
        return _needs_confirm(session_id, "delete", {"target": target, "number": n}, f"This will delete the {label}.")

    m = re.search(r"replace\s+(.+?)\s+with\s+(.+)", raw, re.I)
    if m: return _result("replace_text", "ok", f"Replacing {m.group(1)} with {m.group(2)}.", {"find": m.group(1).strip(), "replace": m.group(2).strip()})
    m = re.search(rf"\bmake\s+(?:it|this|the\s+[\w\s]+?)\s+(?:more\s+)?({STYLES})", t)
    if m: return _result("rewrite", "ok", f"Rewriting to be more {m.group(1)}.", {"style": m.group(1), "scope": "selection"})
    m = re.search(r"\b(rewrite|redo|improve|redraft)\s+(paragraph|clause|section)\s+(\w+)", t)
    if m: return _result("rewrite", "ok", f"Rewriting {m.group(2)} {m.group(3)}.", {"scope": m.group(2), "number": _num(m.group(3))})
    m = re.match(r"(add|insert|include)\s+(.+)", raw, re.I)
    if m: return _result("insert", "ok", "Adding that to the draft.", {"instruction": m.group(2).strip()})

    m = re.search(r"\b(export|download|save)\b.*?\b(pdf|word|docx|markdown|md)\b", t)
    if m:
        fmt = {"word": "docx", "md": "markdown"}.get(m.group(2), m.group(2))
        return _result("export", "ok", f"Exporting as {fmt}.", {"format": fmt})
    if re.search(r"\b(verify|check|validate)\b.*\b(citation|citations|authorit|references)\b", t):
        return _result("verify_citations", "ok", "Opening the verification panel and checking citations.")
    if re.search(r"\bread\b.*\b(back|aloud|draft|document)\b", t): return _result("read_aloud", "ok", "Reading the draft.")
    if re.search(r"\bundo\b", t): return _result("undo", "ok", "Undoing the last change.")

    m = re.match(r"(?:use|open|activate|start|run|switch to|select|launch)\s+(?:the\s+)?(.+?)(?:\s+(?:skill|mode))?$", t)
    if m:
        r = registry.route(m.group(1))
        if r["skill"]:
            return _result("activate_skill", "ok", f"Activating {r['skill']['name']}.", {"skill_id": r["skill"]["id"], "skill_name": r["skill"]["name"]}, alternatives=r["alternatives"])
    r = registry.route(t)
    if r["skill"] and r["confidence"] >= 0.5:
        return _result("activate_skill", "ok", f"Using {r['skill']['name']}.", {"skill_id": r["skill"]["id"], "skill_name": r["skill"]["name"], "instruction": raw}, alternatives=r["alternatives"])
    return _result("instruction", "ok", "Sending that to the drafting assistant.", {"instruction": raw})
