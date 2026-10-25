import os
from drafting_engine.models import DraftRequest, DraftResult, Change
from drafting_engine.skill_loader import get_skill
from drafting_engine.llm import call_llm

def split_changes(text):
    marker = "## Change Summary"
    if marker not in text:
        return text, []
    body, summary = text.split(marker, 1)
    changes = []
    for line in summary.splitlines():
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            changes.append(Change(description=line[2:].strip()))
    return body.strip(), changes
def build_prompt(request, skill):
    system = skill["system_prompt"]
    parts = ["Instruction: " + request.instruction]

    if request.inputs:
        lines = ["- " + str(k) + ": " + str(v) for k, v in request.inputs.items()]
        parts.append("Details provided:\n" + "\n".join(lines))

    if request.source_text:
        parts.append("Existing text to work from:\n" + request.source_text)

    if request.context_chunks:
        parts.append("Relevant context:\n" + "\n\n".join(request.context_chunks))
    if skill.get("use_reference_style") and request.reference_text:
        ref = request.reference_text[:6000]
        parts.append(
            "Style reference (a sample document written by the user):\n" + ref +
            "\n\nMatch the style reference in tone, structure, terminology, "
            "formatting and clause patterns. Use it for style only. "
            "Do NOT copy its names, amounts, dates or facts. "
            "Use only the details provided above."
        )
    sections = skill.get("output_sections")
    if sections:
        parts.append("Write the output in Markdown with these sections: " + ", ".join(sections))

    return system, "\n\n".join(parts)


def run_skill(request, dry_run=None):
    skill = get_skill(request.skill_id)
    if skill.get("requires_source_text") and not request.source_text:
        return DraftResult(
            skill_id=request.skill_id,
            draft_md="",
            missing_inputs=["source_text"],
            warnings=["This skill needs a document. Upload or paste one first."],
        )
    required = skill.get("inputs", {}).get("required", [])
    missing = [f for f in required if not request.inputs.get(f)]
    if missing:
        return DraftResult(
            skill_id=request.skill_id,
            draft_md="",
            missing_inputs=missing,
            warnings=["Missing required details: " + ", ".join(missing)],
        )

    system, user = build_prompt(request, skill)

    if dry_run is None:
        dry_run = not os.getenv("LLM_MODEL")

    if dry_run:
        text = "[DRY RUN - no AI model was called]\n\n--- SYSTEM ---\n" + system + "\n--- USER ---\n" + user
        return DraftResult(
            skill_id=request.skill_id,
            draft_md=text,
            warnings=["Dry run: no AI model was called."],
        )
    text = call_llm(system, user, model=request.model)
    draft, changes = split_changes(text)
    warnings = []
    if "[VERIFY]" in draft:
        warnings.append("Draft contains [VERIFY] flags: check these references.")
    for c in changes:
        if c.description.lower().startswith("warning"):
            warnings.append(c.description)
    return DraftResult(
        skill_id=request.skill_id,
        draft_md=draft,
        changes=changes,
        warnings=warnings,
    )
   