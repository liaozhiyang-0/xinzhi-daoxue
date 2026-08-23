import { useEffect, useRef, useState } from "react";

export interface TaskStreamEvent {
  type: string;
  sequence: number;
  data: Record<string, unknown>;
}

const EVENT_TYPES = [
  "task.created",
  "task.queued",
  "task.running",
  "route.selected",
  "route.reevaluated",
  "intent.recognized",
  "plan.created",
  "plan.node_started",
  "plan.node_completed",
  "skill.selected",
  "tool.selected",
  "knowledge.retrieved",
  "knowledge.context_built",
  "agent.started",
  "agent.progress",
  "agent.input_required",
  "agent.output",
  "artifact.created",
  "cancel.requested",
  "task.cancelled",
  "task.retry_created",
  "task.completed",
  "task.failed",
] as const;

export function useTaskStream(
  taskId: string | null,
  onEvent: (event: TaskStreamEvent) => void,
): { connected: boolean; error: string | null } {
  const callback = useRef(onEvent);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    callback.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!taskId) {
      setConnected(false);
      setError(null);
      return undefined;
    }
    const source = new EventSource(`/api/v1/tasks/${encodeURIComponent(taskId)}/stream`);
    const handle = (type: string) => (event: Event) => {
      const message = event as MessageEvent<string>;
      let data: Record<string, unknown> = {};
      try {
        const parsed = JSON.parse(message.data || "{}");
        if (parsed && typeof parsed === "object") data = parsed as Record<string, unknown>;
      } catch {
        data = { raw: message.data };
      }
      callback.current({
        type,
        sequence: Number(message.lastEventId || 0),
        data,
      });
    };
    const listeners = EVENT_TYPES.map((type) => {
      const listener = handle(type);
      source.addEventListener(type, listener);
      return [type, listener] as const;
    });
    source.onopen = () => {
      setConnected(true);
      setError(null);
    };
    source.onerror = () => {
      setConnected(false);
      setError("SSE 连接暂时不可用，浏览器将按既有语义自动重连");
    };
    return () => {
      listeners.forEach(([type, listener]) => source.removeEventListener(type, listener));
      source.close();
      setConnected(false);
    };
  }, [taskId]);

  return { connected, error };
}
