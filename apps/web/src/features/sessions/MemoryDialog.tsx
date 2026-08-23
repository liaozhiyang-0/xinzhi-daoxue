import { useEffect, useState } from "react";
import type { MemoryRead, SessionRead, SessionSummaryRead } from "../../api-types.js";
import { createMemory, deleteMemory, listMemories, updateMemory } from "../../api/memories.js";
import { getSessionSummary, updateSession } from "../../api/sessions.js";

interface MemoryDialogProps {
  open: boolean;
  userId: string;
  session: SessionRead | null;
  onClose: () => void;
  onSessionChange: (session: SessionRead) => void;
}

export function MemoryDialog({ open, userId, session, onClose, onSessionChange }: MemoryDialogProps) {
  const [memories, setMemories] = useState<MemoryRead[]>([]);
  const [summary, setSummary] = useState<SessionSummaryRead | null>(null);
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !userId || !session) return;
    void Promise.all([listMemories(userId), getSessionSummary(session.id, userId)])
      .then(([items, sessionSummary]) => { setMemories(items); setSummary(sessionSummary); setError(null); })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "记忆暂时无法读取"));
  }, [open, session, userId]);

  if (!open) return null;
  return <dialog className="memory-dialog" open aria-labelledby="memory-dialog-title">
    <header className="dialog-heading"><div><span className="eyebrow">SESSION MEMORY</span><h2 id="memory-dialog-title">记忆设置</h2><p>只保存明确、稳定且对后续学习有帮助的信息。</p></div><button className="icon-button" type="button" onClick={onClose} aria-label="关闭">×</button></header>
    {error && <p className="error-state" role="alert">{error}</p>}
    {session && <div className="memory-settings">
      <label><input type="checkbox" checked={session.memory_enabled} onChange={(event) => void updateSession(session.id, { user_id: userId, memory_enabled: event.target.checked }).then(onSessionChange)} /> 启用会话总结与长期记忆</label>
      <label><input type="checkbox" checked={session.auto_memory_enabled} onChange={(event) => void updateSession(session.id, { user_id: userId, auto_memory_enabled: event.target.checked }).then(onSessionChange)} /> 从摘要中自动保存明确偏好</label>
    </div>}
    <section className="memory-summary"><h3>最近会话摘要</h3><p>{summary?.summary_text || "尚无自动摘要。"}</p>{summary && <small>v{summary.version} · 覆盖至第 {summary.covers_through_sequence} 条消息</small>}</section>
    <form className="memory-form" onSubmit={(event) => { event.preventDefault(); const value = content.trim(); if (!value) return; void createMemory(userId, value, session?.id).then((item) => { setMemories((current) => [item, ...current]); setContent(""); }); }}>
      <input value={content} onChange={(event) => setContent(event.target.value)} maxLength={1000} placeholder="例如：公式优先使用 LaTeX" aria-label="新增记忆" />
      <button className="button secondary" type="submit">添加</button>
    </form>
    <div className="memory-list">{memories.map((memory) => <article className="memory-item" key={memory.memory_id}><div><p>{memory.content}</p><small>{memory.scope === "course" ? memory.course_id : "全局偏好"}</small></div><div><button className="text-button" type="button" onClick={() => { const value = window.prompt("编辑记忆", memory.content)?.trim(); if (value && value !== memory.content) void updateMemory(memory.memory_id, userId, value).then((item) => setMemories((current) => current.map((row) => row.memory_id === item.memory_id ? item : row))); }}>编辑</button><button className="text-button danger" type="button" onClick={() => void deleteMemory(memory.memory_id, userId).then(() => setMemories((current) => current.filter((row) => row.memory_id !== memory.memory_id)))}>删除</button></div></article>)}</div>
    <button className="text-button danger" type="button" onClick={() => onClose()}>完成</button>
  </dialog>;
}
