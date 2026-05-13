"""TrendCurator 사용자용 Streamlit UI."""

from __future__ import annotations

from datetime import date, timedelta
import os
from typing import Any

import requests
import streamlit as st


API_BASE_URL = os.getenv("TRENDCURATOR_API_BASE_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"

CATEGORY_OPTIONS = {
    "AI Agent": "agent",
    "LangGraph": "langgraph",
    "RAG": "rag",
    "LLM": "llm",
    "Benchmark": "benchmark",
    "Multimodal": "multimodal",
    "Open Source": "open-source",
}
SOURCE_OPTIONS = {
    "Hugging Face": "huggingface",
    "Hacker News": "hackernews",
}


st.set_page_config(page_title="TrendCurator", page_icon="TC", layout="wide")


def api_get(path: str) -> dict[str, Any]:
    response = requests.get(f"{API_BASE_URL}{path}", timeout=20)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    response = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def error_message(payload: dict[str, Any], fallback: str) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        code = error.get("code")
        return f"{code}: {message}" if code and message else message or fallback
    if isinstance(error, str):
        return error
    return fallback


def selected_values(labels: list[str], options: dict[str, str]) -> list[str]:
    return [options[label] for label in labels]


def keyword_list(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def render_result_item(item: dict[str, Any], index: int) -> None:
    title = item.get("title") or item.get("document_id") or f"결과 {index}"
    with st.container(border=True):
        top = st.columns([0.64, 0.18, 0.18])
        top[0].markdown(f"**{index}. {title}**")
        top[1].metric("Relevance", f"{item.get('relevance_score', 0.0):.2f}")
        top[2].metric("Similarity", f"{item.get('similarity_score', 0.0):.2f}")

        meta = []
        if item.get("source"):
            meta.append(str(item["source"]))
        if item.get("published_at"):
            meta.append(str(item["published_at"]))
        if meta:
            st.caption(" | ".join(meta))

        st.write(item.get("summary_preview") or "요약 정보가 없습니다.")
        keywords = item.get("matched_keywords") or []
        if keywords:
            st.caption("키워드: " + ", ".join(keywords))
        if item.get("url"):
            st.link_button("원문 열기", item["url"])


def render_sources(sources: list[dict[str, Any]]) -> None:
    if not sources:
        st.info("검색된 근거 문서가 없습니다.")
        return

    for index, source in enumerate(sources, start=1):
        title = source.get("title") or source.get("document_id") or f"근거 {index}"
        with st.container(border=True):
            st.markdown(f"**{index}. {title}**")
            meta = [value for value in [source.get("source"), source.get("period")] if value]
            if meta:
                st.caption(" | ".join(str(value) for value in meta))
            if source.get("url"):
                st.link_button("근거 열기", source["url"])


def render_query_response(data: dict[str, Any]) -> None:
    metrics = st.columns(3)
    metrics[0].metric("Intent", data["intent"])
    metrics[1].metric("Groundedness", f"{data['groundedness_score']:.2f}")
    metrics[2].metric("근거 문서", len(data["sources"]))

    st.markdown("### 답변")
    st.write(data["answer"])

    for warning in data.get("warnings", []):
        st.warning(warning)

    if data.get("comparison_metadata"):
        with st.expander("기간 비교 정보", expanded=True):
            st.json(data["comparison_metadata"])

    st.markdown("### 근거")
    render_sources(data["sources"])


with st.sidebar:
    st.header("TrendCurator")
    st.caption("Backend")
    st.code(API_BASE_URL)

    if st.button("Health check", use_container_width=True):
        try:
            st.success(api_get("/health")["status"])
        except Exception as exc:
            st.error(f"Backend unavailable: {exc}")

    with st.expander("개발자 도구"):
        if st.button("Dashboard 새로고침", use_container_width=True):
            try:
                dashboard = api_get(f"{API_PREFIX}/dashboard")
                if dashboard.get("success"):
                    st.json(dashboard["data"])
                else:
                    st.error(error_message(dashboard, "Dashboard 조회 실패"))
            except Exception as exc:
                st.error(f"Dashboard 요청 실패: {exc}")

        collect_date = st.date_input("수집 날짜", value=date.today(), key="collect_date")
        if st.button("데이터 수집 실행", use_container_width=True):
            try:
                with st.spinner("데이터 수집 및 임베딩 저장 중입니다."):
                    payload = api_post(
                        f"{API_PREFIX}/pipeline/collect",
                        {"date": collect_date.isoformat()},
                        timeout=600,
                    )
                if not payload.get("success"):
                    st.error(error_message(payload, "수집 실패"))
                else:
                    data = payload["data"]
                    st.success(
                        f"수집 {data['collected_count']}개, "
                        f"관련 문서 {data['filtered_count']}개, "
                        f"저장 {data['ingested_count']}개"
                    )
                    for warning in data.get("warnings", []):
                        st.warning(warning)
            except Exception as exc:
                st.error(f"수집 요청 실패: {exc}")


st.title("TrendCurator")
st.caption("Daily Digest, 온디맨드 질의, 기간별 트렌드 비교를 한 화면에서 확인합니다.")

digest_tab, ondemand_tab, comparison_tab = st.tabs([
    "Daily Digest",
    "On-demand 질의",
    "트렌드 비교",
])

with digest_tab:
    st.subheader("Daily Digest")
    st.caption("선호 카테고리와 키워드를 기준으로 관련 문서를 필터링하고 Digest 후보를 확인합니다.")

    left, right = st.columns([0.58, 0.42])
    with left:
        category_labels = st.multiselect(
            "선호 카테고리",
            options=list(CATEGORY_OPTIONS.keys()),
            default=["AI Agent", "LangGraph", "RAG"],
        )
        digest_keywords = st.text_input("Digest 키워드", value="multi-agent, workflow")
    with right:
        source_labels = st.multiselect(
            "수집 채널",
            options=list(SOURCE_OPTIONS.keys()),
            default=list(SOURCE_OPTIONS.keys()),
        )
        digest_date = st.date_input("Digest 기준일", value=date.today())
        digest_top_k = st.slider("Digest 후보 수", min_value=3, max_value=20, value=8)

    if st.button("Digest 후보 보기", type="primary", use_container_width=True):
        categories = selected_values(category_labels, CATEGORY_OPTIONS)
        sources = selected_values(source_labels, SOURCE_OPTIONS)
        query_terms = categories + keyword_list(digest_keywords)
        payload = {
            "query": "AI Agent Daily Digest " + " ".join(query_terms or ["agent", "trend"]),
            "top_k": digest_top_k,
            "date_from": (digest_date - timedelta(days=7)).isoformat(),
            "date_to": digest_date.isoformat(),
            "sources": sources,
            "categories": categories,
        }
        try:
            result = api_post(f"{API_PREFIX}/documents/search", payload)
            if not result.get("success"):
                st.error(error_message(result, "Digest 후보 검색에 실패했습니다."))
            else:
                data = result["data"]
                results = data["results"]
                st.caption(f"검색 쿼리: {data['rewritten_query']}")
                st.metric("필터 적용 결과", len(results))
                if not results:
                    st.info("조건에 맞는 문서가 없습니다. 카테고리나 기간을 넓혀보세요.")
                for index, item in enumerate(results, start=1):
                    render_result_item(item, index)
        except Exception as exc:
            st.error(f"Digest 후보 요청 실패: {exc}")

    with st.expander("Solar Pro Digest 생성"):
        st.caption("VectorDB 후보 문서를 바탕으로 실제 Daily Digest를 생성합니다.")
        if st.button("Daily Digest 생성", use_container_width=True):
            try:
                payload = api_post(
                    f"{API_PREFIX}/digest/generate",
                    {
                        "date": digest_date.isoformat(),
                        "top_k": digest_top_k,
                        "profile_based": True,
                        "keywords": keyword_list(digest_keywords),
                    },
                    timeout=120,
                )
                if not payload.get("success"):
                    st.error(error_message(payload, "Digest 생성 실패"))
                else:
                    data = payload["data"]
                    digest = data["digest"]
                    st.metric("Groundedness", data["groundedness_score"])
                    st.markdown(f"### {digest['title']}")
                    for item in digest["items"]:
                        with st.expander(item["title"]):
                            st.write(item["summary"])
                            for point in item.get("key_points", []):
                                st.markdown(f"- {point}")
                            if item.get("url"):
                                st.link_button("원문 열기", item["url"])
            except Exception as exc:
                st.error(f"Digest 생성 요청 실패: {exc}")

with ondemand_tab:
    st.subheader("On-demand 질의")
    question = st.text_area(
        "질문",
        value="최근 LangGraph와 멀티 에이전트 기술 트렌드를 알려줘",
        height=120,
    )
    query_left, query_right = st.columns([0.5, 0.5])
    with query_left:
        query_top_k = st.slider("근거 문서 수", min_value=1, max_value=20, value=5, key="ondemand_top_k")
    with query_right:
        base_date = st.date_input("기준일", value=date.today(), key="ondemand_base_date")

    if st.button("질문 보내기", type="primary", use_container_width=True):
        try:
            payload = api_post(
                f"{API_PREFIX}/query",
                {
                    "question": question,
                    "top_k": query_top_k,
                    "date_to": base_date.isoformat(),
                },
                timeout=90,
            )
            if not payload.get("success"):
                st.error(error_message(payload, "질의에 실패했습니다."))
            else:
                render_query_response(payload["data"])
        except Exception as exc:
            st.error(f"온디맨드 질의 실패: {exc}")

with comparison_tab:
    st.subheader("트렌드 비교 질문")
    st.caption("기간 비교 의도가 명확한 질문을 입력하면 LangGraph가 트렌드 비교 경로로 오케스트레이션합니다.")

    comparison_question = st.text_area(
        "비교 질문",
        value="지난주 대비 이번 주 LangGraph와 멀티 에이전트 트렌드는 어떻게 달라졌어?",
        height=120,
    )
    comp_left, comp_right = st.columns([0.5, 0.5])
    with comp_left:
        comparison_top_k = st.slider("기간별 근거 문서 수", min_value=1, max_value=20, value=5)
    with comp_right:
        comparison_base_date = st.date_input("비교 기준일", value=date.today())

    if st.button("트렌드 비교 실행", type="primary", use_container_width=True):
        try:
            payload = api_post(
                f"{API_PREFIX}/query",
                {
                    "question": comparison_question,
                    "top_k": comparison_top_k,
                    "date_to": comparison_base_date.isoformat(),
                },
                timeout=90,
            )
            if not payload.get("success"):
                st.error(error_message(payload, "트렌드 비교에 실패했습니다."))
            else:
                data = payload["data"]
                if data["intent"] != "trend_comparison":
                    st.warning("질문이 일반 질의로 분류되었습니다. '지난주 대비 이번 주'처럼 비교 기간을 더 명확히 적어보세요.")
                render_query_response(data)
        except Exception as exc:
            st.error(f"트렌드 비교 요청 실패: {exc}")
