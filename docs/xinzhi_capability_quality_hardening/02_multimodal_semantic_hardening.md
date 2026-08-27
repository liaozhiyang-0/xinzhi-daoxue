# 02 多图语义可靠性专项

## 核心问题

不要再只验证“图片有没有传进去”，而要验证模型是否真正理解全部图片及其关系。

至少 70% 多图专项尽量来自本地真实资产。

## 测试类型

- 题干 + 电路
- 题目 + 学生答案
- 题干 + 电路 + 波形
- 总图 + 局部放大
- 连续两页
- 多个选项
- 图 A / 图 B 比较
- 只分析第二张
- 多轮后回到第一张
- 用户纠正某张图的角色

## 统一语义 manifest

建议保留：

- attachment_id
- file_id
- original_index
- role
- role_source
- display_name
- ingestion_status
- provider_consumed

其中 `role_source` 可为：

- explicit_user
- inferred
- unknown

显式用户说明优先。

## 禁止静默漏图

建立：

`expected_ready_images` vs `provider_consumed_images`

不一致时必须 fallback、decomposition 或明确降级。

硬门槛：

- silent image drop = 0
- image reorder = 0

## Provider 能力

统一描述：

- supports_images
- supports_multi_image
- max_images

Provider 不支持多图时，走统一 Multimodal Orchestrator：

每图理解 → structured observations → fusion → solver

禁止只取第一张图。

## 图像指代

稳定支持：

第一张、第二张、最后一张、图1、图2、图A、图B。

用户如果说“第一张叫原图、第二张叫我的答案”，后续 WorkingState 应保留。

## 图文冲突

文本条件与图片条件冲突时必须指出，不能静默任选。

## 模糊图

不能编造数值。应表达不确定性，必要时给参数化解或明确假设。

## 测试量

至少 40 个多图任务：

- 2图 >= 12
- 3图 >= 12
- 4图 >= 6
- 5图 >= 4
- 异常/模糊 >= 6

## 输出

`docs/audit/30_multimodal_semantic_report.md`
