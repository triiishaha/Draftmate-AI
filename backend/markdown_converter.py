
import re

HEADING_LINE = re.compile(r"^#{1,6}\s+(.*\S)\s*$")


def _relevel(line: str) -> str:
    """
    Put numbered headings at the level the parser expects, whatever level Word used:
      1. Payment Terms   -> ## 1. Payment Terms
      1.1 Late Fees      -> ### 1.1 Late Fees
    Headings that are not numbered (such as the title) keep their level.
    """

    match = HEADING_LINE.match(line)

    if not match:
        return line

    text = match.group(1)

    if re.match(r"^\d+(?:\.\d+)+\s+\S", text):
        return f"### {text}"

    if re.match(r"^\d+\.\s+\S", text):
        return f"## {text}"

    return line


def to_structured_markdown(text: str) -> str:
    """
    Convert extracted legal document text into basic Markdown.
    Preserves the original text while marking likely headings.
    Text that is already Markdown (from the converter) is kept, with numbered headings re-levelled.
    """

    lines = text.splitlines()
    formatted_lines = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            formatted_lines.append("")
            continue

        # Already a Markdown heading from the converter
        if stripped.startswith("#"):
            formatted_lines.append(_relevel(stripped))

        # Table rows and bullet lines are kept exactly as they are
        elif stripped.startswith("|") or stripped.startswith("- "):
            formatted_lines.append(stripped)

        # Numbered clauses, e.g. 1.1 Late Fees
        elif re.match(r"^\d+\.\d+(?:\.\d+)*\s+\S", stripped):
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
