"""Solar Mini 관련성 필터 smoke test를 실행합니다.

이 스크립트는 로컬 .env 값을 읽지만 비밀값은 출력하지 않습니다.
실제 Solar API를 호출하므로 API 사용량과 쿼터를 소모합니다.
"""

from __future__ import annotations

from pathlib import Path
import os
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.agents.solar_relevance_filter import SolarMiniLLMRelevanceFilter
from app.core.models import NormalizedDocument
from app.core.settings import get_solar_settings


def load_local_env(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def make_sample_document() -> NormalizedDocument:
    return NormalizedDocument(
        doc_id="smoke_001",
        title="LangGraph multi-agent workflow benchmark",
        source="huggingface",
        url="https://example.com/smoke",
        published_date="2026-05-08",
        raw_text=(
            "This paper evaluates multi-agent orchestration, tool-use agents, "
            "memory, and workflow planning."
        ),
        category_hint="multi-agent workflow",
        external_id="smoke_001",
        content_hash="hash_smoke_001",
        metadata={"authors": ["Smoke Author"]},
    )


def main() -> None:
    load_local_env()
    settings = get_solar_settings()
    relevance_filter = SolarMiniLLMRelevanceFilter.from_settings(settings, fallback_on_error=False)
    decision = relevance_filter.evaluate(make_sample_document())

    print("Solar Mini relevance smoke test")
    print(f"is_relevant: {decision.is_relevant}")
    print(f"score: {decision.score}")
    print(f"matched_keywords: {', '.join(decision.matched_keywords)}")
    print(f"reason: {decision.reason}")


if __name__ == "__main__":
    main()
