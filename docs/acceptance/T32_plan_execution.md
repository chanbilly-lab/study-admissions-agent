# T32 计划确认与进度验收

2026-10-04源码与合成隔离验收完成；PRIVATE上传以随后实际Git核对为准，真实处理关闭。

T31 PRIVATE b6d9ab396fe2160ef200a0d75755f0352b45555e/594tracked/空索引工作区，新codex/t32-plan-confirmation-progress。先读治理/原spec/docs01–05/相关T30/T31/T49/权限/隐私/API/DB与code/Git，冻结[契约](../plan_execution.md)/ADR045；十一旧路径可改/583其他保护。

只读检索曾猜不存在foundation.py，随后读取实际api/assessments.py与profiles.py；没有修改或将失败视为应用通过。

实施前冻结时，专项Unit/PG/HTTP、迁移/相关回归、前端/Type Check/Build、八生成profile/原文/M0/范围/治理/PRIVATE上传尚未执行；本轮实际结果按下文各轮记录。Lint/Python静态没有配置入口，真实身份/招生/法律/SQL权限/部署/生产恢复未执行。

## 已执行的相关检查

根 `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/backend tests/contracts tests/security/test_mode_isolation.py tests/unit/eligibility tests/unit/planning tests/unit/scheduling tests/unit/dates -m 'not postgres' -q --tb=short`：865 passed/4 deselected/61.81秒/exit0；1条既有Starlette弃用警告。执行时新plans profile尚未生成，最终新契约仍需另验，不将本轮结果当新功能已过。

`.cache/run-web-checks.ps1 -TaskId T32`：474 passed/32前端文件/18.17秒，Type Check exit0、demo/auth Build1.27/1.63秒exit0。此轮在新plans TS生成前；新工件生成后需重验类型及构建。前端源码未改，产物在.cache，过程PATH/模式恢复。

新 wire/生成契约最终分工命令 `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/contracts/test_t32_plans_generation.py tests/unit/plan_execution/test_t32_http_schemas.py -q --tb=short`：44 passed/7.60秒/exit0（24wire＋20contracts），1既有Starlette警告。此前root43 passed/6.66秒发生在新增第20契约测试前，不累计重复。七旧profile精确字节、默认关闭父子factory、8operation/7path、UTC wire转换与固定错误均覆盖。

新plans TS生成后，root实际 `scripts/web.ps1 -Action typecheck` →exit0；process Node24 PATH下demo/auth `pnpm --dir apps/web run build --outDir ../../.cache/t32-{mode}-frontend-validation` →exit0/1.25与1.60秒。PATH/VITE_APP_MODE在finally恢复；Vite指出outDir在项目外不自动清空，未删除用户文件，不影响成功构建。

最终wire/新契约当前45 passed/7.67秒/exit0（24wire＋21contracts），加入有界列表参数导出负例；新工件字节未变，前述44/43不累计重复。root在generator修改后执行 `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/contracts -q --tb=short`：305 passed/39.95秒/exit0、1既有Starlette warning；所有八profile相关契约已覆盖。

root通过subprocess逐一实际 `scripts/generate_contracts.py --profile {foundation,identity,public_catalog,admin,admin_review,profiles,assessments,plans} --check`：八项exit0/match。`scripts/verify_originals.py` 两原文UNCHANGED；`scripts/verify_contract.py` M0契约PASS/exit0。曾误用不存在scripts/check_contracts.py，exit1未执行任何检查，已读取真实scripts清单并运行上述verify_contract；不将错误命令算通过。`git diff --check` exit0，既有core.autocrlf换行提示不代表违规，不改全局设置。

## 新HTTP实际实库

`.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/plan_execution/test_t32_http.py','-q','--tb=short')`：5 passed/148.47秒/exit0、1既有Starlette warning，无skip/失败。专用study_t23_20261003/loopback55438且每用例execution_t32_UUID空schema，真实ASGI/PG首建而不是fixture预置计划或mock结果；涵盖八操作/meta/历史、确认与当前进度重放、请求边界与64KiB、四写Origin/CSRF、其他actor/core拒绝、identity配置但executionNone明确capfalse、conditional DAG父任务与CAS。

