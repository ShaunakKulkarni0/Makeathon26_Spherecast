from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def embedding_backend_available() -> tuple[bool, str]:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception as exc:
        return (False, f"python-dotenv unavailable: {exc}")

    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return (False, "OPENAI_API_KEY not set")

    try:
        from openai import OpenAI
    except Exception as exc:
        return (False, f"openai package unavailable: {exc}")

    try:
        client = OpenAI(api_key=key, timeout=10.0)
        client.embeddings.create(model="text-embedding-3-small", input="healthcheck")
        return (True, "ok")
    except Exception as exc:
        return (False, f"OpenAI embedding backend unreachable: {exc}")
