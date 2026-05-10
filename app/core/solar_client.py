"""Solar API 호출을 위한 최소 클라이언트 경계."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.settings import SolarSettings


@dataclass(frozen=True)
class SolarMessage:
    role: str
    content: str


class SolarClient:
    """Solar 모델용 간단한 chat completions 클라이언트입니다.

    요청 형식은 Solar 호환 엔드포인트에서 흔히 사용하는
    OpenAI 호환 chat completions 형식을 따릅니다.
    """

    def __init__(self, settings: SolarSettings, timeout_seconds: int = 30) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    def chat_json(
        self,
        *,
        model: str,
        messages: list[SolarMessage],
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        content = self.chat_text(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Solar 응답을 JSON으로 해석할 수 없습니다.") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("Solar JSON 응답이 객체 형식이 아닙니다.")
        return parsed

    def chat_text(
        self,
        *,
        model: str,
        messages: list[SolarMessage],
        temperature: float = 0.2,
        response_format: dict[str, str] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [message.__dict__ for message in messages],
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        request = Request(
            url=f"{self.settings.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("Solar API 응답 본문을 JSON으로 해석할 수 없습니다.") from exc
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Solar API 요청이 실패했습니다: {exc.code} {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Solar API에 연결할 수 없습니다: {exc.reason}") from exc

        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Solar API 응답 형식이 올바르지 않습니다.") from exc
