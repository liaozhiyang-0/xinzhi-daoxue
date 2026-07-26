# 前端视觉精修报告

## 阶段 A 基线

回滚点：`a7d82fb3cde65e67401576388c13534605eb58a1`。重构前截图位于 `docs/reviews/workspace_v2_baseline/`。原浏览器基线在完成首页浅色、首页深色和学生空态后，真实任务超过旧脚本 90 秒等待上限；该失败作为基线问题保留。Preflight 当时为 19/19。

## 问题清单

- 视觉问题：卡片、Badge 和边框过多，重点不集中，回答仍像工程结果容器。
- 布局问题：学生回答与来源纵向堆叠，没有常驻上下文区域。
- 排版问题：长回答、状态和来源处于同一视觉权重，阅读宽度不稳定。
- 交互问题：正文引用不能定位来源；来源只在底部折叠区。
- 信息层级问题：Provider、fallback、检索候选与学生可读信息混排。
- RAG 割裂问题：RAG 主要存在于独立 Debug 页面，学生任务没有统一证据视图。
- 工作流割裂问题：前端从多个字段猜测执行状态，LEARN 与 SOLVER 的证据语义没有可视边界。
- 状态不一致问题：中文文案分散在页面脚本，Mock、云端与本地降级容易显示不一致。
- 移动端问题：旧页面以堆叠为主，资料与回答之间跳转成本高。
- 会议投影问题：1280×720 下调试信息密集，故事线不清楚。
- 性能问题：旧浏览器基线任务超过 90 秒；RAG Debug 轻量状态冷启动可能触发向量计数。
- 重复代码问题：学生、RAG、Agent 和演示页分别维护状态展示与局部结构。

## 重构结果

新增三栏 Workspace、上下文抽屉、文档式回答、统一 Execution Debug、证据流转表、真实耗时瀑布和四主题演示中心。全局色彩收敛为低饱和蓝绿色，普通卡片取消阴影，侧栏变窄，主内容与阅读宽度稳定。

新增组件：WorkspaceComposer、ContextPanel、EvidenceCard、ProcessStep、InfoRow、ExecutionSummary、EvidenceFlow、Waterfall、StoryStep 和安全 CitationLink。重复的学生来源折叠逻辑被 presentation/evidence_view 取代；统一状态文案由后端提供。

## 截图与响应式

重构后 17 张截图位于 `docs/reviews/workspace_v2_screenshots/`，覆盖空态、CT/AE/DE、证据联动、过程、回答信息、SOLVER 文字/图片、Mock/fallback、统一调试、证据对照、演示中心、1280×720、深色和 390px 移动端。

前后对比：

- 前：`workspace_v2_baseline/03-student-empty.png`
- 后：`workspace_v2_screenshots/01-workspace-empty.png`
- 调试后：`workspace_v2_screenshots/12-execution-debug.png`
- 投影后：`workspace_v2_screenshots/15-presentation-1280x720.png`

## 性能与尚存问题

首屏仅加载静态 CSS/JS 与轻量 `/health`，不加载图片模型、Reranker 或调用云端。最终无头 Edge 测量为 DOMContentLoaded 23ms、load 25ms、7 个资源/健康请求；资源传输字节受浏览器缓存影响，未作为可靠指标。最后一次回答 DOM 渲染为 1.0ms。回答渲染耗时写入 `localStorage.xinzhi_last_render_ms` 并显示在回答信息面板。

原生 Markdown 渲染器仍以安全、轻量为优先，未完整实现复杂 GFM 表格与 LaTeX 排版；移动端定位为基本可用。浏览器 Mock/禁用重量 RAG 的截图回归不代表真实模型回答质量。真实星辰专项批次长时间无输出并超过外层限制，已终止残留进程，本轮不能宣称真实 LEARN/SOLVER 回归通过。
