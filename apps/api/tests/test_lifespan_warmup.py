from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from app.bootstrap.lifespan import QWEN_WARMUP_PROMPT, _warm_qwen
from app.contracts import ModelResponse
from fastapi import FastAPI


class WarmupModelService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def preflight(self, task_type: str, *, modality: str) -> Any:
        assert task_type == "general_question_answer"
        assert modality == "text"
        return SimpleNamespace(usable_aliases=("qwen_text_fast",))

    async def generate_for_task(self, task_type: str, **kwargs: Any) -> ModelResponse:
        self.calls.append({"task_type": task_type, **kwargs})
        return ModelResponse(
            provider="dashscope",
            model="qwen3.8-flash",
            content="OK",
            elapsed_ms=12,
        )


@pytest.mark.asyncio
async def test_qwen_warmup_makes_one_fixed_standard_flash_call() -> None:
    app = FastAPI()
    service = WarmupModelService()
    settings = SimpleNamespace(
        qwen_warmup_enabled=True,
        qwen_warmup_timeout_seconds=1,
    )

    await _warm_qwen(app, service, settings)  # type: ignore[arg-type]

    assert len(service.calls) == 1
    call = service.calls[0]
    assert call["task_type"] == "general_question_answer"
    assert call["messages"] == [{"role": "user", "content": QWEN_WARMUP_PROMPT}]
    assert call["extra_options"] == {
        "max_tokens": 4,
        "temperature": 0,
        "response_depth": "standard",
        "_allow_route_fallback": False,
    }
    assert app.state.qwen_warmup == {
        "status": "completed",
        "model": "qwen3.8-flash",
        "elapsed_ms": 12,
    }
