from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

import scripts.run_scheduled_digest as entrypoint
from app.core.models import (
    DailyDigestRetrievalResult,
    DigestCandidate,
    DigestItem,
    SolarProDigestGenerationResult,
)
from app.services.scheduler import SchedulerConfig, SchedulerService, SchedulerState


SEOUL = timezone(timedelta(hours=9), name="Asia/Seoul")


# ---------------------------------------------------------------------------
# run_once 동작 테스트
# ---------------------------------------------------------------------------

def test_run_once_skips_before_scheduled_time(capsys) -> None:
    scheduler = SchedulerService(SchedulerState(config=SchedulerConfig(time="09:00")))

    exit_code = entrypoint.run_once(
        scheduler,
        datetime(2026, 5, 6, 8, 0, tzinfo=SEOUL),
    )

    assert exit_code == entrypoint.EXIT_SUCCESS
    output = capsys.readouterr().out
    assert "스케줄 실행 대상이 아닙니다." in output
    assert "reason=before_scheduled_time" in output


def test_run_once_executes_configured_pipeline(monkeypatch, capsys) -> None:
    scheduler = SchedulerService(SchedulerState(config=SchedulerConfig(time="09:00")))
    calls = []

    def fake_pipeline(run_date, config):
        calls.append((run_date, config.sources))
        return "digest_20260506"

    monkeypatch.setattr(entrypoint, "run_daily_digest_pipeline", fake_pipeline)

    exit_code = entrypoint.run_once(
        scheduler,
        datetime(2026, 5, 6, 9, 0, tzinfo=SEOUL),
    )

    assert exit_code == entrypoint.EXIT_SUCCESS
    assert calls == [
        (
            datetime(2026, 5, 6, tzinfo=SEOUL).date(),
            ("huggingface", "hackernews"),
        )
    ]
    assert "스케줄 실행 완료" in capsys.readouterr().out


def test_run_once_prints_no_job_id_when_pipeline_returns_none(monkeypatch, capsys) -> None:
    scheduler = SchedulerService(SchedulerState(config=SchedulerConfig(time="09:00")))
    monkeypatch.setattr(entrypoint, "run_daily_digest_pipeline", lambda d, c: None)

    exit_code = entrypoint.run_once(
        scheduler,
        datetime(2026, 5, 6, 9, 0, tzinfo=SEOUL),
    )

    assert exit_code == entrypoint.EXIT_SUCCESS
    assert "job_id=없음" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# run_daily_digest_pipeline 단위 테스트
# ---------------------------------------------------------------------------

def _make_candidate(document_id: str = "doc_001") -> DigestCandidate:
    return DigestCandidate(
        document_id=document_id,
        source="huggingface",
        title=f"Candidate {document_id}",
        url=f"https://example.com/{document_id}",
        published_at=date(2026, 5, 12),
        content="Agent workflow content",
        summary_preview="Agent workflow summary",
        similarity_score=0.87,
        relevance_score=0.93,
        matched_keywords=["agent"],
        tags=["agent"],
        metadata={},
    )


def _make_item(document_id: str = "doc_001") -> DigestItem:
    return DigestItem(
        document_id=document_id,
        title=f"Candidate {document_id}",
        source="huggingface",
        url=f"https://example.com/{document_id}",
        published_at=date(2026, 5, 12),
        summary="핵심 요약",
        key_points=["핵심 내용"],
        contribution="주요 기여",
        benchmark="명시된 근거 없음",
        critique="명시된 근거 없음",
        tags=["agent"],
        evidence_document_ids=[document_id],
    )


