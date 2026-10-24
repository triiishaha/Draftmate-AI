
from markdown_converter import to_structured_markdown
from structure_parser import parse_document

sample = """SERVICE AGREEMENT

1. Payment Terms
The client must pay within 30 days.

1.1 Late Fees
Late payments may incur additional fees.

2. Termination
Either party may terminate this agreement.
"""

markdown = to_structured_markdown(sample)
parsed = parse_document(markdown)

print(parsed)

assert parsed["title"] == "SERVICE AGREEMENT"
assert len(parsed["sections"]) == 2
assert parsed["sections"][0]["heading"] == "1. Payment Terms"
assert parsed["sections"][0]["clauses"][0]["clause_id"] == "1.1"

print("\nAll structure parser tests passed!")
