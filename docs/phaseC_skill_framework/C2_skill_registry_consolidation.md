# Phase C2：Skill Registry 收敛

## 目标
将已有 SkillRegistry 扩展为系统唯一 Skill manifest，不创建平行 registry。

## 必须完成
- 现有 YAML 兼容；
- SkillDefinition 加载、版本校验、序列化；
- get / list-filter / validate identity-version / validate prerequisites；
- status: active / experimental / frozen / deprecated；
- 旧 Skill ID 继续可解析；
- 为未来课程扩展留接口，但不一次性填满。

## 第一批建议
Academic Solver / CT：KCL/KVL、节点分析、网孔分析、戴维南/诺顿、一阶暂态、相量法。
Research：query planning、evidence review、evidence synthesis。
Knowledge：query rewrite、grounded explanation。
仅在现有实现与知识支持时注册，不为了数量填空 Skill。

## 禁止
Registry 不执行 Provider，不承担 Planner，不存 outcome memory，不默认新建 Skill 数据库表。

## Git
commit: `refactor(agent): consolidate canonical skill registry`
push 当前 Phase C 分支。

## 结束条件
系统只有一个 authoritative SkillRegistry，旧配置兼容测试通过后停止。
