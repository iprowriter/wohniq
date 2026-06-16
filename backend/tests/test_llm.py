"""Tests for the central LLM client.

Uses a fake transport (no network/SDK) to exercise the reliability logic that
matters: validation, single re-prompt, fallback, and hard failure.
"""

import pytest
from pydantic import BaseModel

from core.llm import LLMError, RawResponse, generate_structured


class Demo(BaseModel):
    name: str
    age: int


def _transport_returning(*texts):
    """Fake transport that yields the given raw texts on successive calls."""
    calls = iter(texts)

    def transport(system, user, schema, temperature):
        return RawResponse(text=next(calls), tokens_in=10, tokens_out=5)

    return transport


def test_valid_first_try():
    result = generate_structured(
        prompt_id="demo.v1",
        system="s",
        user="u",
        schema=Demo,
        transport=_transport_returning('{"name": "Anna", "age": 30}'),
    )
    assert result.data == Demo(name="Anna", age=30)
    assert result.attempts == 1
    assert result.used_fallback is False
    assert result.tokens_in == 10


def test_reprompts_then_succeeds():
    result = generate_structured(
        prompt_id="demo.v1",
        system="s",
        user="u",
        schema=Demo,
        transport=_transport_returning("not json", '{"name": "Max", "age": 5}'),
    )
    assert result.data.name == "Max"
    assert result.attempts == 2
    assert result.used_fallback is False


def test_falls_back_when_always_invalid():
    result = generate_structured(
        prompt_id="demo.v1",
        system="s",
        user="u",
        schema=Demo,
        transport=_transport_returning("bad", "still bad"),
        fallback=lambda: Demo(name="fallback", age=0),
    )
    assert result.used_fallback is True
    assert result.data.name == "fallback"


def test_raises_when_invalid_and_no_fallback():
    with pytest.raises(LLMError):
        generate_structured(
            prompt_id="demo.v1",
            system="s",
            user="u",
            schema=Demo,
            transport=_transport_returning("bad", "still bad"),
        )
