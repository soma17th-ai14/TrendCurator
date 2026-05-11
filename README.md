# TrendCurator

TrendCurator는 AI 에이전트 관련 최신 정보를 자동 수집하고, 검색하고, 요약하고, 기간별로 비교하는 AI 시스템입니다.

이 서비스는 AI 에이전트 분야의 변화와 주요 신호를 자동으로 추적하기 위해 설계되었습니다. 수집한 정보를 VectorDB에 저장하고, RAG 기반 검색과 요약을 통해 정기 Digest, 사용자 질의 응답, 기간별 트렌드 비교를 제공합니다.

## 핵심 기능

- 자동 수집: 외부 소스에서 AI 에이전트 관련 최신 정보를 수집합니다.
- RAG 기반 검색: 수집 및 임베딩된 문서를 기반으로 관련 정보를 검색합니다.
- 요약 및 비평: 중요한 업데이트를 요약하고 의미를 해석합니다.
- Daily Digest: 정기적으로 핵심 내용을 정리한 Digest를 생성합니다.
- 트렌드 비교: 기간별 변화, 주제 빈도, 새롭게 등장한 흐름을 비교합니다.

## 시스템 워크플로우

### 정기 발행 파이프라인

```text
스케줄러
-> 발행 서비스
-> 수집기
-> 외부 소스
-> 문서 정규화
-> VectorDB 저장
-> RAG 검색
-> 요약 및 비평
-> Daily Digest 생성
-> 프론트엔드 또는 발행 채널
```

### 온디맨드 질의

```text
사용자 질문
-> 프론트엔드
-> 질의 서비스
-> RAG 검색
-> 에이전트 추론
-> 요약 응답 생성
-> UI 응답
```

### 트렌드 비교

```text
비교 기간 선택
-> 분석 서비스
-> 기간별 문서 조회
-> 핵심 신호 추출
-> 주제와 빈도 비교
-> 트렌드 요약 생성
-> 인사이트 제공
```

## 폴더 구조 설명

- `app/core/`: 설정, 로깅, 공통 타입, 외부 클라이언트 등 공통 인프라를 관리합니다.
- `app/collectors/`: 외부 데이터 수집 모듈만 배치합니다.
- `app/agents/`: 요약, 비평, 검색 추론, 트렌드 비교 등 LLM/AI 처리 단위를 배치합니다.
- `app/prompts/`: 프롬프트 템플릿과 프롬프트 관련 문서를 관리합니다.
- `app/services/`: 파이프라인과 주요 유스케이스를 조합하는 orchestration 계층입니다.
- `frontend/`: 사용자 인터페이스와 통합 화면을 담당합니다.
- `data/profiles/`: 수집 소스 프로필, 수집 규칙, 비밀값이 아닌 참조 설정을 관리합니다.
- `data/samples/`: 샘플 문서와 테스트용 예시 데이터를 관리합니다.
- `tests/`: 향후 구현될 기능의 테스트를 배치합니다.
- `docs/`: 아키텍처, 워크플로우, 프로젝트 문서를 관리합니다.
- `docs/api-spec.md`: 모듈 개발과 프론트엔드 연동에 공통으로 사용할 API 계약 초안을 정의합니다.
- `AGENTS.md`: Codex 및 범용 AI 에이전트 작업 지침을 정의합니다.
- `CLAUDE.md`: Claude 작업 지침과 문서 우선순위를 정의합니다.
- `SKILLS.md`: 팀 공통 개발 규칙과 아키텍처 기준을 정의합니다.
- `CONTRIBUTING.md`: 브랜치, PR, 리뷰, 커밋 규칙을 정의합니다.

## 로컬 환경변수 설정

Solar API를 사용하는 모듈은 환경변수에서 키와 모델 설정을 읽습니다. 공개 레포에는 실제 API 키를 커밋하지 않습니다.

1. `.env.example`을 참고해 레포 루트에 `.env` 파일을 만듭니다.
2. `.env`에 개인 또는 팀에서 발급받은 Upstage API 키를 입력합니다.

