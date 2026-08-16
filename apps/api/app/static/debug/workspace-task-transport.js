/* Task transport boundary for the student workspace.
 *
 * This module owns only the long-running task protocol: SSE, reconnect
 * polling, terminal reconciliation, and Runtime control refreshes. Rendering
 * remains in workspace.js and is injected as callbacks so the transport can
 * be tested without knowing the page layout.
 */
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
}) {
  async function waitForTask(id, runSequence) {
    state.liveProcessSteps.clear();
    return new Promise((resolve, reject) => {
      let settled = false;
      let reconnectPollTimer = null;
      let terminalPollTimer = null;
      let controlRefreshTimer = null;
      let longWaitTimer = null;
      const waitStartedAt = performance.now();
      const events = new EventSource(`/api/v1/tasks/${id}/stream`);

      const cleanup = () => {
        events.close();
        if (reconnectPollTimer) clearInterval(reconnectPollTimer);
        if (terminalPollTimer) clearInterval(terminalPollTimer);
        if (controlRefreshTimer) clearInterval(controlRefreshTimer);
        if (longWaitTimer) clearInterval(longWaitTimer);
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
          const task = await api(ownedTaskUrl(id));
          if (["completed", "failed", "cancelled"].includes(task.status)) {
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

      const progressEventLabels = {
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
              ? (name.endsWith(".failed") || name === "knowledge.insufficient"
                ? "failed"
                : "completed")
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

      controlRefreshTimer = setInterval(() => {
        if (!settled) void refreshRuntimeTaskControls(id);
      }, 900);
      longWaitTimer = setInterval(() => {
        if (!settled) renderLongWaitNotice(performance.now() - waitStartedAt);
      }, 5000);
      terminalPollTimer = setInterval(() => {
        if (!settled) void finish();
      }, 1200);
      events.onerror = () => {
        if (settled || reconnectPollTimer) return;
        // EventSource reconnects with Last-Event-ID. Polling is only a
        // reconciliation safety net while that reconnect is in flight.
        reconnectPollTimer = setInterval(async () => {
          if (settled) return;
          try {
            const task = await api(ownedTaskUrl(id));
            void refreshRuntimeTaskControls(id);
            if (["completed", "failed", "cancelled"].includes(task.status)) {
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
