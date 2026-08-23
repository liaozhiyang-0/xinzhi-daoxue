import { useEffect, useRef, useState } from "react";
import { subscribeTaskStream, type TaskStreamEvent } from "../task-transport.js";

export type { TaskStreamEvent } from "../task-transport.js";

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
    return subscribeTaskStream(
      taskId,
      (event) => callback.current(event),
      (state) => { setConnected(state.connected); setError(state.error); },
    );
  }, [taskId]);

  return { connected, error };
}
