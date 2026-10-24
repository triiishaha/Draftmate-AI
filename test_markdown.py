
from markdown_converter import to_structured_markdown

sample_text = """SERVICE AGREEMENT

1. Payment Terms
The client must pay within 30 days.

1.1 Late Fees
Late payments may incur additional fees.

2. Termination
Either party may terminate this agreement.
"""

result = to_structured_markdown(sample_text)

print(result)

assert "# SERVICE AGREEMENT" in result
assert "## 1. Payment Terms" in result
assert "### 1.1 Late Fees" in result
assert "## 2. Termination" in result

print("\nAll Markdown tests passed!")
