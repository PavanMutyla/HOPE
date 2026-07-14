"""Unit tests for ContextMeter."""

import pytest
from pipecat.metrics.metrics import LLMTokenUsage

from core.voice.context_meter import ContextMeter, resolve_context_limit


def usage(prompt: int, completion: int) -> LLMTokenUsage:
    return LLMTokenUsage(
        prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion
    )


@pytest.mark.unit
def test_initial_state_zero():
    meter = ContextMeter(context_limit=1000)
    assert meter.context_tokens == 0
    assert meter.context_pct == 0.0
    assert not meter.should_summarize()


@pytest.mark.unit
def test_record_usage_updates_last_and_totals():
    meter = ContextMeter(context_limit=1000)
    meter.record_usage(usage(100, 20))
    meter.record_usage(usage(150, 30))
    assert meter.last_prompt_tokens == 150
    assert meter.last_completion_tokens == 30
    assert meter.total_prompt_tokens == 250
    assert meter.total_completion_tokens == 50


@pytest.mark.unit
def test_context_tokens_is_last_prompt_plus_completion():
    # last prompt + completion ≈ what the NEXT call's prompt will contain
    meter = ContextMeter(context_limit=1000)
    meter.record_usage(usage(400, 50))
    assert meter.context_tokens == 450
    assert meter.context_pct == 0.45


@pytest.mark.unit
def test_should_summarize_fires_at_threshold_not_before():
    meter = ContextMeter(context_limit=1000, threshold=0.9)
    meter.record_usage(usage(890, 9))   # 899 = 89.9%
    assert not meter.should_summarize()
    meter.record_usage(usage(880, 20))  # 900 = exactly 90%
    assert meter.should_summarize()


@pytest.mark.unit
def test_zero_limit_never_summarizes():
    meter = ContextMeter(context_limit=0)
    meter.record_usage(usage(100, 10))
    assert meter.context_pct == 0.0
    assert not meter.should_summarize()


@pytest.mark.unit
def test_record_ttfb():
    meter = ContextMeter(context_limit=1000)
    meter.record_ttfb(0.42)
    assert meter.last_ttfb == 0.42


@pytest.mark.unit
def test_resolve_context_limit_known_model():
    # a model litellm ships in its registry — real window, not the fallback
    assert resolve_context_limit("gpt-4o", fallback=1) == 128000


@pytest.mark.unit
def test_resolve_context_limit_unknown_model_uses_fallback():
    assert resolve_context_limit("totally-made-up-model-xyz", fallback=4242) == 4242
