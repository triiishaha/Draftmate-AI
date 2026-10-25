import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def call_llm(system: str, user: str, model: Optional[str] = None,
             max_tokens: int = 2000) -> str:
    provider = os.getenv("LLM_PROVIDER", "anthropic")
    model = model if model and model != "default" else os.getenv("LLM_MODEL")

    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic()
        r = client.messages.create(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return r.content[0].text

    if provider == "openai":
        from openai import OpenAI
        client = OpenAI()
        r = client.chat.completions.create(
            model=model, max_completion_tokens=max_tokens,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],            
        )
        return r.choices[0].message.content

    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")