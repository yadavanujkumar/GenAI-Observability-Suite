from __future__ import annotations

import asyncio
from typing import Callable, List, Tuple

from app.core.config import get_settings

settings = get_settings()

ProviderFn = Callable[[List[dict], float], asyncio.Future]


class FallbackManager:
    """Sequential fallback over multiple provider callables."""

    def __init__(self, providers: List[Tuple[str, ProviderFn]]) -> None:
        self.providers = providers

    async def generate(self, messages: List[dict], temperature: float = 0.7) -> Tuple[str, str]:
        errors = []
        for name, provider_fn in self.providers:
            try:
                answer = await provider_fn(messages, temperature)
                return answer, name
            except Exception as exc:  # noqa: BLE001
                errors.append((name, str(exc)))
                continue
        raise RuntimeError(f"All providers failed: {errors}")
