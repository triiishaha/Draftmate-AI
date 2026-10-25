import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai


# Load the API key from the project root or server/.env
PROJECT_DIR = Path(__file__).resolve().parent

load_dotenv(PROJECT_DIR / ".env")
load_dotenv(PROJECT_DIR / "server" / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY not found. Add it to .env or server/.env."
    )

client = genai.Client(api_key=API_KEY)

# Models are tried in order. Set GEMINI_MODELS=a,b,c in .env to change the list.
MODELS = [m.strip() for m in (os.getenv("GEMINI_MODELS") or "gemini-3.8-flash").split(",") if m.strip()]
MODEL_NAME = MODELS[0]


# ---------------------------------------------------------------------------
# Keep trying until Gemini answers (or the deadline passes):
#   overloaded / rate limited / slow -> wait a bit and retry (growing pauses)
#   model not available              -> skip that model for good
#   after the first failed round     -> look up other Gemini "flash" models the key can use
#   wrong or blocked API key         -> stop at once with a clear error
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

ATTEMPT_TIMEOUT = 30       # seconds for one request
DEADLINE = 100             # seconds in total before giving up
_GONE = re.compile(r"404|NOT_FOUND|no longer available", re.I)
_KEY = re.compile(r"API_KEY_INVALID|API key not valid|PERMISSION_DENIED|UNAUTHENTICATED|\b40[13]\b", re.I)
_RETRY = re.compile(r"503|UNAVAILABLE|429|RESOURCE_EXHAUSTED|overload|high demand|did not respond|"
                    r"timed? ?out|connect|ECONN|temporar|\b500\b|INTERNAL|empty response", re.I)
_pool = ThreadPoolExecutor(max_workers=4)


_QUOTA = re.compile(r"exceeded your current quota|RESOURCE_EXHAUSTED|quota", re.I)


def _msg(e):
    return " ".join(str(getattr(e, "message", None) or e).split())


def _discover(known):
    try:
        found = []
        for m in client.models.list():
            name = str(getattr(m, "name", "")).replace("models/", "")
            actions = getattr(m, "supported_actions", None) or []
            if (re.search("flash", name, re.I)
                    and not re.search(r"image|tts|live|audio|embed|vision|robotics|computer|exp\b", name, re.I)
                    and (not actions or "generateContent" in actions)):
                found.append(name)
        stable = [n for n in found if "preview" not in n.lower()]
        preview = [n for n in found if "preview" in n.lower()]
        return [n for n in stable + preview if n not in known][:4]
    except Exception:
        return []


def _once(model, prompt):
    future = _pool.submit(lambda: client.models.generate_content(model=model, contents=prompt))
    try:
        response = future.result(timeout=ATTEMPT_TIMEOUT)
    except FutureTimeout:
        raise RuntimeError(f"{model} did not respond within {ATTEMPT_TIMEOUT} seconds.")
    if not getattr(response, "text", None):
        raise RuntimeError(f"{model} returned an empty response.")
    return response.text.strip()


def _generate(prompt, sleep=time.sleep, deadline=None, base_delay=2, max_delay=15):
    deadline = DEADLINE if deadline is None else deadline
    started = time.time()
    models, dead, failures = list(MODELS), set(), []
    rounds, discovered, quota_rounds = 0, False, 0
    while time.time() - started < deadline:
        any_retryable = False
        failed_now = quota_now = 0
        for model in models:
            if model in dead or time.time() - started >= deadline:
                continue
            try:
                return _once(model, prompt)
            except Exception as e:
                text = _msg(e)
                failures.append(f"{model}: {text[:140]}")
                failed_now += 1
                if _QUOTA.search(text):
                    quota_now += 1
                if _KEY.search(text):
                    raise RuntimeError("Gemini rejected the API key. " + text[:200])
                if _GONE.search(text):
                    dead.add(model)
                elif _RETRY.search(text):
                    any_retryable = True
        # Quota errors do not clear in seconds: stop hammering the key and say so.
        quota_rounds = quota_rounds + 1 if failed_now and quota_now == failed_now else 0
        if quota_rounds >= 2:
            raise RuntimeError("Gemini quota exceeded for this API key. " + " | ".join(failures[-2:]))
        if not discovered:
            discovered = True
            extra = _discover(models)
            models.extend(extra)
            any_retryable = any_retryable or bool(extra)
        if all(m in dead for m in models) or not any_retryable:
            break
        wait = min(base_delay * 2 ** min(rounds, 10), max_delay)
        rounds += 1
        if time.time() - started + wait >= deadline:
            break
        sleep(wait)
    raise RuntimeError("Gemini did not give an answer. " + " | ".join(failures[-4:]))



def generate_document_response(action, context, transcript):
    """Generate an AI response using the retrieved legal document context."""

    document_text = context.get("text", "")

    if action == "summarize_document":
        task = """
        Summarize the legal document in clear, simple language.
        Include the main purpose, important obligations, deadlines,
        payment terms, and potential risks when they appear in the text.
        Do not invent missing information.
        """

    elif action == "explain_clause":
        task = """
        Explain the requested legal clause in simple language.
        Describe what it means, who it affects, and any important
        conditions or consequences explicitly supported by the text.
        If something is unclear, say so.
        """

    elif action == "rewrite_clause":
        task = """
        Rewrite the requested clause in simpler, clearer language.
        Preserve its original meaning, obligations, conditions,
        dates, and amounts. Do not introduce new legal terms or
        change the parties' rights and responsibilities.
        """

    else:
        task = f"""
        Follow the user's instruction using only the provided
        legal-document context.

        User instruction: {transcript}

        If the instruction asks for information not present in the
        document, clearly state that the information is unavailable.
        """

    prompt = f"""
    You are DraftMate AI, an assistant for understanding legal documents.

    IMPORTANT:
    - Use the supplied document text as your source.
    - Do not invent clauses, facts, dates, amounts, or legal provisions.
    - If the supplied context is insufficient, say so clearly.
    - This is informational assistance, not a substitute for a lawyer.

    TASK:
    {task}

    DOCUMENT CONTEXT:
    {document_text}

    Respond in a clear, structured and useful way.
    """

    return _generate(prompt)
