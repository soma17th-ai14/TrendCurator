# AGENTS.md

이 파일은 Codex 및 범용 AI 개발 에이전트가 TrendCurator 레포지토리에서 작업할 때 따라야 하는 실행 지침입니다.

## 최상위 기준

- 공통 개발 규칙과 아키텍처 기준은 `SKILLS.md`를 따릅니다.
- Claude 전용 지침은 `CLAUDE.md`에 별도로 정리하되, 내용 충돌 시 `SKILLS.md`를 우선합니다.
- PR 작성 방식은 `CONTRIBUTING.md`의 PR 템플릿과 예시를 따릅니다.
- README, 문서, 커밋 메시지, PR 제목, PR 설명은 한국어로 작성합니다.

## 문서 확인 순서

1. `SKILLS.md`
2. `AGENTS.md`
3. `CONTRIBUTING.md`
4. `README.md`
5. `docs/api-spec.md`
6. `docs/architecture.md`
7. `docs/workflow.md`

## 작업 원칙

- 사용자 요청 범위를 벗어난 구현을 하지 않습니다.
- 함수, 클래스, 로직 작성 전에는 인터페이스와 데이터 구조를 먼저 문서화합니다.
- API, 서비스, 프론트엔드 연동 작업 전에는 `docs/api-spec.md`의 요청/응답 계약과 데이터 모델을 먼저 확인합니다.
- 기존 파일을 수정할 때는 현재 구조와 문서 규칙을 먼저 확인합니다.
- 변경 후에는 관련 문서 간 용어, 폴더 책임, 워크플로우 순서가 일치하는지 확인합니다.
- 엔드포인트, 응답 스키마, 에러 코드, 모듈별 API 매핑이 바뀌면 `docs/api-spec.md`를 함께 수정합니다.

## 레포지토리 구조 기준

- `app/collectors/`: 외부 데이터 수집 책임만 가집니다.
- `app/agents/`: LLM/AI 처리 책임만 가집니다.
- `app/prompts/`: 프롬프트 템플릿과 프롬프트 변경 이력을 관리합니다.
- `app/services/`: 파이프라인 orchestration 책임을 가집니다.
- `app/core/`: 공통 인프라와 설정 책임을 가집니다.
- `frontend/`: UI와 사용자 흐름 책임을 가집니다.
- `data/profiles/`: 수집 소스 프로필과 수집 규칙을 관리합니다.
- `data/samples/`: 샘플 문서와 테스트용 예시 데이터를 관리합니다.
- `tests/`: 기능 검증을 위한 테스트를 관리합니다.
- `docs/`: 아키텍처와 워크플로우 설명을 유지합니다.

## Git 및 PR 작업 기준

- 브랜치 전략은 `main`, `feature/<short-description>`를 사용합니다.
- 커밋 메시지는 한국어로 작성합니다.
- 권장 커밋 형식은 `<type>: <요약>`입니다.
- PR 제목과 설명은 한국어로 작성합니다.
- PR 본문에는 변경 목적, 변경 내용, 영향 범위, 테스트 결과 또는 테스트 비대상 사유, 문서 변경 여부, 리뷰 포인트, 후속 작업을 포함합니다.
- API 계약 변경이 포함된 PR은 `docs/api-spec.md` 변경 여부와 호환성 영향을 PR 본문에 명시합니다.
- 예시 커밋 메시지: `docs: 에이전트 공통 작업 지침 추가`