独立安全首完整命令 `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/plan_execution/test_t32_safety.py','-q','--tb=short')`：12 failed/1 passed/220.54秒/exit1；12失败均为新ready helper将UUID slot_id写成字符串标签，发生在业务断言前。精确诊断同文件的重放节点1 failed/19.00秒确认同前提；只改新测试slot_id=uuid4()，最终13仍待实际结果，不把前提失败视为业务算法缺陷或测试通过。

2026-10-04范围补充：只读发现新plans工件未有checkout LF规则，实施前将.gitattributes追加两条plans text/eol=lf列入当前必要范围；原所有属性保持，583其他tracked保护。首次确认采用最终fresh now核排程时点，过去容量提案409；已确认读取/重放/完成按原确认时刻校验安排，不因时段已经过而丢历史。

独立安全修正UUID后第二完整同命令13 passed/299.91秒/exit0，无warning/skip；加载首次确认时效修复前代码，为中间轮。两Session竞争实际观测pg_blocking_pids后只有一条业务确认/完成；deferred COMMIT fault/caller整TXabort、metadata grant/admin/原用途撤回、源撤回及最后SQL单一时刻三TTL均覆盖。之后新增首次确认时效边界，最终只相关复验，不累计重复节点。

最终确认时效源码后HTTP局部命令 `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/plan_execution/test_t32_http.py::test_actual_http_create_workspace_history_confirmation_and_completion','tests/integration/plan_execution/test_t32_http.py::test_confirmation_and_completion_require_precise_current_state','-q','--tb=short')`：2 passed/82.76秒/exit0，1既有Starlette warning。`scripts/generate_contracts.py --profile plans --check` match/exit0，schema/wire没有字段或产物字节变化。

Owned unit首轮9 passed/1 failed/2.35秒为新测试试赋 frozen model，修新测试后10 passed/1.81秒；确认时效投影必要测试新增后11 passed/1.82秒/exit0（`pytest tests/unit/plan_execution/test_t32_domain.py -q --tb=short`）。owned PG首精确1 failed/18.16秒为registry列误用resource_id，真实列id；完整7节点中间4 passed/3 failed/143.60秒分别是新夹具默认unknown缺依赖、tamper非canonical UTC提前拒503、合法get成功审计影响baseline，均仅修新测试前提，未放宽业务源。最终新链/constraints/required audit共10 ownedPG待最后实际结果。

## 最终专项与未执行边界

完整 owned 命令 `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/plan_execution/test_t32_store.py','-q','--tb=short')`：9 passed/1 failed/240.80秒/exit1；九项包括新链往返和三历史/FK/JSONB约束已实际通过。失败为新审计trigger范围过宽误拦已有assessment审计、且预期错误类过窄；只收窄plan/object_version=2并接受既有安全AuditError503，不改业务源。随后无关完整复跑经安全Ctrl-C中止，输出仅两点/exit1，无完整summary，不能宣称十项通过。最终精确 `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/plan_execution/test_t32_store.py::test_required_success_audit_insert_failure_leaves_no_new_proposal_or_head_change','-q','--tb=short')`：1 passed/16.94秒/exit0，无warning/skip。因此10 distinct节点有实际通过记录，来自九项未改结果与一个修复后结果，不是单轮10 passed。postgres marker正负collect-only选择11/21 collected、10 deselected/0.47秒/exit0；只选PG负筛选10 deselected无节点时wrapper exit1属预期收集语义，未执行业务测试。

此前末版8 passed/188.36秒作为新增两项之前的中间结果，不累计重复。新增链仅自有schema降级再升级、旧十二head保持；三历史UPDATE23514、owner/source/task复合FK23503、1MiB JSONB23514；真实required success audit INSERT拒绝及deferredCOMMIT整TX回滚均实际覆盖。

