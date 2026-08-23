import { useState } from "react";
import type { TaskRead } from "../api-types.js";
import { MarkdownRenderer } from "./MarkdownRenderer.js";

type UnknownRecord = Record<string, unknown>;

const KEY_LABELS: Record<string, string> = {
  status: "状态",
  reason: "原因",
  note: "说明",
  notes: "说明",
  confidence: "置信度",
  evidence_status: "证据状态",
  validation_status: "验证状态",
  review_required: "需要复核",
  source: "来源",
  scope: "范围",
  priority: "优先级",
  target: "目标",
  duration: "时长",
  score: "分数",
  decision: "判断",
  action: "处理动作",
};

const STATUS_LABELS: Record<string, string> = {
  accepted: "已接受",
  accepted_with_warnings: "已完成，但有提醒",
  checked: "已检查",
  generated: "已生成",
  needs_review: "需要复核",
  provisional: "暂定结果",
  incomplete: "结果不完整",
  insufficient: "证据不足",
  pass: "通过",
  partial: "部分通过",
  fail: "未通过",
  not_checked: "尚未检查",
  true: "是",
  false: "否",
};

const NEXT_STEP_KEYS = new Set([
  "verification_tasks",
  "verification_task",
  "next_steps",
  "open_questions",
  "homework",
  "teacher_review",
  "review_boundary",
  "learning_suggestions",
  "missing_information",
]);

const ANALYSIS_EXCLUDED_KEYS = new Set([
  "final_answer",
  "answer",
  "answer_text",
  "review_boundary",
  "teacher_review",
  "verification_tasks",
  "verification_task",
  "next_steps",
  "open_questions",
  "homework",
]);

function record(value: unknown): UnknownRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as UnknownRecord
    : {};
}

function text(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    const stringValue = String(value);
    return STATUS_LABELS[stringValue] || stringValue;
  }
  return "";
}

function label(key: string): string {
  return KEY_LABELS[key] || key.replaceAll("_", " ");
}

function ContentValue({ value }: { value: unknown }) {
  const scalar = text(value);
  if (scalar) return <MarkdownRenderer value={scalar} />;
  if (Array.isArray(value)) {
    return (
      <ul className="structured-list">
        {value.map((item, index) => <li key={`${index}-${text(item).slice(0, 24)}`}><ContentValue value={item} /></li>)}
      </ul>
    );
  }
  const objectValue = record(value);
  if (Object.keys(objectValue).length === 0) return null;
  return (
    <dl className="structured-fields">
      {Object.entries(objectValue)
        .filter(([key]) => !key.endsWith("_id") && !key.endsWith("_ids") && key !== "id")
        .map(([key, item]) => (
          <div key={key}>
            <dt>{label(key)}</dt>
            <dd><ContentValue value={item} /></dd>
          </div>
        ))}
    </dl>
  );
}

function statusText(value: unknown): string {
  const valueText = text(value);
  return STATUS_LABELS[valueText] || valueText;
}

function answerText(result: UnknownRecord): string {
  const mathContent = record(result.math_content);
  return text(result.answer) || text(result.answer_text) || text(mathContent.markdown);
}

function businessSections(result: UnknownRecord) {
  const businessView = record(result.business_view);
  const sections = Array.isArray(businessView.sections) ? businessView.sections : [];
  const rendered = sections.filter((item): item is UnknownRecord => Boolean(item) && typeof item === "object");
  if (rendered.length > 0) return rendered;
  const data = record(result.business_data);
  return Object.entries(data)
    .filter(([key, value]) => !["status", "course", "problem_type"].includes(key) && value !== "" && value !== null)
    .map(([key, content]) => ({ key, label: label(key), content }));
}

