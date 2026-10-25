import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai


# Load the API key from the project root or server/.env
PROJECT_DIR = Path(__file__).resolve().parent

load_dotenv(PROJECT_DIR / ".env")
load_dotenv(PROJECT_DIR / "server" / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY not found. Add it to .env or server/.env."
    )

client = genai.Client(api_key=API_KEY)

MODEL_NAME = "gemini-3.8-flash"


def generate_document_response(action, context, transcript):
    """Generate an AI response using the retrieved legal document context."""

    document_text = context.get("text", "")

    if action == "summarize_document":
        task = """
        Summarize the legal document in clear, simple language.
        Include the main purpose, important obligations, deadlines,
        payment terms, and potential risks when they appear in the text.
        Do not invent missing information.
        """

    elif action == "explain_clause":
        task = """
        Explain the requested legal clause in simple language.
        Describe what it means, who it affects, and any important
        conditions or consequences explicitly supported by the text.
        If something is unclear, say so.
        """

    elif action == "rewrite_clause":
        task = """
        Rewrite the requested clause in simpler, clearer language.
        Preserve its original meaning, obligations, conditions,
        dates, and amounts. Do not introduce new legal terms or
        change the parties' rights and responsibilities.
        """

    else:
        task = f"""
        Follow the user's instruction using only the provided
        legal-document context.

        User instruction: {transcript}

        If the instruction asks for information not present in the
        document, clearly state that the information is unavailable.
        """

    prompt = f"""
    You are DraftMate AI, an assistant for understanding legal documents.

    IMPORTANT:
    - Use the supplied document text as your source.
    - Do not invent clauses, facts, dates, amounts, or legal provisions.
    - If the supplied context is insufficient, say so clearly.
    - This is informational assistance, not a substitute for a lawyer.

    TASK:
    {task}

    DOCUMENT CONTEXT:
    {document_text}

    Respond in a clear, structured and useful way.
    """

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")

    return response.text.strip()
