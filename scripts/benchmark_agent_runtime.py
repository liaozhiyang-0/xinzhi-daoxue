"""Local synthetic benchmark for conversation-context overhead.

This script uses a temporary SQLite database, a deliberately unavailable Redis
endpoint, deterministic compaction, and no model or paid provider calls.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from sqlalchemy import event

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.contracts.api import SessionCreate  # noqa: E402
from app.contracts.conversation import MessageRole, MessageStatus  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.conversation_message_service import (  # noqa: E402
    ConversationMessageService,
)
from app.services.session_service import SessionService  # noqa: E402

USER_ID = "synthetic-benchmark-user"


async def run_benchmark() -> dict[str, Any]:
    with TemporaryDirectory(prefix="xzd-runtime-") as directory:
        root = Path(directory)
        settings = Settings(  # type: ignore[call-arg]
            app_env="test",
            log_level="WARNING",
            test_database_url=f"sqlite+aiosqlite:///{root / 'runtime.db'}",
            redis_url="redis://127.0.0.1:1/0",
            default_agent_provider="mock",
            allow_mock_fallback=True,
            rag_enabled=False,
            context_summary_message_trigger=4,
            context_recent_message_limit=2,
            local_storage_path=root / "storage",
            _env_file=None,
        )
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            query_count = 0

            def count_query(*_args: object, **_kwargs: object) -> None:
                nonlocal query_count
                query_count += 1

            event.listen(
                app.state.engine.sync_engine, "before_cursor_execute", count_query
            )
            async with app.state.session_factory() as db:
                session = await SessionService(db).create(
                    SessionCreate(user_id=USER_ID, course_id="CT", title="")
                )
                messages = ConversationMessageService(db)
                first_user = await messages.append(
                    session=session,
                    user_id=USER_ID,
                    role=MessageRole.USER,
                    status=MessageStatus.COMPLETED,
                    content_text="电阻是什么？",
                    metadata={"course_id": "CT", "intent": "general_qa"},
                )
                await messages.append(
                    session=session,
                    user_id=USER_ID,
                    role=MessageRole.ASSISTANT,
                    status=MessageStatus.COMPLETED,
                    content_text="电阻是表征导体阻碍电流能力的物理量。",
                    reply_to_message_id=first_user.id,
                    metadata={"course_id": "CT", "intent": "general_qa"},
                )
                await db.commit()

                async def assemble() -> Any:
                    return await app.state.context_assembly.assemble(
                        db,
                        session_id=session.id,
                        user_id=USER_ID,
                        current_message_id=first_user.id,
                        course_id="CT",
                        task_family="general_qa",
                        agent_id="LEARN_01_LOCAL_RETRIEVAL_V1",
                    )

                before = query_count
                cold = await assemble()
                cold_queries = query_count - before
                before = query_count
                warm = await assemble()
                warm_queries = query_count - before

                for index in range(3):
                    user_message = await messages.append(
                        session=session,
                        user_id=USER_ID,
                        role=MessageRole.USER,
                        status=MessageStatus.COMPLETED,
                        content_text=f"第 {index + 2} 轮追问",
                        metadata={"course_id": "CT", "intent": "follow_up_question"},
                    )
                    await messages.append(
                        session=session,
                        user_id=USER_ID,
                        role=MessageRole.ASSISTANT,
                        status=MessageStatus.COMPLETED,
                        content_text=f"第 {index + 2} 轮合成回答",
                        reply_to_message_id=user_message.id,
                        metadata={"course_id": "CT", "intent": "follow_up_question"},
                    )
                await db.commit()
                await app.state.context_assembly.assemble(
                    db,
                    session_id=session.id,
                    user_id=USER_ID,
                    current_message_id=user_message.id,
                    course_id="CT",
                    task_family="follow_up_question",
                    agent_id="LEARN_01_LOCAL_RETRIEVAL_V1",
                )
                summary, compaction_ms = (
                    await app.state.session_compaction.summarize_completed_turn(
                        db,
                        session=session,
                        source_task_id="synthetic-benchmark-task",
                    )
                )
                await db.commit()
                return {
                    "synthetic": True,
                    "not_for_official_scoring": True,
                    "paid_calls": False,
                    "cache_cold": {
                        "latency_ms": round(cold.build_latency_ms, 3),
                        "queries": cold_queries,
                        "cache_status": cold.cache_status,
                    },
                    "cache_hit": {
                        "latency_ms": round(warm.build_latency_ms, 3),
                        "queries": warm_queries,
                        "cache_status": warm.cache_status,
                        "cache_backend": warm.cache_backend,
                    },
                    "long_session_compaction_ms": round(compaction_ms, 3),
                    "summary_created": summary is not None,
                    "summary_token_estimate": summary.token_estimate if summary else 0,
                    "model_calls": 0,
                    "additional_summary_model_calls": 0,
                }


def main() -> None:
    print(json.dumps(asyncio.run(run_benchmark()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
