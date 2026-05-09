"""LLM 호출 추상화.

`LLMClient` Protocol은 텍스트 프롬프트를 받아 텍스트 응답을 반환하는 단일 인터페이스를
정의한다. 구체 Adapter(OpenAI/Anthropic/Ollama 등)는 별도 모듈에서 이 Protocol을 구현한다.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    async def complete(self, prompt: str) -> str:
        """주어진 프롬프트에 대한 LLM 응답을 반환한다."""
        ...
