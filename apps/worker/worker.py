from __future__ import annotations

import asyncio
import logging
import os

from app.core.config import get_settings
from app.services.task_queue import RedisTaskQueue
from app.services.task_worker import TaskWorker

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    # Avoid constructing an unused FastAPI application during module import.
    os.environ["XZD_SKIP_DEFAULT_APP"] = "1"
    from app.main import create_app

    configured = get_settings()
    # The worker owns the local RuntimeTaskEngine through TaskExecutor. The API
    # uses the same config with TASK_EXECUTOR_MODE=redis and only publishes IDs.
    settings = configured.model_copy(update={"task_executor_mode": "local"})
    app = create_app(settings)
    queue = RedisTaskQueue(
        settings.redis_url,
        queue_name=settings.task_queue_name,
        worker_lock_ttl_seconds=settings.task_worker_lock_ttl_seconds,
    )
    async with app.router.lifespan_context(app):
        try:
            await TaskWorker(
                app.state.task_executor,
                queue,
                block_timeout_seconds=settings.task_queue_block_timeout_seconds,
                recovery_interval_seconds=(
                    settings.task_worker_recovery_interval_seconds
                ),
            ).run()
        finally:
            await queue.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("task_worker_stopped")


if __name__ == "__main__":
    main()
