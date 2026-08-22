# Phase E3：Experience Write 与 Promotion Pipeline

## Candidate 来源

允许来源为 successful verified run、failed run、Skill/Planner/Reflection evaluation、controlled canary observation 和 offline benchmark。写入服务只接受已绑定的 source trace/run/eval ID，随后执行结构化 feature summary、敏感字段移除和文本脱敏；没有任何 provenance 的记录被拒绝。

```text
Trace / Run / Evaluation / Reflection
                 ↓
       Experience candidate writer
                 ↓
     schema + privacy/redaction check
                 ↓
       evidence + offline replay
                 ↓
          conflict check/review
                 ↓
       approved → active (explicit)
```

## Promotion rules

| 类型 | 可记录 | validated 条件 | active 条件 |
| --- | --- | --- | --- |
| Success | verified run/evaluation | verification pass、无 critical regression、证据合法、非 synthetic 偶然成功 | approved + 独立 review + evidence 不低于 offline real case |
| Failure | failed run/evaluation | provenance 完整、故障可复现或有明确错误码 | 不把暂时 Provider 故障泛化为永久策略；需要 review |
| Strategy | 多次结果或高质量 evaluation | 适用条件、反例、版本、失败率和 replay 证据齐全 | 至少两个支持样本或 high-quality eval，且可 rollback/deprecate |

实现中的状态转换是显式分步调用：`create_candidate` → `validate_candidate` → `approve` → `activate`。模型不会自行调用 promotion；Critic pass 也不会自动转为 Success。

## 禁止自动化

- 不允许 candidate 直接 active。
- 不允许 synthetic/provider-free 记录成为 production Success/Strategy。
- 不允许自动修改 prompt、Skill、Router、Planner 或 Tool policy。
- 不允许把完整学生答案、原始聊天、联系方式、账号或附件内容写入经验。
- Failure 记录用于 warning/evaluation，不用于单次永久禁用能力。

## E3 状态

`PASS`。候选写入、脱敏、证据门禁、独立批准和激活已实现并由测试覆盖。
