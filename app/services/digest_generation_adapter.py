"""Digest 생성 단계 사이의 요청/결과 변환."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.models import (
    DailyDigestRetrievalResult,
    DigestGenerationRunResult,
    SolarProDigestGenerationRequest,
    SolarProDigestGenerationResult,
)


@dataclass(frozen=True)
class DigestGenerationAdapter:
    """Retriever 결과를 Generator와 후속 저장/검증 계층 계약으로 변환합니다."""

    language: str = "ko"

    def to_generation_request(
        self,
        retrieval_result: DailyDigestRetrievalResult,
        *,
        profile_keywords: list[str] | None = None,
    ) -> SolarProDigestGenerationRequest:
        return SolarProDigestGenerationRequest(
            digest_date=retrieval_result.digest_date,
            language=self.language,
            profile_keywords=profile_keywords or [],
            candidates=retrieval_result.candidates,
        )

    def to_run_result(
        self,
        *,
        retrieval_result: DailyDigestRetrievalResult,
        generation_result: SolarProDigestGenerationResult,
    ) -> DigestGenerationRunResult:
        self._validate_generation_matches_retrieval(
            retrieval_result=retrieval_result,
            generation_result=generation_result,
        )
        source_document_ids = [candidate.document_id for candidate in retrieval_result.candidates]

        # Groundedness 검사 단계에서 generation_result.groundedness_score 를 채워야 합니다.
        # 검사가 누락된 채 어댑터로 진입하는 것은 호출 측 버그이므로 명시적으로 막습니다.
        if generation_result.groundedness_score is None:
            raise ValueError(
                "Digest 생성 결과의 groundedness_score 가 비어 있습니다. "
                "Groundedness 검사 후 어댑터를 호출해야 합니다."
            )

        return DigestGenerationRunResult(
            digest_id=generation_result.digest_id,
            date=generation_result.date,
            item_count=len(generation_result.items),
            candidate_count=retrieval_result.total_count,
            selected_candidate_count=retrieval_result.selected_count,
            source_document_ids=source_document_ids,
            groundedness_score=generation_result.groundedness_score,
            digest=generation_result,
        )

    def _validate_generation_matches_retrieval(
        self,
        *,
        retrieval_result: DailyDigestRetrievalResult,
        generation_result: SolarProDigestGenerationResult,
    ) -> None:
        if generation_result.date != retrieval_result.digest_date:
            raise ValueError("Digest 생성 결과 date가 검색 결과 digest_date와 다릅니다.")

        candidate_id_set = {candidate.document_id for candidate in retrieval_result.candidates}
        unknown_item_ids = [
            item.document_id
            for item in generation_result.items
            if item.document_id not in candidate_id_set
        ]
        if unknown_item_ids:
            raise ValueError("Digest 생성 결과 item의 document_id가 검색 후보 문서에 없습니다.")

        unknown_evidence_ids = [
            evidence_id
            for item in generation_result.items
            for evidence_id in item.evidence_document_ids
            if evidence_id not in candidate_id_set
        ]
        if unknown_evidence_ids:
            raise ValueError("Digest 생성 결과 evidence_document_ids가 검색 후보 문서에 없습니다.")
