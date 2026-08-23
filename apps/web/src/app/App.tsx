import { useCallback, useEffect, useMemo, useState } from "react";
import type { SessionRead, TaskRead } from "../api-types.js";
import { uploadAttachment } from "../api/attachments.js";
import { ApiError } from "../api/client.js";
import { createSession, listSessionMessages, listSessions } from "../api/sessions.js";
import {
  cancelTask,
  createTask,
  getTask,
  getTaskRuntimeControls,
  pauseTask,
  retryTask,
  resumeTask,
} from "../api/tasks.js";
import { MarkdownRenderer } from "../components/MarkdownRenderer.js";
import { TaskStatus } from "../components/TaskStatus.js";
import { useTaskStream, type TaskStreamEvent } from "../hooks/useTaskStream.js";
import { buildStudentTaskPayload } from "../workspace-contracts.js";
import { Composer } from "../features/chat/Composer.js";
import { MessageList, type ChatMessage } from "../features/chat/MessageList.js";
import { SessionList } from "../features/sessions/SessionList.js";
import "../styles/app.css";

const USER_ID = "react-workspace-student";

function taskAnswer(task: TaskRead | null): string {
  const result = task?.result_content;
  if (!result || typeof result !== "object") return "";
  const answer = (result as { answer?: unknown }).answer;
  return typeof answer === "string" ? answer : "";
}

export function App() {
  const [sessions, setSessions] = useState<SessionRead[]>([]);
  const [activeSession, setActiveSession] = useState<SessionRead | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [task, setTask] = useState<TaskRead | null>(null);
  const [runtimeControls, setRuntimeControls] = useState<Record<string, boolean>>({});
  const [events, setEvents] = useState<TaskStreamEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshSessions = useCallback(async () => {
    const rows = await listSessions(USER_ID);
    setSessions(rows);
    if (!activeSession && rows[0]) setActiveSession(rows[0]);
  }, [activeSession]);

  useEffect(() => {
    void refreshSessions()
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "会话加载失败"))
      .finally(() => setLoading(false));
  }, [refreshSessions]);

  useEffect(() => {
    if (!activeSession) {
      setMessages([]);
      return;
    }
    void listSessionMessages(activeSession.id, USER_ID)
      .then((rows) => setMessages(rows.map((row) => ({ id: row.id, role: row.role, text: row.content_text }))))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "消息加载失败"));
  }, [activeSession]);

  const handleEvent = useCallback((event: TaskStreamEvent) => {
    setEvents((current) => [...current.slice(-49), event]);
    if (["task.completed", "task.failed", "task.cancelled"].includes(event.type) && task?.id) {
      void getTask(task.id).then(setTask).catch(() => undefined);
    }
  }, [task?.id]);
  const stream = useTaskStream(task?.id || null, handleEvent);

  useEffect(() => {
    if (!task?.id) {
      setRuntimeControls({});
      return;
    }
    void getTaskRuntimeControls(task.id)
      .then((projection) => {
        setRuntimeControls(
          Object.fromEntries(
            (projection.controls || []).map((control) => [control.action, control.available]),
          ),
        );
      })
      .catch(() => setRuntimeControls({}));
  }, [task?.id, task?.status]);

  const createNewSession = useCallback(async () => {
    const created = await createSession(USER_ID);
    setSessions((current) => [created, ...current]);
    setActiveSession(created);
    setMessages([]);
    setTask(null);
  }, []);

  async function submit(text: string, files: File[]) {
    setError(null);
    let session = activeSession;
    if (!session) {
      session = await createSession(USER_ID);
      setSessions((current) => [session as SessionRead, ...current]);
      setActiveSession(session);
    }
    const materials = [];
    for (const file of files) {
      const uploaded = await uploadAttachment(file);
      materials.push({ uploaded, extractedText: uploaded.extracted_text, originalType: file.type });
    }
    const payload = buildStudentTaskPayload({
      sessionId: session.id,
      userId: USER_ID,
      userRole: "student",
      courseId: session.course_id || "AUTO",
      intent: "unknown",
      scenarioId: null,
      canonicalInput: { text },
      materials,
      responseDepth: "standard",
      teachingMode: "direct_answer",
      studentAttempt: "",
      requestId: crypto.randomUUID(),
    });
    const created = await createTask(payload);
    setTask(created);
    setRuntimeControls({});
    setEvents([]);
    setMessages((current) => [...current, { id: `${created.id}-user`, role: "user", text }]);
  }

  const answer = useMemo(() => taskAnswer(task), [task]);
  const statusText = loading ? "正在加载工作区" : error || "React alternate workspace";

  return (
    <div className="react-workspace">
      <header className="topbar">
        <div><span className="eyebrow">XINZHI DAOXUE</span><strong>芯智导学 · React Workspace</strong></div>
        <span className="boundary-note">后端 Task / Planner / Skill / Runtime 语义保持不变</span>
      </header>
      <div className="workspace-grid">
        <SessionList sessions={sessions} activeId={activeSession?.id || null} onSelect={setActiveSession} onCreate={() => void createNewSession()} />
        <main className="workspace-main">
          <div className="workspace-heading">
            <div><span className="eyebrow">任务工作台</span><h1>{activeSession?.title || "开始一次学习任务"}</h1></div>
            {task && <TaskStatus status={task.status} />}
          </div>
          <MessageList messages={messages} />
          {task && answer && <section className="answer-card"><MarkdownRenderer value={answer} /></section>}
          {task && (task.retryable || runtimeControls.pause || runtimeControls.resume) && (
            <div className="task-controls" aria-label="任务控制">
              {task.retryable && <button type="button" onClick={() => void retryTask(task.id).then(setTask)}>重试</button>}
              {runtimeControls.pause && <button type="button" onClick={() => void pauseTask(task.id).then(setTask)}>暂停</button>}
              {runtimeControls.resume && <button type="button" onClick={() => void resumeTask(task.id).then(setTask)}>恢复</button>}
            </div>
          )}
          {task && events.length > 0 && <details className="event-panel" open><summary>执行过程 · {events.length} 个事件</summary><ol>{events.map((event) => <li key={`${event.sequence}-${event.type}`}><code>{event.sequence || "—"}</code> {event.type}</li>)}</ol></details>}
          <div className="stream-state"><span className={stream.connected ? "dot connected" : "dot"} />{stream.error || statusText}</div>
          <Composer disabled={Boolean(task && !["completed", "failed", "cancelled"].includes(task.status))} onSubmit={submit} onCancel={() => task && void cancelTask(task.id).then(setTask)} />
        </main>
      </div>
      {error && <button className="error-banner" type="button" onClick={() => setError(null)}><span>{error}</span> ×</button>}
      <footer className="footer-note">React Workspace；旧版回滚入口：<code>/workspace-legacy</code>。</footer>
    </div>
  );
}

export function formatApiError(error: unknown): string {
  if (error instanceof ApiError) return `${error.message}（${error.status}）`;
  return error instanceof Error ? error.message : "未知错误";
}
