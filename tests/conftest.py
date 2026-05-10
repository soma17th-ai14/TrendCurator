"""테스트 공통 설정."""

from __future__ import annotations

import asyncio
import sys


def pytest_configure() -> None:
    """Windows에서 Proactor 대신 Selector 이벤트 루프를 사용한다."""
    # Windows에서 pytest-asyncio 이벤트 루프 오류 방지

    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())