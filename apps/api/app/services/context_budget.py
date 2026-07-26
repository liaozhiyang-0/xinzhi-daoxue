from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from app.contracts.conversation import ContextMessage
from app.core.config import Settings


@dataclass(frozen=True)
class BudgetDecision:
    recent_messages: list[ContextMessage]
    older_messages: list[ContextMessage]
    memories: list[dict[str, object]]
    token_estimate: int
    budget: int
    trimmed: bool
    estimation_method: str


class ContextBudgetManager:
    ESTIMATION_METHOD = "conservative_chars_div_2"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def available_input_tokens(self) -> int:
        return max(
            1,
            self.settings.context_max_input_tokens
            - self.settings.context_reserved_output_tokens,
        )

    def estimate_text(self, text: str) -> int:
        return 0 if not text else max(1, ceil(len(text) / 2))

    def apply(
        self,
        *,
        fixed_text: str,
        recent_messages: list[ContextMessage],
        older_messages: list[ContextMessage],
        memories: list[dict[str, object]],
    ) -> BudgetDecision:
        budget = self.available_input_tokens
        recent = self._deduplicate(recent_messages)
        older = self._deduplicate(older_messages)
        memory_items = list(memories)
        trimmed = len(recent) != len(recent_messages) or len(older) != len(
            older_messages
        )

        def estimate() -> int:
            text = "\n".join(
                [
                    fixed_text,
                    *(item.content_text for item in recent),
                    *(item.content_text for item in older),
                    *(str(item.get("content", "")) for item in memory_items),
                ]
            )
            return self.estimate_text(text)

        while estimate() > budget and older:
            older.pop(0)
            trimmed = True
        while estimate() > budget and memory_items:
            memory_items.pop()
            trimmed = True
        # Preserve the current turn. Remove the oldest complete pair only.
        while estimate() > budget and len(recent) > 2:
            recent.pop(0)
            trimmed = True
        return BudgetDecision(
            recent_messages=recent,
            older_messages=older,
            memories=memory_items,
            token_estimate=estimate(),
            budget=budget,
            trimmed=trimmed,
            estimation_method=self.ESTIMATION_METHOD,
        )

    @staticmethod
    def _deduplicate(messages: list[ContextMessage]) -> list[ContextMessage]:
        seen: set[tuple[str, str]] = set()
        result: list[ContextMessage] = []
        for message in messages:
            key = (message.role.value, message.content_text)
            if key in seen:
                continue
            seen.add(key)
            result.append(message)
        return result
