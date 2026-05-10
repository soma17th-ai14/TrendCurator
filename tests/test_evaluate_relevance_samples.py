from pathlib import Path

import pytest

from app.agents.relevance_filter import RelevanceDecision
from app.core.models import NormalizedDocument
import scripts.evaluate_relevance_samples as evaluation_script


class FakeRelevanceFilter:
    def evaluate(self, document: NormalizedDocument) -> RelevanceDecision:
        is_relevant = document.doc_id == "relevant"
        return RelevanceDecision(
            document=document,
            is_relevant=is_relevant,
            score=0.8 if is_relevant else 0.1,
            matched_keywords=[],
            reason="테스트 판정",
        )


class FakeFilterFactory:
    @classmethod
    def from_settings(cls, settings, *, fallback_on_error=True):
        return FakeRelevanceFilter()


def _sample(doc_id: str, expected: bool) -> dict:
    return {
        "document": {
            "doc_id": doc_id,
            "source": "huggingface",
            "title": "sample",
            "url": "https://example.com/sample",
            "published_date": "2026-05-08",
            "raw_text": "sample text",
            "category_hint": "agent",
            "external_id": doc_id,
            "content_hash": f"hash_{doc_id}",
            "metadata": {},
        },
        "expected_is_relevant": expected,
    }


def _patch_runtime(monkeypatch, samples: list[dict]) -> None:
    monkeypatch.setattr(evaluation_script, "load_local_env", lambda: None)
    monkeypatch.setattr(evaluation_script, "get_solar_settings", lambda: object())
    monkeypatch.setattr(evaluation_script, "load_samples", lambda path: samples)
    monkeypatch.setattr(evaluation_script, "SolarMiniLLMRelevanceFilter", FakeFilterFactory)


def test_evaluate_relevance_samples_returns_success_when_all_samples_match(monkeypatch):
    _patch_runtime(monkeypatch, [_sample("relevant", True), _sample("irrelevant", False)])

    assert evaluation_script.main() == 0


def test_evaluate_relevance_samples_returns_failure_when_any_sample_mismatches(monkeypatch):
    _patch_runtime(monkeypatch, [_sample("relevant", False)])

    assert evaluation_script.main() == 1


def test_evaluate_relevance_samples_rejects_empty_sample_file(monkeypatch, tmp_path: Path):
    sample_path = tmp_path / "samples.json"
    sample_path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(evaluation_script, "load_local_env", lambda: None)
    monkeypatch.setattr(evaluation_script, "get_solar_settings", lambda: object())
    monkeypatch.setattr(evaluation_script, "SAMPLES_PATH", sample_path)
    monkeypatch.setattr(evaluation_script, "SolarMiniLLMRelevanceFilter", FakeFilterFactory)

    with pytest.raises(RuntimeError, match="평가 샘플이 비어 있습니다"):
        evaluation_script.main()


def test_expected_is_relevant_rejects_non_bool_label():
    sample = _sample("doc_001", True)
    sample["expected_is_relevant"] = "false"

    with pytest.raises(RuntimeError, match="expected_is_relevant 값이 bool이 아닙니다"):
        evaluation_script.expected_is_relevant(sample)
