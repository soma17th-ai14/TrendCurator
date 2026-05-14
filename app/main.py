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

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

from app.api.dashboard import router as dashboard_router
from app.api.digest import router as digest_router
from app.api.documents import router as documents_router
from app.api.groundedness import router as groundedness_router
from app.api.pipeline import router as pipeline_router
from app.api.query import router as query_router
from app.api.profile import router as profile_router
from app.api.scheduler import router as scheduler_router

logger = logging.getLogger(__name__)


def _spawn_startup_coordinator(scheduler, *, demo_days: int) -> threading.Thread:
    """부팅 작업을 정해진 순서대로 직렬 실행한 뒤 스케줄러 루프를 시작합니다.

    순서:

    1. demo bootstrap (``demo_days`` > 0 일 때만, 직전 N일 다이제스트 보강)
    2. startup digest (효력 일자 다이제스트 생성)
    3. 스케줄러 루프 가동

    이전 구조에서는 1~3 이 모두 데몬 스레드로 동시에 spawn 되어, 같은 외부 API 를 짧은
    간격으로 두 번 호출하는 race 가 있었습니다. ``_RUN_PIPELINE_LOCK`` 으로 직렬화는
    돼 있지만, 부트스트랩이 완료되기 전에 스케줄러 루프가 같은 날짜 파이프라인을 추가로
    돌리는 시나리오를 구조적으로 차단하기 위해 한 스레드 안에서 순차 실행합니다.

    ASGI 이벤트 루프를 막지 않도록 코디네이터 자체는 데몬 스레드로 분리합니다.
    """
    from app.api.scheduler import ensure_loop_running
    from app.services.scheduled_pipeline import run_demo_bootstrap, run_startup_digest

    config = scheduler.state.config

    def _runner() -> None:
        if demo_days > 0:
            try:
                run_demo_bootstrap(config, days=demo_days)
            except Exception as exc:  # pragma: no cover - run_demo_bootstrap 내부에서 일자별 처리됨
                logger.warning("startup coordinator: demo bootstrap 실패 (%s)", exc)

        try:
            run_startup_digest(config)
        except Exception as exc:  # pragma: no cover - run_startup_digest 내부에서 처리됨
            logger.warning("startup coordinator: 효력 일자 다이제스트 생성 실패 (%s)", exc)

        # 부트스트랩 결과와 무관하게 스케줄러 루프는 가동돼야 향후 일일 사이클이 동작합니다.
        try:
            ensure_loop_running(scheduler)
            logger.info("startup coordinator: 부트스트랩 완료 후 스케줄러 루프를 시작했습니다.")
        except Exception as exc:  # pragma: no cover
            logger.warning("startup coordinator: 스케줄러 루프 시작 실패 (%s)", exc)

    thread = threading.Thread(target=_runner, daemon=True, name="startup-coordinator")
    thread.start()
    return thread


def _spawn_demo_bootstrap_thread(config, days: int) -> threading.Thread:
    """Run demo startup backfill in a daemon thread.

    스케줄러 autostart 가 비활성일 때만 사용됩니다. 스케줄러가 켜져 있으면
    ``_spawn_startup_coordinator`` 가 부트스트랩 → startup digest → 스케줄러 시작 순서로
    직렬 실행합니다.
    """
    from app.services.scheduled_pipeline import run_demo_bootstrap

    def _runner() -> None:
        try:
            run_demo_bootstrap(config, days=days)
        except Exception as exc:  # pragma: no cover - run_demo_bootstrap handles per-date failures.
            logger.warning("demo bootstrap thread error: %s", exc)

    thread = threading.Thread(target=_runner, daemon=True, name="demo-bootstrap")
    thread.start()
    return thread


def _is_truthy_env(name: str) -> bool:
    return os.getenv(name, "").lower() in ("1", "true", "yes")


def _demo_bootstrap_days_from_env() -> int:
    raw_value = os.getenv("DEMO_BOOTSTRAP_DAYS", "5")
    try:
        days = int(raw_value)
    except ValueError:
        logger.warning("invalid DEMO_BOOTSTRAP_DAYS=%s, using 5", raw_value)
        return 5
    if days < 0:
        logger.warning("invalid DEMO_BOOTSTRAP_DAYS=%s, skipping demo bootstrap", raw_value)
        return 0
    return days


def _maybe_spawn_demo_bootstrap_on_startup(config=None) -> threading.Thread | None:
    if not _is_truthy_env("DEMO_BOOTSTRAP_ON_STARTUP"):
        return None

    if config is None:
        try:
            from app.core.scheduler_settings import load_scheduler_config_from_env

            config = load_scheduler_config_from_env()
        except Exception as exc:
            logger.warning("demo bootstrap: scheduler config load failed: %s", exc)
            return None

    days = _demo_bootstrap_days_from_env()
    if days <= 0:
        return None
    return _spawn_demo_bootstrap_thread(config, days)


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

    scheduler_config = None
    coordinator_started = False

    # SCHEDULER_AUTOSTART=1 환경변수가 있을 때만 부팅 시 코디네이터 스레드를 통해
    # 부트스트랩 → startup digest → 스케줄러 루프 순서로 직렬 실행합니다. 동시 spawn 으로
    # 인한 race(같은 날짜 파이프라인 중복 실행, 외부 API rate-limit 노출)를 구조적으로 차단합니다.
    if _is_truthy_env("SCHEDULER_AUTOSTART"):
        from app.api.scheduler import ensure_loop_running, get_scheduler_service
        scheduler = get_scheduler_service()
        if scheduler is not None:
            scheduler_config = scheduler.state.config
            # SCHEDULER_ENABLED=false 로 명시적으로 꺼둔 경우엔 부팅 자동 실행과 코디네이터를
            # 건너뛰고 루프만 가동합니다(스케줄러가 disable 인 의도를 보존).
            if scheduler.state.config.enabled:
                demo_days = (
                    _demo_bootstrap_days_from_env()
                    if _is_truthy_env("DEMO_BOOTSTRAP_ON_STARTUP")
                    else 0
                )
                _spawn_startup_coordinator(scheduler, demo_days=demo_days)
                coordinator_started = True
            else:
                ensure_loop_running(scheduler)

    # 스케줄러 autostart 가 꺼져 있어도 데모 부트스트랩만 따로 돌리는 경로는 유지합니다.
    if not coordinator_started:
        _maybe_spawn_demo_bootstrap_on_startup(scheduler_config)
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
