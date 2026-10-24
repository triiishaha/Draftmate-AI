
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

# Load API key from the .env file beside this script
load_dotenv(Path(__file__).with_name(".env"))

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY missing. Check server/.env"
    )

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents="Explain in one simple sentence what a legal document summary is."
)

print("\nGemini response:")
print(response.text)
