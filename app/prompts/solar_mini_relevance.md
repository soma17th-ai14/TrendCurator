# Solar Mini 관련성 필터 프롬프트

## 목적

수집된 문서가 TrendCurator의 AI Agent Daily Digest 후보로 적합한지 판정합니다.
이 프롬프트는 `POST /pipeline/collect` 내부의 `Relevance Filter` 단계에서 사용할 수 있습니다.

## 판정 기준

관련성이 높음:

- AI Agent, 멀티 에이전트, LangGraph, tool-use, function calling, workflow orchestration을 직접 다룹니다.
- RAG, memory, planner, reasoning, evaluation이 에이전트 시스템 맥락에서 설명됩니다.
- 에이전트 프레임워크, 벤치마크, 운영 패턴, 실패 사례, 비교 분석을 포함합니다.

관련성이 낮음:

- 일반 LLM 뉴스지만 에이전트 시스템과 연결되지 않습니다.
- 단순 제품 출시, 투자, 채용, 마케팅성 글입니다.
- AI와 무관한 개발 일반 주제입니다.

## 출력

반드시 아래 JSON 형식만 반환합니다.

```json
{
  "is_relevant": true,
  "score": 0.0,
  "matched_keywords": ["string"],
  "reason": "판정 이유 1문장"
}
```

## 변경 이력

- 2026-05-08: 수집 파이프라인의 관련성 필터 계약에 맞춰 초기 프롬프트를 정의했습니다.
