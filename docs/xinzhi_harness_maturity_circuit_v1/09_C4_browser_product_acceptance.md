# C4：Circuit Browser Product Acceptance

后端通过不代表完成，必须 `/workspace` 实测。

优先使用本地已有真实电路题、电路图、教材截图、多图题、历史人工复测题。

Browser Matrix：
A. 10 个文字电路题，不要求绘图，确认完全无退化。
B. 10 个明确要求绘图。
C. 10 个图片电路题 + 重绘。
D. 5 个多图题。
E. 5 个复杂/模糊图。
F. 5 个追问，例如：
- 把刚才的等效电路画出来
- 第二张图重新画
- 只画小信号模型

检查：
answer correctness
render correctness
artifact visible
refresh restore
history restore
latency
wrong auto trigger
missing render

硬门槛：
OFF mode regression = 0
renderer failure causing solver failure = 0
artifact invisible after successful render = 0
browser infinite loading = 0

初版 render success 目标 >= 90%。

输出：
`docs/audit/54_circuit_browser_acceptance.md`

提交：
`feat(web): present circuit artifacts in solver results`
