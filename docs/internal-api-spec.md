# LangGraph 상태 정의

```python
class AgentState(TypedDict):
    query: str                # 사용자 원본 질문
    base_date: str            # 기준 날짜 (date_to)
    intent: str               # "TREND_COMPARISON" | "GENERAL_QA"
    context: dict             # 노드별 처리 결과 (분석 내용, 기간 정보 등)
    retrieved_docs: List[dict] # 검색된 원본 문서들 (출처 표기용)
    answer: str               # 최종 생성된 답변
    groundedness_score: float # 신뢰도 점수
```

# 내부 모듈별 Input/Output 스펙

### Intent Router

사용자의 발화 의도를 일반 질문 또는 트렌드 비교 질문으로 분류하고 적절한 워크플로우로 라우팅합니다.

- **Input:** `UserQueryState` (질문 텍스트, 현재 시간)
- **Output:** JSON
  ```python
  {
    "intent": "TREND_COMPARISON | GENERAL_QA",
    "confidence": 0.0 to 1.0,
    "reasoning": "왜 이 의도로 분류했는지에 대한 LLM의 사고 과정"
  }
  ```

## 일반 질문

### Query Rewriter

모호한 질문을 VectorDB 검색에 최적화된 영어/한글 혼합 쿼리로 재작성합니다.

- **Input:** `UserQueryState` (질문 텍스트)
- **Output:** JSON
  ```python
  {
    "optimized_queries": ["query 1", "query 2"],
    "search_filter": { "sources": ["huggingface", "hackernews"] }
  }
  ```

## 트렌드 비교 질문

### Date Range Parser

자연어로 된 시간 표현을 검색 가능한 날짜 객체로 변환합니다.

- **Input:** `UserQueryState` (질문 텍스트, 현재 시간)
- **Output:** JSON
  ```python
  {
    "period_a": { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD" },
    "period_b": { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD" },
    "focus_keywords": ["검색에 집중할 키워드 리스트"]
  }
  ```

### Period Retriever

ChromaDB에서 특정 기간과 키워드에 맞는 컨텍스트를 가져옵니다.

- **Input:** JSON, Date Range Parser 결과물
  ```python
  {
    "period_a": { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD" },
    "period_b": { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD" },
    "focus_keywords": ["검색에 집중할 키워드 리스트"]
  }
  ```
- **Output:** JSON (구조화된 문서 집합)
  ```python
  {
    "context_a": {
      "period": { "start": "2026-04-22", "end": "2026-04-28" },
      "documents": [ { "doc_id": "...", "content": "..." }, ... ],
      "total_count": 15
    },
    "context_b": {
      "period": { "start": "2026-04-29", "end": "2026-05-06" },
      "documents": [ { "doc_id": "...", "content": "..." }, ... ],
      "total_count": 20
    }
  }
  ```

### Trend Comparator

두 기간의 문서 집합을 비교 분석하여 변화 양상을 추출합니다.

- **Input:** JSON, Period Retriever 결과물
- **Output:** JSON
  ```python
  {
    "period_a_summary": "당시 주요 흐름",
    "period_b_summary": "현재 주요 흐름",
    "delta": {
      "new_signals": ["새로 등장한 것"],
      "fading_signals": ["사라지거나 약해진 것"]
    },
    "insight": "엔지니어 관점의 기술적 함의"
  }
  ```

## 정기 발행 Digest

### Scheduler

정기 Daily Digest 실행 시각을 판단하고, 실행 대상일 때 Digest 파이프라인을 한 번 호출합니다.

- **Input:** `SchedulerRunRequest`
  ```json
  {
    "now": "2026-05-06T09:00:00+09:00",
    "config": {
      "enabled": true,
      "time": "09:00",
      "timezone": "Asia/Seoul",
      "sources": ["huggingface", "hackernews"]
    }
  }
  ```
- **Output:** `SchedulerRunResult`
  ```json
  {
    "ran": true,
    "run_date": "2026-05-06",
    "last_run_at": "2026-05-06T09:00:00+09:00",
    "job_id": "digest_20260506",
    "skipped_reason": null
  }
  ```

스케줄러가 실행 대상이 아니면 `ran=false`, `run_date=null`, `job_id=null`로 두고 `skipped_reason`에 `disabled`, `before_scheduled_time`, `already_ran_today` 중 하나를 사용합니다.

`job_id`는 스케줄러가 호출한 파이프라인의 실행 결과 식별자입니다. Daily Digest 파이프라인을 호출한 경우 `digest_id` 값을 넣습니다.

### SchedulerConfig

`GET /scheduler`, `PUT /scheduler`, 정기 발행 실행 진입점에서 공통으로 사용하는 설정입니다.

```json
{
  "enabled": true,
  "time": "09:00",
  "timezone": "Asia/Seoul",
  "sources": ["huggingface", "hackernews"]
}
```

- `time`은 `HH:MM` 24시간 형식을 사용합니다.
- `timezone`은 IANA timezone 이름을 사용합니다.
- `sources`는 비어 있을 수 없습니다.

### Solar Mini Relevance Filter

수집/정규화된 문서가 AI Agent Daily Digest 후보로 적합한지 판정합니다.

- **Input:** `SolarMiniRelevanceRequest`
  ```json
  {
    "document": {
      "document_id": "doc_001",
      "source": "huggingface",
      "title": "LangGraph agent workflow",
      "url": "https://example.com/doc",
      "published_at": "2026-05-06",
      "raw_text": "원문 또는 정규화된 본문",
      "category_hint": "multi-agent workflow",
      "external_id": "2405.01234",
      "content_hash": "sha256:...",
      "metadata": {}
    },
    "profile_keywords": ["LangGraph", "Multi-agent", "RAG"],
    "threshold": 0.18
  }
  ```
