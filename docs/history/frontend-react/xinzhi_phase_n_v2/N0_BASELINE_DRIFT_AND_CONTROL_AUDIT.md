# N0：基线漂移治理 + 控制面审计

## 目标

Phase N 开始前，先把 Phase M 留下的 5 个失败分类清楚，建立可信 baseline。

## 已知 5 个失败

1. commercial scenario coverage
2. commercial scenario count/preflight
3. external source registry count
4. local text model / SentenceTransformer compatibility
5. demo scenario count assertion

## 处理原则

### 对“旧数量断言”

不能直接把测试数字改大。

必须先确认：
- 当前场景目录扩展是否是明确设计；
- 当前 external registry 扩展是否是明确设计；
- API 是否应该返回全部场景，还是只返回某个 filtered subset。

确认语义后再更新测试。

### 对 embedding compatibility

必须判断是：
- 测试替身过时；
- 还是本地模型加载路径真的可能访问网络/绕过兼容接口。

若是实际 bug，先修；若是 stale fixture，再更新 fixture。

## Baseline 输出

生成：

`docs/history/frontend-react/architecture/phase_n0_baseline_drift.md`

明确：

```text
baseline_failures
resolved_before_n
accepted_known_failures
reason
evidence
```

## 控制面审计

审计：
Supervisor / TaskRouter / IntentPlanCompiler / Planner / OverallRoutingService / FallbackRoutingService / RuntimeRequestPreparation / RuntimeBusinessRegistry / legacy-runtime / scenario_catalog / Agent registry。

建立：

```text
ControlOwnerMatrix
```

字段：
component、authority、can_change_route、can_change_plan、production_enabled、target_status、removal_condition。

## Telemetry

必须具备：

```text
taskrouter_final_route_count
overall_router_rewrite_count
planner_shadow_count
planner_controlled_count
planner_active_count
legacy_runtime_invocation_count
fixed_agent_route_count
fallback_route_count
```

本阶段不 commit。
