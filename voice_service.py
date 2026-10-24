
import re

NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


def parse_voice_command(transcript: str) -> dict:
    """Convert a natural-language instruction into a structured action."""

    command = transcript.strip()
    normalized = command.lower()

    # Handle empty commands
    if not command:
        return {
            "action": "clarification_needed",
            "target_clause": None,
            "instruction": "",
            "message": "Please enter or speak a command."
        }

    # Handle document summary commands
    if "summar" in normalized:
        return {
            "action": "summarize_document",
            "target_clause": None,
            "instruction": command
        }

    # Handle explain-clause commands
    explain_match = re.search(
        r"\bexplain\s+(?:the\s+)?clause\s+"
        r"(one|two|three|four|five|six|seven|eight|nine|ten|\d+(?:\.\d+)*)\b",
        normalized
    )

    if explain_match:
        target = explain_match.group(1)
        target = NUMBER_WORDS.get(target, target)

        return {
            "action": "explain_clause",
            "target_clause": target,
            "instruction": command
        }

    # Handle rewrite/revise/edit/simplify commands
    rewrite_match = re.search(
        r"\b(?:rewrite|revise|edit|simplify)\s+"
        r"(?:the\s+)?clause\s+"
        r"(one|two|three|four|five|six|seven|eight|nine|ten|\d+(?:\.\d+)*)\b",
        normalized
    )

    if rewrite_match:
        target = rewrite_match.group(1)
        target = NUMBER_WORDS.get(target, target)

        return {
            "action": "rewrite_clause",
            "target_clause": target,
            "instruction": command
        }

    # Handle other commands
    return {
        "action": "general_instruction",
        "target_clause": None,
        "instruction": command
    }

