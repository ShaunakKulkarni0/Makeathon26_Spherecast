from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI


def main() -> int:
    load_dotenv(".env")
    api_key = os.getenv("OPENAI_API_KEY")

    print("OpenAI Mini Connectivity Test")
    print(f"OPENAI_API_KEY gesetzt: {bool(api_key)}")
    if api_key:
        print(f"Key-Laenge: {len(api_key)}")

    if not api_key:
        print("FEHLER: OPENAI_API_KEY fehlt in .env")
        return 1

    try:
        client = OpenAI(api_key=api_key, timeout=10.0)
    except Exception as exc:
        print("FEHLER: OpenAI Client konnte nicht erstellt werden.")
        print(f"Grund: {type(exc).__name__}: {exc}")
        return 2

    chat_ok = False
    embedding_ok = False

    print("\n1) Chat-Test")
    try:
        chat_response = client.responses.create(
            model="gpt-4o-mini",
            input="Antworte bitte nur mit: API-Chat-Test OK und sag mir was die Hauptstadt von Frankreich ist.",
            max_output_tokens=50,
        )
        print("OK: Chat funktioniert.")
        print(f"Antwort: {chat_response.output_text.strip()}")
        chat_ok = True
    except Exception as exc:
        print("FEHLER: Chat fehlgeschlagen.")
        print(f"Grund: {type(exc).__name__}: {exc}")

    print("\n2) Embedding-Test")
    try:
        embedding_response = client.embeddings.create(
            model="text-embedding-3-small",
            input="API key connectivity test",
        )
        vector_len = len(embedding_response.data[0].embedding)
        print("OK: Embedding funktioniert.")
        print(f"Dimension: {vector_len}")
        embedding_ok = True
    except Exception as exc:
        print("FEHLER: Embedding fehlgeschlagen.")
        print(f"Grund: {type(exc).__name__}: {exc}")

    print("\nGesamtstatus:")
    if chat_ok and embedding_ok:
        print("OK: Chat + Embedding funktionieren.")
        return 0
    if chat_ok and not embedding_ok:
        print("TEILWEISE OK: Chat geht, Embedding nicht.")
        return 3
    if not chat_ok and embedding_ok:
        print("TEILWEISE OK: Embedding geht, Chat nicht.")
        return 4

    print("FEHLER: Weder Chat noch Embedding funktionieren.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
