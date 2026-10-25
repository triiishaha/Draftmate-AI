
import re

from context_opt import est_tokens, optimize


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


_ENCODING = None
_ENCODING_FAILED = False


def estimate_tokens(text: str) -> int:
    """
    Count tokens with the cl100k_base tokenizer.
    tiktoken downloads its vocabulary on first use; if that is not possible
    (offline, firewall), fall back to a close estimate instead of crashing.
    """

    global _ENCODING, _ENCODING_FAILED

    if not _ENCODING_FAILED and _ENCODING is None:
        try:
            import tiktoken
            _ENCODING = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _ENCODING_FAILED = True

    if _ENCODING is not None:
        return len(_ENCODING.encode(text))

    return est_tokens(text)


def select_context(markdown: str, query: str = "", max_tokens: int = 6000) -> dict:
    """
    Choose the parts of a long document that matter for the task, within a token budget.
    Original wording and order are kept. See context_opt.optimize for the report fields.
    """

    return optimize(markdown, query=query, max_tokens=max_tokens)
