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
import { ExecutionTrace } from "../components/ExecutionTrace.js";
import { ScenarioPicker } from "../components/ScenarioPicker.js";
import { StructuredResult } from "../components/StructuredResult.js";
import { TaskStatus } from "../components/TaskStatus.js";
import { useTaskStream, type TaskStreamEvent } from "../hooks/useTaskStream.js";
import { buildStudentTaskPayload } from "../workspace-contracts.js";
import { Composer } from "../features/chat/Composer.js";
import { MessageList, type ChatMessage } from "../features/chat/MessageList.js";
import { SessionList } from "../features/sessions/SessionList.js";
import {
  DEFAULT_DEMO_SCENARIO,
  DEMO_SCENARIOS,
  loadScenarioImage,
  type DemoScenario,
} from "../demo/scenarios.js";
import "../styles/app.css";

const USER_ID = "react-workspace-student";

export function App() {
  const [sessions, setSessions] = useState<SessionRead[]>([]);
  const [activeSession, setActiveSession] = useState<SessionRead | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [task, setTask] = useState<TaskRead | null>(null);
  const [runtimeControls, setRuntimeControls] = useState<Record<string, boolean>>({});
  const [events, setEvents] = useState<TaskStreamEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const demoMode = useMemo(
    () => new URLSearchParams(window.location.search).get("demo") === "1",
    [],
  );
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(
    demoMode ? DEFAULT_DEMO_SCENARIO.id : null,
  );
  const [scenarioFiles, setScenarioFiles] = useState<File[]>([]);

  const selectedScenario = useMemo(
    () => DEMO_SCENARIOS.find((scenario) => scenario.id === selectedScenarioId) || null,
    [selectedScenarioId],
  );

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

  useEffect(() => {
    if (!task?.id || ["completed", "failed", "cancelled", "waiting_review", "waiting_user"].includes(task.status)) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void getTask(task.id).then(setTask).catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [task?.id, task?.status]);

  const createNewSession = useCallback(async () => {
    const created = await createSession(USER_ID);
    setSessions((current) => [created, ...current]);
    setActiveSession(created);
    setMessages([]);
    setTask(null);
  }, []);

  const selectScenario = useCallback(async (scenario: DemoScenario) => {
    setSelectedScenarioId(scenario.id);
    setError(null);
    try {
      const image = await loadScenarioImage(scenario);
      setScenarioFiles(image ? [image] : []);
    } catch (reason: unknown) {
      setScenarioFiles([]);
      setError(reason instanceof Error ? reason.message : "示例材料加载失败");
    }
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
      courseId: selectedScenario?.courseId || session.course_id || "AUTO",
      intent: selectedScenario?.intent || "unknown",
      scenarioId: selectedScenario?.runtimeScenarioId !== undefined
        ? selectedScenario.runtimeScenarioId
        : selectedScenario?.id || null,
      canonicalInput: {
        text,
        scenario_case_id: selectedScenario?.caseId || "",
      },
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
    setScenarioFiles([]);
  }

  const statusText = loading ? "正在加载工作区" : error || "工作区已就绪";

  return (
    <div className="react-workspace">
      <header className="topbar">
        <div><span className="eyebrow">XINZHI DAOXUE</span><strong>芯智导学 · 学科智能任务工作台</strong></div>
        <span className="boundary-note">展示真实任务的规划、能力、依据和复核边界</span>
      </header>
      <div className="workspace-grid">
        <aside className="workspace-sidebar">
          <ScenarioPicker
            scenarios={DEMO_SCENARIOS}
            selectedId={selectedScenarioId}
            onSelect={(scenario) => void selectScenario(scenario)}
            demoMode={demoMode}
          />
          <SessionList sessions={sessions} activeId={activeSession?.id || null} onSelect={setActiveSession} onCreate={() => void createNewSession()} />
        </aside>
        <main className="workspace-main">
          <div className="workspace-heading">
            <div><span className="eyebrow">任务工作台</span><h1>{selectedScenario?.title || activeSession?.title || "开始一次学习任务"}</h1></div>
            {task && <TaskStatus status={task.status} />}
          </div>
          <MessageList messages={messages} />
          {task && <StructuredResult task={task} />}
          {task && (task.retryable || runtimeControls.pause || runtimeControls.resume) && (
            <div className="task-controls" aria-label="任务控制">
              {task.retryable && <button type="button" onClick={() => void retryTask(task.id).then(setTask)}>重试</button>}
              {runtimeControls.pause && <button type="button" onClick={() => void pauseTask(task.id).then(setTask)}>暂停</button>}
              {runtimeControls.resume && <button type="button" onClick={() => void resumeTask(task.id).then(setTask)}>恢复</button>}
            </div>
          )}
          <div className="stream-state"><span className={stream.connected ? "dot connected" : "dot"} />{stream.error || statusText}</div>
          <Composer
            key={`${selectedScenario?.id || "free"}-${scenarioFiles.length}`}
            disabled={Boolean(task && !["completed", "failed", "cancelled"].includes(task.status))}
            onSubmit={(text, files) => submit(text, files).catch((reason: unknown) => {
              setError(formatApiError(reason));
            })}
            onCancel={() => task && void cancelTask(task.id).then(setTask)}
            initialText={selectedScenario?.exampleInput || ""}
            initialFiles={scenarioFiles}
            scenarioTitle={selectedScenario?.title}
          />
        </main>
        <ExecutionTrace task={task} events={events} />
      </div>
      {error && <button className="error-banner" type="button" onClick={() => setError(null)}><span>{error}</span> ×</button>}
      <footer className="footer-note">结果以可核验依据为准；资料不足或图像不清晰时请人工复核。</footer>
    </div>
  );
}

export function formatApiError(error: unknown): string {
  if (error instanceof ApiError) return `${error.message}（${error.status}）`;
  return error instanceof Error ? error.message : "未知错误";
}
