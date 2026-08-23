import { useMemo, useState } from "react";
import type { TaskRead } from "../../api-types.js";
import type { TaskStreamEvent } from "../../task-transport.js";
import { ExecutionTrace } from "../../components/ExecutionTrace.js";

type ContextTab = "task" | "evidence" | "process" | "context";
type RecordValue = Record<string, unknown>;

function record(value: unknown): RecordValue {
  return value && typeof value === "object" && !Array.isArray(value) ? value as RecordValue : {};
}

interface WorkspaceContextPaneProps {
  task: TaskRead | null;
  events: readonly TaskStreamEvent[];
  summaryText?: string;
  mobileOpen?: boolean;
  onClose?: () => void;
}

export function WorkspaceContextPane({ task, events, summaryText = "", mobileOpen = false, onClose }: WorkspaceContextPaneProps) {
  const [tab, setTab] = useState<ContextTab>("evidence");
  const result = record(task?.result_content);
  const evidence = useMemo(() => Array.isArray(result.evidence_view) ? result.evidence_view.filter((item): item is RecordValue => Boolean(item) && typeof item === "object") : [], [result.evidence_view]);
  return <aside className={`context-pane${mobileOpen ? " workspace-drawer-open" : ""}`} aria-label="课程证据与执行信息">
    <header className="context-pane-heading"><div><span className="eyebrow">TASK CONTEXT</span><h2>{task ? "任务详情" : "等待提问"}</h2></div>{onClose && <button className="context-pane-close" type="button" onClick={onClose} aria-label="关闭任务详情">关闭</button>}</header>
    <nav className="context-tabs" aria-label="任务详情标签">{([["task", "任务"], ["evidence", "资料依据"], ["process", "执行过程"], ["context", "上下文"]] as const).map(([key, label]) => <button className={tab === key ? "active" : ""} type="button" key={key} onClick={() => setTab(key)}>{label}</button>)}</nav>
    {tab === "task" && <section className="context-section"><dl className="context-fields"><div><dt>任务 ID</dt><dd>{task?.id || "尚未创建"}</dd></div><div><dt>课程</dt><dd>{task?.course_id || "自动识别"}</dd></div><div><dt>意图</dt><dd>{task?.intent || "—"}</dd></div><div><dt>Provider</dt><dd>{task?.provider || "—"}</dd></div><div><dt>结果状态</dt><dd>{task?.status || "等待提问"}</dd></div></dl></section>}
    {tab === "evidence" && <section className="context-section">{evidence.length ? evidence.map((item, index) => <article className="context-evidence" key={`${String(item.title || "evidence")}-${index}`}><strong>{String(item.title || item.chapter || "资料依据")}</strong><small>{String(item.course_name || item.course_id || "课程资料")}</small><p>{String(item.summary || "已进入当前任务上下文。")}</p></article>) : <div className="context-empty"><strong>资料会在这里出现</strong><p>{task ? "当前结果没有可展示的证据卡片。" : "提交任务后，这里会展示真正进入任务的课程证据。"}</p></div>}</section>}
    {tab === "process" && <section className="context-section context-process"><ExecutionTrace task={task} events={events} /></section>}
    {tab === "context" && <section className="context-section"><div className="context-empty"><strong>上下文状态</strong><p>{summaryText || "展示会话摘要、消息和长期记忆的使用状态；不展示内部提示词。"}</p></div></section>}
  </aside>;
}
