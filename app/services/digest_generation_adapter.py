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

        candidate_ids = [candidate.document_id for candidate in retrieval_result.candidates]
        item_ids = [item.document_id for item in generation_result.items]
        if item_ids != candidate_ids:
            raise ValueError("Digest 생성 결과 item 순서가 검색 후보 문서와 일치하지 않습니다.")

        candidate_id_set = set(candidate_ids)
        unknown_evidence_ids = [
            evidence_id
            for item in generation_result.items
            for evidence_id in item.evidence_document_ids
            if evidence_id not in candidate_id_set
        ]
        if unknown_evidence_ids:
            raise ValueError("Digest 생성 결과 evidence_document_ids가 검색 후보 문서에 없습니다.")
