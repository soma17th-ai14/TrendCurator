"""문서 중복 제거 모듈.

1차 구현: URL 정확 일치 + 정규화된 제목 일치 기준. 먼저 등장한 항목을 보존.
semantic 중복 제거(임베딩 유사도)는 후속 plan에서 검토.
"""

import re

from app.core.models import Document

_NON_ALPHANUM_RE = re.compile(r"[^0-9a-z\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_title(title: str) -> str:
    """대소문자/공백/문장부호 차이를 제거한 비교용 제목."""
    lowered = title.lower()
    no_punct = _NON_ALPHANUM_RE.sub(" ", lowered)
    collapsed = _WHITESPACE_RE.sub(" ", no_punct).strip()
    return collapsed


def dedup(documents: list[Document]) -> list[Document]:
    """URL 정확 일치 또는 정규화 제목 일치를 중복으로 보고 제거한다.

    먼저 등장한 항목을 보존하며 입력 순서를 유지한다.
    """
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    result: list[Document] = []

    for doc in documents:
        if doc.url in seen_urls:
            continue
        normalized_title = _normalize_title(doc.title)
        if normalized_title and normalized_title in seen_titles:
            continue
        seen_urls.add(doc.url)
        if normalized_title:
            seen_titles.add(normalized_title)
        result.append(doc)

    return result
