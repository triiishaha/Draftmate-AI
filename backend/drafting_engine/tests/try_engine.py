from drafting_engine.models import DraftRequest
from drafting_engine.engine import run_skill

req = DraftRequest(
    skill_id="legal_notice",
    instruction="Draft a legal notice for non-payment of rent",
    inputs={
        "sender": "Ramesh Kumar, landlord",
        "recipient": "Suresh Verma, tenant",
        "facts": "Rent of Rs 15,000 per month unpaid for 3 months.",
        "relief_sought": "Pay the dues within 15 days.",
    },
)
result = run_skill(req)
print(result.draft_md)
print("WARNINGS:", result.warnings)

print("-----")
bad = DraftRequest(
    skill_id="legal_notice",
    instruction="Draft a notice",
    inputs={"sender": "Ramesh Kumar"},
)
print("MISSING:", run_skill(bad).missing_inputs)