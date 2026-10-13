# T30 差距到草案任务验收

2026-10-04本地源码与合成隔离验收完成；公众处理仍关闭。源码上传以本轮后续实际Git核对为准。

## 基线与冻结

T29 PRIVATE 4ef4e9e1fb849ee28bf10b1ab6b5c1b17234989e/远程SHA核对/索引工作区空，568tracked/八允许旧治理路径/560其他保护；新codex/t30-gap-plan-drafts。先核治理/两原输入/相关T12/T28/权限/数据库及现M0planning，再冻结[契约](../plan_drafts.md)/ADR043。M0名称碰撞沿T11隔离namespace做法，不重构旧模块；API/UI/排程/确认/live/真实处理关闭。

只读查找误猜不存在docs/04_ACCEPTANCE_TESTS.md，未执行应用测试，后按rg实际路径读取；不当作检查通过。

## 实际检查

原文保护预检由backend执行：两输入UNCHANGED；Git只读HEAD/status通过。

根代理执行 `.cache/run-web-checks.ps1 -TaskId T30`：Vitest 474通过/32文件（19.07秒），Type Check exit0，demo/auth Build exit0（1.40/1.73秒）。本Task未修改前端；这是本轮实际运行，非引用历史结果。

根代理逐项执行 `.venv\Scripts\python.exe -X utf8 -B scripts/generate_contracts.py --profile <foundation|identity|public_catalog|admin|admin_review|profiles|assessments> --check`：七profile均匹配、exit0；`scripts/verify_originals.py` 两原输入UNCHANGED、`scripts/verify_contract.py` M0契约一致、exit0。560受保护旧tracked哈希未变。上述检查结束时新增草案专项测试仍未运行。

`.venv\Scripts\python.exe -X utf8 -B -m pytest tests/backend tests/contracts tests/security/test_mode_isolation.py tests/unit/eligibility -m 'not postgres' -q --tb=short`：641 passed、4 deselected、49.86秒、exit0；1既有Starlette弃用warning。被筛掉的是显式PG用例，不计为通过；新增T30专库测试另行执行。

backend执行 `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/unit/planning/ -q --tb=short`：合并轮80 passed（41 owned＋39独立）、2.99秒、exit0，无warning/skip；四态、实际必要any分支、去重兼容与周期、主补独立日期、不升格官方UTC、未知优先、估时调整、构造绕过与原SHA均覆盖。五owned Python模块内存compile exit0。

独立补充私密文本nested construct不回显检查后，根执行同完整 `tests/unit/planning/` 命令：**81 passed（41 owned＋40独立）、3.02秒、exit0**，无warning/skip。这是最后完整纯套件结果；前80为中间轮，不能累计作161项。独立单文件40 passed/2.29秒。

中间轮次保留：两个owned文件首轮37 passed/1.31秒；独立 `test_t30_safety.py` 首轮34 passed/1 failed（2.35秒、exit1），freshprocess测试guard误识别Pydantic内部providers.aws，限定业务导入后35 passed/2.25秒；追加独立金标准后38 passed/2.22秒，再补当天date-only拒绝、合入最终80。首轮通过数不与最终重复累计。源码审查修正新CHECK的SQL NULL/JSON绑定风险、精确release版本和未知优先顺序；这些只读发现不冒称PG测试失败。

真实PG中间轮次：`.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/planning/test_t30_store.py','-q','--tb=short')` 首13为12 passed/1 failed、340.03秒、exit1，新测试trigger误用audit_events而实际为auth_audit_events，已修。独立 `test_t30_safety.py` 首8为7 passed/1 failed、171.93秒、exit1，夹具用了不在原CHECK中的inactive，改为合法disabled后受影响节点1 passed/13.64秒。两真实PG审计锁等待跨文件/申请期限回滚在首轮通过；完整源投影与当前画像版本检查补强后，最终两个PG套件结果及最后局部时间补丁后的相关复验见下。

## 最终PG与修改范围

`.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/planning/test_t30_store.py','-q','--tb=short')`：14 passed/324.20秒/exit0，无warning/skip。覆盖实际五表/owner registry/精确source/date refs、required audit与COMMIT失败回滚、caller TX、当前确认画像、合法坏INSERT即使重算SHA也不能改target、缺marker与bool类型、同版FK/五表UPDATE拒绝/可信DELETE、upgrade/current/downgrade/upgrade及旧十一heads与选定历史数据保持。

同helper独立 `test_t30_safety.py`：8 passed/147.98秒/exit0，无warning/skip；真实metadata grant不授私有业务、用途撤回再同意不复活原proof、withdrawn/unavailable核验、错mapper零新连接、caller失败回滚和两个真实pg_blocking_pids锁等待跨原文件/主申请期限后整笔回滚。

随后只读发现末端缺新草案created_at下界，授权最小补丁 `_final(created_at=...)`，统一最终 `[created_at,expires_at)`，不是新增功能。最终代码相关复验：同helper ownedfile加 `-k 'real_draft_stores or actual_conditional'` →2 passed/12 deselected/57.37秒/exit0；独立精确节点 `test_clock_rewind_after_required_audit_cannot_commit_a_future_created_draft` 和 `test_same_transaction_failure_aborts_prior_caller_changes` →2 passed/28.74秒/exit0，无warning/skip。新增clock节点源评估后2秒生成、必需audit真实INSERT后时钟回退1秒，其他源仍有效，正确409且所有新计划/registry/成功audit回滚。没有在补丁前执行该新node，不编红测。PG总共23 distinct（14＋9），复验不累计为27；两真实SQL锁等待仍是两项，clock回退用实际audit hook而不冒称第三项等待。最终七持久Python内存compile/服务import exit0。

只使用既有专用loopback study_t23_20261003的随机planning_t30_UUID schema，合成身份/学生/DEMO发布，测试finally逐schema清理；无外网或商业API。无新依赖/旧迁移/前端/API/M0变更；560其他tracked哈希保护。最终治理/链接/原文/实际暂存diff/PRIVATE源与SHA由根随后执行，不把预计结果写成已经通过。

## 已知问题与未执行

极端合法纯组合可能约794881B（只读纯探针的JSONB格式估计，未PG），超过新版本JSONB524288B资源上限；数据库拒写并整笔回滚，目前固定503。此次保留上限，后续API预算边界需明确422/请求总量，未宣称该极限已验证或所有合法组合均可持久。

Lint和Python静态类型没有配置入口，未执行；没有新增HTTP/UI所以不执行T30 HTTP或浏览器流程。真实领域/身份/法律/SQL GRANT/RLS/生产备份恢复/部署未执行且不属于合成验证。随机schema的迁移往返不等于生产恢复。


## 修改文件

- `AGENTS.md`
- `README.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/tasks.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/plan_drafts.md`
- `docs/acceptance/T30_plan_drafts.md`
- `services/api/app/plans/__init__.py`
- `services/api/app/plans/schemas.py`
- `services/api/app/plans/drafts.py`
- `services/api/app/plans/models.py`
- `services/api/app/plans/store.py`
- `services/api/app/plans/service.py`
- `services/api/plans_alembic.ini`
- `services/api/plans_migrations/env.py`
- `services/api/plans_migrations/script.py.mako`
- `services/api/plans_migrations/versions/0001_plans_t30.py`
- `tests/unit/planning/test_t30_drafts.py`
- `tests/unit/planning/test_t30_estimates.py`
- `tests/unit/planning/test_t30_safety.py`
- `tests/integration/planning/conftest.py`
- `tests/integration/planning/test_t30_store.py`
- `tests/integration/planning/test_t30_safety.py`
