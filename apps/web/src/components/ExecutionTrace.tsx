import type { TaskRead } from "../api-types.js";
import type { TaskStreamEvent } from "../hooks/useTaskStream.js";

type TraceStatus = "pending" | "running" | "completed" | "warning" | "failed";

interface TraceStage {
  key: string;
  label: string;
  description: string;
}

const STAGES: TraceStage[] = [
  { key: "understand", label: "任务理解", description: "识别目标、学科和输入材料" },
  { key: "plan", label: "任务规划", description: "形成可执行的步骤和检查点" },
  { key: "capability", label: "能力调用", description: "调用专业能力、工具或模型" },
  { key: "evidence", label: "证据准备", description: "整理资料、图像或外部来源" },
  { key: "verification", label: "结果复核", description: "检查结构、依据和边界" },
  { key: "result", label: "结果提交", description: "提交结果并标记下一步" },
];

const stageByEvent: Record<string, string> = {
  "task.created": "understand",
  "task.queued": "understand",
  "task.running": "understand",
  "intent.recognized": "understand",
  "route.selected": "plan",
  "route.reevaluated": "plan",
  "plan.created": "plan",
  "plan.node_started": "plan",
  "plan.node_completed": "plan",
  "skill.selected": "capability",
  "tool.selected": "capability",
  "agent.started": "capability",
  "agent.progress": "capability",
  "knowledge.retrieved": "evidence",
  "knowledge.context_built": "evidence",
  "external_retrieval.started": "evidence",
  "external_retrieval.completed": "evidence",
  "external_retrieval.failed": "evidence",
  "agent.output": "verification",
  "artifact.created": "verification",
  "task.completed": "result",
  "task.failed": "result",
  "task.cancelled": "result",
};

function statusLabel(status: TraceStatus): string {
  return {
    pending: "等待",
    running: "进行中",
    completed: "已完成",
    warning: "需留意",
    failed: "失败",
  }[status];
}

function buildStatuses(task: TaskRead | null, events: readonly TaskStreamEvent[]) {
  const current: Record<string, TraceStatus> = Object.fromEntries(
    STAGES.map((stage) => [stage.key, "pending"]),
  );
  const touched = new Set<string>();
  events.forEach((event) => {
    const stage = stageByEvent[event.type];
    if (!stage) return;
    touched.add(stage);
    current[stage] = event.type.endsWith("failed") ? "failed" : "completed";
  });
  if (task && task.status === "running") {
    const lastCompleted = [...STAGES].reverse().find(
      (stage) => touched.has(stage.key) && current[stage.key] === "completed",
    );
    const next = lastCompleted
      ? STAGES[STAGES.indexOf(lastCompleted) + 1]
      : STAGES[0];
    if (next) current[next.key] = "running";
  }
  if (task?.status === "waiting_review" || task?.status === "waiting_user") {
    current.verification = "warning";
  }
  if (task?.status === "completed") current.result = "completed";
  if (task?.status === "failed") current.result = "failed";
  return current;
}

export function ExecutionTrace({
  task,
  events,
}: {
  task: TaskRead | null;
  events: readonly TaskStreamEvent[];
}) {
  const statuses = buildStatuses(task, events);
  return (
    <aside className="execution-trace" aria-label="执行轨迹">
      <div className="execution-trace-heading">
        <div>
          <span className="eyebrow">可审计轨迹</span>
          <h2>执行进度</h2>
        </div>
        {task && <span className="trace-count">{events.length} 个事件</span>}
      </div>
      <ol className="trace-list">
        {STAGES.map((stage) => {
          const status = statuses[stage.key];
          return (
            <li className={`trace-item trace-${status}`} key={stage.key}>
              <span className="trace-marker" aria-hidden="true" />
              <div>
                <div className="trace-item-title">
                  <strong>{stage.label}</strong>
                  <span>{statusLabel(status)}</span>
                </div>
                <p>{stage.description}</p>
              </div>
            </li>
          );
        })}
      </ol>
      {!task && <p className="trace-empty">提交任务后，这里会显示实际执行过程。</p>}
    </aside>
  );
}
