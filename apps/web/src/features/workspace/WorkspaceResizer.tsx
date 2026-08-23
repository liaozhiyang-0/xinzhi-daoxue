import { useRef, type KeyboardEvent, type PointerEvent } from "react";

export type WorkspaceResizerSide = "left" | "right";

interface WorkspaceResizerProps {
  side: WorkspaceResizerSide;
  onDelta: (delta: number) => void;
}

export function WorkspaceResizer({ side, onDelta }: WorkspaceResizerProps) {
  const startX = useRef<number | null>(null);

  function stopResizing() {
    startX.current = null;
    document.body.classList.remove("workspace-resizing");
    window.removeEventListener("pointermove", handlePointerMove);
    window.removeEventListener("pointerup", stopResizing);
    window.removeEventListener("pointercancel", stopResizing);
  }

  function handlePointerMove(event: PointerEvent) {
    if (startX.current === null) return;
    onDelta(event.clientX - startX.current);
  }

  function startResizing(event: PointerEvent<HTMLDivElement>) {
    event.preventDefault();
    startX.current = event.clientX;
    document.body.classList.add("workspace-resizing");
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", stopResizing);
    window.addEventListener("pointercancel", stopResizing);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const direction = event.key === "ArrowRight" ? 16 : -16;
    onDelta(side === "left" ? direction : -direction);
  }

  return (
    <div
      className={`workspace-resizer workspace-resizer-${side}`}
      role="separator"
      aria-label={`${side === "left" ? "会话栏" : "任务详情栏"}宽度调整`}
      aria-orientation="vertical"
      tabIndex={0}
      onPointerDown={startResizing}
      onKeyDown={handleKeyDown}
    />
  );
}
