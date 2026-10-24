
from markdown_converter import to_structured_markdown
from structure_parser import parse_document
from voice_service import parse_voice_command
from context_service import retrieve_clause, estimate_tokens

sample_text = """SERVICE AGREEMENT

1. Payment Terms
The client must pay within 30 days.

1.1 Late Fees
Late payments may incur additional fees.

2. Termination
Either party may terminate this agreement.
"""

# Step 1: Convert text into Markdown
markdown = to_structured_markdown(sample_text)

# Step 2: Extract sections and clauses
parsed_document = parse_document(markdown)

# Step 3: Parse the user's command
command = parse_voice_command(
    "Rewrite clause 1.1 in simpler language"
)

# Step 4: Retrieve the requested clause
context = retrieve_clause(
    parsed_document,
    command["target_clause"]
)

# Step 5: Validate the pipeline
assert command["action"] == "rewrite_clause"
assert context["found"] is True
assert context["clause_id"] == "1.1"

tokens = estimate_tokens(context["text"])

print("Action:", command["action"])
print("Target clause:", command["target_clause"])
print("Retrieved text:", context["text"])
print("Estimated tokens:", tokens)
print("\nEnd-to-end pipeline passed!")

