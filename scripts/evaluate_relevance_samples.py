"""라벨된 샘플 문서로 관련성 필터를 평가합니다.

실제 Solar API를 호출하므로 API 사용량과 쿼터를 소모합니다.
"""

from __future__ import annotations

from pathlib import Path
import json
import os
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"
SAMPLES_PATH = ROOT_DIR / "data" / "samples" / "relevance_eval_documents.json"

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


def load_samples(path: Path = SAMPLES_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def expected_is_relevant(sample: dict) -> bool:
    expected = sample.get("expected_is_relevant")
    if not isinstance(expected, bool):
        doc_id = sample.get("document", {}).get("doc_id", "<unknown>")
        raise RuntimeError(f"{doc_id} 샘플의 expected_is_relevant 값이 bool이 아닙니다.")
    return expected


def main() -> int:
    load_local_env()
    settings = get_solar_settings()
    relevance_filter = SolarMiniLLMRelevanceFilter.from_settings(settings, fallback_on_error=False)
    samples = load_samples(SAMPLES_PATH)

    correct = 0
    false_positive = 0
    false_negative = 0
    rows = []

    for sample in samples:
        document = NormalizedDocument(**sample["document"])
        expected = expected_is_relevant(sample)
        decision = relevance_filter.evaluate(document)
        predicted = decision.is_relevant
        correct += int(predicted == expected)
        false_positive += int(predicted and not expected)
        false_negative += int(not predicted and expected)
        rows.append(
            {
                **decision.to_response(),
                "expected_is_relevant": expected,
                "passed": predicted == expected,
            }
        )

    total = len(samples)
    if total == 0:
        raise RuntimeError("관련성 평가 샘플이 비어 있습니다.")

    print("Solar Mini relevance evaluation")
    print(f"total: {total}")
    print(f"accuracy: {correct / total:.3f}")
    print(f"false_positive: {false_positive}")
    print(f"false_negative: {false_negative}")
    print("failed_documents:")
    for row in rows:
        if not row["passed"]:
            print(
                f"- {row['doc_id']}: expected={row['expected_is_relevant']} "
                f"predicted={row['is_relevant']} score={row['score']} reason={row['reason']}"
            )
    return 0 if correct == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
