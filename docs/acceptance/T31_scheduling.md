# T31 工时容量与依赖排程验收

2026-10-04纯函数源码与合成离线验收完成，正式处理关闭；PRIVATE上传以本轮随后实际Git核对为准。

## 基线与冻结

T30 PRIVATE 9d70b9a0d587c6d0291d06c69df4f4919767d675，586tracked/空索引工作区；新codex/t31-capacity-scheduling。先阅读治理、两原规格、docs01–05、T12日期/T30草案/相关源及Git，冻结[契约](../scheduling.md)/ADR044。仅七旧治理文档可改，579其他tracked保护。

只读预检曾误猜docs/05_SECURITY_OPERATIONS.md及根app/plans文件，随后按rg实际路径读取docs/05_SOURCES_AND_REVIEW.md及services/api/app/plans；begin辅助清单误写03_ARCHITECTURE.md，存在性断言失败且未开始修改，修正实际03_ARCHITECTURE_API.md并重新核空索引/工作区后执行成功。这些失败不是应用测试通过。

## 实际检查

`.venv\Scripts\python.exe -X utf8 -B -m pytest tests/unit/planning tests/unit/eligibility -q --tb=short`：185 passed/19.79秒/exit0；相关旧纯逻辑不变。

同Python `-m pytest tests/unit/dates -q --tb=short`：43 passed/0.94秒/exit0。

`.cache/run-web-checks.ps1 -TaskId T31`：完整前端Unit 474 passed/32文件/18.63秒；Type Check exit0，demo/auth Build分别1.25/1.69秒exit0。Node24.19/pnpm11.19仅本进程PATH，模式随后恢复，输出仅.cache，不改前端；Vite提示outDir在项目外且不会清空，未对未知产物做删除。

七次 `scripts/generate_contracts.py --profile <foundation|identity|public_catalog|admin|admin_review|profiles|assessments> --check`及`scripts/verify_contract.py` exit0；`scripts/verify_originals.py`两原文UNCHANGED；579保护tracked哈希不变，diff --check exit0。

最终根执行 `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/unit/scheduling -q --tb=short`：100 passed/3.75秒/exit0，无warning/skip（8owned、29容量日期、63独立边界，不累计重复）。覆盖来源及完整投影、SHA/模式/TTL、未知/历史核验与自主目标、严格确认标志/预算/非法构造/依赖环、输出重hash后容量/周界/重叠/依赖拒绝、隔离纯import无数据库/模型/网络及M0路径保持。较早根100/3.65秒后补强当前及下周Monday唯一往返与draft集合提前限额；补丁后后端整套100/3.62秒，根最后3.75秒为当前码。

分工实际检查：owned scheduler 8 passed/0.94秒；容量日期首轮28 failed/1 passed/1.90秒，为新helper展开Expr含inactive空字段，尚未进入排程断言；保留nativeExpr重验后同命令29 passed/1.57秒。独立首轮58 passed/2 failed/2.72秒，为坏fresh SHA与重复源ID应409而断言预期422；修断言及新增必要边界后独立63 passed/2.41秒。没有放宽旧解析器或来源检查。

范围15路径（7旧/8新），579受保护tracked、66其他Task卡与旧CHANGELOG/ADR历史保持。最终治理/链接/实际暂存diff/PRIVATE源及远程SHA随后核对，不把预计上传写成已通过。


## 未执行

本Task纯函数，无HTTP/UI/DB变化，PG迁移和浏览器未执行；无Lint/Python静态入口，相关检查未执行。当前官方UTC未核定，官方精确硬期限正例未执行；候选/日期-only与内部目标边界必须测且不能冒称官方通过。真实身份/招生/法律/SQL权限/部署未执行。

## 已知问题

当前官方utc_instant恒null，候选/日期-only保持未核定，constraints_complete恒false；内部目标相等边界已测，不冒称官方硬期限正例通过。有界贪心不承诺全局最优或绝对排不下。既有T30极端JSONB限额问题未动。

## 修改文件

- `AGENTS.md`
- `README.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/tasks.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/scheduling.md`
- `docs/acceptance/T31_scheduling.md`
- `services/api/app/plans/schedule_schemas.py`
- `services/api/app/plans/scheduler.py`
- `tests/unit/scheduling/test_t31_scheduler.py`
- `tests/unit/scheduling/test_t31_capacity.py`
- `tests/unit/scheduling/test_t31_dates.py`
- `tests/unit/scheduling/test_t31_safety.py`