export function StructuredResult({ task }: { task: TaskRead }) {
  const [copied, setCopied] = useState(false);
  const result = record(task.result_content);
  const terminal = ["completed", "failed", "cancelled"].includes(task.status);
  if (!terminal) {
    return (
      <section className="result-section result-pending" aria-label="任务执行中">
        <span className="eyebrow">结果准备中</span>
        <h2>{task.status === "waiting_review" ? "等待人工复核" : "任务正在执行"}</h2>
        <p>{task.status === "waiting_review" ? "结果已到达复核门，获得授权后才会继续。" : "结果将在完成复核后显示；请先查看右侧执行轨迹。"}</p>
      </section>
    );
  }
  const presentation = record(result.presentation);
  const businessView = record(result.business_view);
  const contract = record(result.scenario_contract);
  const sections = businessSections(result);
  const answer = answerText(result) || text(
    sections.find((section) => section.key === "final_answer")?.content,
  );
  const analysis = sections.filter((section) => !ANALYSIS_EXCLUDED_KEYS.has(text(section.key)));
  const nextSteps = sections.filter((section) => NEXT_STEP_KEYS.has(text(section.key)));
  const evidence = Array.isArray(result.evidence_view)
    ? result.evidence_view.filter((item): item is UnknownRecord => Boolean(item) && typeof item === "object")
    : [];
  const qualityGate = record(result.quality_gate);
  const boundaryDecision = record(result.boundary_decision);
  const qualityStatus = statusText(
    presentation.answer_quality_status || qualityGate.status || result.result_status || result.status,
  );
  const reviewItems = [
    ...((Array.isArray(contract.quality_gaps) ? contract.quality_gaps : []).map(String)),
    ...((Array.isArray(result.warnings) ? result.warnings : []).map(String)),
    ...((Array.isArray(result.remaining_risks) ? result.remaining_risks : []).map(String)),
    ...((Array.isArray(boundaryDecision.missing_information) ? boundaryDecision.missing_information : []).map(String)),
  ];
  const requiresReview = Boolean(presentation.requires_review)
    || ["partial", "fail", "needs_review", "insufficient"].includes(
      String(qualityGate.status || result.status || result.evidence_status),
    )
    || boundaryDecision.can_continue === false
    || reviewItems.length > 0;
  const reviewBoundary = text(
    sections.find((section) => section.key === "review_boundary")?.content,
  ) || text(contract.review_boundary)
    || text(boundaryDecision.reason)
    || (reviewItems.length > 0 ? "请先补充或核对上述信息，再继续使用结论。" : "");
  const evidenceMessage = text(presentation.evidence_message)
    || (text(result.evidence_status) === "insufficient"
      ? "当前证据不足，结果仅作条件性判断。"
      : "本次结果没有附带可展示的资料依据。");
  const fallbackNextSteps = sections.filter((section) => NEXT_STEP_KEYS.has(text(section.key)));
  const finalNextSteps = nextSteps.length > 0 ? nextSteps : fallbackNextSteps;

  return (
    <section className="structured-result" aria-label="结构化任务结果">
      <div className="result-summary result-section">
        <div>
          <span className="eyebrow">结果摘要</span>
          <h2>{text(presentation.title) || "任务结果"}</h2>
          <p>{text(presentation.source_summary) || "结果已返回，请核对下方依据和复核边界。"}</p>
        </div>
        <span className={`quality-badge quality-${requiresReview ? "review" : "ok"}`}>
          {qualityStatus || (requiresReview ? "需要复核" : "已完成")}
        </span>
      </div>

      {text(businessView.banner) && <div className="result-banner">{text(businessView.banner)}</div>}

      <section className="result-section">
        <div className="result-section-heading"><h3>核心结论</h3>{answer && <button className="text-button" type="button" onClick={() => { if (navigator.clipboard) void navigator.clipboard.writeText(answer).then(() => setCopied(true)); }}>{copied ? "已复制" : "复制回答"}</button>}</div>
        {answer ? <MarkdownRenderer value={answer} /> : <p className="muted">当前没有可展示的核心结论。</p>}
      </section>

      {analysis.length > 0 && (
        <section className="result-section">
          <h3>分析与计划</h3>
          <div className="result-sections">
            {analysis.map((section, index) => (
              <article className="result-subsection" key={`${text(section.key)}-${index}`}>
                <h4>{text(section.label) || label(text(section.key))}</h4>
                <ContentValue value={section.content} />
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="result-section">
        <h3>证据与依据</h3>
        <p>{evidenceMessage}</p>
        {evidence.length > 0 ? (
          <div className="evidence-grid">
            {evidence.map((item, index) => (
              <article className="evidence-card" key={`${text(item.title)}-${index}`}>
                <strong>{text(item.title) || "资料依据"}</strong>
                <span>{text(item.course_name) || text(item.chapter)}</span>
                <p>{text(item.summary) || "已进入任务上下文。"}</p>
                <small>{item.used_by_answer ? "已用于回答" : "补充依据"}</small>
              </article>
            ))}
          </div>
        ) : <p className="muted">暂无可展示的证据卡片。</p>}
      </section>

      <section className={`result-section review-section ${requiresReview ? "needs-review" : ""}`}>
        <h3>复核与限制</h3>
        <p>{text(presentation.answer_quality_message) || (requiresReview ? "结果需要人工复核后再使用。" : "当前未标记强制人工复核。")}</p>
        {reviewBoundary && <div className="review-boundary"><strong>人工复核边界</strong><MarkdownRenderer value={reviewBoundary} /></div>}
        {reviewItems.length > 0 && <ContentValue value={reviewItems} />}
      </section>

      {finalNextSteps.length > 0 && (
        <section className="result-section">
          <h3>下一步</h3>
          <div className="result-sections">
            {finalNextSteps.map((section, index) => (
              <article className="result-subsection" key={`${text(section.key)}-${index}`}>
                <h4>{text(section.label) || label(text(section.key))}</h4>
                <ContentValue value={section.content} />
              </article>
            ))}
          </div>
        </section>
      )}
    </section>
  );
}
