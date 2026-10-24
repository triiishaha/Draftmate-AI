
from voice_service import parse_voice_command

test_cases = [
    ("Summarise this agreement", "summarize_document"),
    ("Rewrite clause four", "rewrite_clause"),
    ("Rewrite clause 1.1 in simpler language", "rewrite_clause"),
    ("", "clarification_needed"),
    ("Explain clause two", "explain_clause"),
]

for transcript, expected_action in test_cases:
    result = parse_voice_command(transcript)

    print("Input:", repr(transcript))
    print("Result:", result)

    assert result["action"] == expected_action, (
        f"Expected {expected_action}, got {result['action']}"
    )

print("\nVoice command tests passed!")

summary = parse_voice_command("Summarise this agreement")
print(summary)
assert summary["action"] == "summarize_document"

rewrite = parse_voice_command(
    "Rewrite clause four in simpler language"
)
print(rewrite)
assert rewrite["action"] == "rewrite_clause"
assert rewrite["target_clause"] == "4"

decimal = parse_voice_command("Rewrite clause 1.1")
assert decimal["target_clause"] == "1.1"

empty = parse_voice_command("")
assert empty["action"] == "clarification_needed"

print("\nAll voice command tests passed!")
