from __future__ import annotations

from app.contracts import AgentRequest, RetrievalContextPacket


def with_learning_context(
    request: AgentRequest,
    packet: RetrievalContextPacket,
) -> AgentRequest:
    """Attach a typed retrieval packet to a Provider-facing request."""

    context = packet.to_retrieved_context()
    options = dict(request.options)
    packet_payload = packet.model_dump(mode="json")
    packet_payload["formatted_context"] = context
    options["retrieval_context_packet"] = packet_payload
    options["retrieved_context"] = context
    options.setdefault("request_id", request.task_id)
    options["knowledge_source_refs"] = packet.source_refs
    return request.model_copy(update={"options": options})
