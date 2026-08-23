import { useState } from "react";

interface ComposerProps {
  disabled: boolean;
  onSubmit: (text: string, files: File[]) => Promise<void>;
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

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true);
    try {
      await onSubmit(text.trim(), files);
      setText("");
      setFiles([]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      {scenarioTitle && <div className="composer-scenario">当前场景：{scenarioTitle}</div>}
      {files.length > 0 && <div className="attachment-strip">已选择：{files.map((file) => file.name).join("、")}</div>}
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        disabled={disabled || busy}
        rows={3}
        maxLength={4000}
        placeholder="描述你的学习、教学或研究目标"
        aria-label="任务目标"
      />
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
        <button type="button" onClick={onCancel} disabled={!disabled}>停止</button>
        <button className="primary" type="submit" disabled={disabled || busy || !text.trim()}>
          {busy ? "提交中…" : "发送"}
        </button>
      </div>
    </form>
  );
}
