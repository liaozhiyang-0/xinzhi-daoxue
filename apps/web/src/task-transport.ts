/** Typed task-stream boundary used by the student workspace. */

import type { Api } from "./materials.js";

export interface TaskRecord {
  id: string;
  status: string;
  [key: string]: unknown;
}

export interface TaskStreamEvent {
  type: string;
  sequence: number;
  data: ProgressData;
}

const taskEventTypes = [
  "task.created", "task.queued", "task.running", "route.selected", "route.reevaluated",
  "intent.recognized", "plan.created", "plan.node_started", "plan.node_completed", "skill.selected",
  "tool.selected", "knowledge.retrieved", "knowledge.context_built", "agent.started", "agent.progress",
  "agent.input_required", "agent.output", "artifact.created", "cancel.requested", "task.cancelled",
  "task.retry_created", "task.completed", "task.failed",
] as const;

export function subscribeTaskStream(
  taskId: string,
  onEvent: (event: TaskStreamEvent) => void,
  onState: (state: { connected: boolean; error: string | null }) => void,
): () => void {
  const source = new EventSource(`/api/v1/tasks/${encodeURIComponent(taskId)}/stream`);
  const listeners = taskEventTypes.map((type) => {
    const listener = (event: Event) => {
      const message = event as MessageEvent<string>;
      let data: ProgressData = {};
      try {
        const parsed = JSON.parse(message.data || "{}");
        if (parsed && typeof parsed === "object") data = parsed as ProgressData;
      } catch {
        data = { raw: message.data };
      }
      onEvent({ type, sequence: Number(message.lastEventId || 0), data });
    };
    source.addEventListener(type, listener);
    return [type, listener] as const;
  });
  source.onopen = () => onState({ connected: true, error: null });
  source.onerror = () => onState({ connected: false, error: "SSE 连接暂时不可用，浏览器将按既有语义自动重连" });
  return () => {
    listeners.forEach(([type, listener]) => source.removeEventListener(type, listener));
    source.close();
    onState({ connected: false, error: null });
  };
}

export interface ActiveTaskWait {
  runSequence: number;
  cancel: () => void;
}

export interface TaskTransportState {
  liveProcessSteps: Map<string, unknown>;
  activeTaskWait: ActiveTaskWait | null;
}

export type ProgressData = Record<string, unknown>;
export type AddMessage = (message: string, kind?: string) => void;
export type SelectContextTab = (tab: string) => void;
export type LiveProgressData = (event: Event) => ProgressData;
export type UpdateLiveProgress = (data: ProgressData, fallback?: ProgressData) => void;
export type RefreshRuntimeTaskControls = (taskId: string) => void | Promise<unknown>;
export type RenderLongWaitNotice = (elapsedMs: number) => void;

export interface TaskTransportOptions {
  api: Api;
  ownedTaskUrl: (id: string) => string;
  state: TaskTransportState;
  addMessage: AddMessage;
  selectContextTab: SelectContextTab;
  liveProgressData: LiveProgressData;
  updateLiveProgress: UpdateLiveProgress;
  refreshRuntimeTaskControls: RefreshRuntimeTaskControls;
  renderLongWaitNotice: RenderLongWaitNotice;
}

const terminalStatuses = new Set(["completed", "failed", "cancelled"]);

function isTerminal(task: TaskRecord) {
  return terminalStatuses.has(task.status);
}

