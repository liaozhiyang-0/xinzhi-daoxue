# 数学公式规范化、传输与渲染

## 内容协议

后端使用 `MathExpression`、`RichTextSegment` 和 `MathRichContent` 表达数学内容。任务结果继续保留兼容字段 `answer`/`answer_text`，并增加可选的 `math_content`；其中 `markdown` 是可复制、可导出的规范 Markdown，`segments` 和 `math_expressions` 用于后续结构化展示与调试。数据库保存 Markdown 和结构化公式，不保存 KaTeX DOM。

公式字段的处理优先级为：`key_equations`，`intermediate_results` 的 `equation/formula/value/matrix`，`solution_steps` 的公式字段，结构化 `final_answer`，最后才是 `answer_text`。已有合法 LaTeX 只校验、不重新猜测语义。

## LaTeX 边界

- 行内公式统一为 `$...$`。
- 独立公式统一为 `$$...$$`。
- 后端兼容读取旧的 `\(...\)` 和 `\[...\]`，输出时收敛为美元分隔符。
- 结构化公式字段只保存 LaTeX 正文，不带分隔符。
- 代码围栏、行内代码、URL、日期、JSON、HTML 标签和 Markdown 表格不会进入普通文本公式猜测。

## 后端流程

`MathFormattingService` 是唯一的确定性格式化边界，不调用模型或网络。统一 TaskRunner 在业务校验、回答组装和展示数据生成完成后调用一次：

```text
Agent 结构化结果 -> 业务校验 -> final answer -> MathFormattingService
-> answer Markdown + MathRichContent -> API/数据库/Artifact
```

混合 Markdown 由分段状态机识别代码、表格、HTML、已有行内/块级公式和普通文本。普通文本只自动修复 exact/high 模式；歧义模式保留原文并写入 warning。处理超过 50 ms 时只记录耗时、数量、失败类型和内容哈希，不记录学生原文。

## 前端渲染

所有页面复用 `ui-core.js` 的 `renderMarkdown`/`renderLatex`。本地静态 KaTeX 0.16.22 是唯一主渲染器，配置为 `trust: false`、`throwOnError: true`，不加载 CDN。消息优先读取 `math_content.markdown`，缺失时回退到旧 `answer`。

公式或矩阵过宽时容器横向滚动；代码块和行内代码不参与公式渲染。非法 LaTeX、危险命令或 KaTeX 异常只让当前公式降级为原始 LaTeX，不会使整条消息崩溃。复制和 Markdown 导出读取原始 Markdown，而不是渲染后的 HTML。

## 支持范围

当前覆盖分数、根式、指数/下标、常微分与偏微分、积分/重积分、求和、连乘、极限、矩阵/行列式、`aligned`、方程组、分段函数、向量、复数、相量、拉普拉斯/傅里叶/Z 变换和卷积。矩阵自然语言维度不会被猜测；应传入二维数组或完整 LaTeX。

## 安全与降级

服务检查花括号、环境配对、允许环境、矩阵列数、嵌套分隔符和空公式。`\input`、`\include`、`\write`、`\openout`、`\read`、`\usepackage`、`\documentclass`、`\newcommand`、`\def`、`\href` 会标记为非法；前端再次阻断并显示原文。

## 扩展符号与案例

新增符号只修改 `apps/api/app/services/math_symbol_dictionary.py` 中对应分类，并为数学片段增加测试；不要添加第二份 YAML 词典。相量默认使用 `\underline{V}`，`MathFormattingService(phasor_style="dot")` 可供 CoursePack 后续显式覆盖。

验收样本位于 `apps/api/tests/fixtures/math_rendering_cases.json`，保持 20—30 个高价值案例。新增案例需提供唯一 `case_id`、输入、`expected_latex` 和 `mode`，并运行：

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_math_formatting_service.py -q --no-cov
```

## 已知限制

- 不实现完整 TeX 编译、MathML 协议、OCR/手写识别或大模型公式纠错。
- 普通正文中的歧义表达（如 `alpha2`）不会自动判断上标或下标。
- 矩阵二维结构仅支持同一环境；跨行单元格等高级表格语法不在当前范围。
- PDF、Word/OMML 公式导出留给后续独立适配器。
