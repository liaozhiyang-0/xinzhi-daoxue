# 08 多模态与附件边界

至少 50 cases。

覆盖：
1图、2图、3图、4图、5图、横竖混合、不同尺寸、模糊、旋转、长截图、局部图、题目+答案、题目+电路+波形、图文冲突、用户指定“只看第二张”。

硬门槛：
silent image drop = 0
image reorder = 0
explicit image reference error = 0

记录：
expected image count
provider consumed image count

不一致必须明确失败/降级，禁止静默继续。

Circuit 联动：
总图 + 局部图生成 CircuitIR 时不能重复元件，也不能误认为两套独立电路。

输出：
`docs/audit/74_multimodal_boundary_report.md`
