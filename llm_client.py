"""Thin model adapter: Quick / Balanced / Advanced tiers. Works without an API key in dry-run mode
(returns the assembled prompt) so the UI and pipeline can be demoed offline."""
import os

TIERS = {
    "quick": {"provider": "anthropic", "model": os.environ.get("MODEL_QUICK", "claude-haiku-5-5"), "label": "Quick"},
    "balanced": {"provider": "anthropic", "model": os.environ.get("MODEL_BALANCED", "claude-sonnet-5-5"), "label": "Balanced"},
    "advanced": {"provider": "anthropic", "model": os.environ.get("MODEL_ADVANCED", "claude-opus-5-5"), "label": "Advanced"},
}
if os.environ.get("OPENAI_API_KEY"):
    TIERS["openai"] = {"provider": "openai", "model": os.environ.get("MODEL_OPENAI", "gpt-4o"), "label": "GPT-4o"}

def list_models():
    return [{"id": k, "label": v["label"], "model": v["model"]} for k, v in TIERS.items()]

def complete(system: str, user: str, tier: str = "balanced", max_tokens: int = 2000):
    t = TIERS.get(tier, TIERS["balanced"])
    try:
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
    return {"text": "(Dry run: set ANTHROPIC_API_KEY to get a real draft.)\n\n--- SYSTEM ---\n" + system + "\n\n--- USER ---\n" + user,
            "model": t["model"], "dry_run": True}
