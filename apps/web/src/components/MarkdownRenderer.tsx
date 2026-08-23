interface MarkdownRendererProps {
  value: string;
}

export function MarkdownRenderer({ value }: MarkdownRendererProps) {
  return (
    <div className="markdown-renderer" data-testid="markdown-renderer">
      {value || "暂无回答"}
    </div>
  );
}
