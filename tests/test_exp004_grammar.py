"""Pure-logic tests for the exp-004 grammar-router spike (no server)."""

from __future__ import annotations

from agentic_evals.experiments.exp004.grammar_router import ROUTE_SCHEMA
from agentic_evals.experiments.exp005.iris_router import INTENT_TO_AGENT


def test_schema_encodes_every_valid_intent_agent_pair() -> None:
    pairs = {
        (alt["properties"]["intent"]["const"], alt["properties"]["agent_type"]["const"])
        for alt in ROUTE_SCHEMA["oneOf"]
    }
    assert pairs == set(INTENT_TO_AGENT.items())


def test_schema_requires_all_route_fields() -> None:
    assert set(ROUTE_SCHEMA["required"]) == {
        "intent",
        "agent_type",
        "is_multi_step",
        "confidence",
    }
    assert ROUTE_SCHEMA["additionalProperties"] is False
