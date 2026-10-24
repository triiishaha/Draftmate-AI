
import re


def retrieve_clause(
    parsed_document: dict,
    clause_number: str
) -> dict:
    """
    Find a specific clause in the parsed document.
    Returns the clause and its parent section as context.
    """

    target = clause_number.strip()

    # Search for an exact clause ID, such as 1.1 or 4
    for section in parsed_document.get("sections", []):
        for clause in section.get("clauses", []):
            if clause["clause_id"] == target:
                return {
                    "found": True,
                    "clause_id": clause["clause_id"],
                    "heading": clause["heading"],
                    "text": clause["text"].strip(),
                    "section_heading": section["heading"],
                    "section_context": section.get("text", "").strip()
                }

    # A plain section number, such as 2, can match section 2.
    # It does not automatically match subsection 2.1.
    for section in parsed_document.get("sections", []):
        match = re.match(r"^(\d+)\.", section["heading"])

        if match and match.group(1) == target:
            return {
                "found": True,
                "clause_id": target,
                "heading": section["heading"],
                "text": section.get("text", "").strip(),
                "section_heading": section["heading"],
                "section_context": ""
            }

    return {
        "found": False,
        "clause_id": target,
        "message": f"Clause or section {target} was not found."
    }

import tiktoken


def estimate_tokens(text: str) -> int:
    """Estimate tokens using the cl100k_base tokenizer."""

    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))
