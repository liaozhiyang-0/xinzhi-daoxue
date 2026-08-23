import { MarkdownRenderer } from "../../components/MarkdownRenderer.js";

export interface ChatMessage {
  id: string;
  role: string;
  text: string;
}

export function MessageList({ messages }: { messages: ChatMessage[] }) {
  return (
    <section className="message-list" aria-live="polite" data-testid="message-list">
      {messages.length === 0 ? (
        <div className="welcome-card">
          <span className="eyebrow">芯智导学</span>
          <h1>从一个真实学习任务开始</h1>
          <p>左侧选择示范场景，系统会填入示例任务；提交后将展示任务规划、能力调用、证据依据、结果复核和下一步。</p>
        </div>
      ) : messages.map((message) => (
        <article className={`message message-${message.role}`} key={message.id}>
          <span className="message-role">{message.role === "user" ? "我的任务" : "芯智导学"}</span>
          <MarkdownRenderer value={message.text} />
        </article>
      ))}
    </section>
  );
}
