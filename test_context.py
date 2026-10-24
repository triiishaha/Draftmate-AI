
from markdown_converter import to_structured_markdown
from structure_parser import parse_document
from context_service import retrieve_clause
from context_service import estimate_tokens
sample_text = """SERVICE AGREEMENT

1. Payment Terms
The client must pay within 30 days.

1.1 Late Fees
Late payments may incur additional fees.

2. Termination
Either party may terminate this agreement.
"""

markdown = to_structured_markdown(sample_text)
parsed = parse_document(markdown)

# Test 1: Find clause 1.1
result = retrieve_clause(parsed, "1.1")

print("Clause 1.1 result:")
print(result)

assert result["found"] is True
assert result["clause_id"] == "1.1"
assert "additional fees" in result["text"]

# Test 2: Missing clause
missing = retrieve_clause(parsed, "9.9")
assert missing["found"] is False

# Test 3: Find section 2
section = retrieve_clause(parsed, "2")
assert section["found"] is True
assert "Termination" in section["heading"]

print("\nAll context retrieval tests passed!")
count = estimate_tokens(result["text"])
print("Estimated tokens:", count)

assert count > 0
 