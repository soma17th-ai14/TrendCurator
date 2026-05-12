"""Streamlit UI for TrendCurator."""

from __future__ import annotations

from datetime import date
import os

import requests
import streamlit as st


API_BASE_URL = os.getenv("TRENDCURATOR_API_BASE_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"


st.set_page_config(page_title="TrendCurator", page_icon="TC", layout="wide")
st.title("TrendCurator")
st.caption("AI Agent trend digest, query, groundedness check, and orchestration demo")


def api_get(path: str) -> dict:
    response = requests.get(f"{API_BASE_URL}{path}", timeout=20)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict, timeout: int = 60) -> dict:
    response = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


with st.sidebar:
    st.header("Backend")
    st.code(API_BASE_URL)
    if st.button("Health check", use_container_width=True):
        try:
            st.success(api_get("/health")["status"])
        except Exception as exc:
            st.error(f"Backend unavailable: {exc}")


dashboard_tab, collect_tab, query_tab, digest_tab, groundedness_tab = st.tabs([
    "Dashboard",
    "Collect",
    "Query",
    "Digest",
    "Groundedness",
])


with dashboard_tab:
    st.subheader("Pipeline status")
    try:
        payload = api_get(f"{API_PREFIX}/dashboard")
        if not payload.get("success"):
            st.warning(payload.get("error") or "Dashboard data unavailable")
        else:
            data = payload["data"]
            status = data["collection_status"]
            col1, col2, col3 = st.columns(3)
            col1.metric("Collected", status["collected_count"])
            col2.metric("Filtered", status["filtered_count"])
            col3.metric("Generated at", data["generated_at"])
            st.json(data)
    except Exception as exc:
        st.error(f"Dashboard request failed: {exc}")


with collect_tab:
    st.subheader("데이터 수집 및 저장")
    collect_date = st.date_input("수집 날짜", value=date.today(), key="collect_date")
    if st.button("수집 실행", type="primary"):
        try:
            with st.spinner("수집 중... 임베딩 포함 2~5분 소요될 수 있습니다."):
                payload = api_post(f"{API_PREFIX}/pipeline/collect", {
                    "date": collect_date.isoformat(),
                }, timeout=600)
            if not payload.get("success"):
                st.error(payload.get("error") or "수집 실패")
            else:
                data = payload["data"]
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("수집", data["collected_count"])
                col2.metric("관련 문서", data["filtered_count"])
                col3.metric("저장", data["ingested_count"])
                col4.metric("스킵", data["skipped_count"])
                st.caption(f"완료: {data['collected_at']}")
                for w in data.get("warnings", []):
                    st.warning(w)
        except Exception as exc:
            st.error(f"수집 요청 실패: {exc}")


with query_tab:
    st.subheader("Ask TrendCurator")
    question = st.text_area(
        "Question",
        value="Summarize recent LangGraph and multi-agent technology trends.",
        height=100,
    )
    top_k = st.slider("Top K", min_value=1, max_value=20, value=5)
    base_date = st.date_input("Base date", value=date.today())
    if st.button("Run query", type="primary"):
        try:
            payload = api_post(f"{API_PREFIX}/query", {
                "question": question,
                "top_k": top_k,
                "date_to": base_date.isoformat(),
            })
            if not payload.get("success"):
                st.error(payload.get("error") or "Query failed")
            else:
                data = payload["data"]
                st.metric("Groundedness", data["groundedness_score"])
                st.write(data["answer"])
                for warning in data.get("warnings", []):
                    st.warning(warning)
                if data.get("comparison_metadata"):
                    st.write("Comparison metadata")
                    st.json(data["comparison_metadata"])
                st.write("Sources")
                st.dataframe(data["sources"], use_container_width=True)
        except Exception as exc:
            st.error(f"Query request failed: {exc}")


with digest_tab:
    st.subheader("Generate Daily Digest")
    digest_date = st.date_input("Digest date", value=date.today())
    digest_top_k = st.slider("Digest Top K", min_value=1, max_value=20, value=5)
    keywords = st.text_input("Profile keywords", value="LangGraph, Multi-agent, RAG")
    if st.button("Generate digest", type="primary"):
        try:
            payload = api_post(f"{API_PREFIX}/digest/generate", {
                "date": digest_date.isoformat(),
                "top_k": digest_top_k,
                "profile_based": True,
                "keywords": [item.strip() for item in keywords.split(",") if item.strip()],
            })
            if not payload.get("success"):
                st.error(payload.get("error") or "Digest failed")
            else:
                data = payload["data"]
                st.metric("Groundedness", data["groundedness_score"])
                st.write(data["digest"]["title"])
                for item in data["digest"]["items"]:
                    label = f"[{item.get('source', '')}] {item['title']}"
                    with st.expander(label):
                        meta_cols = st.columns(2)
                        meta_cols[0].caption(f"출처: {item.get('source', '-')}")
                        meta_cols[1].caption(f"발행일: {item.get('published_at') or '-'}")

                        st.markdown("**요약**")
                        st.write(item["summary"])

                        st.markdown("**핵심 포인트**")
                        for pt in item.get("key_points", []):
                            st.markdown(f"- {pt}")

                        st.markdown("**기여**")
                        st.write(item.get("contribution") or "-")

                        st.markdown("**벤치마크**")
                        st.write(item.get("benchmark") or "-")

                        st.markdown("**비평**")
                        st.write(item.get("critique") or "-")

                        tags = item.get("tags", [])
                        if tags:
                            st.caption("태그: " + ", ".join(tags))

                        st.link_button("원문 보기", item["url"])
        except Exception as exc:
            st.error(f"Digest request failed: {exc}")


with groundedness_tab:
    st.subheader("Groundedness Check")
    answer = st.text_area("Answer", height=140)
    contexts = st.text_area("Source contexts", height=180, help="Separate multiple contexts with a blank line.")
    threshold = st.slider("Threshold", min_value=0.0, max_value=1.0, value=0.8, step=0.05)
    if st.button("Check groundedness", type="primary"):
        try:
            payload = api_post(f"{API_PREFIX}/groundedness/check", {
                "answer": answer,
                "contexts": [part.strip() for part in contexts.split("\n\n") if part.strip()],
                "threshold": threshold,
            })
            data = payload["data"]
            st.metric("Score", data["score"])
            st.write("Passed" if data["passed"] else "Needs repair")
            st.write(data["feedback"])
        except Exception as exc:
            st.error(f"Groundedness request failed: {exc}")
