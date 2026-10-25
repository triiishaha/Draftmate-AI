from drafting_engine.models import DraftRequest
from drafting_engine.engine import run_skill, split_changes
from drafting_engine.skill_loader import load_skills

SAMPLES = {
    "legal_notice": {
        "inputs": {"sender": "A", "recipient": "B",
                   "facts": "Rent unpaid", "relief_sought": "Pay dues"}},
    "agreement_drafting": {
        "inputs": {"agreement_type": "Rent agreement", "party_one": "A",
                   "party_two": "B", "key_terms": "Rs 15,000 per month"}},
    "contract_review": {
        "inputs": {"review_perspective": "tenant"},
        "source_text": "Clause 1: Rent is Rs 15,000."},
    "revise_draft": {
        "inputs": {"change_request": "Change 30 days to 15 days"},
        "source_text": "Clause 4: Pay within 30 days."},
    "summarise_document": {
        "inputs": {},
        "source_text": "Clause 1: Rent is Rs 15,000."},
}

results = []


def check(name, ok):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)


skills = load_skills()
check("5 skills load", len(skills) == 5)

for sid, skill in skills.items():
    has_keys = all(k in skill for k in ("id", "name", "system_prompt", "inputs"))
    check(sid + ": has id, name, system_prompt, inputs", has_keys)
    check(sid + ": prompt tells the model to flag uncertain references",
          "[VERIFY]" in skill.get("system_prompt", ""))

    sample = SAMPLES.get(sid)
    if not sample:
        check(sid + ": has a test sample in this script", False)
        continue

    # 1. runs and builds a prompt
    req = DraftRequest(skill_id=sid, instruction="test", **sample)
    r = run_skill(req, dry_run=True)
    check(sid + ": dry run builds a prompt", "--- USER ---" in r.draft_md)

    # 2. reference style only where the skill allows it
    req2 = DraftRequest(skill_id=sid, instruction="test",
                        reference_text="SAMPLE STYLE TEXT", **sample)
    r2 = run_skill(req2, dry_run=True)
    appears = "SAMPLE STYLE TEXT" in r2.draft_md
    check(sid + ": reference style used only if skill allows it",
          appears == bool(skill.get("use_reference_style")))

    # 3. missing required inputs are reported
    required = skill.get("inputs", {}).get("required", [])
    if required:
        extra = {}
        if sample.get("source_text"):
            extra["source_text"] = sample["source_text"]
        r3 = run_skill(DraftRequest(skill_id=sid, instruction="test", **extra),
                       dry_run=True)
        check(sid + ": reports missing required inputs",
              set(r3.missing_inputs) == set(required))

    # 4. skills that need a document refuse to run without one
    if skill.get("requires_source_text"):
        r4 = run_skill(DraftRequest(skill_id=sid, instruction="test",
                                    inputs=sample["inputs"]), dry_run=True)
        check(sid + ": refuses to run without a document",
              r4.missing_inputs == ["source_text"])

body, changes = split_changes(
    "New text.\n\n## Change Summary\n- Changed A (Clause 1)\n- Warning: B")
check("change summary splits into body and 2 changes",
      body == "New text." and len(changes) == 2)

try:
    run_skill(DraftRequest(skill_id="no_such_skill", instruction="x"),
              dry_run=True)
    check("unknown skill gives a clear error", False)
except KeyError:
    check("unknown skill gives a clear error", True)

print()
print("%d of %d checks passed" % (sum(results), len(results)))