# Drafting Engine

Takes a request, picks a legal skill, and returns a draft with a change summary and warnings.

## How to call it

```python
from drafting_engine.models import DraftRequest
from drafting_engine.engine import run_skill

result = run_skill(DraftRequest(
    skill_id="legal_notice",
    instruction="Draft a legal notice for non-payment of rent",
    inputs={
        "sender": "Ramesh Kumar, landlord",
        "recipient": "Suresh Verma, tenant",
        "facts": "Rent unpaid for 3 months.",
        "relief_sought": "Pay dues within 15 days.",
    },
))
print(result.draft_md)
```

## Request fields (DraftRequest)

| Field | Meaning |
|---|---|
| skill_id | Which skill to run |
| instruction | The user's text or voice instruction |
| inputs | Details the skill needs (see the skill's required list) |
| source_text | An existing document to edit or review |
| reference_text | A sample document to copy the style from |
| context_chunks | Relevant excerpts supplied by the context module |
| model | Model name, or "default" |

## Result fields (DraftResult)

| Field | Meaning |
|---|---|
| draft_md | The draft in Markdown, with [[cite:n]] citation markers |
| changes | List of changes made (used by edit skills) |
| warnings | Things to check, such as [VERIFY] flags |
| missing_inputs | Required details the user has not given yet |

If `missing_inputs` is not empty, ask the user for those details and call again.

## Skills available

| skill_id | Needs |
|---|---|
| legal_notice | sender, recipient, facts, relief_sought |
| agreement_drafting | agreement_type, party_one, party_two, key_terms |
| contract_review | review_perspective, plus source_text |
| revise_draft | change_request, plus source_text |
| summarise_document | source_text only |

List them in code with `from drafting_engine.skill_loader import load_skills`.

## Dry-run mode

If the environment variable `LLM_MODEL` is not set, no AI model is called.
The engine returns the assembled prompt instead, so the app can be built and
tested without an API key. Set `LLM_PROVIDER`, `LLM_MODEL` and the provider's
API key in `.env` to get real drafts.

## Adding a skill

Create a new `.yaml` file in `drafting_engine/skills/` with the same fields as
the existing ones. No code changes are needed.