# T36 持久作业与站内提醒验收

2026-10-04源码及合成隔离验收完成；PRIVATE保存以后续实际Git核对为准，真实处理关闭。

## 基线与范围

PRIVATE d5bcfe3e917346b1cc37f33ad9c2b1647f5beab0/686tracked，codex/t36-durable-notifications；初工作区/索引为空。必读治理/原规格/docs01–05/相关模块已核，代码前冻结[契约](../jobs_notifications.md)。12旧路径允许、674其他tracked保护，旧head/原规格/M0/历史保持。

## 实际检查

- `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/contracts tests/unit/auth tests/unit/changes tests/unit/profiles tests/unit/plan_execution tests/unit/plan_revisions -q --tb=short`：712 passed，52.00s，exit 0，1 条现有 Starlette/anyio DeprecationWarning；此进程加载在新 jobs service 落盘前，旧回归不是新增作业验收。

- 新 migration literal 生成：`.venv\Scripts\python.exe -X utf8 -B .cache/t36-freeze-migration.py` 最终 exit 0，5 表/3 索引/UPDATE-only guards；首次辅助脚本因脚本目录无项目 import path，ModuleNotFoundError，exit 1，未写迁移/未执行 SQL；限定 root path 修正后通过。

- `scripts/generate_contracts.py --profile notifications` 首次退出1；新契约首轮11 passed/1 failed（2.12s），HTTP OpenAPI的limit字符串/nullable cursor未遵守冻结分页界限。只修新factory的文档归一后生成退出0；`.venv\Scripts\python.exe -X utf8 -B -m pytest tests/contracts/test_t36_notifications_contract.py -q --tb=short`：12 passed，2.04s，exit0，未放宽旧generator/契约。

- `.cache\run-web-checks.ps1 -TaskId T36`：完整Vitest 684 passed/43files/22.02s；`scripts\web.ps1 -Action typecheck` exit0；Node24.19/作用域PATH下 pnpm --dir apps/web run build --outDir ../../.cache/t36-demo-frontend-validation 1.44s、auth 1.94s，125modules、所有退出0。只在.cache输出；auth主包522.75kB有Vite500kB提示，outDir提示保留。

- `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/unit/jobs tests/contracts/test_t36_notifications_contract.py -q --tb=short`：48 passed（36 new pure + 12 new contract），3.25s，exit0；不将重复专项相加。

- 十个有限生成 profile逐一 `scripts/generate_contracts.py --profile <profile> --check` 全部exit0；读取基线SHA实际确认18个原9profile工件字节保持、新2工件LF。`scripts/verify_contract.py`：M0 TS/OpenAPI required/null/literal/type/array/record一致，exit0。

- 新T36 migration ast→upgrade literalDDL与JobsBase PostgreSQL CreateTable/索引逐字符比较：5表3索引一致，exit0；十五旧迁移文件未改。

- 最终两 predicate 修后：`.venv\Scripts\python.exe -X utf8 -B -m pytest tests/unit/jobs tests/contracts/test_t36_notifications_contract.py -q --tb=short` 48 passed/3.13s/exit0。

- 后端新pure首轮9 passed/1 failed（2.32s）为新Meta夹具字段错误；修后10 passed/2.02s。独立pure首轮25 passed/1 failed为新reason断言错误；修后26 passed/0.75s；合并36 passed/1.87s，不累计重复。

- 真实PG执行 `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/jobs/test_t36_store.py','tests/integration/jobs/test_t36_http.py','-q','--tb=short')` 最终8 passed/134.09s/exit0/1现有Starlette弃用提示；首次collection失败（新测试非package relative import）；下一轮5 passed/3 failed（121.39s，新fixture clock别名/wholequeue断言/reviewer cookie路径）。首次正常偏好节点触发真正autoflush顺序503，最小修复后1 passed/18.14s。首失败均保留，不以历史结果替新结果。

- 同owned既有偏好节点补实际已claim export/model有限seam撤权测试：`...test_t36_store.py::test_preference_default_cas_disable_stops_queued_and_reoptin -q --tb=short` 1 passed/18.24s/exit0，无warning/skip；偏好关闭与真实logout均AUTHORITY_REVOKED取消，无业务effects。

