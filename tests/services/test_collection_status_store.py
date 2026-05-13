import pytest

from app.services.collection_status_store import CollectionStatusStore


def test_load_collected_at_returns_none_when_file_missing(tmp_path):
    store = CollectionStatusStore(str(tmp_path / "status.json"))
    assert store.load_collected_at() is None


def test_save_and_load_collected_at(tmp_path):
    store = CollectionStatusStore(str(tmp_path / "status.json"))
    store.save_collected_at("2026-05-13T09:00:00Z")
    assert store.load_collected_at() == "2026-05-13T09:00:00Z"


def test_save_overwrites_previous(tmp_path):
    store = CollectionStatusStore(str(tmp_path / "status.json"))
    store.save_collected_at("2026-05-12T09:00:00Z")
    store.save_collected_at("2026-05-13T09:00:00Z")
    assert store.load_collected_at() == "2026-05-13T09:00:00Z"


def test_save_creates_parent_directory(tmp_path):
    store = CollectionStatusStore(str(tmp_path / "nested" / "dir" / "status.json"))
    store.save_collected_at("2026-05-13T09:00:00Z")
    assert store.load_collected_at() == "2026-05-13T09:00:00Z"
