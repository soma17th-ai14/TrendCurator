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
