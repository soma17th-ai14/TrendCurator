from __future__ import annotations

import asyncio

from app.core.llm_client import LLMClient
from app.core.solar_client import SolarClient, SolarMessage


class SolarLLMClient(LLMClient):
    """SolarClient 기반 LLMClient 구현체"""

    def __init__(
        self,
        *,
        solar_client: SolarClient,
        model: str,
        temperature: float = 0.2,
        response_format: dict[str, str] | None = None,
    ) -> None:
        self._solar_client = solar_client
        self._model = model
        self._temperature = temperature
        self._response_format = response_format

    async def complete(self, prompt: str) -> str:
        return await asyncio.to_thread(
            self._solar_client.chat_text,
            model=self._model,
            messages=[SolarMessage(role="user", content=prompt)],
            temperature=self._temperature,
            response_format=self._response_format,
        )
