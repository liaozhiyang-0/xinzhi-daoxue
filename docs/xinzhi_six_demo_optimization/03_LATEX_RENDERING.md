# LaTeX 数学公式呈现专项优化

## 目标
完整支持：
行内/独立公式、上下标、分式、根式、求和、积分、微分、偏导、极限、矩阵、行列式、cases、aligned、相量、复数、单位和中文混排。

## 技术建议
优先审计并复用现有 renderer。
若 React 当前方案不完整，可统一采用：
`react-markdown + remark-math + rehype-katex`
并继续遵循现有安全策略。

不要并存两套公式渲染器。

## Canonical delimiter
推荐统一：
行内 `\( ... \)`
独立 `\[ ... \]`

如果后端还输出 `$...$` / `$$...$$`，由统一预处理器规范化，不能在各组件分别猜，且注意货币 `$`。

## 必测公式
- `Z_C=\frac{1}{j\omega C}`
- `y(t)=\int_{-\infty}^{+\infty}x(\tau)h(t-\tau)\,d\tau`
- `i_C=C\frac{du_C}{dt}`
- `\frac{\partial f}{\partial x}`
- `X[k]=\sum_{n=0}^{N-1}x[n]e^{-j2\pi kn/N}`
- bmatrix
- cases
- aligned
- `10\angle30^\circ\,\mathrm{V}`

## 容错
渲染失败不能让整个消息崩溃，应显示：
“公式暂时无法完整显示 [查看原始表达式]”。

## 长公式
支持横向滚动、复制 LaTeX、不撑破卡片。

## 验收
至少 30 个 math fixtures。
