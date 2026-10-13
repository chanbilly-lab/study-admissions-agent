# T35 明确修订与有限历史工作台验收

2026-10-04源码及合成隔离验收完成；PRIVATE保存以后续实际Git核对为准，真实处理关闭。

## 基线与范围

PRIVATE ed59876d21b0ba5ceb21d60d720187da5bbab9ed/653tracked，codex/t35-explicit-plan-revisions；初工作区/索引为空。必读治理/原规格/docs01–05/相关模块已核，代码前冻结[契约](../plan_revisions.md)。12旧路径允许、641其他tracked保护，旧head/原规格/M0/历史保持。

## 实际检查

以下为本Task实际执行，使用专用PostgreSQL16.15/随机schema、合成画像/DEMO来源，不接商业API。重复复验不累计为额外独立节点。

- `.\.venv\Scripts\python.exe -X utf8 -B -m pytest tests/unit/profiles tests/unit/planning tests/unit/scheduling tests/unit/plan_execution tests/unit/changes -q --tb=short`：350 passed/10.69s，exit0，1条既有Starlette BlockingPortal警告。
- `.\.venv\Scripts\python.exe -X utf8 -B -m pytest tests/contracts tests/unit/plan_revisions -q --tb=short`：378 passed/55.36s，exit0，1条既有警告，包含321 contracts（16新）和57新pure。最后纯日期DTO耦合补丁后 `pytest tests/unit/plan_revisions tests/contracts/test_t35_revisions_contract.py -q --tb=short`：73 passed/9.82s，exit0，1条同类警告；旧305不变。完整契约首轮曾320 passed/1 failed/47.17s，新日期枚举写入期间生成工件尚未同步；末生成与完整回归已修正。
- `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/plan_revisions/test_t35_store.py','tests/integration/plan_revisions/test_t35_http.py','-q','--tb=short')`：5 passed/139.83s，exit0，1条既有警告，无skip。实际profile append→newassessment/draft→proposal/accept/repeat、旧确认/完成物理不变、新编辑后reject、必需审计失败回滚、三不可变表与第15迁移down/up/十四旧head、真实HTTP session/owner/core/CSRF/Origin/64KiB/重复JSON/未知字段/no-store无writes。此轮已加载原pin/创建时impact/隐藏原时间期限补强；最后纯日期DTO耦合由新pure与后续六PG及Edge验证。首整组4 passed/1 failed/140.14s因新测试错用了audit_events表名，改为实际auth_audit_events后复验；首次正向1 failed/23.44s及诊断1 failed/25.68s暴露重复native时间解码，修后正向1 passed/31.82s，均属于相同节点。
- `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/plan_revisions/test_t35_safety.py','-q','--tb=short')`：13 passed/358.74s，exit0，无warning/skip；真实两个Session决定去重/相反CAS、唯一old successor、旧completion/newworkspace变化、原notice/core/owner/admin/grant/错误mapper零IO、末SQL实际锁等待到期、必需审计与真正延迟COMMIT回滚、坏初始INSERT重哈希伪历史拒绝。该完整轮在最后创建时过滤/隐藏时间和纯日期DTO耦合补丁前加载。末版 `-k 'initial_rehashed or acceptance_does_not_silently_absorb_changed_plan_cas or new_profile_and_withdrawn_source or required_final_sql_wait'`：6 passed/7 deselected/161.11s，exit0，无warning/skip。实际proposal后clock+1→withdraw ChangeEvent→T34process，新impact时间大于proposal仍可reject并保原diff/SHA/history；accept409。13为distinct，不累计成19。首旧12轮11 passed/1 failed/305.64s，新夹具在画像指针改变后试旧T32 completion，被正确409；对应节点改用仍current的原画像以真正测试completion CAS。
- 新前端专项 `pnpm --dir apps/web exec vitest run tests/revisionsClient.test.ts tests/revisionsWorkspace.test.ts tests/RevisionPanel.test.ts`：末45 passed/3文件/5.46s，exit0，无warning/skip（19 client/19 state/7 component）。首Type Check因PlanPin未re-export失败，修后exit0。完整新测试曾634 passed/1 failed/22.11s，固定20ms等待无法保证WebCrypto终态；新测试改为等待实际DOM/Promise终态，未放宽断言。
- `.cache/run-web-checks.ps1 -TaskId T35`：最后635 passed/40文件/21.90s，exit0；`scripts/web.ps1 -Action typecheck` exit0；`pnpm --dir apps/web run build --outDir ../../.cache/t35-{demo,auth}-frontend-validation`两模式exit0，1.47/1.94s、各119模块。缓存outDir提示与auth主包503.53kB体积提示保留。先前633/634轮为中间版，不当末版或独立新增数量。
- `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/revisions_ui/test_t35_browser.py','-q','--tb=short','-s')`：最后1 passed/40.70s，exit0，1既有警告。实际Edge154.0.4258.53→透明loopback→真实ASGI→PG，13检查点，无API mock/商业调用/页错误/外网，真实接受/拒绝/旧history完成保留/new仍draft0done、手机390/键盘/当前owner与other已同意账号拒绝、实际history200迟到退出不复活。根已用view_image核最后mobile-decision与desktop-workspace可读无溢出；安全缓存位于 `.cache/t35-ui/1abf2f8d-483f-4e4b-839c-f84764ebb8c5`，未入Git。首1 failed/33.18s真实history503；第二1 failed/43.47s测试API context没证明第二账号secure cookie；改为真实Page同源GET session200/精确账号后再403/404。第三1 passed/41.46s为最终补强前，重复不计。
- `python scripts/generate_contracts.py --profile <profile> --check`：foundation/identity/public_catalog/admin/admin_review/profiles/assessments/plans/revisions九profile实际各exit0，旧八工件字节保持，第九最终check0。新DDL literal与最终PostgreSQL metadata三table/一index完全比对exit0；原14head、accept action FK、仅UPDATE触发器/未来DELETE允许、down范围已独立核。
- `python scripts/verify_originals.py`、`python scripts/verify_contract.py`：最后各exit0，两份原文/M0契约保持。641其他tracked SHA与初空索引已实际核0。
- python .cache/check_task.py T35 实际exit0：45路径（12旧/33新）、641其他tracked、66其他任务卡、456文档链接、20 Python内存compile、历史与凭据检查通过；内存compile不等于Lint或Type Check。实际暂存diff/blob、PRIVATE/branch/origin/commit/push/SHA核对在保存步骤另执行，以实际Git输出为准。

