
from document_service import extract_document
from markdown_converter import to_structured_markdown
from structure_parser import parse_document
from voice_service import parse_voice_command
from context_service import retrieve_clause, estimate_tokens
from ai_service import generate_document_response


def process_document_command(filename, file_bytes, transcript):
    # 1. Extract document text
    text = extract_document(filename, file_bytes)

    # 2. Convert text into structured Markdown
    markdown = to_structured_markdown(text)

    # 3. Parse the document structure
    parsed = parse_document(markdown)

    # 4. Interpret the user's command
    command = parse_voice_command(transcript)

    action = command["action"]
    target_clause = command["target_clause"]

    # 5. Select relevant context
    if action in ("rewrite_clause", "explain_clause"):
        context = retrieve_clause(parsed, target_clause)

    elif action == "clarification_needed":
        context = {
            "found": False,
            "text": "",
            "message": command.get(
                "message",
                "Please enter or speak a command."
            )
        }

    else:
        # Summary and general instructions need the full document
        context = {
            "found": True,
            "text": markdown
        }

    # 6. Estimate tokens from the selected context
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

    # 7. Generate an AI response only when context is usable
    ai_response = None

    if action == "clarification_needed":
        pass

    elif not context.get("found", False):
        pass

    else:
        ai_response = generate_document_response(
            action=action,
            context=context,
            transcript=transcript
        )

    # 8. Return the existing results plus the AI response
    return {
        "action": action,
        "target_clause": target_clause,
        "context": context,
        "estimated_tokens": estimated_tokens,
        "ai_response": ai_response
    }

