"""
shared/openai_client.py

Low-level HTTP wrapper around the OpenAI REST API.
- No openai SDK dependency — uses httpx directly so the call stack is explicit.
- Handles auth (Bearer token), retries with exponential back-off, and raises
  typed exceptions so callers can react without parsing raw HTTP errors.
- Both Layer 1 (chat completions) and Layer 2 (embeddings) go through here.
"""
from __future__ import annotations

import json
import os
import time
import logging
from typing import Any

import httpx
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

from .constants import (
    OPENAI_CHAT_URL,
    OPENAI_EMBEDDINGS_URL,
    OPENAI_REQUEST_TIMEOUT_S,
    MAX_RETRIES,
    RETRY_BACKOFF_BASE_S,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OpenAIError(Exception):
    """Raised when the OpenAI API returns a non-2xx status."""
    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"OpenAI API error {status_code}: {body[:300]}")


class OpenAIRateLimitError(OpenAIError):
    """429 — caller should back off."""


class OpenAIAuthError(OpenAIError):
    """401 / 403 — bad key or insufficient quota."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    key = os.environ.get("OpenAIAPI", "")
    if not key:
        raise EnvironmentError(
            "OpenAIAPI environment variable is not set. "
            "Export it before running the pipeline."
        )
    return key


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
    }


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 200:
        return
    if response.status_code == 429:
        raise OpenAIRateLimitError(response.status_code, response.text)
    if response.status_code in (401, 403):
        raise OpenAIAuthError(response.status_code, response.text)
    raise OpenAIError(response.status_code, response.text)


def _post_with_retry(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    POST `payload` to `url` with exponential back-off retries.
    Returns the parsed JSON body on success.
    """
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=OPENAI_REQUEST_TIMEOUT_S) as client:
                response = client.post(url, headers=_headers(), json=payload)
            _raise_for_status(response)
            return response.json()
        except OpenAIRateLimitError as exc:
            wait = RETRY_BACKOFF_BASE_S ** attempt
            logger.warning("Rate limited (attempt %d/%d). Waiting %ds.", attempt, MAX_RETRIES, wait)
            time.sleep(wait)
            last_exc = exc
        except OpenAIAuthError:
            # Auth errors will not resolve with retries — re-raise immediately
            raise
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            wait = RETRY_BACKOFF_BASE_S ** attempt
            logger.warning("Network error (attempt %d/%d): %s. Waiting %ds.", attempt, MAX_RETRIES, exc, wait)
            time.sleep(wait)
            last_exc = exc
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chat_completion(
    *,
    model: str,
    system_prompt: str,
    user_content: str,
    json_mode: bool = True,
    temperature: float = 0.0,
) -> str:
    """
    Send a single-turn chat completion request.

    Args:
        model:         OpenAI model identifier (e.g. "gpt-4o").
        system_prompt: The system message content.
        user_content:  The user message content.
        json_mode:     If True, sets response_format to json_object.
                       The system prompt MUST contain the word "JSON" when True,
                       otherwise OpenAI returns a 400.
        temperature:   Sampling temperature (0.0 = deterministic).

    Returns:
        The raw text content of the assistant's reply.
    """
    payload: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ],
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    data = _post_with_retry(OPENAI_CHAT_URL, payload)

    # OpenAI chat completions always return choices[0].message.content for
    # non-streaming requests — guard against unexpected shapes gracefully.
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise OpenAIError(200, f"Unexpected response shape: {data}") from exc

    return content


def create_embeddings(inputs: list[str], model: str, dimensions: int) -> list[list[float]]:
    """
    Embed a list of strings in a single API call.

    Args:
        inputs:     List of strings to embed. Max ~8191 tokens per string.
        model:      Embedding model identifier.
        dimensions: Expected output dimensionality (used for validation only;
                    the API respects the model's native dimensions).

    Returns:
        List of float vectors, same order as `inputs`.

    Raises:
        ValueError: If the returned embedding count doesn't match `inputs`.
    """
    if not inputs:
        return []

    payload: dict[str, Any] = {
        "model": model,
        "input": inputs,
    }

    data = _post_with_retry(OPENAI_EMBEDDINGS_URL, payload)

    try:
        # OpenAI returns data sorted by index field — sort to be safe
        embeddings_raw = sorted(data["data"], key=lambda x: x["index"])
        vectors = [item["embedding"] for item in embeddings_raw]
    except (KeyError, TypeError) as exc:
        raise OpenAIError(200, f"Unexpected embeddings response shape: {data}") from exc

    if len(vectors) != len(inputs):
        raise ValueError(
            f"Expected {len(inputs)} embeddings, got {len(vectors)}. "
            "Check for truncated input or API error."
        )

    # Dimension sanity check — catch model config mismatches early
    if vectors and len(vectors[0]) != dimensions:
        raise ValueError(
            f"Embedding dimension mismatch: expected {dimensions}, "
            f"got {len(vectors[0])}. Check EMBEDDING_MODEL / EMBEDDING_DIMENSIONS."
        )

    return vectors