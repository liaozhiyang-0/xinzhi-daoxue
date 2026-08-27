# P5：UX / 中文 / LaTeX / 可读性收口

## 原则
不重做 React，只做 Pilot 驱动的 polish。

## 中文
扫描：
loading / error / status / toast / review / evidence / fallback / buttons / empty state。

主界面不允许无必要英文。
KCL、FFT、BJT、DOI、模型名、论文标题等可保留。

## LaTeX
保持 Phase M 的单一 `MarkdownRenderer`。
现有 31 条 fixture 必须持续通过。

将 Pilot 新发现的问题加入 fixtures：
- 长矩阵
- 多行 aligned
- 单位
- 中文混排
- 复杂分式
- 相量
- 复制 LaTeX

不得新增第二数学渲染器。

## UX
重点验证：
- 第一屏是否看懂
- 核心结论是否突出
- 是否知道下一步
- waiting_review 是否明显
- attachment 状态是否清楚
- 错误是否可恢复

最低可访问性：
keyboard focus / button label / basic contrast / status not color-only。
