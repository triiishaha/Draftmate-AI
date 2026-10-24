
import re


def to_structured_markdown(text: str) -> str:
    """
    Convert extracted legal document text into basic Markdown.
    Preserves the original text while marking likely headings.
    """

    lines = text.splitlines()
    formatted_lines = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            formatted_lines.append("")
            continue

        # Numbered clauses, e.g. 1.1 Late Fees
        if re.match(r"^\d+\.\d+(?:\.\d+)*\s+\S", stripped):
            formatted_lines.append(f"### {stripped}")

        # Numbered sections, e.g. 1. Payment Terms
        elif re.match(r"^\d+\.\s+[A-Z]", stripped):
            formatted_lines.append(f"## {stripped}")

        # All-uppercase document headings
        elif (
            len(stripped) <= 100
            and stripped.isupper()
            and re.search(r"[A-Z]", stripped)
        ):
            formatted_lines.append(f"# {stripped}")

        else:
            formatted_lines.append(stripped)

    return "\n".join(formatted_lines)
