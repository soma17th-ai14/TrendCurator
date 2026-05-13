"""TrendCurator FastAPI 앱 진입점."""

from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

# lifespan 에서 os.getenv 로 읽는 운영 옵션(CHROMA_RESET_ON_STARTUP, SCHEDULER_AUTOSTART 등)이
# .env 파일에서도 적용되도록, 라우터 import 전에 한 번만 dotenv 를 로드한다.
load_dotenv(".env")
load_dotenv(".env.local")

from app.api.dashboard import router as dashboard_router
from app.api.digest import router as digest_router
from app.api.documents import router as documents_router
from app.api.groundedness import router as groundedness_router
from app.api.pipeline import router as pipeline_router
from app.api.query import router as query_router
from app.api.profile import router as profile_router
from app.api.scheduler import router as scheduler_router

logger = logging.getLogger(__name__)


def _spawn_startup_digest_thread(config) -> threading.Thread:
    """부팅 직후 효력 일자 기준 다이제스트를 백그라운드 스레드에서 생성합니다.

    ``run_pipeline`` 은 LLM 호출과 외부 수집을 포함해 수십 초~수 분이 걸릴 수 있으므로,
    ASGI 이벤트 루프를 막지 않도록 별도 데몬 스레드로 실행합니다.
    """
    from app.services.scheduled_pipeline import run_startup_digest

    def _runner() -> None:
        try:
            run_startup_digest(config)
        except Exception as exc:  # pragma: no cover - run_startup_digest 내부에서 처리됨
            logger.warning("부팅 자동 실행 스레드 오류: %s", exc)

    thread = threading.Thread(target=_runner, daemon=True, name="startup-digest")
    thread.start()
    return thread


def _is_truthy_env(name: str) -> bool:
    return os.getenv(name, "").lower() in ("1", "true", "yes")


def _maybe_reset_state_on_startup() -> None:
    """``CHROMA_RESET_ON_STARTUP`` 가 켜져있으면 시연용 상태를 모두 비운다.

    범위:
    - 벡터DB(ChromaDB) 컬렉션
    - 다이제스트 JSON 파일 ``data/digests/digest_*.json``
    - 수집 상태 파일 ``data/collection_status.json``

    데모/시연 환경에서 부팅 시 항상 깨끗한 상태로 시작하기 위한 옵션이며, 기본값은 비활성이다.
    각 단계는 독립적으로 try/except 로 감싸므로 한 단계가 실패해도 나머지는 진행한다.
    """
    if not _is_truthy_env("CHROMA_RESET_ON_STARTUP"):
        return

    from app.core.settings import get_settings

    settings = get_settings()

    try:
        from app.core.chroma_client import ChromaClient

        ChromaClient(settings).reset_collection()
        logger.info("부팅 시 ChromaDB 컬렉션을 비웠습니다.")
    except Exception as exc:
        logger.warning("부팅 시 ChromaDB 청소 실패: %s", exc)

    try:
        from app.services.digest_store import FileDigestStore

        removed = FileDigestStore(settings.digest_data_path).delete_all()
        logger.info("부팅 시 다이제스트 파일 %d 건을 삭제했습니다.", removed)
    except Exception as exc:
        logger.warning("부팅 시 다이제스트 청소 실패: %s", exc)

    try:
        from app.services.collection_status_store import CollectionStatusStore

        cleared = CollectionStatusStore(settings.collection_status_path).clear()
        if cleared:
            logger.info("부팅 시 수집 상태 파일을 비웠습니다.")
    except Exception as exc:
        logger.warning("부팅 시 수집 상태 청소 실패: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 데모 시연 시 부팅 시 상태(벡터DB + 다이제스트 + 수집 상태)를 모두 비우는 옵션.
    # SCHEDULER_AUTOSTART 와 독립적으로 동작한다.
    _maybe_reset_state_on_startup()

    # SCHEDULER_AUTOSTART=1 환경변수가 있을 때만 시작 시 루프를 자동 시작합니다.
    # 테스트 환경에서는 이 변수를 설정하지 않으면 루프가 시작되지 않습니다.
    if _is_truthy_env("SCHEDULER_AUTOSTART"):
        from app.api.scheduler import ensure_loop_running, get_scheduler_service
        scheduler = get_scheduler_service()
        if scheduler is not None:
            ensure_loop_running(scheduler)
            # SCHEDULER_ENABLED=false 로 명시적으로 꺼둔 경우엔 부팅 자동 실행도 건너뛴다.
            # 그렇지 않으면 스케줄링을 disable 한 의도와 무관하게 부팅이 수집/LLM 호출을
            # 트리거할 수 있다.
            if scheduler.state.config.enabled:
                # 효력 일자 기준 다이제스트가 없으면 즉시 생성 (스케줄 시각을 기다리지 않음).
                _spawn_startup_digest_thread(scheduler.state.config)
    try:
        yield
    finally:
        from app.api.scheduler import stop_scheduler_loop
        stop_scheduler_loop()


app = FastAPI(title="TrendCurator API", lifespan=lifespan)
API_PREFIX = "/api/v1"

app.include_router(pipeline_router, prefix=API_PREFIX)
app.include_router(documents_router, prefix=API_PREFIX)
app.include_router(groundedness_router, prefix=API_PREFIX)
app.include_router(query_router, prefix=API_PREFIX)
app.include_router(dashboard_router, prefix=API_PREFIX)
app.include_router(digest_router, prefix=API_PREFIX)
app.include_router(scheduler_router, prefix=API_PREFIX)
app.include_router(profile_router, prefix=API_PREFIX)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
