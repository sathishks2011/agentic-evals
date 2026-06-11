"""Minimal stdlib llama.cpp (llama-server) client for exp-004.

Talks to llama-server's OpenAI-compatible ``/v1/chat/completions`` with
optional JSON-schema-constrained decoding (``response_format`` with
``json_schema``) — the capability Ollama does not expose and the whole
point of spike 1.
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "http://localhost:8088"


def chat(
    system: str,
    user: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    json_schema: dict[str, Any] | None = None,
    temperature: float = 0.1,
    max_tokens: int = 256,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """One chat completion. Returns {content, latency_ms, completion_tokens}."""
    body: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if json_schema is not None:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "route", "strict": True, "schema": json_schema},
        }
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - localhost only
        f"{base_url}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        parsed = json.loads(response.read().decode("utf-8"))
    latency_ms = (time.monotonic() - start) * 1000.0
    return {
        "content": parsed["choices"][0]["message"]["content"],
        "latency_ms": latency_ms,
        "completion_tokens": parsed.get("usage", {}).get("completion_tokens"),
    }


def health(base_url: str = DEFAULT_BASE_URL, *, timeout: float = 5.0) -> bool:
    """True when llama-server reports ready."""
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8")).get("status") == "ok"
    except Exception:  # noqa: BLE001
        return False
