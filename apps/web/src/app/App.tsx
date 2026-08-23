import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import type { SessionRead, TaskRead, TaskRuntimeControlProjectionRead, UserRole } from "../api-types.js";
import { uploadAttachment } from "../api/attachments.js";
import { ApiError } from "../api/client.js";
import { archiveSession, createSession, getSessionSummary, listSessionMessages, listSessions, restoreSession, searchSessions } from "../api/sessions.js";
import {
  cancelTask,
  approveTask,
  createTask,
  getTask,
  getTaskRuntimeControls,
  pauseTask,
  retryTask,
  resumeTask,
  submitRuntimeInput,
} from "../api/tasks.js";
import { ScenarioPicker } from "../components/ScenarioPicker.js";
import { StructuredResult } from "../components/StructuredResult.js";
import { TaskStatus } from "../components/TaskStatus.js";
import { useTaskStream, type TaskStreamEvent } from "../hooks/useTaskStream.js";
import { buildStudentTaskPayload } from "../workspace-contracts.js";
import { Composer, type ComposerSubmitOptions } from "../features/chat/Composer.js";
import { MessageList, type ChatMessage } from "../features/chat/MessageList.js";
import { SessionList } from "../features/sessions/SessionList.js";
import { MemoryDialog } from "../features/sessions/MemoryDialog.js";
import { FeedbackPanel } from "../features/chat/FeedbackPanel.js";
import { WorkspaceContextPane } from "../features/workspace/WorkspaceContextPane.js";
import { WorkspaceResizer } from "../features/workspace/WorkspaceResizer.js";
import {
  DEFAULT_DEMO_SCENARIO,
  DEMO_SCENARIOS,
  loadScenarioImage,
  type DemoScenario,
} from "../demo/scenarios.js";
import "../styles/app.css";
import { AppShell } from "./AppShell.js";
import { useAuth } from "./AuthContext.js";

