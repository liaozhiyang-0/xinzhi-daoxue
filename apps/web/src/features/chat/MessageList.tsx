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
          <span className="eyebrow">AI LEARNING WORKSPACE</span>
          <h1>把目标交给学科智能体</h1>
          <p>React Workspace 仅负责展示、交互和调用既有 API；任务、Planner、Skill、Runtime 与证据仍由后端负责。</p>
        </div>
      ) : messages.map((message) => (
        <article className={`message message-${message.role}`} key={message.id}>
          <span className="message-role">{message.role === "user" ? "我" : "芯智导学"}</span>
          <MarkdownRenderer value={message.text} />
        </article>
      ))}
    </section>
  );
}
