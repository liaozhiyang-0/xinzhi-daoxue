# CT/AE/DE SkillRegistry

技能配置位于 `config/skills/{CT,AE,DE}.yaml`。课程技能包含稳定的课程技能和
domain-scoped 技能；当前 AE 额外覆盖图像解析、反馈/饱和边界、教学、首错诊断和
学习先修关系。每个 `skill_id` 包含标题、章节、前置技能、题型、Capability、
证据要求、验证要求、常见错误签名和关键词。它是轻量版本化元数据，不是知识图谱，
也不替代 CoursePack 或 CapabilityPack。

Planner 使用的映射优先级为：

1. 当前执行实际选择的 Capability；
2. 已识别的 `problem_type`；
3. 标题或关键词的确定性精确命中。

映射只返回最高可信的少量候选。domain 技能可以跨课程复用，但仍必须通过
Capability、worker、tool、证据和风险策略；未知课程返回 `unavailable`；未知题型或
没有可靠命中返回 `partial` 和空列表，不做模糊猜测。

启动和 `scripts/validate_config.py` 会校验：

- skill ID 唯一且课程一致；
- problem type 与 Capability 已注册；
- prerequisites 存在且不跨课程；
- 前置关系没有循环依赖。

扩展技能时应先复用已有 CoursePack/CapabilityPack 标识，再添加合成评测案例；
不要复制课程求解图。
