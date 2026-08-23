# T3：Targeted 专项测试集建设报告

## 结论

T3 已建立 6 个针对 T2 高频失败模式的专项测试集，共 120 个 case 引用、68 个 distinct case。每个 suite 固定 20 cases，包含 5 个 `positive`、5 个 `negative`、5 个 `boundary` 和 5 个 `already_correct`，并保留 5 个 hidden targeted regression case（25%）。

专项清单位于 `evaluation/targeted/`。清单只引用已有 case ID，不复制题面、不修改 expected answer、不新增业务代码。

## Suite 覆盖

| Suite | T2 patterns | cases | official baseline | supplemental `not_official` | hidden | T1 baseline selection result |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `teaching_timeout_recovery` | P02/P03/P07/P11/P14/P16/P17 | 20 | 20 | 0 | 5 | passed 11 / failed 5 / timeout 4 |
| `tool_boundary_selection` | P01/P15 | 20 | 19 | 1 | 5 | passed 13 / failed 5 / error 1 / not in baseline 1 |
| `task_creation_idempotency` | P04 | 20 | 9 | 11 | 5 | passed 8 / failed 1 / not in baseline 11 |
| `visual_fixture_acceptance` | P05/P06 | 20 | 19 | 1 | 5 | passed 14 / failed 5 / not in baseline 1 |
| `routing_boundary_learning` | P07/P11/P12/P13/P14 | 20 | 16 | 4 | 5 | passed 9 / failed 5 / error 2 / not in baseline 4 |
| `generation_verification_contracts` | P08/P09/P10/P16/P17 | 20 | 20 | 0 | 5 | passed 15 / failed 5 |
| **合计** | **P01–P17 主要失败族** | **120** | **103** | **17** | **30** | **按 T1 报告做离线选择核对** |

Suite 之间的重复是有意的：同一个边界或已知失败可能同时影响 routing、tool、verification 和 task lifecycle，需要在不同 owner 视角下保留回归覆盖。120 是 suite 引用数，不等于 distinct case 数。

## 证据边界

- T1 官方 runner 对 `evaluation/cases` 中带 `not_official` 标签的 case 过滤，因此公开基线为 84 cases；声明目录实际包含 96 个 case，其中 12 个是补充目标池。
- `not in baseline` 只表示该 case 没有进入 `evaluation/reports/phase_h/latest.json`，不表示通过或失败。它们必须在后续专项执行中单独运行，不能混入 T1 通过率。
- 当前 T1 报告有 38 条 cache 命中；本报告只做 case 选择覆盖核对，不把它描述为一次新的 uncached benchmark。
- 当前附件 manifest 的 `case_attachment_count` 为 0。`visual_fixture_acceptance` 只能验证 fixture/citation contract 的选择边界，不能宣称真实图片理解或视觉质量已验证。
- 所有 suite 的 `evidence_level` 是 `synthetic_provider_free`；没有执行真实 Provider，也没有产生费用或生产质量结论。

## 可复现核对

先验证官方 case catalog：

```powershell
.\.venv\Scripts\python.exe scripts/run_evaluation.py --validate-only
```

再验证 targeted manifest 的数量、分类、hidden 比例和 case ID 存在性：

```powershell
@'
from pathlib import Path
import yaml

declared = set()
for path in Path("evaluation/cases").rglob("*.yaml"):
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    declared.update(item["case_id"] for item in payload.get("cases", []))

for path in sorted(Path("evaluation/targeted").glob("*.yaml")):
    suite = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = suite["cases"]
    assert len(cases) == suite["case_count"] == 20
    assert len({item["case_id"] for item in cases}) == 20
    assert sum(item["hidden_targeted"] for item in cases) == 5
    assert {item["category"] for item in cases} == {
        "positive", "negative", "boundary", "already_correct"
    }
    assert all(item["case_id"] in declared for item in cases)
    print(suite["suite_id"], "PASS")
'@ | .\.venv\Scripts\python.exe -
```

T3 完成后，下一阶段才允许基于这些专项结果做最小、可归因的优化；本阶段不修改 Router、Runtime、Prompt、Skill、Tool policy 或 expected answer。
