import os

from dotenv import load_dotenv
from google import genai


# Load API configuration from .env
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("GEMINI_MODEL", "").strip()


def test_gemini():

    if not API_KEY:
        print("ERROR: Gemini API key is missing.")
        return

    if not MODEL:
        print("ERROR: Gemini model is missing.")
        return

    try:

        print("Connecting to Gemini API...")

        client = genai.Client(api_key=API_KEY)

        # Verify that the configured model is accessible
        model_info = client.models.get(model=MODEL)

        print("Model found:", model_info.name)

        # Send a simple test question
        response = client.models.generate_content(
            model=MODEL,
            contents="Introduce yourself as an IT Asset Management AI assistant in two sentences."
        )

        print("\nGemini API response:")
        print(response.text)

        print("\nSUCCESS: Gemini API connection is working!")

    except Exception as error:

        print("\nGEMINI API TEST FAILED")
        print("Error:", str(error))


if __name__ == "__main__":
    test_gemini()