def _mock_retriever(monkeypatch, retrieval_result: DailyDigestRetrievalResult) -> None:
    """외부 의존 전체를 목킹하고 DailyDigestRetriever가 지정된 결과를 반환하게 합니다."""
    monkeypatch.setattr(entrypoint, "get_settings", lambda: MagicMock())
    monkeypatch.setattr(entrypoint, "get_solar_settings", lambda: MagicMock())
    monkeypatch.setattr(entrypoint, "EmbeddingClient", lambda settings: MagicMock())
    monkeypatch.setattr(entrypoint, "ChromaClient", lambda settings: MagicMock())
    monkeypatch.setattr(entrypoint, "Retriever", lambda emb, chroma: MagicMock())

    mock_retriever_instance = MagicMock()
    mock_retriever_instance.retrieve.return_value = retrieval_result
    monkeypatch.setattr(
        entrypoint, "DailyDigestRetriever", lambda retriever: mock_retriever_instance
    )


def test_pipeline_returns_digest_id_when_candidates_found(monkeypatch) -> None:
    candidate = _make_candidate("doc_001")
    retrieval_result = DailyDigestRetrievalResult(
        digest_date=date(2026, 5, 12),
        candidates=[candidate],
        total_count=1,
        selected_count=1,
    )
    _mock_retriever(monkeypatch, retrieval_result)

    generation_result = SolarProDigestGenerationResult(
        digest_id="digest_20260512",
        date=date(2026, 5, 12),
        title="AI Agent Daily Digest",
        items=[_make_item("doc_001")],
        groundedness_score=0.85,
    )
    mock_generator = MagicMock()
    mock_generator.generate.return_value = generation_result
    monkeypatch.setattr(
        entrypoint,
        "SolarProDigestGenerator",
        MagicMock(from_settings=lambda settings: mock_generator),
    )

    result = entrypoint.run_daily_digest_pipeline(
        date(2026, 5, 12), SchedulerConfig()
    )

    assert result == "digest_20260512"
    mock_generator.generate.assert_called_once()


def test_pipeline_returns_none_when_no_candidates_found(monkeypatch, capsys) -> None:
    empty_retrieval = DailyDigestRetrievalResult(
        digest_date=date(2026, 5, 12),
        candidates=[],
        total_count=0,
        selected_count=0,
    )
    _mock_retriever(monkeypatch, empty_retrieval)

    result = entrypoint.run_daily_digest_pipeline(
        date(2026, 5, 12), SchedulerConfig()
    )

    assert result is None
    assert "후보 문서가 없어" in capsys.readouterr().out


def test_pipeline_passes_config_sources_to_retrieval_request(monkeypatch) -> None:
    candidate = _make_candidate("doc_001")
    retrieval_result = DailyDigestRetrievalResult(
        digest_date=date(2026, 5, 12),
        candidates=[candidate],
        total_count=1,
        selected_count=1,
    )

    monkeypatch.setattr(entrypoint, "get_settings", lambda: MagicMock())
    monkeypatch.setattr(entrypoint, "get_solar_settings", lambda: MagicMock())
    monkeypatch.setattr(entrypoint, "EmbeddingClient", lambda settings: MagicMock())
    monkeypatch.setattr(entrypoint, "ChromaClient", lambda settings: MagicMock())
    monkeypatch.setattr(entrypoint, "Retriever", lambda emb, chroma: MagicMock())

    captured_requests = []
    mock_retriever_instance = MagicMock()
    mock_retriever_instance.retrieve.side_effect = lambda req: (
        captured_requests.append(req) or retrieval_result
    )
    monkeypatch.setattr(
        entrypoint, "DailyDigestRetriever", lambda retriever: mock_retriever_instance
    )

    generation_result = SolarProDigestGenerationResult(
        digest_id="digest_20260512",
        date=date(2026, 5, 12),
        title="AI Agent Daily Digest",
        items=[_make_item("doc_001")],
        groundedness_score=0.85,
    )
    mock_generator = MagicMock()
    mock_generator.generate.return_value = generation_result
    monkeypatch.setattr(
        entrypoint,
        "SolarProDigestGenerator",
        MagicMock(from_settings=lambda settings: mock_generator),
    )

    config = SchedulerConfig(sources=("huggingface",))
    entrypoint.run_daily_digest_pipeline(date(2026, 5, 12), config)

    assert len(captured_requests) == 1
    assert captured_requests[0].digest_date == date(2026, 5, 12)
    assert list(captured_requests[0].sources) == ["huggingface"]
