# M8：Legacy Cleanup 与 Code Health

## 前端
React 覆盖完成并 parity 后：
- React 成为默认入口；
- 删除不再使用的旧 DOM orchestration；
- rollback 需要时保留清晰 legacy snapshot/branch，不在活动代码双维护；
- workspace.js 不再是主业务文件。

## 后端
清理：
- zero importer compatibility re-export
- duplicate forwarding wrapper
- obsolete import
- dead wiring

不要删除 rollback-critical compatibility、migration history、审计所需 frozen baseline。

## 大文件治理
>800 行 review；>1200 split candidate；>2000 必须说明不拆理由。生成文件/Schema/Migration 除外。

## services 指标
不设 LOC KPI，只看 owner clear / import direction / no duplicate implementation / facade thin / capability boundary clear。

## 大型数据
只版本化 manifest / schema / rubric / small sample / reproducibility metadata。
大原始数据、生成报告、缓存按实际用 `.gitignore` / LFS / external storage。
不得未经验证大规模删除数据。

输出：
- `docs/history/frontend-react/modernization/m8_code_health.md`
- `docs/history/frontend-react/modernization/final_architecture_map.md`

本阶段不 commit。
