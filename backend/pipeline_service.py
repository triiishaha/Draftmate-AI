
from document_service import extract_document_details
from markdown_converter import to_structured_markdown
from structure_parser import parse_document
from voice_service import parse_voice_command
from context_service import retrieve_clause, estimate_tokens, select_context
from context_opt import clean

DEFAULT_BUDGET = 6000


def _generate(action, context, transcript):
    # Imported here so the rest of the pipeline works without a Gemini key
    from ai_service import generate_document_response

    return generate_document_response(
        action=action,
        context=context,
        transcript=transcript
    )


def process_document_command(
    filename,
    file_bytes,
    transcript,
    max_tokens=DEFAULT_BUDGET,
    generate_ai=True
):
    # 1. Convert the document to Markdown (headings, lists and tables kept)
    conversion = extract_document_details(filename, file_bytes)

    # 2. Remove repeated page headers/footers, page numbers and duplicate paragraphs
    text, clean_steps = clean(conversion["markdown"])

    # 3. Mark headings the parser understands
    markdown = to_structured_markdown(text)
    full_tokens = estimate_tokens(markdown)

    # 4. Parse the document structure
    parsed = parse_document(markdown)

    # 5. Interpret the user's command
    command = parse_voice_command(transcript)

    action = command["action"]
    target_clause = command["target_clause"]

    # 6. Select only the context the task needs
    optimization = None

    if action in ("rewrite_clause", "explain_clause"):
        context = retrieve_clause(parsed, target_clause)
        strategy = "clause"

    elif action == "clarification_needed":
        context = {
            "found": False,
            "text": "",
            "message": command.get(
                "message",
                "Please enter or speak a command."
            )
        }
        strategy = "none"

    else:
        # Summary and general instructions: choose the relevant sections within a budget
        query = "" if action == "summarize_document" else command["instruction"]
        optimization = select_context(markdown, query, max_tokens)
        context = {
            "found": True,
            "text": optimization["text"]
        }
        strategy = "budgeted sections"

    # 7. Count tokens in what will be sent to the model
    if context.get("found", False):
        context_parts = [
            context.get("section_heading", ""),
            context.get("section_context", ""),
            context.get("heading", ""),
            context.get("text", "")
        ]

        context_text = "\n".join(
            part for part in context_parts if part.strip()
        )
    else:
        context_text = ""

    estimated_tokens = estimate_tokens(context_text)

    # 8. Report what was saved against sending the whole document
    saved = max(full_tokens - estimated_tokens, 0)

    report = {
        "strategy": strategy,
        "full_document_tokens": full_tokens,
        "sent_tokens": estimated_tokens,
        "saved_tokens": saved if context.get("found", False) else 0,
        "saved_pct": round(100 * saved / full_tokens) if full_tokens and context.get("found", False) else 0,
        "cleaning": clean_steps,
        "sections": optimization["sections"] if optimization else [],
        "citations": optimization["citations"] if optimization else None,
        "budget": max_tokens,
    }

    # 9. Generate an AI response only when context is usable
    ai_response = None

    if generate_ai and action != "clarification_needed" and context.get("found", False):
        ai_response = _generate(action, context, transcript)

    # 10. Return the existing results plus the new reports
    return {
        "action": action,
        "target_clause": target_clause,
        "context": context,
        "estimated_tokens": estimated_tokens,
        "ai_response": ai_response,
        "conversion": {
            "engine": conversion["engine"],
            "pages": conversion["pages"],
            "warnings": conversion["warnings"],
        },
        "optimization": report,
    }