新增pure早期错误夹具与严格false故障先失败（29 passed/19 failed、45 passed/3 failed），并行写模块曾有collection SyntaxError未执行测试；修复后最终57 distinct通过，不能累加各轮。无Lint/Python静态入口，见下方未执行。

## 未执行与已知问题

Lint与Python静态Type Check未执行：项目无对应入口，未新增依赖；内存compile不等于静态检查。真实模型/商业API、真实学生/学校要求发布、全国采集、未成年私有、正式Keycloak/法律/SQL角色GRANT/RLS/HTTPS部署及生产备份恢复均未执行；专用合成PG和Edge不代表公众上线。旧T32整体停用/自动完成转移不在本Task。

正式学生/规则/供应商/法律/SQL角色及公众部署仍关闭；原官方精确UTC仍未知，历史不能恢复当前资格。关系未全局停用旧T32端口，原证明仍有效时旧完成可继续追加；不承接完成信用。创建时来源轨迹最多100，超限明确409；无真实跨年度项目验收。auth构建主包503.53kB触发Vite体积提示，未为当前Task顺带重构；1条既有Starlette BlockingPortal警告保留。

## 修改文件

- `.gitattributes`
- `AGENTS.md`
- `README.md`
- `apps/web/src/features/plans/revisions/RevisionPanel.vue`
- `apps/web/src/features/plans/revisions/client.ts`
- `apps/web/src/features/plans/revisions/useRevisions.ts`
- `apps/web/src/features/plans/revisions/validation.ts`
- `apps/web/src/views/PlanView.vue`
- `apps/web/tests/RevisionPanel.test.ts`
- `apps/web/tests/revisionsClient.test.ts`
- `apps/web/tests/revisionsFixtures.ts`
- `apps/web/tests/revisionsWorkspace.test.ts`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T35_plan_revisions.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/plan_revisions.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `packages/contracts/v2/revisions/generated.ts`
- `packages/contracts/v2/revisions/openapi.json`
- `scripts/generate_contracts.py`
- `scripts/plans_t35_browser_smoke.mjs`
- `services/api/app/api/revisions.py`
- `services/api/app/plan_revisions/__init__.py`
- `services/api/app/plan_revisions/diff.py`
- `services/api/app/plan_revisions/models.py`
- `services/api/app/plan_revisions/router.py`
- `services/api/app/plan_revisions/schemas.py`
- `services/api/app/plan_revisions/service.py`
- `services/api/app/plan_revisions/store.py`
- `services/api/revisions_alembic.ini`
- `services/api/revisions_migrations/env.py`
- `services/api/revisions_migrations/versions/0001_revisions_t35.py`
- `tests/contracts/test_t35_revisions_contract.py`
- `tests/integration/plan_revisions/conftest.py`
- `tests/integration/plan_revisions/test_t35_http.py`
- `tests/integration/plan_revisions/test_t35_safety.py`
- `tests/integration/plan_revisions/test_t35_store.py`
- `tests/integration/revisions_ui/conftest.py`
- `tests/integration/revisions_ui/test_t35_browser.py`
- `tests/unit/plan_revisions/test_t35_domain.py`
- `tests/unit/plan_revisions/test_t35_safety.py`
