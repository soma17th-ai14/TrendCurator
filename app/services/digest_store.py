"""Daily Digest 저장소.

생성된 Digest 실행 결과를 후속 조회 API와 Dashboard가 재사용할 수 있도록
파일 기반 JSON 저장소로 영속화한다.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.core.models import DigestGenerationRunResult


class DigestStoreError(RuntimeError):
    """Digest 저장소를 읽거나 쓸 수 없을 때 발생합니다."""


class FileDigestStore:
    """DigestGenerationRunResult를 digest_id 단위 JSON 파일로 저장합니다."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def save(self, result: DigestGenerationRunResult) -> DigestGenerationRunResult:
        self._root.mkdir(parents=True, exist_ok=True)
        payload = result.model_dump(mode="json")
        target = self._path_for(result.digest_id)

        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._root,
                delete=False,
                suffix=".tmp",
            ) as temp_file:
                json.dump(payload, temp_file, ensure_ascii=False, indent=2)
                temp_file.write("\n")
                temp_path = Path(temp_file.name)
            temp_path.replace(target)
        except OSError as exc:
            raise DigestStoreError(f"Digest 저장 실패: {result.digest_id}") from exc

        return result

    def get(self, digest_id: str) -> DigestGenerationRunResult | None:
        path = self._path_for(digest_id)
        if not path.exists():
            return None

        return self._load(path)

    def list(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[DigestGenerationRunResult]:
        if not self._root.exists():
            return []

        results = [self._load(path) for path in self._root.glob("digest_*.json")]
        filtered = []
        for result in results:
            if date_from is not None and result.date < date_from:
                continue
            if date_to is not None and result.date > date_to:
                continue
            filtered.append(result)

        return sorted(filtered, key=lambda item: (item.date, item.digest_id), reverse=True)

    def latest(self) -> DigestGenerationRunResult | None:
        if not self._root.exists():
            return None

        latest_path = max(
            self._root.glob("digest_*.json"),
            key=lambda path: path.stem,
            default=None,
        )
        if latest_path is None:
            return None

        return self._load(latest_path)

    def _path_for(self, digest_id: str) -> Path:
        if not digest_id.startswith("digest_") or any(char in digest_id for char in "\\/:"):
            raise DigestStoreError(f"유효하지 않은 digest_id: {digest_id}")
        return self._root / f"{digest_id}.json"

    def _load(self, path: Path) -> DigestGenerationRunResult:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return DigestGenerationRunResult(**payload)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise DigestStoreError(f"Digest 조회 실패: {path.name}") from exc
