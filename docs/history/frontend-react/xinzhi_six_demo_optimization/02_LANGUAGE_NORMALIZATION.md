# 前端中英文混杂专项治理

## 目标
普通用户可见主界面统一简体中文。

## 建议
建立统一文案表，如 `src/i18n/zh-CN.ts`，不要在组件中散落英文字符串。

## 标准映射
Task→任务
Session→会话
Planner→任务规划
Skill→专业能力
Tool→工具
RAG→资料检索
Evidence→证据
Reflection→结果复核
Verification→结果验证
Experience→历史经验
Runtime→执行引擎
Pending→等待处理
Running→正在执行
Completed→已完成
Failed→执行失败
Retry→重新尝试
Resume→继续执行
Confidence→置信度
Review→复核
Fallback→降级处理

## 英文枚举
`needs_review` → 需要人工复核
`conditional_go` → 条件通过
`no_existing_runtime_handler` → 当前能力暂不可用

原始 code 仅放高级详情。

## 允许保留英文
KCL/KVL、FFT/DFT、BJT/MOSFET、DOI、arXiv、IEEE、模型名、英文论文题名、URL。

首次出现专业英文可用“中文（缩写）”。

## 验收
扫描按钮、tooltip、toast、error、loading、status、empty state、Agent progress、evidence、review、demo cards。
无必要英文计数应为 0。
