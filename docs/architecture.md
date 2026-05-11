# 아키텍처

TrendCurator는 AI 에이전트 관련 정보를 수집하고, VectorDB에 저장하고, RAG로 관련 문맥을 검색한 뒤 요약, Digest, 트렌드 비교를 생성하는 파이프라인 기반 AI 시스템입니다.

## 전체 구조

```text
스케줄러 / 사용자 요청 / 프론트엔드
-> app/services
-> app/collectors
-> VectorDB / RAG 검색
-> app/agents
-> frontend 또는 발행 채널
```

`app/services`는 각 유스케이스의 orchestration 경계입니다. 정기 발행에서는 수집기, 저장, 검색, 요약 단계를 조합하고, 온디맨드 질의와 트렌드 비교에서는 검색과 에이전트 처리를 조합합니다.

## 애플리케이션 계층

- `app/collectors`: 소스별 수집 경계
- `app/core`: 공통 인프라와 설정 경계
- `app/agents`: AI 추론, 요약, 비평, 비교 경계
- `app/prompts`: 프롬프트 템플릿과 프롬프트 변경 관리 경계
- `app/services`: end-to-end 워크플로우 orchestration 경계
- `frontend`: 사용자 대상 상호작용 경계
- `data/profiles`: 수집 소스 프로필과 수집 규칙 경계
- `data/samples`: 샘플 문서와 테스트용 예시 데이터 경계
- `tests`: 기능 검증 경계
- `docs`: 아키텍처와 워크플로우 문서화 경계

## 아키텍처 방향

이 프로젝트는 LangGraph 스타일의 상태 기반 워크플로우를 전제로 합니다. 각 파이프라인 단계는 명시적인 상태를 입력받고, 자신이 책임지는 필드만 갱신한 뒤, 정의된 계약을 통해 다음 단계로 결과를 전달해야 합니다.
## Query API workflow

Public API routes are mounted under `/api/v1`. The UI-facing query endpoint uses this flow:

```text
POST /api/v1/query
-> app/api/query.py
-> app/graphs/query_graph.py
-> IntentRouter
-> GENERAL_QA: QueryRewriter -> Retriever
-> TREND_COMPARISON: DateRangeParser -> PeriodRetriever
-> Answer generation
-> GroundednessChecker
```

Additional layers:

- `app/api`: FastAPI external API routers.
- `app/graphs`: LangGraph workflow orchestration.
- `frontend`: Streamlit UI that calls `/api/v1` APIs.

The graph keeps the internal intent labels from the agent contract:

- `GENERAL_QA`
- `TREND_COMPARISON`

The external API response maps these labels to API-facing values:

- `general_query`
- `trend_comparison`
