from datetime import datetime, timezone
from types import SimpleNamespace

from app.services import scheduled_pipeline
from app.services.scheduled_pipeline import demo_bootstrap_dates, run_demo_bootstrap
from app.services.scheduler import SchedulerConfig


SEOUL = timezone.utc


def test_demo_bootstrap_dates_returns_previous_five_effective_dates():
    config = SchedulerConfig(time="09:00", timezone="UTC")
    now = datetime(2026, 5, 14, 10, 0, tzinfo=SEOUL)

    dates = demo_bootstrap_dates(config, days=5, now=now)

    assert [d.isoformat() for d in dates] == [
        "2026-05-09",
        "2026-05-10",
        "2026-05-11",
        "2026-05-12",
        "2026-05-13",
    ]


def test_demo_bootstrap_dates_uses_previous_effective_date_before_cutoff():
    config = SchedulerConfig(time="09:00", timezone="UTC")
    now = datetime(2026, 5, 14, 8, 30, tzinfo=SEOUL)

    dates = demo_bootstrap_dates(config, days=3, now=now)

    assert [d.isoformat() for d in dates] == [
        "2026-05-10",
        "2026-05-11",
        "2026-05-12",
    ]


def test_run_demo_bootstrap_skips_existing_digest_and_generates_missing(monkeypatch):
    class FakeStore:
        def __init__(self, path):
            self.path = path

        def get(self, digest_id):
            return object() if digest_id == "digest_20260510" else None

    calls = []

    def fake_run_pipeline(run_date, config):
        calls.append(run_date.isoformat())
        return f"digest_{run_date:%Y%m%d}"

    monkeypatch.setattr(
        scheduled_pipeline,
        "demo_bootstrap_dates",
        lambda config, days=5: [
            datetime(2026, 5, 10).date(),
            datetime(2026, 5, 11).date(),
        ],
    )
    monkeypatch.setattr(scheduled_pipeline, "get_settings", lambda: SimpleNamespace(digest_data_path="x"))
    monkeypatch.setattr(scheduled_pipeline, "FileDigestStore", FakeStore)
    monkeypatch.setattr(scheduled_pipeline, "run_pipeline", fake_run_pipeline)

    generated = run_demo_bootstrap(SchedulerConfig(), days=2)

    assert calls == ["2026-05-11"]
    assert generated == ["digest_20260511"]


def test_run_demo_bootstrap_continues_after_one_date_fails(monkeypatch):
    class FakeStore:
        def __init__(self, path):
            self.path = path

        def get(self, digest_id):
            return None

    calls = []

    def fake_run_pipeline(run_date, config):
        calls.append(run_date.isoformat())
        if run_date.isoformat() == "2026-05-10":
            raise scheduled_pipeline.PipelineRunError("boom")
        return f"digest_{run_date:%Y%m%d}"

    monkeypatch.setattr(
        scheduled_pipeline,
        "demo_bootstrap_dates",
        lambda config, days=5: [
            datetime(2026, 5, 10).date(),
            datetime(2026, 5, 11).date(),
        ],
    )
    monkeypatch.setattr(scheduled_pipeline, "get_settings", lambda: SimpleNamespace(digest_data_path="x"))
    monkeypatch.setattr(scheduled_pipeline, "FileDigestStore", FakeStore)
    monkeypatch.setattr(scheduled_pipeline, "run_pipeline", fake_run_pipeline)

    generated = run_demo_bootstrap(SchedulerConfig(), days=2)

    assert calls == ["2026-05-10", "2026-05-11"]
    assert generated == ["digest_20260511"]
