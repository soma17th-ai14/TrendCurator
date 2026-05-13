"""백그라운드 스케줄러 루프 — FastAPI lifespan에서 실행됩니다."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Callable, Optional

from app.services.scheduler import PipelineRunner, SchedulerService

logger = logging.getLogger(__name__)

_CHECK_INTERVAL_SECONDS = 60


class SchedulerLoop:
    """별도 스레드에서 스케줄러를 주기적으로 확인하고 파이프라인을 실행합니다."""

    def __init__(
        self,
        scheduler: SchedulerService,
        runner: Optional[PipelineRunner] = None,
    ) -> None:
        if runner is None:
            from app.services.scheduled_pipeline import run_pipeline
            runner = run_pipeline
        self._scheduler = scheduler
        self._runner = runner
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="scheduler-loop")
        self._thread.start()
        logger.info("스케줄러 루프 시작")

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        logger.info("스케줄러 루프 종료")

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                result = self._scheduler.run_due(
                    runner=self._runner,
                    now=datetime.now(tz=self._scheduler.state.config.zoneinfo),
                )
                if result.ran:
                    logger.info(
                        "스케줄러: 파이프라인 실행 완료 — date=%s job_id=%s",
                        result.run_date,
                        result.job_id,
                    )
                elif result.skipped_reason:
                    logger.debug("스케줄러: 실행 건너뜀 (%s)", result.skipped_reason)
            except Exception as exc:
                logger.error("스케줄러 루프 오류: %s", exc)

            self._stop.wait(_CHECK_INTERVAL_SECONDS)
