"""effective_digest_date 헬퍼 동작 테스트.

발행 시각 이전엔 어제, 이후엔 오늘이 효력 일자로 잡혀야 한다.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.services.scheduler import SchedulerConfig, effective_digest_date


SEOUL = timezone(timedelta(hours=9), name="Asia/Seoul")
UTC = timezone.utc


def _config(time: str = "09:00", tz: str = "Asia/Seoul") -> SchedulerConfig:
    return SchedulerConfig(enabled=True, time=time, timezone=tz)


def test_before_scheduled_time_returns_yesterday():
    """발행 시각 이전엔 어제 일자를 반환한다."""
    config = _config(time="09:00")
    now = datetime(2026, 5, 14, 8, 30, tzinfo=SEOUL)

    assert effective_digest_date(config, now=now) == date(2026, 5, 13)


def test_at_scheduled_time_returns_today():
    """발행 시각 정각엔 오늘 일자를 반환한다 (경계 포함)."""
    config = _config(time="09:00")
    now = datetime(2026, 5, 14, 9, 0, tzinfo=SEOUL)

    assert effective_digest_date(config, now=now) == date(2026, 5, 14)


def test_after_scheduled_time_returns_today():
    """발행 시각 이후엔 오늘 일자를 반환한다."""
    config = _config(time="09:00")
    now = datetime(2026, 5, 14, 18, 0, tzinfo=SEOUL)

    assert effective_digest_date(config, now=now) == date(2026, 5, 14)


def test_midnight_returns_yesterday():
    """자정 직후엔 어제 일자를 반환한다."""
    config = _config(time="09:00")
    now = datetime(2026, 5, 14, 0, 0, 1, tzinfo=SEOUL)

    assert effective_digest_date(config, now=now) == date(2026, 5, 13)


def test_naive_datetime_is_interpreted_in_config_timezone():
    """tz 정보 없는 datetime은 config 타임존으로 해석한다."""
    config = _config(time="09:00", tz="Asia/Seoul")
    now = datetime(2026, 5, 14, 8, 0)  # naive — Seoul로 해석되면 어제

    assert effective_digest_date(config, now=now) == date(2026, 5, 13)


def test_utc_now_converted_to_local_for_judgment():
    """UTC 기준 시각이 들어와도 config 타임존으로 변환해 비교한다.

    UTC 23:00 = Seoul 08:00 다음 날 → Seoul 시간 발행시각(09:00) 이전이므로 어제 판정.
    """
    config = _config(time="09:00", tz="Asia/Seoul")
    now = datetime(2026, 5, 13, 23, 0, tzinfo=UTC)  # = 2026-05-14 08:00 KST

    assert effective_digest_date(config, now=now) == date(2026, 5, 13)


def test_default_now_uses_config_timezone(monkeypatch):
    """now 인자 생략 시 config 타임존 기준 현재 시각을 사용한다."""
    config = _config(time="09:00", tz="Asia/Seoul")
    fixed = datetime(2026, 5, 14, 7, 0, tzinfo=SEOUL)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed if tz is None else fixed.astimezone(tz)

    monkeypatch.setattr("app.services.scheduler.datetime", _FrozenDateTime)

    assert effective_digest_date(config) == date(2026, 5, 13)