最终独立相关命令 `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/plan_execution/test_t32_safety.py::test_exact_confirmation_and_completion_replays_preserve_current_progress_and_old_history','tests/integration/plan_execution/test_t32_safety.py::test_two_actual_sessions_return_one_event_and_exact_replay_after_real_contention[confirm]','tests/integration/plan_execution/test_t32_safety.py::test_last_sql_after_idempotency_returns_cannot_extend_any_current_deadline','-q','--tb=short')`：5 passed/109.98秒/exit0，无warning/skip。helper采用明确未来5分钟，排除容量过去遮蔽file/session/receipt期限，真实末SQL阻塞和无新增durable行均核对。13 distinct仍为13，不重复计18。

root最终 `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/unit/plan_execution -q --tb=short`：35 passed/1.85秒/exit0，无warning/skip（11domain＋24wire）；加21新契约合计56新增pure。新HTTP5/独立13/owned10为28 distinctPG，相关复验单独记录不重复相加。

Lint与Python静态Type Check没有配置入口，未执行；前端Type Check和两Build已实际执行。T32不改UI，浏览器专项未执行，留T33；官方精确期限正例（T12尚未核定）、真实规则/身份/未成年人核验/法律/SQL登录角色GRANT_RLS/部署/生产备份恢复未执行，未宣称全部生产检查通过。

## 已知问题

官方utc_instant仍未知，constraints_complete恒false；确认只接受本人准备安排。真实处理关闭。旧T30内部极端JSONB组合503问题保持，新包装提前384KiB拒422，不裁证据；有界贪心不保证全局最优。既有Starlette弃用警告保留。

## 修改文件

- `.gitattributes`
- `AGENTS.md`
- `README.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T32_plan_execution.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/plan_execution.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `packages/contracts/v2/plans/generated.ts`
- `packages/contracts/v2/plans/openapi.json`
- `scripts/generate_contracts.py`
- `services/api/app/api/plans.py`
- `services/api/app/plan_execution/__init__.py`
- `services/api/app/plan_execution/http_schemas.py`
- `services/api/app/plan_execution/models.py`
- `services/api/app/plan_execution/router.py`
- `services/api/app/plan_execution/schemas.py`
- `services/api/app/plan_execution/service.py`
- `services/api/app/plan_execution/store.py`
- `services/api/execution_alembic.ini`
- `services/api/execution_migrations/env.py`
- `services/api/execution_migrations/versions/0001_execution_t32.py`
- `tests/contracts/test_t32_plans_generation.py`
- `tests/integration/plan_execution/conftest.py`
- `tests/integration/plan_execution/test_t32_http.py`
- `tests/integration/plan_execution/test_t32_safety.py`
- `tests/integration/plan_execution/test_t32_store.py`
- `tests/unit/plan_execution/test_t32_domain.py`
- `tests/unit/plan_execution/test_t32_http_schemas.py`

## 最终范围与治理

`.cache/check_task.py T32`：exit0，33paths（11旧/22新）、583其他tracked/66任务卡、415文档链接、18新/改Python内存编译、历史/credential扫描通过；`git diff --check` exit0。GitHub实际readonly isPrivate=true、origin准确指向已授权仓库、分支codex/t32-plan-confirmation-progress。推送及远程SHA尚待随后的实际操作，不提前宣称上传。

中止无关完整复跑留下的唯一已知 schema execution_t32_4adf96b13b9f4881b4ba3e22d5262c2e，经精确loopback专库/属当前测试DB用户/全部AuthUser synthetic/无活跃测试客户端及其他query引用核对后，仅删除该自有残留，exit0；execution_t32_%余0。未删除其它schema或停止PG，专库保留给下一Task。原.gitattrs完整属性前缀保留，新plans两工件LF及checkout规则实际检查通过。
