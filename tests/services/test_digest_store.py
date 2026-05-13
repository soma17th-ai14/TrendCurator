from datetime import date

import pytest

from app.core.models import DigestGenerationRunResult, DigestItem, SolarProDigestGenerationResult
from app.services.digest_store import DigestStoreError, FileDigestStore


def _run_result(digest_date: date = date(2026, 5, 6)) -> DigestGenerationRunResult:
    digest_id = f"digest_{digest_date:%Y%m%d}"
    digest = SolarProDigestGenerationResult(
        digest_id=digest_id,
        date=digest_date,
        title="AI Agent Daily Digest",
        groundedness_score=0.91,
        items=[
            DigestItem(
                document_id="doc_001",
                title="테스트 문서",
                source="huggingface",
                url="https://example.com/doc_001",
                published_at=digest_date,
                summary="핵심 요약",
                key_points=["핵심 내용"],
                contribution="주요 기여",
                benchmark="명시된 근거 없음",
                critique="명시된 근거 없음",
                tags=["agent"],
                evidence_document_ids=["doc_001"],
            )
        ],
    )
    return DigestGenerationRunResult(
        digest_id=digest_id,
        date=digest_date,
        item_count=1,
        candidate_count=3,
        selected_candidate_count=1,
        source_document_ids=["doc_001"],
        groundedness_score=0.91,
        digest=digest,
    )


def test_file_digest_store_saves_and_loads_result(tmp_path):
    store = FileDigestStore(tmp_path)
    result = _run_result()

    store.save(result)
    loaded = store.get("digest_20260506")

    assert loaded == result


def test_file_digest_store_returns_none_for_missing_digest(tmp_path):
    store = FileDigestStore(tmp_path)

    assert store.get("digest_20260506") is None


def test_file_digest_store_lists_results_by_date_desc(tmp_path):
    store = FileDigestStore(tmp_path)
    store.save(_run_result(date(2026, 5, 5)))
    store.save(_run_result(date(2026, 5, 7)))
    store.save(_run_result(date(2026, 5, 6)))

    results = store.list()

    assert [result.digest_id for result in results] == [
        "digest_20260507",
        "digest_20260506",
        "digest_20260505",
    ]


def test_file_digest_store_filters_by_date_range(tmp_path):
    store = FileDigestStore(tmp_path)
    store.save(_run_result(date(2026, 5, 5)))
    store.save(_run_result(date(2026, 5, 6)))
    store.save(_run_result(date(2026, 5, 7)))

    results = store.list(date_from=date(2026, 5, 6), date_to=date(2026, 5, 6))

    assert [result.digest_id for result in results] == ["digest_20260506"]


def test_file_digest_store_rejects_invalid_digest_id(tmp_path):
    store = FileDigestStore(tmp_path)

    with pytest.raises(DigestStoreError):
        store.get("../digest_20260506")
