"""질의 오케스트레이션용 프롬프트 로더."""

from __future__ import annotations

from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parent


def load_query_intent_router_prompt() -> str:
    return (PROMPT_DIR / "query_intent_router.md").read_text(encoding="utf-8")


def load_query_rewriter_prompt() -> str:
    return (PROMPT_DIR / "query_rewriter.md").read_text(encoding="utf-8")


def load_query_date_range_parser_prompt() -> str:
    return (PROMPT_DIR / "query_date_range_parser.md").read_text(encoding="utf-8")
