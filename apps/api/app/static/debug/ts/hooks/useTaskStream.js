import { useEffect, useRef, useState } from "react";
import { subscribeTaskStream } from "../task-transport.js";
export function useTaskStream(taskId, onEvent) {
    const callback = useRef(onEvent);
    const [connected, setConnected] = useState(false);
    const [error, setError] = useState(null);
    useEffect(() => {
        callback.current = onEvent;
    }, [onEvent]);
    useEffect(() => {
        if (!taskId) {
            setConnected(false);
            setError(null);
            return undefined;
        }
        return subscribeTaskStream(taskId, (event) => callback.current(event), (state) => { setConnected(state.connected); setError(state.error); });
    }, [taskId]);
    return { connected, error };
}
