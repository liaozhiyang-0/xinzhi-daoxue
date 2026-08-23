import type { SessionRead } from "../../api-types.js";

interface SessionListProps {
  sessions: SessionRead[];
  activeId: string | null;
  onSelect: (session: SessionRead) => void;
  onCreate: () => void;
}

export function SessionList({ sessions, activeId, onSelect, onCreate }: SessionListProps) {
  return (
    <aside className="session-list" aria-label="会话列表">
      <div className="session-list-heading">
        <strong>会话</strong>
        <button type="button" onClick={onCreate} aria-label="新建会话">＋</button>
      </div>
      {sessions.length === 0 ? (
        <p className="muted">还没有会话</p>
      ) : (
        sessions.map((session) => (
          <button
            className={session.id === activeId ? "session-item active" : "session-item"}
            key={session.id}
            type="button"
            onClick={() => onSelect(session)}
          >
            <strong>{session.title || "未命名会话"}</strong>
            <small>{session.course_id} · {session.message_count} 条消息</small>
          </button>
        ))
      )}
    </aside>
  );
}
