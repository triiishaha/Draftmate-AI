"""Model adapter. Tiers: Gemini (default, uses GEMINI_API_KEY via ai_service with retry/fallback),
plus Claude Quick/Balanced/Advanced and GPT-4o when those keys are set. Without any key it
returns a dry run (the assembled prompt) so the UI can be demoed offline."""
import os

TIERS = {}
if os.environ.get("GEMINI_API_KEY"):
    TIERS["gemini"] = {"provider": "gemini", "model": (os.environ.get("GEMINI_MODELS") or "gemini-3.8-flash").split(",")[0].strip(), "label": "Gemini"}
if os.environ.get("ANTHROPIC_API_KEY"):
    TIERS["quick"] = {"provider": "anthropic", "model": os.environ.get("MODEL_QUICK", "claude-haiku-5-5"), "label": "Claude Quick"}
    TIERS["balanced"] = {"provider": "anthropic", "model": os.environ.get("MODEL_BALANCED", "claude-sonnet-5-5"), "label": "Claude Balanced"}
    TIERS["advanced"] = {"provider": "anthropic", "model": os.environ.get("MODEL_ADVANCED", "claude-opus-5-5"), "label": "Claude Advanced"}
if os.environ.get("OPENAI_API_KEY"):
    TIERS["openai"] = {"provider": "openai", "model": os.environ.get("MODEL_OPENAI", "gpt-4o"), "label": "GPT-4o"}
if not TIERS:
    TIERS["gemini"] = {"provider": "gemini", "model": "gemini-3.8-flash", "label": "Gemini (no key set: dry run)"}


def list_models():
    return [{"id": k, "label": v["label"], "model": v["model"]} for k, v in TIERS.items()]


def _default_tier():
    return next(iter(TIERS))


def complete(system: str, user: str, tier: str = "gemini", max_tokens: int = 2000):
    t = TIERS.get(tier) or TIERS[_default_tier()]
    try:
        if t["provider"] == "gemini" and os.environ.get("GEMINI_API_KEY"):
            from ai_service import _generate          # retries overloads, falls back to other flash models
            text = _generate(system + "\n\n" + user)
            return {"text": text, "model": t["model"], "dry_run": False}
        if t["provider"] == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic
            r = anthropic.Anthropic().messages.create(model=t["model"], max_tokens=max_tokens, system=system,
                                                      messages=[{"role": "user", "content": user}])
            return {"text": "".join(b.text for b in r.content if b.type == "text"), "model": t["model"], "dry_run": False,
                    "usage": {"input": r.usage.input_tokens, "output": r.usage.output_tokens}}
        if t["provider"] == "openai" and os.environ.get("OPENAI_API_KEY"):
            from openai import OpenAI
            r = OpenAI().chat.completions.create(model=t["model"], max_tokens=max_tokens,
                                                 messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
            return {"text": r.choices[0].message.content, "model": t["model"], "dry_run": False,
                    "usage": {"input": r.usage.prompt_tokens, "output": r.usage.completion_tokens}}
    except Exception as e:  # network/auth/model errors should not crash the API
        return {"text": "", "model": t["model"], "dry_run": True, "error": str(e)}
    return {"text": "(Dry run: set GEMINI_API_KEY to get a real draft.)\n\n--- SYSTEM ---\n" + system + "\n\n--- USER ---\n" + user,
            "model": t["model"], "dry_run": True}
