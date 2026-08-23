# Phase E3：Experience Write 与 Promotion Pipeline

## 目标
建立“什么可以写入、什么时候可以激活”的严格门禁。

## 写入来源
允许 candidate 来源：
- successful verified run
- failed run
- Skill evaluation
- Planner evaluation
- Reflection evaluation
- controlled canary observation
- offline benchmark result

## Candidate 生成
必须：
1. 绑定 source trace/run/eval；
2. 脱敏；
3. 生成结构化 feature summary；
4. 标明 evidence level；
5. 不直接 active。

## Promotion Pipeline

```text
Candidate
  ↓
Schema / Privacy Validation
  ↓
Evidence Quality Check
  ↓
Offline Replay / Regression
  ↓
Conflict Check
  ↓
Independent Review / Policy
  ↓
Approved
  ↓
Active
```

## Promotion 规则

### Success
只有 verification pass、no critical regression、evidence 合法且非 mock/synthetic 偶然成功才可 promotion。

### Failure
可以较早记录，但避免把 Provider 暂时故障当永久策略事实。

### Strategy
要求：
- 多个支持样本或高质量评测
- 明确适用条件
- 明确反例/失败率
- version
- rollback/deprecation

## 禁止
- 模型自己写经验并立刻 active；
- Critic pass 自动变 Success；
- 单次成功自动变 Strategy；
- 自动修改 prompt / Skill / Planner policy；
- mock/synthetic promotion 为 production strategy。

## 本阶段不 commit
完成后继续 E4。
