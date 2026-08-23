import { useState } from "react";
import type { TaskRead } from "../../api-types.js";
import { submitFeedback } from "../../api/feedback.js";

export function FeedbackPanel({ task }: { task: TaskRead | null }) {
  const [resolved, setResolved] = useState("");
  const [satisfaction, setSatisfaction] = useState("");
  const [problemType, setProblemType] = useState("");
  const [manualReview, setManualReview] = useState(false);
  const [comment, setComment] = useState("");
  const [message, setMessage] = useState("");
  if (!task || !["completed", "failed", "cancelled"].includes(task.status)) return null;
  return <section className="feedback-panel" aria-labelledby="feedback-title"><div className="section-heading"><div><h3 id="feedback-title">这次回答是否有帮助？</h3><p>反馈用于改进任务链，不替代人工教学判断。</p></div></div><div className="feedback-grid"><label>是否解决<select value={resolved} onChange={(event) => setResolved(event.target.value)}><option value="">暂不判断</option><option value="true">已解决</option><option value="false">未解决</option></select></label><label>满意度<select value={satisfaction} onChange={(event) => setSatisfaction(event.target.value)}><option value="">暂不评价</option><option value="satisfied">满意</option><option value="neutral">一般</option><option value="unsatisfied">不满意</option></select></label><label>问题类型<select value={problemType} onChange={(event) => setProblemType(event.target.value)}><option value="">未指定</option><option value="answer_quality">答案质量</option><option value="citation">资料引用</option><option value="retrieval">资料检索</option><option value="latency">响应速度</option><option value="usability">使用体验</option><option value="other">其他</option></select></label></div><label className="feedback-checkbox"><input type="checkbox" checked={manualReview} onChange={(event) => setManualReview(event.target.checked)} /> 需要人工复核</label><textarea value={comment} onChange={(event) => setComment(event.target.value)} maxLength={2000} rows={2} placeholder="可选：补充问题描述，不要填写个人敏感信息" /><div className="feedback-actions"><button className="button secondary" type="button" onClick={() => void submitFeedback({ task_id: task.id, resolved: resolved === "" ? null : resolved === "true", satisfaction: (satisfaction || null) as "satisfied" | "neutral" | "unsatisfied" | null, problem_type: problemType || null, manual_review_required: manualReview, comment }).then(() => setMessage("反馈已记录")).catch((reason: unknown) => setMessage(reason instanceof Error ? reason.message : "反馈提交失败"))}>提交反馈</button><span role="status">{message}</span></div></section>;
}
