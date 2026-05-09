"""Daily Digest 생성 응답 파서.

이 모듈은 Solar Pro 2 호출 자체가 아니라, 모델 응답을 내부 Digest 계약으로
검증하는 책임만 가진다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.models import (
    DigestCandidate,
    SolarProDigestGenerationRequest,
    SolarProDigestGenerationResult,
)


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "solar_pro_digest.md"


class SolarProDigestResponseParser:
    """Solar Pro 2 Digest JSON 응답을 내부 결과 모델로 변환합니다."""

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
        candidate_ids = {candidate.document_id for candidate in candidates}
        items = payload.get("items")
        if not isinstance(items, list):
            raise ValueError("Solar Pro Digest 응답의 items 값이 유효하지 않습니다.")

        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Solar Pro Digest 응답의 item 값이 유효하지 않습니다.")

            document_id = item.get("document_id")
            if document_id not in candidate_ids:
                raise ValueError("Digest item의 document_id가 후보 문서에 없습니다.")

            evidence_ids = item.get("evidence_document_ids")
            if not isinstance(evidence_ids, list) or not evidence_ids:
                raise ValueError("Digest item에는 evidence_document_ids가 필요합니다.")

            unknown_ids = [doc_id for doc_id in evidence_ids if doc_id not in candidate_ids]
            if unknown_ids:
                raise ValueError("Digest item의 evidence_document_ids가 후보 문서에 없습니다.")


def load_solar_pro_digest_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")