```env
SOLAR_API_KEY=여기에_Upstage_API_Key
SOLAR_BASE_URL=https://api.upstage.ai/v1
SOLAR_MINI_MODEL=solar-mini
SOLAR_DIGEST_MODEL=solar-pro3
```

`.env`와 `.env.*` 파일은 `.gitignore`에 포함되어 있어 커밋 대상이 아닙니다. `.env.example`에는 키 이름과 기본 설정만 남깁니다.

Solar Mini 관련성 필터의 실제 API 연결을 확인하려면 다음 명령을 실행합니다.

```powershell
python scripts/smoke_solar_relevance.py
```

라벨된 샘플 문서 기준으로 필터 성능을 확인하려면 다음 명령을 실행합니다. 이 명령은 실제 Solar API를 호출하므로 API 사용량과 쿼터를 소모합니다.

```powershell
python scripts/evaluate_relevance_samples.py
```

## 스케줄러 설정

정기 Daily Digest 실행 진입점은 다음 명령으로 실행합니다.

```bash
python scripts/run_scheduled_digest.py
```

Docker Compose 환경에서는 scheduler 서비스의 `command`에서 같은 entrypoint를 호출합니다.

```yaml
command: ["python", "scripts/run_scheduled_digest.py"]
```

스케줄러는 환경변수에서 실행 설정을 읽습니다. 환경변수가 없으면 기본값을 사용합니다.

```env
SCHEDULER_ENABLED=true
SCHEDULER_TIME=09:00
SCHEDULER_TIMEZONE=Asia/Seoul
SCHEDULER_SOURCES=huggingface,hackernews
```

## 팀 역할 분담

- 데이터 수집: 소스 발굴, 수집 전략, 수집 프로필, 수집 안정성을 담당합니다.
- VectorDB / RAG: 문서 구조, 임베딩 전략, VectorDB 저장, 검색 품질을 담당합니다.
- Digest 생성: 정기 요약, 비평 형식, Digest 발행 규칙을 담당합니다.
- 온디맨드 / 트렌드 분석: 사용자 질의 처리, 질의 해석, 기간별 비교, 응답 품질을 담당합니다.
- UI / 통합: 프론트엔드, API 연동, 사용자 흐름, 발행 채널 통합을 담당합니다.

## 개발 순서

1. 수집
2. 저장
3. 검색
4. 요약
5. 비교
6. UI

## UI / integration / validation / deployment notes

This repository now includes the UI and integration layer for the education assignment:

- Streamlit UI in `frontend/streamlit_app.py`
- FastAPI integration endpoints for dashboard, query, digest generation, and groundedness checks
- LangGraph-based query orchestration with a sequential fallback before dependencies are installed
- Groundedness Check service with an injectable RAGAS evaluator contract and a deterministic fallback scorer
- Docker Compose services for the FastAPI backend and Streamlit frontend

### Local run

```bash
uvicorn app.main:app --reload
streamlit run frontend/streamlit_app.py
```

Streamlit calls `http://localhost:8000` by default. Override it with `TRENDCURATOR_API_BASE_URL`.

### Docker Compose run

```bash
docker compose up --build
```

- FastAPI: `http://localhost:8000`
- Streamlit: `http://localhost:8501`

Set `SOLAR_API_KEY` before running when real Solar generation or embedding calls are needed. Without the key, the UI and fallback groundedness/demo paths remain available.

### Added API surface

- `GET /health`
- `GET /api/v1/dashboard`
- `POST /api/v1/query`
- `POST /api/v1/groundedness/check`
- `POST /api/v1/digest/generate`

### Query orchestration

`POST /api/v1/query` uses the query agents from the earlier integration work:

```text
IntentRouter
-> GENERAL_QA: QueryRewriter -> Retriever
-> TREND_COMPARISON: DateRangeParser -> PeriodRetriever
-> answer generation
-> GroundednessChecker
```

If the Solar API key or VectorDB search is unavailable, the workflow returns a warning and an empty-source response instead of failing with a 500 error.