- 独立真实PG `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/jobs/test_t36_safety.py','-q','--tb=short')` 首6 passed/1 failed/138.20s：单新增测试错用两个同offering夹具expected0；改单case后两节点1 passed/1 failed/6 deselected/37.58s，authority通过，新jobTTL失败真正发现running过期但lease未来不terminalize。只修store/service两筛选predicate后 `...test_t36_safety.py::test_actual_last_role_sql_wait_rechecks_private_authority_or_lease[job] -q --tb=short` 1 passed/21.51s/exit0/no warning或skip；8distinct独立PG全部覆盖，分次通过不累计重复。实际双consumer/新Python进程恢复/最后role SQL advisory等跨TTL/受理cleanup退出不受影响/伪造mint与水位拒绝/零IO覆盖。

- 新前端专项 Node24.19 scoped PATH `pnpm --dir apps/web exec vitest run tests/notificationsClient.test.ts tests/notificationsWorkspace.test.ts tests/NotificationsPanel.test.ts` 最终49 passed/3files/5.12s；TypeCheck exit0。首47 passed/1 failed（错误expect旧source409DOM位置）和两TS nullable/union收窄错误修后通过；首次shellfinally exit0不改变真实Vitest失败记录。最终完整684加载全部前端修复。

- 最终两predicate修复面 `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/jobs/test_t36_store.py::test_required_audit_failure_and_retry_backoff_are_atomic','tests/integration/jobs/test_t36_store.py::test_preference_default_cas_disable_stops_queued_and_reoptin','-q','--tb=short')` 2 passed/38.39s/exit0/no warnings或skip；不重跑无关八节点。前端最终文档/交互只读复核无重要偏差。

- `.venv\Scripts\python.exe -X utf8 -B .cache/check_task.py T36`：exit0，47路径（12旧/35新）、674其他tracked/66卡/467文档链接保护与23新Python内存编译通过；历史/凭据审查通过。

## 未执行与已知问题

Lint及Python静态Type Check：项目无配置入口，未执行；Vue Type Check已实际执行。新浏览器验收未执行（T36卡不要求，实际HTTP和组件已有验收）；真实学生、真实来源发布、商业模型、外部通知、未成年私有功能、爬虫、真实Keycloak、部署、生产SQL权限和生产备份恢复未执行。

真实模型/export/物理删除/外部通知关闭；cleanup_probe仅registry scope完整性，不能代替附件字节和T40删除。尚无正式供应商/法律/SQL GRANT-RLS/部署与生产备份恢复验收。auth主包522.75kB有Vite体积提示，Starlette现有弃用提示。

## 修改文件

- `.gitattributes`
- `AGENTS.md`
- `README.md`
- `apps/web/src/features/plans/notifications/NotificationsPanel.vue`
- `apps/web/src/features/plans/notifications/client.ts`
- `apps/web/src/features/plans/notifications/useNotifications.ts`
- `apps/web/src/features/plans/notifications/validation.ts`
- `apps/web/src/views/PlanView.vue`
- `apps/web/tests/NotificationsPanel.test.ts`
- `apps/web/tests/notificationsClient.test.ts`
- `apps/web/tests/notificationsFixtures.ts`
- `apps/web/tests/notificationsWorkspace.test.ts`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T36_jobs_notifications.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/jobs_notifications.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `packages/contracts/v2/notifications/generated.ts`
- `packages/contracts/v2/notifications/openapi.json`
- `scripts/generate_contracts.py`
- `services/api/app/api/notifications.py`
- `services/api/app/jobs/__init__.py`
- `services/api/app/jobs/models.py`
- `services/api/app/jobs/schemas.py`
- `services/api/app/jobs/service.py`
- `services/api/app/jobs/store.py`
- `services/api/app/notifications/__init__.py`
- `services/api/app/notifications/models.py`
- `services/api/app/notifications/router.py`
- `services/api/app/notifications/schemas.py`
- `services/api/app/notifications/service.py`
- `services/api/app/notifications/store.py`
- `services/api/jobs_alembic.ini`
- `services/api/jobs_migrations/env.py`
- `services/api/jobs_migrations/versions/0001_jobs_t36.py`
- `services/api/worker.py`
- `tests/contracts/test_t36_notifications_contract.py`
- `tests/integration/jobs/conftest.py`
- `tests/integration/jobs/test_t36_http.py`
- `tests/integration/jobs/test_t36_safety.py`
- `tests/integration/jobs/test_t36_store.py`
- `tests/unit/jobs/test_t36_notifications.py`
- `tests/unit/jobs/test_t36_safety.py`
