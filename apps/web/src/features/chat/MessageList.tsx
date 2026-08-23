import { useEffect, useRef, useState, type ReactNode } from "react";
import { MarkdownRenderer } from "../../components/MarkdownRenderer.js";

export interface ChatMessage {
  id: string;
  role: string;
  text: string;
}

interface MessageListProps {
  messages: ChatMessage[];
  children?: ReactNode;
  activityKey?: string;
}

export function MessageList({ messages, children, activityKey = String(messages.length) }: MessageListProps) {
  const listRef = useRef<HTMLElement | null>(null);
  const nearBottomRef = useRef(true);
  const userScrolledRef = useRef(false);
  const programmaticScrollRef = useRef(false);
  const [showJumpButton, setShowJumpButton] = useState(false);

  useEffect(() => {
    const node = listRef.current;
    if (!node) return undefined;
    const updateScrollState = () => {
      const distanceFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
      nearBottomRef.current = distanceFromBottom < 72;
      if (userScrolledRef.current && !programmaticScrollRef.current) {
        setShowJumpButton(distanceFromBottom >= 72);
      }
    };
    const handleScroll = () => {
      if (!programmaticScrollRef.current) userScrolledRef.current = true;
      updateScrollState();
    };
    node.addEventListener("scroll", handleScroll, { passive: true });
    updateScrollState();
    return () => node.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    const node = listRef.current;
    if (!node) return;
    if (nearBottomRef.current) {
      programmaticScrollRef.current = true;
      node.scrollTo({ top: node.scrollHeight, behavior: "auto" });
      setShowJumpButton(false);
      window.requestAnimationFrame(() => { programmaticScrollRef.current = false; });
    } else {
      setShowJumpButton(userScrolledRef.current);
    }
  }, [activityKey]);

  function jumpToLatest() {
    const node = listRef.current;
    if (!node) return;
    nearBottomRef.current = true;
    node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
    setShowJumpButton(false);
  }

  return (
    <section ref={listRef} className="message-list" aria-live="polite" data-testid="message-list">
      {messages.map((message) => (
        <article className={`message message-${message.role}`} key={message.id}>
          <span className="message-role">{message.role === "user" ? "我的任务" : "芯智导学"}</span>
          <MarkdownRenderer value={message.text} />
        </article>
      ))}
      {children}
      {showJumpButton && <button className="message-jump-button" type="button" onClick={jumpToLatest}>查看最新内容</button>}
    </section>
  );
}
