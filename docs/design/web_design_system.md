# 芯智导学 Web 设计系统

## 方向

界面采用中性背景、克制的蓝青强调色、轻边框、少量阴影和宽松阅读区。学生回答使用文档式排版，调试页提高信息密度但保持标签分层。设计只借鉴现代对话产品的布局原则，未使用 ChatGPT 名称、Logo、专有图标、配色或文案。

## Token

`design-tokens.css` 集中定义背景、文字、边框、强调色、成功/警告/失败/Mock 状态、阴影、圆角、内容宽度、侧栏宽度和系统字体。主题值为 `light`、`dark`、`system`，偏好保存在 `localStorage.xinzhi_theme`；切换立即生效，system 跟随系统媒体查询。

## 组件约定

- `status-badge`：正常、运行中、成功、部分完成、降级运行、开发中、开发模拟、失败、停用、未配置。
- `button`：primary、secondary、danger；真实云端只在高风险动作使用二次确认。
- `card` / `metric-card`：统一边框、圆角和状态层级。
- `empty-state` / `loading-state` / `error-state` / `toast`：统一反馈。
- `tabs`、`data-table`、`timeline`、`code-view`、`markdown-viewer`、`image-thumbnail`：调试和回答展示。

状态中文映射只在 `ui-core.js` 维护，禁止页面自行把同一状态显示成不同名称。Focus outline、label、aria-live、Esc 关闭抽屉和图片 alt 均保留。小于 900px 时侧栏成为抽屉；双栏在窄屏堆叠；表格和代码横向或内部滚动。
