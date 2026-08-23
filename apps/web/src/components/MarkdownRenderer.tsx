import { Component, type ErrorInfo, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";

interface FormulaBoundaryProps {
  source: string;
  children: ReactNode;
}

interface FormulaBoundaryState {
  failed: boolean;
}

class FormulaBoundary extends Component<FormulaBoundaryProps, FormulaBoundaryState> {
  state: FormulaBoundaryState = { failed: false };

  static getDerivedStateFromError(): FormulaBoundaryState {
    return { failed: true };
  }

  componentDidCatch(_error: Error, _info: ErrorInfo) {
    // Keep the user-facing fallback stable while retaining the original source below it.
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="formula-fallback" role="alert">
          公式暂时无法完整显示
          <details>
            <summary>查看原始表达式</summary>
            <pre>{this.props.source}</pre>
          </details>
        </div>
      );
    }
    return this.props.children;
  }
}

function normalizeMathDelimiters(source: string): string {
  let normalized = source.replace(/\$\$([\s\S]*?)\$\$/g, (_, expression: string) => `\\[${expression}\\]`);
  normalized = normalized.replace(/(^|[^\\])\$([^$\n]+)\$/g, (_, prefix: string, expression: string) => `${prefix}\\(${expression}\\)`);
  return normalized;
}

function toRemarkMath(source: string): string {
  return source
    .replace(/\\\[([\s\S]*?)\\\]/g, (_, expression: string) => `$$${expression}$$`)
    .replace(/\\\(([^\n]*?)\\\)/g, (_, expression: string) => `$${expression}$`);
}

export function MarkdownRenderer({ value }: { value: string }) {
  const source = value || "暂无回答";
  const canonical = normalizeMathDelimiters(source);
  const parserSource = toRemarkMath(canonical);
  const hasMath = /(?:\$\$|\$[^$]+\$|\\\(|\\\[)/.test(parserSource);
  return (
    <FormulaBoundary source={canonical}>
      <div className="markdown-renderer" data-testid="markdown-renderer">
        <ReactMarkdown
          remarkPlugins={[[remarkMath, { singleDollarTextMath: true }]]}
          rehypePlugins={[rehypeKatex]}
        >
          {parserSource}
        </ReactMarkdown>
        {hasMath && (
          <details className="math-source">
            <summary>查看公式原始表达式</summary>
            <div className="math-source-actions">
              <pre>{canonical}</pre>
              <button
                type="button"
                onClick={() => void navigator.clipboard?.writeText(canonical)}
              >
                复制
              </button>
            </div>
          </details>
        )}
      </div>
    </FormulaBoundary>
  );
}
