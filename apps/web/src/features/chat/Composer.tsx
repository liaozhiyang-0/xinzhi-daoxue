import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

export interface ComposerSubmitOptions {
  responseDepth: string;
  teachingMode: string;
  studentAttempt: string;
  researchAnalysis?: Record<string, unknown>;
}

interface ComposerProps {
  disabled: boolean;
  onSubmit: (text: string, files: File[], options: ComposerSubmitOptions) => Promise<void>;
  onCancel: () => void;
  initialText?: string;
  initialFiles?: readonly File[];
  scenarioTitle?: string;
}

export function Composer({
  disabled,
  onSubmit,
  onCancel,
  initialText = "",
  initialFiles = [],
  scenarioTitle,
}: ComposerProps) {
  const [text, setText] = useState(initialText);
  const [files, setFiles] = useState<File[]>([...initialFiles]);
  const [busy, setBusy] = useState(false);
  const [responseDepth, setResponseDepth] = useState("standard");
  const [inputHeight, setInputHeight] = useState(96);
  const resizeStartY = useRef<number | null>(null);
  const resizeStartHeight = useRef(96);
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);

  useEffect(() => {
    const urls = files.filter((file) => file.type.startsWith("image/")).map((file) => URL.createObjectURL(file));
    setPreviewUrls(urls);
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, [files]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true);
    try {
      await onSubmit(text.trim(), files, { responseDepth, teachingMode: "direct_answer", studentAttempt: "", researchAnalysis: undefined });
      setText("");
      setFiles([]);
    } finally {
      setBusy(false);
    }
  }

  function stopInputResize() {
    resizeStartY.current = null;
    document.body.classList.remove("composer-resizing");
    window.removeEventListener("pointermove", resizeInput);
    window.removeEventListener("pointerup", stopInputResize);
    window.removeEventListener("pointercancel", stopInputResize);
  }

  function resizeInput(event: PointerEvent) {
    if (resizeStartY.current === null) return;
    setInputHeight(Math.min(240, Math.max(64, resizeStartHeight.current + event.clientY - resizeStartY.current)));
  }

  function startInputResize(event: PointerEvent<HTMLDivElement>) {
    event.preventDefault();
    resizeStartY.current = event.clientY;
    resizeStartHeight.current = inputHeight;
    document.body.classList.add("composer-resizing");
    window.addEventListener("pointermove", resizeInput);
    window.addEventListener("pointerup", stopInputResize);
    window.addEventListener("pointercancel", stopInputResize);
  }

  function handleResizeKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
    event.preventDefault();
    setInputHeight((current) => Math.min(240, Math.max(64, current + (event.key === "ArrowDown" ? 16 : -16))));
  }

  return (
    <form className="composer" onSubmit={submit}>
      {scenarioTitle && <div className="composer-scenario">当前场景：{scenarioTitle}</div>}
      {files.length > 0 && <div className="attachment-strip">已选择：{files.map((file) => file.name).join("、")}</div>}
      {previewUrls.length > 0 && <div className="attachment-previews">{previewUrls.map((url) => <img src={url} alt="待上传材料预览" key={url} />)}</div>}
      <div className="composer-input-shell">
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          disabled={disabled || busy}
          style={{ height: `${inputHeight}px` }}
          maxLength={4000}
          placeholder="写下你的问题或目标"
          aria-label="任务目标"
        />
        <div className="composer-resize-handle" role="separator" aria-orientation="horizontal" aria-label="调整输入框高度" tabIndex={0} onPointerDown={startInputResize} onKeyDown={handleResizeKeyDown} />
      </div>
      <div className="composer-actions">
        <label className="file-button">
          添加材料
          <input
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp,.txt,.md,.csv,.json,.pdf,.doc,.docx,.xlsx,.parquet"
            onChange={(event) => setFiles(Array.from(event.target.files || []))}
            disabled={disabled || busy}
          />
        </label>
        <label className="depth-control">回答深度
          <select value={responseDepth} onChange={(event) => setResponseDepth(event.target.value)} disabled={disabled || busy}><option value="brief">简要</option><option value="standard">标准</option><option value="deep">深入</option></select>
        </label>
        {disabled && <button type="button" onClick={onCancel} disabled={busy}>停止</button>}
        <button className="primary" type="submit" disabled={disabled || busy || !text.trim()}>
          {busy ? "提交中…" : "发送"}
        </button>
      </div>
    </form>
  );
}
