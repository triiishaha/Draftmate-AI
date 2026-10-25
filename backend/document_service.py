
from pathlib import Path

from doc_convert import convert_bytes, ConvertError

SUPPORTED = {".pdf", ".docx"}


def extract_document_details(filename: str, file_bytes: bytes) -> dict:
    """
    Convert a PDF or DOCX into Markdown and report how it was done.
    Headings, lists and tables stay where they were in the document.
    Returns: {markdown, engine, pages, warnings, tokens_estimate, filename}
    """

    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED:
        raise ValueError("Only PDF and DOCX files are supported.")

    try:
        result = convert_bytes(filename, file_bytes)
    except ConvertError as error:
        raise ValueError(str(error))

    if not result["markdown"].strip():
        raise ValueError(
            "No text found. The file may be scanned and require OCR."
        )

    return result


def extract_document(filename: str, file_bytes: bytes) -> str:
    """
    Extract a PDF or DOCX as Markdown text.
    (Same name and return type as before, so existing code keeps working.)
    """

    return extract_document_details(filename, file_bytes)["markdown"]
