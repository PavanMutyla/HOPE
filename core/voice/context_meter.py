from dataclasses import dataclass

from loguru import logger
from pipecat.metrics.metrics import LLMTokenUsage


def resolve_context_limit(model: str, fallback: int) -> int:
    """The model's real input-context window, or `fallback` for models litellm
    doesn't know (custom/local names, aliases). litellm is slow to import, so
    the import is local — this is called once at pipeline build."""
    try:
        import litellm

        info = litellm.get_model_info(model)
        limit = info.get("max_input_tokens") or info.get("max_tokens")
        return int(limit) if limit else fallback
    except Exception:
        logger.info(f"No context window for '{model}' in litellm; using {fallback}")
        return fallback


@dataclass
class ContextMeter:
    """Tracks LLM token usage per turn. context_tokens approximates the live
    context size using the last call's prompt+completion (the next prompt
    contains everything the last one did, plus the last completion)."""

    context_limit: int
    threshold: float = 0.9
    last_prompt_tokens: int = 0
    last_completion_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    last_ttfb: float = 0.0

    def record_usage(self, usage: LLMTokenUsage) -> None:
        self.last_prompt_tokens = usage.prompt_tokens
        self.last_completion_tokens = usage.completion_tokens
        self.total_prompt_tokens += usage.prompt_tokens
        self.total_completion_tokens += usage.completion_tokens

    def record_ttfb(self, seconds: float) -> None:
        self.last_ttfb = seconds

    @property
    def context_tokens(self) -> int:
        return self.last_prompt_tokens + self.last_completion_tokens


    @property
    def context_pct(self) -> float:
        if self.context_limit <= 0:
            return 0.0
        return self.context_tokens / self.context_limit

    def should_summarize(self) -> bool:
        return self.context_limit > 0 and self.context_pct >= self.threshold