export function App() {
  const { identity, loading: authLoading, error: authError } = useAuth();
  const userId = identity?.userId || "";
  const userRole: UserRole = identity && ["student", "teacher", "researcher", "operator", "admin"].includes(identity.role)
    ? identity.role as UserRole
    : "student";
  const [sessions, setSessions] = useState<SessionRead[]>([]);
  const [activeSession, setActiveSession] = useState<SessionRead | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionSearch, setSessionSearch] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [task, setTask] = useState<TaskRead | null>(null);
  const [runtimeControls, setRuntimeControls] = useState<Record<string, boolean>>({});
  const [runtimeProjection, setRuntimeProjection] = useState<TaskRuntimeControlProjectionRead | null>(null);
  const [runtimeInput, setRuntimeInput] = useState("");
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [sessionSummary, setSessionSummary] = useState("");
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
  const [leftWidth, setLeftWidth] = useState(264);
  const [rightWidth, setRightWidth] = useState(280);
  const [mobileLeftOpen, setMobileLeftOpen] = useState(false);
  const [mobileRightOpen, setMobileRightOpen] = useState(false);

  const selectedScenario = useMemo(
    () => DEMO_SCENARIOS.find((scenario) => scenario.id === selectedScenarioId) || null,
    [selectedScenarioId],
  );

  const resizeWorkspace = useCallback((side: "left" | "right", delta: number) => {
    if (side === "left") {
      setLeftWidth((current) => Math.min(400, Math.max(220, current + delta)));
    } else {
      setRightWidth((current) => Math.min(400, Math.max(240, current - delta)));
    }
  }, []);

  const workspaceStyle = {
    "--workspace-left-width": `${leftWidth}px`,
    "--workspace-right-width": `${rightWidth}px`,
  } as CSSProperties;

  const refreshSessions = useCallback(async () => {
    if (!userId) return;
    const rows = sessionSearch.trim()
      ? await searchSessions(userId, sessionSearch.trim(), showArchived)
      : await listSessions(userId, showArchived);
    setSessions(rows);
    if (!activeSession && rows[0]) setActiveSession(rows[0]);
  }, [activeSession, sessionSearch, showArchived, userId]);

  useEffect(() => {
    void refreshSessions()
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "会话加载失败"))
      .finally(() => setLoading(false));
  }, [refreshSessions, userId]);

  useEffect(() => {
    if (!activeSession) {
      setMessages([]);
      return;
    }
    if (!userId) return;
    void listSessionMessages(activeSession.id, userId)
      .then((rows) => setMessages(rows.map((row) => ({ id: row.id, role: row.role, text: row.content_text }))))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "消息加载失败"));
  }, [activeSession, userId]);

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
      setRuntimeProjection(null);
      return;
    }
    void getTaskRuntimeControls(task.id)
      .then((projection) => {
        setRuntimeProjection(projection);
        setRuntimeControls(
          Object.fromEntries(
            (projection.controls || []).map((control) => [control.action, control.available]),
          ),
        );
      })
      .catch(() => { setRuntimeProjection(null); setRuntimeControls({}); });
  }, [task?.id, task?.status]);

  useEffect(() => {
    if (!activeSession || !userId) {
      setSessionSummary("");
      return;
    }
    void getSessionSummary(activeSession.id, userId)
      .then((summary) => setSessionSummary(summary?.summary_text || ""))
      .catch(() => setSessionSummary(""));
  }, [activeSession, userId]);

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
    if (!userId) return;
    const created = await createSession(userId);
    setSessions((current) => [created, ...current]);
    setActiveSession(created);
    setMessages([]);
    setTask(null);
    setMemoryOpen(false);
  }, [userId]);

  const archiveOrRestoreSession = useCallback(async (session: SessionRead) => {
    if (!userId) return;
    const updated = session.archived_at
      ? await restoreSession(session.id, userId)
      : await archiveSession(session.id, userId);
    setSessions((current) => current.filter((item) => item.id !== updated.id));
    if (activeSession?.id === updated.id && updated.archived_at) {
      setActiveSession(null);
      setMessages([]);
      setTask(null);
    }
    void refreshSessions();
  }, [activeSession?.id, refreshSessions, userId]);

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

  const selectSession = useCallback((session: SessionRead) => {
    setActiveSession(session);
    setMobileLeftOpen(false);
  }, []);

  async function submit(text: string, files: File[], options: ComposerSubmitOptions) {
    if (!identity) throw new Error("身份尚未准备好，请稍后重试");
    setError(null);
    let session = activeSession;
    if (!session) {
      session = await createSession(identity.userId, selectedScenario?.courseId || "AUTO");
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
      userId: identity.userId,
      userRole,
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
      responseDepth: options.responseDepth,
      teachingMode: options.teachingMode,
      studentAttempt: options.studentAttempt,
      researchAnalysis: options.researchAnalysis,
      requestId: crypto.randomUUID(),
    });
    const created = await createTask(payload);
    setTask(created);
    setRuntimeControls({});
    setEvents([]);
    setMessages((current) => [...current, { id: `${created.id}-user`, role: "user", text }]);
    setScenarioFiles([]);
  }

  const statusText = authLoading || loading ? "正在加载工作区" : error || "工作区已就绪";

  return (
    <AppShell>
      <main className="react-workspace app-main">
        {authError && <div className="error-state" role="alert">{authError}。<a href="/login?next=/workspace">前往登录</a></div>}
      <div className="workspace-grid" style={workspaceStyle}>
        <aside className={`workspace-sidebar${mobileLeftOpen ? " workspace-drawer-open" : ""}`}>
          <SessionList sessions={sessions} activeId={activeSession?.id || null} onSelect={selectSession} onCreate={() => void createNewSession()} search={sessionSearch} onSearch={setSessionSearch} showArchived={showArchived} onToggleArchived={() => setShowArchived((value) => !value)} onArchive={(session) => void archiveOrRestoreSession(session)} />
          <button className="memory-open-button" type="button" onClick={() => setMemoryOpen(true)} disabled={!activeSession}>记忆设置</button>
        </aside>
        <WorkspaceResizer side="left" onDelta={(delta) => resizeWorkspace("left", delta)} />
        <main className="workspace-main">
          <div className="workspace-mobile-toolbar" aria-label="工作区面板切换">
            <button type="button" className={mobileLeftOpen ? "active" : ""} onClick={() => { setMobileLeftOpen(true); setMobileRightOpen(false); }} aria-expanded={mobileLeftOpen}>会话</button>
            <button type="button" className={mobileRightOpen ? "active" : ""} onClick={() => { setMobileRightOpen(true); setMobileLeftOpen(false); }} aria-expanded={mobileRightOpen}>任务详情</button>
          </div>
          <div className="workspace-heading">
            <div><span className="eyebrow">任务工作台</span><h1>{selectedScenario?.title || activeSession?.title || "开始任务"}</h1></div>
            {task && <TaskStatus status={task.status} />}
          </div>
          <MessageList messages={messages} activityKey={`${messages.length}:${task?.id || ""}:${task?.status || ""}:${events.length}`}>
            {!messages.length && !task && <ScenarioPicker
              scenarios={DEMO_SCENARIOS}
              selectedId={selectedScenarioId}
              onSelect={(scenario) => void selectScenario(scenario)}
              demoMode={demoMode}
            />}
            {task && <StructuredResult task={task} />}
            {task && (task.retryable || runtimeControls.pause || runtimeControls.resume || runtimeControls.approve || runtimeControls.input) && (
              <div className="task-controls" aria-label="任务控制">
                {task.retryable && <button type="button" onClick={() => void retryTask(task.id).then(setTask)}>重试</button>}
                {runtimeControls.pause && <button type="button" onClick={() => void pauseTask(task.id, runtimeProjection?.runtime_run_id).then(setTask)}>暂停</button>}
                {runtimeControls.resume && <button type="button" onClick={() => void resumeTask(task.id, runtimeProjection?.runtime_run_id).then(setTask)}>恢复</button>}
                {runtimeControls.approve && <button type="button" onClick={() => void approveTask(task.id, runtimeProjection?.runtime_run_id).then(setTask)}>提交审批</button>}
              </div>
            )}
            {task && runtimeControls.input && <form className="runtime-input" onSubmit={(event) => { event.preventDefault(); const value = runtimeInput.trim(); if (!value) return; void submitRuntimeInput(task.id, value, runtimeProjection?.runtime_run_id).then(setTask).then(() => setRuntimeInput("")); }}><textarea value={runtimeInput} onChange={(event) => setRuntimeInput(event.target.value)} rows={2} maxLength={4000} placeholder="补充完成当前节点所需的信息" /><button className="button secondary" type="submit">提交并继续</button></form>}
            <FeedbackPanel task={task} />
          </MessageList>
          <div className="stream-state"><span className={stream.connected ? "dot connected" : "dot"} />{stream.error || statusText}</div>
          <div className="workspace-composer-sticky">
            <Composer
              key={`${selectedScenario?.id || "free"}-${scenarioFiles.length}`}
              disabled={Boolean(task && !["completed", "failed", "cancelled"].includes(task.status))}
              onSubmit={(text, files, options) => submit(text, files, options).catch((reason: unknown) => {
                setError(formatApiError(reason));
              })}
              onCancel={() => task && void cancelTask(task.id).then(setTask)}
              initialText={selectedScenario?.exampleInput || ""}
              initialFiles={scenarioFiles}
              scenarioTitle={selectedScenario?.title}
            />
          </div>
        </main>
        <WorkspaceResizer side="right" onDelta={(delta) => resizeWorkspace("right", delta)} />
        <WorkspaceContextPane task={task} events={events} summaryText={sessionSummary} mobileOpen={mobileRightOpen} onClose={() => setMobileRightOpen(false)} />
        {(mobileLeftOpen || mobileRightOpen) && <button className="workspace-drawer-scrim" type="button" aria-label="关闭工作区面板" onClick={() => { setMobileLeftOpen(false); setMobileRightOpen(false); }} />}
      </div>
      {error && <button className="error-banner" type="button" onClick={() => setError(null)}><span>{error}</span> ×</button>}
      <footer className="footer-note">结果以可核验依据为准；资料不足或图像不清晰时请人工复核。</footer>
      </main>
      <MemoryDialog open={memoryOpen} userId={userId} session={activeSession} onClose={() => setMemoryOpen(false)} onSessionChange={(session) => { setActiveSession(session); setSessions((current) => current.map((item) => item.id === session.id ? session : item)); }} />
    </AppShell>
  );
}

export function formatApiError(error: unknown): string {
  if (error instanceof ApiError) return `${error.message}（${error.status}）`;
  return error instanceof Error ? error.message : "未知错误";
}