- **Output:** `SolarMiniRelevanceDecision`
  ```json
  {
    "document_id": "doc_001",
    "is_relevant": true,
    "score": 0.93,
    "matched_keywords": ["langgraph", "multi-agent"],
    "reason": "AI Agent 관련 키워드와 카테고리 신호가 기준을 충족했습니다."
  }
  ```

`score`는 `0.0` 이상 `1.0` 이하의 소수입니다. `is_relevant`는 `score >= threshold`와 Solar Mini의 판정을 함께 반영합니다.

### Daily Digest Retriever

Digest 생성 대상 기간과 사용자 프로필을 기준으로 후보 문서를 검색합니다.

- **Input:** `DailyDigestRetrievalRequest`
  ```json
  {
    "digest_date": "2026-05-06",
    "lookback_days": 1,
    "top_k": 10,
    "profile_based": true,
    "keywords": ["LangGraph", "Multi-agent", "RAG"],
    "sources": ["huggingface", "hackernews"],
    "min_relevance_score": 0.18
  }
  ```
- **Output:** `DailyDigestRetrievalResult`
  ```json
  {
    "digest_date": "2026-05-06",
    "candidates": [
      {
        "document_id": "doc_001",
        "source": "huggingface",
        "title": "Example Daily Paper",
        "url": "https://huggingface.co/papers/xxxx.xxxxx",
        "published_at": "2026-05-05",
        "content": "후보 문서 본문 또는 요약 가능한 컨텍스트",
        "summary_preview": "검색 단계에서 생성되거나 저장된 짧은 요약",
        "similarity_score": 0.87,
        "relevance_score": 0.93,
        "matched_keywords": ["langgraph", "multi-agent"],
        "tags": ["multi-agent", "rag"],
        "metadata": {}
      }
    ],
    "total_count": 31,
    "selected_count": 10
  }
  ```

### Solar Pro 3 Summary/Critique Prompt

Daily Digest 후보 문서를 바탕으로 요약, 핵심 포인트, 기여, 벤치마크, 비평을 생성합니다.

- **Input:** `SolarProDigestGenerationRequest`
  ```json
  {
    "digest_date": "2026-05-06",
    "language": "ko",
    "profile_keywords": ["LangGraph", "Multi-agent", "RAG"],
    "candidates": [
      {
        "document_id": "doc_001",
        "source": "huggingface",
        "title": "Example Daily Paper",
        "url": "https://huggingface.co/papers/xxxx.xxxxx",
        "published_at": "2026-05-05",
        "content": "후보 문서 본문 또는 요약 가능한 컨텍스트",
        "summary_preview": "검색 단계에서 생성되거나 저장된 짧은 요약",
        "similarity_score": 0.87,
        "relevance_score": 0.93,
        "matched_keywords": ["langgraph", "multi-agent"],
        "tags": ["multi-agent", "rag"],
        "metadata": {}
      }
    ]
  }
  ```
- **Output:** `SolarProDigestGenerationResult`
  ```json
  {
    "digest_id": "digest_20260506",
    "date": "2026-05-06",
    "title": "AI Agent Daily Digest",
    "items": [
      {
        "document_id": "doc_001",
        "title": "논문 또는 게시글 제목",
        "source": "huggingface",
        "url": "https://huggingface.co/papers/xxxx.xxxxx",
        "published_at": "2026-05-05",
        "summary": "핵심 요약",
        "key_points": ["핵심 내용 1", "핵심 내용 2"],
        "contribution": "주요 기여",
        "benchmark": "성능 수치 또는 실험 결과",
        "critique": "기존 기술 대비 차별점 및 한계",
        "tags": ["multi-agent", "rag"],
        "evidence_document_ids": ["doc_001"],
        "llm_model": "solar-pro-3"
      }
    ],
    "groundedness_score": 0.91
  }
  ```

근거 문서에 없는 수치, 벤치마크, 주장, 한계를 생성할 수 없으면 해당 필드는 빈 문자열 또는 `"명시된 근거 없음"`으로 반환합니다.

### Digest Generation Adapter

Daily Digest Retriever 결과를 Solar Pro 3 Digest Generator 요청으로 변환하고, 생성 결과를 저장소, Groundedness Check, API 응답 계층이 재사용할 수 있는 실행 결과 계약으로 정리합니다.

- **Input:** `DailyDigestRetrievalResult`, profile keywords
- **Output:** `SolarProDigestGenerationRequest`
  ```json
  {
    "digest_date": "2026-05-06",
    "language": "ko",
    "profile_keywords": ["LangGraph", "Multi-agent", "RAG"],
    "candidates": []
  }
  ```

- **Input:** `DailyDigestRetrievalResult`, `SolarProDigestGenerationResult`
- **Output:** `DigestGenerationRunResult`
  ```json
  {
    "digest_id": "digest_20260506",
    "date": "2026-05-06",
    "status": "completed",
    "item_count": 10,
    "candidate_count": 31,
    "selected_candidate_count": 10,
    "source_document_ids": ["doc_001"],
    "groundedness_score": 0.91,
    "digest": {}
  }
  ```

Adapter는 생성 결과의 `date`가 검색 기준일과 일치하는지, 생성된 `items`의 `document_id` 순서가 검색 후보 순서와 일치하는지, `evidence_document_ids`가 검색 후보 안에 있는지 검증합니다.
