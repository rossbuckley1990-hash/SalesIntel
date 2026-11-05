"""What AI research costs, measured from the provider's own usage figures, and the provider to use.

Prices are list prices in US dollars per million tokens (Anthropic API reference, November 2026).
An unknown model is priced at a deliberately high rate so a limit can never be under-counted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil
from typing import Any, Callable

from app.config import Settings

Post = Callable[[dict[str, Any]], dict[str, Any]]
PRICES = {'claude-sonnet-5-5': (2.0, 10.0), 'claude-opus-5-5': (4.0, 20.0), 'claude-haiku-5-5': (0.10, 0.50), 'claude-fable-5-1': (10.0, 50.0)}
FALLBACK = (10.0, 50.0)
SEARCH_DOLLARS = 0.01  # $10 per 1,000 web searches


def cost_cents(model: str, usage: dict[str, int]) -> int:
    rate_in, rate_out = PRICES.get(model, FALLBACK)
    dollars = (usage.get('input_tokens', 0) * rate_in + usage.get('output_tokens', 0) * rate_out) / 1_000_000 + usage.get('web_searches', 0) * SEARCH_DOLLARS
    return ceil(dollars * 100)


@dataclass
class Meter:
    """Wraps a provider call and adds up what it reports it used."""
    post: Post
    model: str
    provider: str
    simulated: bool = False
    ceiling_cents: int | None = None  # stop before a call once this much has been spent
    on_call: Any = None  # records usage after every call, so a later crash cannot lose it
    usage: dict[str, int] = field(default_factory=lambda: {'input_tokens': 0, 'output_tokens': 0, 'web_searches': 0, 'calls': 0})

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.ceiling_cents is not None and self.cents >= self.ceiling_cents:
            raise ValueError('This research reached its cost ceiling and stopped before making another paid call.')
        result = self.post(payload)
        u = result.get('usage') or {}
        self.usage['input_tokens'] += int(u.get('input_tokens') or 0) + int(u.get('cache_read_input_tokens') or 0) + int(u.get('cache_creation_input_tokens') or 0)
        self.usage['output_tokens'] += int(u.get('output_tokens') or 0)
        self.usage['web_searches'] += int((u.get('server_tool_use') or {}).get('web_search_requests') or 0)
        self.usage['calls'] += 1
        if self.on_call is not None:
            self.on_call()
        return result

    @property
    def cents(self) -> int:
        return cost_cents(self.model, self.usage)

    def summary(self) -> dict[str, Any]:
        return {**self.usage, 'model': self.model, 'provider': self.provider, 'cents': self.cents, 'simulated': self.simulated}


def research_provider(settings: Settings) -> Meter | None:
    """Replayed, deterministic research in demo and test; the real provider only with a key elsewhere."""
    if settings.research_provider == 'replay' and settings.app_env in {'demo', 'test'}:
        from app.services.research_replay import replay_post
        return Meter(replay_post, 'claude-sonnet-5-5', 'replay', simulated=True)
    if settings.app_env == 'demo':
        return None  # demo never spends API credit
    if settings.anthropic_api_key:
        from app.services.opportunity_dossier import anthropic_post
        return Meter(anthropic_post(settings.anthropic_api_key, timeout=600), settings.anthropic_model, 'anthropic')
    return None


# Estimated maximum cost reserved before a job may call a provider, and the ceiling it stops at.
# Sized for live web research with search results counted as input: a Navigator run is about 100-150k input
# tokens, 8 searches and two calls; a prospect search allows up to 20 searches and longer output.
ESTIMATE_CENTS = {'contact_navigator': 150, 'prospect_search': 300, 'deep_investigation': 400, 'gap_research': 120}  # investigation includes the Navigator
