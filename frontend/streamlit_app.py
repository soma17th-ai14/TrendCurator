"""TrendCurator - AI Agent 트렌드 큐레이터."""

from __future__ import annotations

from datetime import date
import os
from typing import Any

import requests
import streamlit as st

API_BASE_URL = os.getenv("TRENDCURATOR_API_BASE_URL", "http://localhost:8001")
API_PREFIX = "/api/v1"

st.set_page_config(
    page_title="TrendCurator",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=Source+Serif+4:opsz,wght@8..60,300;8..60,400;8..60,600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">',
    unsafe_allow_html=True,
)

_DARK_VARS = """
    :root {
        --bg-base:       #0F0E0C;
        --bg-surface:    #161411;
        --bg-raised:     #1E1C18;
        --bg-input:      #1A1814;
        --border:        #2E2B24;
        --border-soft:   #242118;
        --accent:        #C8821A;
        --accent-muted:  rgba(200, 130, 26, 0.10);
        --accent-border: rgba(200, 130, 26, 0.28);
        --text-primary:  #EDE8DC;
        --text-secondary:#9B9080;
        --text-muted:    #5C5548;
        --success-bg:    rgba(50, 100, 65, 0.18);
        --success-border:#3D7A50;
        --error-bg:      rgba(120, 50, 50, 0.18);
        --error-border:  #8B3A3A;
    }
"""

_LIGHT_VARS = """
    :root {
        --bg-base:       #FAFAF8;
        --bg-surface:    #F2EDE6;
        --bg-raised:     #EAE4DB;
        --bg-input:      #F2EDE6;
        --border:        #B8AFA3;
        --border-soft:   #CCC5BB;
        --accent:        #A85F10;
        --accent-muted:  rgba(168, 95, 16, 0.08);
        --accent-border: rgba(168, 95, 16, 0.22);
        --text-primary:  #1C1A17;
        --text-secondary:#6B6358;
        --text-muted:    #9C9088;
        --success-bg:    rgba(40, 90, 55, 0.10);
        --success-border:#2D6B3E;
        --error-bg:      rgba(110, 40, 40, 0.10);
        --error-border:  #7A2E2E;
    }
"""

_is_light = st.session_state.get("theme") == "light"
_theme_vars = _LIGHT_VARS if _is_light else _DARK_VARS

st.markdown(f"<style>{_theme_vars}</style>", unsafe_allow_html=True)

