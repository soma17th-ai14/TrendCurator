"""Daily Digest 생성기와 응답 파서.

이 모듈은 Solar Pro 3 호출과 모델 응답을 내부 Digest 계약으로 검증하는
책임을 가진다. 검색, 저장, Groundedness 검증은 서비스 계층에서 조합한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from app.core.models import (
    DigestCandidate,
    SolarProDigestGenerationRequest,
    SolarProDigestGenerationResult,
)
from app.core.settings import SolarSettings
from app.core.solar_client import SolarClient, SolarMessage


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "solar_pro_digest.md"


class SolarTextClient(Protocol):
    def chat_text(
        self,
        *,
        model: str,
        messages: list[SolarMessage],
        temperature: float = 0.2,
        response_format: dict[str, str] | None = None,
    ) -> str:
        ...


@dataclass(frozen=True)
class SolarProDigestGenerator:
    """Solar Pro 3를 호출해 Daily Digest 생성 결과를 반환합니다."""

    client: SolarTextClient
    settings: SolarSettings
    parser: SolarProDigestResponseParser = field(default_factory=lambda: SolarProDigestResponseParser())
    system_prompt: str = field(default_factory=lambda: load_solar_pro_digest_prompt())

    @classmethod
    def from_settings(cls, settings: SolarSettings) -> "SolarProDigestGenerator":
        return cls(client=SolarClient(settings), settings=settings)

    def generate(
        self,
        request: SolarProDigestGenerationRequest,
    ) -> SolarProDigestGenerationResult:
        try:
            raw_response = self.client.chat_text(
                model=self.settings.digest_model,
                messages=[
                    SolarMessage(role="system", content=self.system_prompt),
                    SolarMessage(role="user", content=self._format_request(request)),
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise RuntimeError("Solar Pro Digest 생성 호출이 실패했습니다.") from exc

        return self.parser.parse(raw_response, request=request)

    def _format_request(self, request: SolarProDigestGenerationRequest) -> str:
        return json.dumps(request.model_dump(mode="json"), ensure_ascii=False)


class SolarProDigestResponseParser:
    """Solar Pro 3 Digest JSON 응답을 내부 결과 모델로 변환합니다."""

    def parse(
        self,
        response: str | dict[str, Any],
        *,
        request: SolarProDigestGenerationRequest,
    ) -> SolarProDigestGenerationResult:
        payload = self._parse_payload(response)
        self._validate_evidence_ids(payload, request.candidates)

        try:
            result = SolarProDigestGenerationResult(**payload)
        except ValidationError as exc:
            raise ValueError("Solar Pro Digest 응답이 생성 결과 계약과 맞지 않습니다.") from exc

        if result.date != request.digest_date:
            raise ValueError("Solar Pro Digest 응답의 date가 요청 digest_date와 다릅니다.")

        expected_digest_id = f"digest_{request.digest_date:%Y%m%d}"
        if result.digest_id != expected_digest_id:
            raise ValueError("Solar Pro Digest 응답의 digest_id가 요청 digest_date와 맞지 않습니다.")

        invalid_models = [
            item.llm_model for item in result.items if item.llm_model != "solar-pro-3"
        ]
        if invalid_models:
            raise ValueError("Digest item의 llm_model은 solar-pro-3이어야 합니다.")

        return result

    def _parse_payload(self, response: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(response, dict):
            return response

        try:
            parsed = json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError("Solar Pro Digest 응답을 JSON으로 해석할 수 없습니다.") from exc

        if not isinstance(parsed, dict):
            raise ValueError("Solar Pro Digest 응답은 JSON 객체여야 합니다.")

        return parsed

    def _validate_evidence_ids(
        self,
        payload: dict[str, Any],
        candidates: list[DigestCandidate],
    ) -> None:
        candidate_ids = [candidate.document_id for candidate in candidates]
        candidate_id_set = set(candidate_ids)
        items = payload.get("items")
        if not isinstance(items, list):
            raise ValueError("Solar Pro Digest 응답의 items 값이 유효하지 않습니다.")

        item_ids = [
            item.get("document_id")
            for item in items
            if isinstance(item, dict)
        ]
        if item_ids != candidate_ids:
            raise ValueError("Digest items의 document_id 순서가 후보 문서와 일치해야 합니다.")

        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Solar Pro Digest 응답의 item 값이 유효하지 않습니다.")

            document_id = item.get("document_id")
            if document_id not in candidate_id_set:
                raise ValueError("Digest item의 document_id가 후보 문서에 없습니다.")

            evidence_ids = item.get("evidence_document_ids")
            if not isinstance(evidence_ids, list) or not evidence_ids:
                raise ValueError("Digest item에는 evidence_document_ids가 필요합니다.")

            unknown_ids = [doc_id for doc_id in evidence_ids if doc_id not in candidate_id_set]
            if unknown_ids:
                raise ValueError("Digest item의 evidence_document_ids가 후보 문서에 없습니다.")


def load_solar_pro_digest_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")
