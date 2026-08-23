import type { SessionRead } from "../../api-types.js";

interface SessionListProps {
  sessions: SessionRead[];
  activeId: string | null;
  onSelect: (session: SessionRead) => void;
  onCreate: () => void;
  search: string;
  onSearch: (value: string) => void;
  showArchived: boolean;
  onToggleArchived: () => void;
  onArchive: (session: SessionRead) => void;
}

export function SessionList({ sessions, activeId, onSelect, onCreate, search, onSearch, showArchived, onToggleArchived, onArchive }: SessionListProps) {
  return (
    <aside className="session-list" aria-label="会话列表">
      <div className="session-list-heading">
        <strong>会话</strong>
        <button type="button" onClick={onCreate} aria-label="新建会话">＋</button>
      </div>
      <input className="session-search" type="search" value={search} onChange={(event) => onSearch(event.target.value)} placeholder="搜索会话" aria-label="搜索会话" />
      <button className="session-archive-toggle" type="button" onClick={onToggleArchived}>{showArchived ? "最近会话" : "归档会话"}</button>
      {sessions.length === 0 ? (
        <p className="muted">还没有会话</p>
      ) : (
        sessions.map((session) => <div className="session-row" key={session.id}>
          <button
            className={session.id === activeId ? "session-item active" : "session-item"}
            type="button"
            onClick={() => onSelect(session)}
          >
            <strong>{session.title || "未命名会话"}</strong>
            <small>{session.course_id} · {session.message_count} 条消息</small>
          </button>
          <button className="session-action" type="button" onClick={() => onArchive(session)} aria-label={session.archived_at ? "恢复会话" : "归档会话"}>{session.archived_at ? "↩" : "×"}</button>
        </div>)
      )}
    </aside>
  );
}