st.markdown(
    """
    <style>

    /* ── Base ── */
    html, body, .stApp {
        background-color: var(--bg-base) !important;
        color: var(--text-primary) !important;
        font-family: 'Source Serif 4', Georgia, serif !important;
    }

    /* ── System UI 숨김 ── */
    header[data-testid="stHeader"]  { display: none !important; }
    [data-testid="stStatusWidget"]  { display: none !important; }
    .stApp { opacity: 1 !important; }

    /* ── Layout ── */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 4rem !important;
        background-color: var(--bg-base) !important;
    }

    /* ── Typography ── */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Playfair Display', Georgia, serif !important;
        color: var(--text-primary) !important;
        letter-spacing: -0.02em !important;
        font-weight: 600 !important;
    }
    code, pre, kbd,
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
    }
    code {
        background: var(--accent-muted) !important;
        color: var(--accent) !important;
        border: 1px solid var(--accent-border) !important;
        padding: 0.1em 0.4em !important;
        border-radius: 4px !important;
    }
    strong { color: var(--text-primary) !important; font-weight: 600 !important; }
    .stMarkdown a { color: var(--accent) !important; text-decoration: none !important; }
    .stMarkdown a:hover { text-decoration: underline !important; }
    hr { border-color: var(--border) !important; margin: 1rem 0 !important; }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        min-width: 340px !important;
        max-width: 340px !important;
        background-color: var(--bg-surface) !important;
        border-right: 1px solid var(--border) !important;
    }
    section[data-testid="stSidebar"] > div {
        background-color: var(--bg-surface) !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.72rem !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
        border-radius: 8px !important;
        border: 1px solid var(--border) !important;
        background: var(--bg-raised) !important;
        color: var(--text-secondary) !important;
        transition: all 0.15s ease !important;
        white-space: nowrap !important;
    }
    .stButton > button:hover {
        border-color: var(--accent-border) !important;
        color: var(--accent) !important;
        background: var(--accent-muted) !important;
    }
    .stButton > button[kind="primary"] {
        background: var(--accent) !important;
        color: #0F0E0C !important;
        border-color: var(--accent) !important;
        font-weight: 500 !important;
    }
    .stButton > button[kind="primary"]:hover {
        opacity: 0.88 !important;
        color: #0F0E0C !important;
    }
    [data-testid="column"] button { white-space: nowrap !important; }

    /* ── Link button ── */
    .stLinkButton a {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.7rem !important;
        letter-spacing: 0.05em !important;
        text-transform: uppercase !important;
        color: var(--accent) !important;
        border: 1px solid var(--accent-border) !important;
        border-radius: 8px !important;
        background: transparent !important;
    }
    .stLinkButton a:hover {
        background: var(--accent-muted) !important;
        text-decoration: none !important;
    }

    /* ── Inputs ── */
    .stTextInput input,
    .stTextArea textarea,
    [data-testid="stNumberInput"] input {
        background: var(--bg-input) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
        font-family: 'Source Serif 4', serif !important;
    }
    .stTextInput input:focus,
    .stTextArea textarea:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 2px var(--accent-muted) !important;
    }
    [data-baseweb="select"] > div {
        background: var(--bg-input) !important;
        border-color: var(--border) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
    }

    /* ── Metrics ── */
    [data-testid="stMetric"] {
        background: var(--bg-raised) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        padding: 0.75rem 1rem !important;
    }
    [data-testid="stMetricValue"] {
        color: var(--accent) !important;
        font-size: 1.4rem !important;
    }
    [data-testid="stMetricLabel"] > div {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.68rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        color: var(--text-muted) !important;
    }

    /* ── Expanders ── */
    [data-testid="stExpander"] details {
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        background: var(--bg-raised) !important;
    }
    [data-testid="stExpander"] summary {
        color: var(--text-primary) !important;
    }
    [data-testid="stExpander"] summary:hover {
        color: var(--accent) !important;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        background: transparent !important;
        border-bottom: 1px solid var(--border) !important;
        gap: 0 !important;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.7rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.07em !important;
        color: var(--text-muted) !important;
        background: transparent !important;
        padding: 0.5rem 1.2rem !important;
    }
    .stTabs [aria-selected="true"] {
        color: var(--accent) !important;
        border-bottom: 2px solid var(--accent) !important;
    }

    /* ── Alerts ── */
    [data-testid="stAlert"] {
        border-radius: 8px !important;
        border-left-width: 3px !important;
    }
    [data-testid="stAlert"][data-baseweb="notification"] {
        background: var(--accent-muted) !important;
    }

    /* ── Chat ── */
    [data-testid="stChatMessage"] {
        background: var(--bg-raised) !important;
        border: 1px solid var(--border-soft) !important;
        border-radius: 10px !important;
        color: var(--text-primary) !important;
    }
    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] span,
    [data-testid="stChatMessage"] div {
        color: var(--text-primary) !important;
    }
    [data-testid="stChatInputTextArea"] {
        font-family: 'Source Serif 4', serif !important;
        background: var(--bg-input) !important;
        color: var(--text-primary) !important;
    }

    /* ── Scrollable container ── */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 10px !important;
        border: 1px solid var(--border) !important;
        background: var(--bg-surface) !important;
        overflow: hidden !important;
    }

    /* ── Spinner ── */
    [data-testid="stSpinner"] {
        display: flex !important;
        justify-content: center !important;
        padding: 1rem 0 !important;
    }
    [data-testid="stSpinner"] svg {
        stroke: var(--accent) !important;
        color: var(--accent) !important;
    }

    /* ── Caption ── */
    [data-testid="stCaptionContainer"] p,
    .stCaption {
        font-family: 'Source Serif 4', Georgia, serif !important;
        font-size: 0.82rem !important;
        color: var(--text-secondary) !important;
        letter-spacing: 0 !important;
    }

    /* ── Expander open 상태 ── */
    [data-testid="stExpander"] details[open] summary {
        background: var(--bg-raised) !important;
        color: var(--text-primary) !important;
    }
    [data-testid="stExpander"] details[open] summary p,
    [data-testid="stExpander"] details[open] summary span,
    [data-testid="stExpander"] details[open] summary * {
        color: var(--text-primary) !important;
    }

    /* ── Chat input 컨테이너 ── */
    [data-testid="stChatInput"],
    [data-testid="stChatInput"] > div,
    [data-testid="stChatInputContainer"],
    [data-testid="stChatInputContainer"] > div,
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div {
        background: var(--bg-surface) !important;
    }
    /* 채팅 입력 박스 외곽 래퍼 (Streamlit 1.45 기준 내부 클래스 — 버전 업 시 재확인 필요) */
    .e1vtqrcf1 {
        border: 1px solid var(--border) !important;
        background: var(--bg-input) !important;
    }
    [data-testid="stChatInput"] textarea,
    [data-testid="stChatInputTextArea"] textarea {
        color: var(--text-primary) !important;
    }
    [data-testid="stChatInput"] textarea::placeholder,
    [data-testid="stChatInputTextArea"] textarea::placeholder {
        color: var(--text-muted) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─── API helpers ─────────────────────────────────────────────────────────────

def api_get(path: str, timeout: int = 20) -> dict[str, Any]:
    r = requests.get(f"{API_BASE_URL}{path}", timeout=timeout)
    r.raise_for_status()
    return r.json()


def api_post(path: str, payload: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    r = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def error_msg(payload: dict[str, Any], fallback: str = "오류가 발생했습니다.") -> str:
    err = payload.get("error")
    if isinstance(err, dict):
        code = err.get("code", "")
        msg = err.get("message", fallback)
        return f"{code}: {msg}" if code else msg
    return str(err) if err else fallback


# ─── Session state 초기화 ─────────────────────────────────────────────────────

if "show_settings" not in st.session_state:
    st.session_state.show_settings = False
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "confirm_regen" not in st.session_state:
    st.session_state.confirm_regen = False
if "theme" not in st.session_state:
    st.session_state.theme = "dark"


# ═══ 사이드바: 채팅 질의 (고정) ═══════════════════════════════════════════════

with st.sidebar:
    st.markdown("### 💬 질의")
    st.caption("AI 답변은 수집된 데이터를 기반으로 생성되며, 부정확하거나 누락된 내용이 있을 수 있습니다.")
    st.divider()

    has_pending = "pending_question" in st.session_state

    # 메시지 영역: 내부 스크롤 (입력창은 아래에 고정)
    msg_area = st.container(height=520)
    with msg_area:
        if not st.session_state.chat_messages and not has_pending:
            st.markdown(
                "<div style='color:var(--text-muted); font-size:0.85rem; margin-top:0.5rem;'>"
                "예시 질문:<br><br>"
                "• 최근 LangGraph 관련 주요 연구는?<br>"
                "• 지난주 대비 이번 주 멀티에이전트 트렌드 변화는?<br>"
                "• RAG와 에이전트 결합 관련 최신 동향은?"
                "</div>",
                unsafe_allow_html=True,
            )

        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if msg["role"] == "assistant":
                    sources = msg.get("sources") or []
                    if msg.get("groundedness_passed") and sources:
                        with st.expander(f"근거 문서 {len(sources)}건"):
                            for src in sources:
                                title = src.get("title") or src.get("document_id") or "문서"
                                period = src.get("period", "")
                                period_label = f" ({period})" if period else ""
                                if src.get("url"):
                                    st.markdown(f"- [{title}{period_label}]({src['url']})")
                                else:
                                    st.markdown(f"- {title}{period_label}")

        if has_pending:
            question = st.session_state.pop("pending_question")

            with st.chat_message("user"):
                st.write(question)

            with st.chat_message("assistant"):
                with st.spinner(""):
                    result = None
                    _exc: Exception | None = None
                    try:
                        result = api_post(
                            f"{API_PREFIX}/query",
                            {"question": question, "top_k": 5, "date_to": str(date.today())},
                            timeout=90,
                        )
                    except Exception as exc:
                        _exc = exc

                if result is None:
                    full_answer = f"요청 실패: {_exc}"
                    sources: list = []
                    groundedness = None
                    groundedness_passed = False
                elif result.get("success"):
                    data = result["data"]
                    intent = data.get("intent", "")
                    answer = data.get("answer", "")
                    prefix = "📊 **트렌드 비교 결과**\n\n" if intent == "trend_comparison" else ""
                    full_answer = prefix + answer
                    sources = data.get("sources", [])
                    groundedness = data.get("groundedness_score")
                    groundedness_passed = data.get("groundedness_passed", False)
                else:
                    full_answer = f"오류: {error_msg(result)}"
                    sources = []
                    groundedness = None
                    groundedness_passed = False

                st.write(full_answer)
                if groundedness_passed and sources:
                    with st.expander(f"근거 문서 {len(sources)}건"):
                        for src in sources:
                            title = src.get("title") or src.get("document_id") or "문서"
                            period = src.get("period", "")
                            period_label = f" ({period})" if period else ""
                            if src.get("url"):
                                st.markdown(f"- [{title}{period_label}]({src['url']})")
                            else:
                                st.markdown(f"- {title}{period_label}")

            st.session_state.chat_messages.append({"role": "user", "content": question})
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": full_answer,
                "sources": sources,
                "groundedness": groundedness,
                "groundedness_passed": groundedness_passed,
            })
            st.rerun()

    if question := st.chat_input("질문을 입력하세요..."):
        st.session_state.pending_question = question
        st.rerun()


# ─── 헤더 ────────────────────────────────────────────────────────────────────

title_col, spacer, theme_col, settings_col = st.columns([5, 1, 1.2, 2])
with title_col:
    st.markdown("## 📡 TrendCurator")
    st.caption("AI Agent 분야 Daily Digest · 트렌드 질의")
with theme_col:
    theme_label = "☀ 라이트" if _is_light else "◑ 다크"
    if st.button(theme_label, use_container_width=True):
        st.session_state.theme = "dark" if _is_light else "light"
        st.rerun()
with settings_col:
    btn_label = "✕ 닫기" if st.session_state.show_settings else "⚙️ 설정"
    if st.button(btn_label, use_container_width=True):
        st.session_state.show_settings = not st.session_state.show_settings
        st.rerun()


# ─── 설정 패널 (드롭다운) ─────────────────────────────────────────────────────

if st.session_state.show_settings:
    with st.container(border=True):
        profile_tab, scheduler_tab, admin_tab = st.tabs(["프로필", "스케줄러", "관리"])

        with profile_tab:
            try:
                prof_payload = api_get(f"{API_PREFIX}/profile")
                prof = prof_payload.get("data") or {} if prof_payload.get("success") else {}
            except Exception:
                prof = {}

            with st.form("profile_form"):
                keywords_raw = st.text_input(
                    "관심 키워드 (쉼표로 구분)",
                    value=", ".join(prof.get("keywords", ["LangGraph", "Multi-agent", "RAG"])),
                )
                left, right = st.columns(2)
                with left:
                    lang_options = ["ko", "en"]
                    lang_idx = lang_options.index(prof.get("language", "ko")) if prof.get("language") in lang_options else 0
                    language = st.selectbox("출력 언어", lang_options, index=lang_idx)
                with right:
                    digest_time = st.text_input("Digest 수신 시각", value=prof.get("digest_time", "09:00"))
                if st.form_submit_button("저장", type="primary"):
                    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
                    try:
                        result = api_post(f"{API_PREFIX}/profile", {
                            "keywords": keywords,
                            "language": language,
                            "digest_time": digest_time,
                        })
                        if result.get("success"):
                            st.success("프로필이 저장되었습니다.")
                        else:
                            st.error(error_msg(result, "저장 실패"))
                    except Exception as exc:
                        st.error(f"저장 요청 실패: {exc}")

        with scheduler_tab:
            try:
                sched_payload = api_get(f"{API_PREFIX}/scheduler")
                sched = sched_payload.get("data") or {} if sched_payload.get("success") else {}
            except Exception:
                sched = {}

            with st.form("scheduler_form"):
                enabled = st.toggle("스케줄러 활성화", value=sched.get("enabled", False))
                left, right = st.columns(2)
                with left:
                    sched_time = st.text_input("실행 시각 (HH:MM)", value=sched.get("time", "09:00"))
                with right:
                    timezone = st.text_input("시간대", value=sched.get("timezone", "Asia/Seoul"))
                sources = st.multiselect(
                    "수집 소스",
                    options=["huggingface", "hackernews"],
                    default=sched.get("sources", ["huggingface", "hackernews"]),
                )
                if st.form_submit_button("저장", type="primary"):
                    try:
                        result = api_post(f"{API_PREFIX}/scheduler", {
                            "enabled": enabled,
                            "time": sched_time,
                            "timezone": timezone,
                            "sources": sources,
                        })
                        if result.get("success"):
                            next_run = result["data"].get("next_run_at", "-")
                            st.success(f"저장됐습니다. 다음 실행: {next_run}")
                        else:
                            st.error(error_msg(result, "저장 실패"))
                    except Exception as exc:
                        st.error(f"요청 실패: {exc}")

        with admin_tab:
            left, right = st.columns(2)
            with left:
                st.markdown("**데이터 수집**")
                collect_date = st.date_input("수집 날짜", value=date.today(), key="admin_collect_date")
                if st.button("수집 실행", use_container_width=True):
                    with st.spinner("데이터 수집 중입니다... (2~5분 소요)"):
                        try:
                            result = api_post(
                                f"{API_PREFIX}/pipeline/collect",
                                {"date": collect_date.isoformat()},
                                timeout=600,
                            )
                            if result.get("success"):
                                d = result["data"]
                                st.success(
                                    f"수집 {d['collected_count']}건 · "
                                    f"관련 {d['filtered_count']}건 · "
                                    f"저장 {d['ingested_count']}건"
                                )
                                for w in d.get("warnings", []):
                                    st.warning(w)
                            else:
                                st.error(error_msg(result, "수집 실패"))
                        except Exception as exc:
                            st.error(f"수집 요청 실패: {exc}")

            with right:
                st.markdown("**시스템 현황**")
                try:
                    dash = api_get(f"{API_PREFIX}/dashboard")
                    if dash.get("success"):
                        d = dash["data"]
                        cs = d.get("collection_status", {})
                        ss = d.get("source_stats", {})
                        col1, col2 = st.columns(2)
                        col1.metric("HuggingFace", ss.get("huggingface", 0))
                        col2.metric("HackerNews", ss.get("hackernews", 0))
                        if cs.get("last_collected_at"):
                            st.caption(f"마지막 수집: {cs['last_collected_at']}")
                        top_tags = d.get("top_tags", [])
                        if top_tags:
                            st.caption("주요 키워드: " + " · ".join(t["tag"] for t in top_tags[:6]))
                except Exception as exc:
                    st.warning(f"현황 조회 실패: {exc}")

                if st.button("Backend 연결 확인", use_container_width=True):
                    try:
                        status = api_get("/health")["status"]
                        st.success(f"정상 ({status})")
                    except Exception as exc:
                        st.error(f"연결 실패: {exc}")

    st.divider()


# ═══ Daily Digest (메인 영역, 자연 스크롤) ════════════════════════════════════

try:
    list_payload = api_get(f"{API_PREFIX}/digest")
    digest_list: list[dict] = list_payload.get("data") or [] if list_payload.get("success") else []
except Exception:
    digest_list = []

dg_header, dg_ctrl = st.columns([2, 1])
with dg_header:
    st.markdown("### 📋 Daily Digest")
with dg_ctrl:
    if digest_list:
        options = {f"{d['date']}  ({d['item_count']}건)": d["digest_id"] for d in digest_list}
        selected_label = st.selectbox(
            "날짜",
            list(options.keys()),
            label_visibility="collapsed",
        )
        selected_id = options[selected_label]
    else:
        selected_id = None

today_str = str(date.today())
has_today = any(d["date"] == today_str for d in digest_list)
if not has_today:
    st.info("오늘의 Digest가 아직 생성되지 않았습니다.")

btn_col, num_col = st.columns([3, 1])
with num_col:
    gen_top_k = st.number_input("항목 수", min_value=1, max_value=50, value=10, step=1, label_visibility="collapsed")
with btn_col:
    regen_label = "오늘의 Digest 재생성" if has_today else "오늘의 Digest 생성"
    btn_type = "secondary" if has_today else "primary"
    if st.button(regen_label, type=btn_type, use_container_width=True):
        if has_today:
            st.session_state.confirm_regen = True
        else:
            st.session_state.confirm_regen = False
            with st.spinner("Digest 생성 중입니다... (최대 2분 소요)"):
                try:
                    result = api_post(
                        f"{API_PREFIX}/digest/generate",
                        {"date": today_str, "profile_based": True, "top_k": int(gen_top_k)},
                        timeout=180,
                    )
                    if result.get("success"):
                        st.success("Digest가 생성되었습니다.")
                        st.rerun()
                    else:
                        st.error(error_msg(result, "생성 실패"))
                except Exception as exc:
                    st.error(f"생성 요청 실패: {exc}")

if st.session_state.confirm_regen:
    st.warning(
        "기존 오늘의 Digest를 삭제하고 재생성합니다. "
        "재생성 시 참조 항목과 내용이 기존과 달라질 수 있습니다.",
        icon="⚠️",
    )
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("재생성 확인", type="primary", use_container_width=True):
            st.session_state.confirm_regen = False
            with st.spinner("Digest 재생성 중입니다... (최대 2분 소요)"):
                try:
                    result = api_post(
                        f"{API_PREFIX}/digest/generate",
                        {"date": today_str, "profile_based": True, "top_k": int(gen_top_k)},
                        timeout=180,
                    )
                    if result.get("success"):
                        st.success("Digest가 재생성되었습니다.")
                        st.rerun()
                    else:
                        st.error(error_msg(result, "재생성 실패"))
                except Exception as exc:
                    st.error(f"재생성 요청 실패: {exc}")
    with cancel_col:
        if st.button("취소", use_container_width=True):
            st.session_state.confirm_regen = False
            st.rerun()

if selected_id:
    try:
        detail = api_get(f"{API_PREFIX}/digest/{selected_id}")
        if detail.get("success"):
            digest = detail["data"]
            items = digest.get("items", [])

            m1, m2 = st.columns(2)
            m1.metric("수록 항목", len(items))
            m2.caption(f"기준일: {digest.get('date', '-')}")

            st.markdown(f"#### {digest.get('title', 'Daily Digest')}")

            for idx, item in enumerate(items, 1):
                source = item.get("source", "-")
                label = f"**{idx}.** {item['title']}  `{source}`"
                with st.expander(label, expanded=(idx == 1)):
                    st.caption(f"발행일: {item.get('published_at') or '-'}")

                    st.markdown("**요약**")
                    st.write(item.get("summary") or "-")

                    key_points = item.get("key_points") or []
                    if key_points:
                        st.markdown("**핵심 포인트**")
                        for pt in key_points:
                            st.markdown(f"- {pt}")

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown("**기여**")
                        st.write(item.get("contribution") or "명시된 근거 없음")
                    with c2:
                        st.markdown("**벤치마크**")
                        st.write(item.get("benchmark") or "명시된 근거 없음")
                    with c3:
                        st.markdown("**비평**")
                        st.write(item.get("critique") or "명시된 근거 없음")

                    tags = item.get("tags") or []
                    if tags:
                        st.caption("태그: " + " · ".join(tags))
                    if item.get("url"):
                        st.link_button("원문 보기 →", item["url"])
        else:
            st.warning(error_msg(detail, "Digest를 불러올 수 없습니다."))
    except Exception as exc:
        st.error(f"Digest 조회 실패: {exc}")
elif not digest_list:
    st.markdown("---")
    st.markdown("수집된 Digest가 없습니다. 위 버튼으로 생성하거나 설정에서 스케줄러를 확인하세요.")
