from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI


def main() -> int:
    # Load .env from current directory or search upwards
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    print("🔍 Debugging:")
    print(f"  .env file loaded from: {os.path.abspath('.env')}")
    print(f"  API Key found: {'Yes' if api_key else 'No'}")
    if api_key:
        print(f"  Key length: {len(api_key)}")
        print(f"  Key starts with: {api_key[:15]}")
        print(f"  Key ends with: ...{api_key[-10:]}")
        print(f"  Full key: {api_key}")  # REMOVE AFTER DEBUGGING
    print()

    if not api_key:
        print("OPENAI_API_KEY fehlt. Bitte in .env setzen.")
        return 1

    try:
        client = OpenAI(api_key=api_key, timeout=10.0)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input="API key connectivity test",
        )
        vector_len = len(response.data[0].embedding)
        print("✓ OK: OpenAI API-Key funktioniert.")
        print(f"  Embedding erzeugt (Dimension: {vector_len}).")
        return 0
    except Exception as exc:
        print("✗ FEHLER: API-Key oder Verbindung konnte nicht verifiziert werden.")
        print(f"  Grund: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())