
from pathlib import Path

from document_service import extract_document
from markdown_converter import to_structured_markdown
from structure_parser import parse_document
from voice_service import parse_voice_command
from context_service import retrieve_clause, estimate_tokens

# A real sample DOCX file must exist at this path.
file_path = Path("sample_agreement.docx")

if not file_path.exists():
    print("Please add sample_agreement.docx to this folder first.")
else:
    # 1. Read the actual document
    file_bytes = file_path.read_bytes()
    extracted_text = extract_document(
        file_path.name,
        file_bytes
    )

    # 2. Convert extracted text into Markdown
    markdown = to_structured_markdown(extracted_text)

    # 3. Parse sections and clauses
    parsed_document = parse_document(markdown)

    # 4. Interpret the user's command
    command = parse_voice_command(
        "Rewrite clause 1.1 in simpler language"
    )

    # 5. Retrieve the relevant clause
    context = retrieve_clause(
        parsed_document,
        command["target_clause"]
    )

    print("Action:", command["action"])
    print("Target clause:", command["target_clause"])
    print("Clause found:", context["found"])

    if context["found"]:
        print("Heading:", context["heading"])
        print("Text:", context["text"])
        print("Estimated tokens:", estimate_tokens(context["text"]))
        print("\nReal-document pipeline passed!")
    else:
        print(context["message"])
