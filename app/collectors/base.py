"""수집기 추상 베이스.

fetch()는 외부 I/O만 담당하고, normalize()는 RawItem을 공통 Document로
변환한다. 분리 이유: I/O와 변환 로직 분리로 normalize를 fixture 기반으로
단위 테스트 가능.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import ClassVar

from pydantic import BaseModel

from app.core.models import Document, Source


class RawItem(BaseModel):
    source: Source
    payload: dict


class BaseCollector(ABC):
    source_name: ClassVar[str]

    @abstractmethod
    async def fetch(self, target_date: date) -> list[RawItem]:
        """주어진 날짜에 해당하는 raw 데이터를 외부 소스에서 가져온다."""

    @abstractmethod
    def normalize(self, item: RawItem) -> Document:
        """source-specific RawItem을 공통 Document로 변환한다."""