export function createTaskTransport({
  api,
  ownedTaskUrl,
  state,
  addMessage,
  selectContextTab,
  liveProgressData,
  updateLiveProgress,
  refreshRuntimeTaskControls,
  renderLongWaitNotice,
}: TaskTransportOptions) {
  async function waitForTask(id: string, runSequence: number): Promise<TaskRecord | null> {
    state.liveProcessSteps.clear();
    return new Promise((resolve, reject) => {
      let settled = false;
      let reconnectPollTimer: number | null = null;
      let terminalPollTimer: number | null = null;
      let controlRefreshTimer: number | null = null;
      let longWaitTimer: number | null = null;
      const waitStartedAt = performance.now();
      const events = new EventSource(`/api/v1/tasks/${id}/stream`);

      const cleanup = () => {
        events.close();
        if (reconnectPollTimer !== null) clearInterval(reconnectPollTimer);
        if (terminalPollTimer !== null) clearInterval(terminalPollTimer);
        if (controlRefreshTimer !== null) clearInterval(controlRefreshTimer);
        if (longWaitTimer !== null) clearInterval(longWaitTimer);
        reconnectPollTimer = null;
        terminalPollTimer = null;
        controlRefreshTimer = null;
        longWaitTimer = null;
        if (state.activeTaskWait?.runSequence === runSequence) {
          state.activeTaskWait = null;
        }
      };

      const cancel = () => {
        if (settled) return;
        settled = true;
        cleanup();
        resolve(null);
      };
      state.activeTaskWait = { runSequence, cancel };

      const finish = async () => {
        if (settled) return;
        try {
          const task = await api<TaskRecord>(ownedTaskUrl(id));
          if (isTerminal(task)) {
            settled = true;
            cleanup();
            resolve(task);
          }
        } catch (error) {
          settled = true;
          cleanup();
          reject(error);
        }
      };

      ["task.completed", "task.failed", "task.cancelled"].forEach((name) => {
        events.addEventListener(name, finish);
      });
      events.addEventListener("intent.recognized", () => {
        addMessage("已识别用户意图，正在选择能力与执行方式", "system");
      });
      events.addEventListener("plan.created", () => {
        addMessage("已生成执行计划，正在按依赖关系调度本地能力", "system");
        selectContextTab("process");
      });
      events.addEventListener("agent.started", () => {
        addMessage("已完成能力编排，内部 Agent 正在协作处理", "system");
      });
      events.addEventListener("knowledge.retrieved", () => {
        addMessage("已完成课程资料检索，正在整理本次证据", "system");
        selectContextTab("process");
      });

      const progressEventLabels: Record<string, string> = {
        "plan.node_started": "正在执行计划节点",
        "plan.node_completed": "计划节点已完成",
        "knowledge.query_normalized": "已完成知识检索定位",
        "knowledge.context_built": "已组装课程证据",
        "knowledge.insufficient": "课程证据不足，进入保守回答",
        "external_retrieval.started": "正在检索外部证据",
        "external_retrieval.completed": "外部证据检索完成",
        "external_retrieval.failed": "外部证据检索未完成",
      };
      Object.entries(progressEventLabels).forEach(([name, label]) => {
        events.addEventListener(name, (event) => {
          const data = liveProgressData(event);
          const terminal = name.endsWith(".completed")
            || name.endsWith(".failed")
            || name === "knowledge.context_built"
            || name === "knowledge.insufficient";
          updateLiveProgress(data, {
            stage_id: String(data.stage_id || data.node_id || name),
            status: terminal
              ? (name.endsWith(".failed") || name === "knowledge.insufficient" ? "failed" : "completed")
              : "running",
            label,
          });
          void refreshRuntimeTaskControls(id);
        });
      });
      events.addEventListener("agent.progress", (event) => {
        updateLiveProgress(liveProgressData(event));
        void refreshRuntimeTaskControls(id);
      });

      controlRefreshTimer = window.setInterval(() => {
        if (!settled) void refreshRuntimeTaskControls(id);
      }, 900);
      longWaitTimer = window.setInterval(() => {
        if (!settled) renderLongWaitNotice(performance.now() - waitStartedAt);
      }, 5000);
      terminalPollTimer = window.setInterval(() => {
        if (!settled) void finish();
      }, 1200);
      events.onerror = () => {
        if (settled || reconnectPollTimer !== null) return;
        // EventSource reconnects with Last-Event-ID. Polling is only a
        // reconciliation safety net while that reconnect is in flight.
        reconnectPollTimer = window.setInterval(async () => {
          if (settled) return;
          try {
            const task = await api<TaskRecord>(ownedTaskUrl(id));
            void refreshRuntimeTaskControls(id);
            if (isTerminal(task)) {
              settled = true;
              cleanup();
              resolve(task);
            }
          } catch (error) {
            settled = true;
            cleanup();
            reject(error);
          }
        }, 900);
      };
    });
  }

  return { waitForTask };
}
