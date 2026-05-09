"""수집된 Document를 파이프라인 내부 계약으로 정규화한다."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from app.core.models import Document, NormalizedDocument


def normalize_document(document: Document) -> NormalizedDocument:
    """공통 API Document를 내부 파이프라인용 NormalizedDocument로 변환한다."""

    published_date = (
        document.published_at.isoformat()
        if document.published_at is not None
        else document.collected_at.date().isoformat()
    )
    raw_text = _build_raw_text(document)
    category_hint = _build_category_hint(document)
    external_id = _extract_external_id(document)

    return NormalizedDocument(
        doc_id=document.document_id,
        source=document.source,
        title=document.title,
        url=document.url,
        published_date=published_date,
        raw_text=raw_text,
        category_hint=category_hint,
        external_id=external_id,
        content_hash=_build_content_hash(document=document, raw_text=raw_text),
        metadata=deepcopy(document.metadata),
    )


def normalize_documents(documents: list[Document]) -> list[NormalizedDocument]:
    """여러 Document를 입력 순서 그대로 정규화한다."""

    return [normalize_document(document) for document in documents]


def _build_raw_text(document: Document) -> str:
    parts = [document.summary, document.content]
    return "\n\n".join(part.strip() for part in parts if part.strip())


def _build_category_hint(document: Document) -> str:
    parts = [document.category, *document.tags]
    return " ".join(part for part in parts if part)


def _extract_external_id(document: Document) -> str:
    metadata_external_id = document.metadata.get("external_id")
    if isinstance(metadata_external_id, str) and metadata_external_id.strip():
        return metadata_external_id.strip()
    return document.document_id


def _build_content_hash(*, document: Document, raw_text: str) -> str:
    payload: dict[str, Any] = {
        "source": document.source,
        "url": document.url,
        "title": document.title,
        "raw_text": raw_text,
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
