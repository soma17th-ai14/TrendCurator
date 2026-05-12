# API 스펙 초안

이 문서는 TrendCurator의 API 계약 초안입니다. 모든 모듈은 API 구현, 서비스 인터페이스, 프론트엔드 연동, 테스트 작성 시 이 문서를 공통 기준으로 참조합니다.

## 1. 기본 정보

### Base URL

```text
/api/v1
```

### 고정 데이터 소스

```json
["huggingface", "hackernews"]
```

### 공통 응답 형식

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

### 공통 에러 형식

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "에러 설명"
  }
}
```

## 2. 사용자 프로필 API

### 2.1 관심사 프로필 조회

```http
GET /profile
```

Response

```json
{
  "success": true,
  "data": {
    "keywords": ["LangGraph", "Multi-agent", "RAG"],
    "language": "ko",
    "digest_time": "09:00"
  },
  "error": null
}
```

### 2.2 관심사 프로필 저장/수정

```http
PUT /profile
```

Request

```json
{
  "keywords": ["LangGraph", "Multi-agent", "RAG"],
  "language": "ko",
  "digest_time": "09:00"
}
```

Response

```json
{
  "success": true,
  "data": {
    "message": "Profile updated"
  },
  "error": null
}
```

## 3. 데이터 수집 파이프라인 API

### 3.1 수동 수집 실행

```http
POST /pipeline/collect
```

HuggingFace Daily Papers와 HackerNews에서 최신 AI Agent 관련 콘텐츠를 수집합니다.
수집·필터·임베딩·저장을 동기적으로 완료하고 최종 결과를 반환합니다.

Request

```json
{
  "date": "2026-05-06"
}
```

내부 처리 흐름

```text
Collector (HuggingFace + HackerNews 병렬)
-> Normalizer
-> Relevance Filter (SolarMini)
-> Chunker
-> Embedder
-> ChromaDB 저장
```

Response

```json
{
  "success": true,
  "data": {
    "collected_count": 86,
    "filtered_count": 31,
    "ingested_count": 30,
    "skipped_count": 1,
    "collected_at": "2026-05-06T09:00:00Z",
    "warnings": []
  },
  "error": null
}
```

일부 소스만 실패한 경우 `success: true`로 반환하되 `warnings` 배열에 실패한 소스와 오류 메시지를 포함합니다.
모든 소스가 실패한 경우 `success: false`로 반환합니다.

## 4. 문서 검색 API

### 4.1 문서 검색

```http
POST /documents/search
```

Request

```json
{
  "query": "멀티 에이전트 프레임워크 최신 동향",
  "top_k": 10,
  "date_from": "2026-05-01",
  "date_to": "2026-05-06",
  "sources": ["huggingface", "hackernews"],
  "categories": ["agent", "rag", "multi-agent"]
}
```

Response

```json
{
  "success": true,
  "data": {
    "rewritten_query": "recent multi-agent framework trends for AI agents",
    "results": [
      {
        "document_id": "doc_001",
        "title": "Example Daily Paper",
        "source": "huggingface",
        "url": "https://huggingface.co/papers/xxxx.xxxxx",
        "published_at": "2026-05-05",
        "similarity_score": 0.87,
        "summary_preview": "멀티 에이전트 오케스트레이션 관련 최신 연구 요약"
      }
    ]
  },
  "error": null
}
```

## 5. Daily Digest API

### 5.1 Daily Digest 생성

```http
POST /digest/generate
```

Request

```json
{
  "date": "2026-05-06",
  "profile_based": true,
  "top_k": 10
}
```

내부 처리 흐름

```text
Daily Digest Retriever
-> Digest Generator
-> Groundedness Check
-> Daily Digest 저장
```

Response

```json
{
  "success": true,
  "data": {
    "digest_id": "digest_20260506",
    "status": "completed",
    "item_count": 10,
    "candidate_count": 31,
    "groundedness_score": 0.91
  },
  "error": null
}
```

### 5.2 Daily Digest 조회

```http
GET /digest/{digest_id}
```

Response

```json
{
  "success": true,
  "data": {
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
  },
  "error": null
}
```

### 5.3 Daily Digest 목록 조회

```http
GET /digest?date_from=2026-05-01&date_to=2026-05-06
```

Response

```json
{
  "success": true,
  "data": [
    {
      "digest_id": "digest_20260506",
      "date": "2026-05-06",
      "item_count": 10,
      "candidate_count": 31,
      "groundedness_score": 0.91
    }
  ],
  "error": null
}
```

## 6. 온디맨드 질의 API

### 6.1 사용자 질문 응답

```http
POST /query
```

사용자의 일반적인 질문이나 기간별 트렌드 비교 질문을 처리합니다. 내부적으로 `Intent Router`가 질문의 의도를 분석하여 적절한 워크플로우(일반 QA vs 트렌드 비교)로 라우팅합니다.

Request

```json
{
  "question": "최근 HuggingFace에서 주목받는 AI Agent 기술은? (또는 '지난주 대비 이번 주 트렌드 비교해줘')",
  "top_k": 10,
  "date_to": "2026-05-06"
}
```

- `date_to`: (Optional) 검색 및 분석의 기준 종료일. 미입력 시 '현재 날짜'를 기본값으로 사용합니다. `Date Range Parser`가 이 날짜를 기준으로 "지난주", "어제" 등을 해석합니다.

내부 처리 흐름

```text
Intent Router (LangGraph)
-> (Branch A) General QA: Query Rewriter -> Retriever -> LLM Generator
-> (Branch B) Trend Comparison: Date Range Parser -> Period Retriever -> Trend Comparator -> LLM Generator
-> Groundedness Check
-> 통합 응답 반환
```

Response

```json
{
  "success": true,
  "data": {
    "intent": "general_query | trend_comparison",
    "answer": "사용자의 질문에 대한 최종 응답 (트렌드 비교인 경우 분석 결과 포함)",
    "groundedness_score": 0.89,
    "sources": [
      {
        "document_id": "doc_001",
        "title": "Example Title",
        "source": "huggingface",
        "url": "https://...",
        "period": "period_a | period_b"
      }
    ],
    "comparison_metadata": {
      "period_a": {
        "start": "2026-04-22",
        "end": "2026-04-28",
        "summary": "..."
      },
      "period_b": {
        "start": "2026-04-29",
        "end": "2026-05-06",
        "summary": "..."
      },
      "new_trends": ["트렌드 1", "트렌드 2"],
      "declining_trends": ["사라지는 흐름"]
    }
  },
  "error": null
}
```

## 7. Groundedness Check API

### 7.1 응답 근거성 검증

```http
POST /groundedness/check
```

Request

```json
{
  "answer": "생성된 응답 내용",
  "source_document_ids": ["doc_001", "doc_002"]
}
```

Response

```json
{
  "success": true,
  "data": {
    "score": 0.92,
    "passed": true,
    "threshold": 0.8,
    "fallback_required": false
  },
  "error": null
}
```

## 8. Streamlit UI 통합 API

### 8.1 대시보드 데이터 조회

```http
GET /dashboard
```

Response

```json
{
  "success": true,
  "data": {
    "latest_digest": {
      "digest_id": "digest_20260506",
      "date": "2026-05-06",
      "item_count": 10
    },
    "collection_status": {
      "last_collected_at": "2026-05-06T09:00:00",
      "collected_count": 86,
      "filtered_count": 31
    },
    "source_stats": {
      "huggingface": 18,
      "hackernews": 13
    },
    "top_tags": [
      {
        "tag": "multi-agent",
        "count": 12
      },
      {
        "tag": "rag",
        "count": 9
      }
    ]
  },
  "error": null
}
```

## 9. 스케줄러 API

### 9.1 정기 발행 스케줄 조회

```http
GET /scheduler
```

Response

```json
{
  "success": true,
  "data": {
    "enabled": true,
    "time": "09:00",
    "timezone": "Asia/Seoul",
    "sources": ["huggingface", "hackernews"],
    "last_run_at": "2026-05-06T09:00:00+09:00",
    "next_run_at": "2026-05-07T09:00:00+09:00"
  },
  "error": null
}
```

### 9.2 정기 발행 스케줄 수정

```http
PUT /scheduler
```

Request

```json
{
  "enabled": true,
  "time": "09:00",
  "timezone": "Asia/Seoul",
  "sources": ["huggingface", "hackernews"]
}
```

Response

```json
{
  "success": true,
  "data": {
    "enabled": true,
    "time": "09:00",
    "timezone": "Asia/Seoul",
    "sources": ["huggingface", "hackernews"],
    "last_run_at": null,
    "next_run_at": "2026-05-06T09:00:00+09:00"
  },
  "error": null
}
```

## 10. 주요 데이터 모델

### Document

`SKILLS.md`의 기본 Document 필드 중 `date`는 API 모델에서 `published_at`을 우선 사용하고, 발행일이 없는 경우 `collected_at` 기준 날짜로 해석합니다.

```json
{
  "document_id": "doc_001",
  "title": "string",
  "source": "huggingface | hackernews",
  "url": "string",
  "published_at": "YYYY-MM-DD",
  "collected_at": "YYYY-MM-DDTHH:mm:ss",
  "category": "agent | rag | llm | framework | benchmark",
  "tags": ["string"],
  "content": "string",
  "summary": "string",
  "metadata": {
    "author": "string",
    "score": 123,
    "comments_count": 45
  }
}
```

### DigestItem

```json
{
  "document_id": "doc_001",
  "title": "string",
  "source": "huggingface | hackernews",
  "url": "string",
  "published_at": "YYYY-MM-DD",
  "summary": "string",
  "key_points": ["string"],
  "contribution": "string",
  "benchmark": "string",
  "critique": "string",
  "tags": ["string"],
  "evidence_document_ids": ["doc_001"],
  "llm_model": "solar-pro-3"
}
```

### TrendComparison

```json
{
  "period_a_summary": "string",
  "period_b_summary": "string",
  "new_trends": ["string"],
  "declining_trends": ["string"],
  "analysis": "string",
  "sources": []
}
```

## 11. 주요 에러 코드

| Code                           | 설명                                    |
| ------------------------------ | --------------------------------------- |
| `PROFILE_NOT_FOUND`            | 관심사 프로필이 설정되지 않음           |
| `HUGGINGFACE_COLLECTOR_FAILED` | HuggingFace Daily Papers 수집 실패      |
| `HACKERNEWS_COLLECTOR_FAILED`  | HackerNews 수집 실패                    |
| `NORMALIZATION_FAILED`         | 공통 Document 스키마 변환 실패          |
| `VECTOR_DB_ERROR`              | ChromaDB 저장 또는 검색 실패            |
| `INSUFFICIENT_DATA`            | 트렌드 비교에 필요한 기간별 데이터 부족 |
| `GROUNDING_FAILED`             | Groundedness Check 기준 미달            |
| `LLM_GENERATION_FAILED`        | LLM 응답 생성 실패                      |
| `INVALID_DATE_RANGE`           | 날짜 범위 입력 오류                     |
| `SCHEDULER_ERROR`              | 정기 발행 스케줄러 오류                 |
| `RELEVANCE_FILTER_FAILED`      | Solar Mini 관련성 판정 실패             |
| `DIGEST_RETRIEVAL_FAILED`      | Daily Digest 후보 문서 검색 실패        |
| `DIGEST_GENERATION_FAILED`     | Solar Pro 3 Digest 요약/비평 생성 실패  |

## 12. 역할 분담 기준 API 매핑

| 담당 모듈                         | 관련 API                                                                         |
| --------------------------------- | -------------------------------------------------------------------------------- |
| 데이터 수집 및 정규화 파이프라인  | `POST /pipeline/collect`                                                         |
| VectorDB, 임베딩, 검색 인덱스     | `POST /documents/search`                                                         |
| 정기 발행 Digest 생성 모듈        | `POST /digest/generate`, `GET /digest/{digest_id}`, `GET /digest`                |
| Scheduler                         | `GET /scheduler`, `PUT /scheduler`, 내부 `SchedulerRunResult`                    |
| Solar Mini 관련성 필터            | `POST /pipeline/collect`, 내부 `SolarMiniRelevanceDecision`                      |
| Daily Digest Retriever           | `POST /digest/generate`, 내부 `DailyDigestRetrievalResult`                       |
| Solar Pro 3 요약/비평 프롬프트    | `POST /digest/generate`, `GET /digest/{digest_id}`                               |
| 온디맨드 질의 및 트렌드 비교 모듈 | `POST /query`                                                                    |
| UI, 통합, 검증, 배포              | `GET /dashboard`, `POST /groundedness/check`                                     |
