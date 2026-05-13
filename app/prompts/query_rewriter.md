사용자 질문을 VectorDB 검색에 적합한 짧은 검색 쿼리 1~2개로 재작성합니다.

반드시 JSON만 반환합니다.

출력 형식:
{
  "optimized_queries": ["검색 쿼리"],
  "search_filter": {
    "sources": ["huggingface", "hackernews"]
  }
}

규칙:
- 핵심 기술명, 프레임워크명, 방법론, 평가 지표를 보존합니다.
- 사용자가 특정 출처를 암시하지 않으면 sources에는 huggingface와 hackernews를 모두 포함합니다.
- sources 값은 huggingface, hackernews 중 하나 이상만 사용합니다.

질문: {query}
