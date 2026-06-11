"""Spike 1 — grammar-constrained router on llama.cpp.

JSON-schema-constrained decoding with the intent↔agent consistency guard
ENCODED IN THE SCHEMA: the valid (intent, agent_type) pairs are an
``oneOf`` of const-pairs, so the server cannot emit an invalid label or a
mismatched pair. Parse-fallback becomes structurally impossible; what
remains is pure routing judgment.

Start the server first (reads Ollama's GGUF blob directly):

    llama-server -m <gguf-path> --port 8088 -c 2048 --jinja

Then:

    uv run agentic-evals exp-004 grammar-router          # constrained
    EXP004_UNCONSTRAINED=1 uv run agentic-evals exp-004 grammar-router

Env: EXP004_BASE_URL (default http://localhost:8088), EXP004_LABEL
(config label in results, default "llamacpp:schema"), EXP004_UNCONSTRAINED=1
to drop the schema (A/B control on the same server/model).
"""

from __future__ import annotations

import json
import os
import statistics
from pathlib import Path
from typing import Any

from agentic_evals.experiments.exp004 import llamacpp_client
from agentic_evals.experiments.exp005.iris_router import (
    INTENT_TO_AGENT,
    ROUTER_SYSTEM_PROMPT,
    route_llm_with_fallback,
)
from agentic_evals.experiments.exp005.model_sweep import load_cases
from agentic_evals.harness.report import append_jsonl, write_run

EXP_DIR = (
    Path(__file__).resolve().parents[4]
    / "docs"
    / "experiments"
    / "exp-004-serving-stack-bakeoff"
)
OUT_DIR = EXP_DIR / "spikes" / "0001-grammar-router"
RESULTS_DIR = EXP_DIR / "results"

# The consistency guard as a schema: only the 11 valid pairs are emittable.
ROUTE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "agent_type": {"type": "string"},
        "is_multi_step": {"type": "boolean"},
        "confidence": {"type": "number"},
    },
    "required": ["intent", "agent_type", "is_multi_step", "confidence"],
    "additionalProperties": False,
    "oneOf": [
        {
            "properties": {
                "intent": {"const": intent},
                "agent_type": {"const": agent},
            }
        }
        for intent, agent in sorted(INTENT_TO_AGENT.items())
    ],
}


def main() -> None:
    base_url = os.getenv("EXP004_BASE_URL", llamacpp_client.DEFAULT_BASE_URL)
    unconstrained = os.getenv("EXP004_UNCONSTRAINED", "").strip() == "1"
    label = os.getenv(
        "EXP004_LABEL",
        "llamacpp:unconstrained" if unconstrained else "llamacpp:schema",
    )
    schema = None if unconstrained else ROUTE_SCHEMA

    if not llamacpp_client.health(base_url):
        raise SystemExit(f"llama-server not healthy at {base_url} — start it first")

    # Warm call so model/ctx setup doesn't pollute case latencies.
    llamacpp_client.chat(ROUTER_SYSTEM_PROMPT, "ok?", base_url=base_url, json_schema=schema)

    cases = load_cases()
    rows: list[dict[str, Any]] = []
    for case in cases:
        reply = llamacpp_client.chat(
            ROUTER_SYSTEM_PROMPT,
            case["utterance"],
            base_url=base_url,
            json_schema=schema,
        )
        routed = route_llm_with_fallback(reply["content"], case["utterance"])
        ok = (
            routed["intent"] == case["expect_intent"]
            and routed["agent"] == case["expect_agent"]
        )
        rows.append(
            {
                "config": label,
                "run": 0,
                "case_id": case["id"],
                "class": case.get("class", "clear"),
                "pass": ok,
                "expected": f"{case['expect_intent']}/{case['expect_agent']}",
                "actual": f"{routed['intent']}/{routed['agent']}",
                "source": routed.get("source", ""),
                "latency_ms": round(reply["latency_ms"], 1),
                "completion_tokens": reply.get("completion_tokens"),
            }
        )

    latencies = sorted(r["latency_ms"] for r in rows)
    fallbacks = sum(1 for r in rows if str(r["source"]).startswith("fallback-"))
    by_class: dict[str, list[bool]] = {}
    for row in rows:
        by_class.setdefault(row["class"], []).append(row["pass"])
    summary = {
        "config": label,
        "cases": len(rows),
        "accuracy": round(sum(r["pass"] for r in rows) / len(rows), 4),
        "accuracy_by_class": {
            cls: round(sum(vals) / len(vals), 4) for cls, vals in sorted(by_class.items())
        },
        "fallback_rate": round(fallbacks / len(rows), 4),
        "latency_p50_ms": round(statistics.median(latencies), 1),
        "latency_p95_ms": round(latencies[int(len(latencies) * 0.95) - 1], 1),
    }
    append_jsonl(RESULTS_DIR / "raw-results.jsonl", rows)
    write_run(OUT_DIR, {"spike": "0001-grammar-router", "summary": summary})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
