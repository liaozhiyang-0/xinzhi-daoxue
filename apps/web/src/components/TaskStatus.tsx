interface TaskStatusProps {
  status: string;
}

const labels: Record<string, string> = {
  created: "已创建",
  queued: "排队中",
  running: "运行中",
  waiting_user: "等待补充信息",
  waiting_review: "等待审核",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

export function TaskStatus({ status }: TaskStatusProps) {
  return (
    <span className={`task-status task-status-${status}`} role="status">
      {labels[status] || status}
    </span>
  );
}
