# T09 明确共享授权验收

日期：2026-10-03。状态：已完成源码、合成与隔离实库验收；真实共享关闭。实施前已读必读治理、原始规格和相关模块/Git；基线HEAD081f5a01aad9caf61df0b865eda7e5cab3222293，codex/t09-explicit-sharing，初始工作区与索引干净，207tracked哈希存忽略缓存。

契约、范围和验收先冻结于[共享契约](../sharing.md)，ADR-020。当前只T09；其他Task不同时实施。

PostgreSQL16.15：新建专用sharing_t09_test、随机schema；复用本批自有T08 loopback55438 cluster，仅测试数据，不接触旧用户数据库。凭据及环境文件不上传。helper.cache/t09-postgres/run-tests.ps1注入T09及旧4个测试URLs，输出不打印DSN。

## 实际测试过程

首轮独立schema安全：`.\.venv\Scripts\python.exe -m pytest tests/security/grants/test_t09_adversarial.py -q --tb=short`，113 passed/3 failed，1.12s，exit1。numeric int/float/数字字符串被datetime coercion当作UTC，违背明确offset输入；已交后端修复，初轮不记为通过。其他mandatory PG/HTTP/UI/Type Check/Build尚未执行。

## 正式运行限制

真实共享仍关闭；本Task只registry metadata状态/version及read/list，不能当成学生画像、对话、附件下载或真实worker已实现。30天为合成策略上限。controller/告知/法律审查、真实Keycloak/MFA/恢复、生产GRANT/RLS及正式部署未验收。

到期输入修复后同独立命令实际116 passed，0.72s/exit0。PG/HTTP仍待装配，不能由纯输入测试推定通过。

认证迁移/旧会话兼容实际root命令：`.cache/t09-postgres/run-tests.ps1 -PytestArguments @('tests/integration/auth/test_persistence.py','tests/security/auth/test_postgresql.py','tests/security/authorization/test_postgresql.py','-q','--tb=short')` →54 passed/1既有Starlette-AnyIO warning，41.42s/exit0。旧exacthead/table集合只按当前0005四表扩展；保持旧值保留/不自动DDL断言。辅助编辑script首次因原断言出现3处而非2处安全assert退出1、无改动，重新核对后调整三处；不是应用测试失败。

前端首版 `.\scripts\web.ps1 -Action test` →162 passed/15files（旧116+新46），尚待真实生成TS接线/最终专项，不称Type Check或Build已通过。

root契约首次实际 `python -m pytest tests/contracts/test_sharing_contract.py tests/contracts/test_identity_contract.py tests/contracts/test_privacy_contract.py tests/contracts/test_v2_generation.py -q --tb=short` →100 passed/1 failed，harness把合法export interface误断言export type；修正实际generator已有函数语义后同命令101 passed/1既有warning/6.41s/exit0。identity生成成功，foundation未改；新增分页lexical检查还需最终回归。root模型直接观察GrantQuery limit='1.0'被coerce为1，将复用既有OfferingQuery语法校验；此前未把此项称为HTTP失败。

前端最终165 passed/15files、Type Check exit0；最初browser6checks后因harness用了旧owner revision正确409，显式重读后两次完整9checks/exit0，无页面错误/外部请求；最终.cache/t09-ui/b7870ab4-1ce7-4b62-8358-24117c18474c含面板截图。

root Build：先误将VITE_APP_MODE设m0（非法入口，编译退出0但只生成拒绝入口，不能计M0功能Build通过）；按实际main.ts更正为demo，`.\scripts\web.ps1 -Action build` demo/auth均实际exit0，分别App/AuthViewchunk生成。VITE_APP_MODE为进程变量，操作后恢复，无.env改动。

后端最终基础helper+test_t09_service.py14 passed/16.62s，独立完整安全160 passed/1既有warning/55.89s、最后仅PID observer改进再跑4并发nodeids4 passed/5.81s；首次PG142 passed/15 failed为新fixture过期时间CHECK与错误envelope/503预期不符，修正后159/160通过，不把首轮记为通过。完整最终项目回归尚未执行。

## 最终实际验收

| 实际命令 | 最终结果 |
| --- | --- |
| `.cache/t09-postgres/run-tests.ps1 -PytestArguments @('tests','-q','--tb=short')` | 1483 passed，1既有warning，330.30s/exit0，无skip；marker收集321PG/1162其他 |
| 同helper，`tests/security/privacy/test_persistence.py::test_incremental_t08_preserves_t07_accounts_roles_metadata_and_m0 -q --tb=short` | 1 passed/1.61s；先显式T08 milestone再升级current head，保留数据/降级检查 |
| `python -m pytest tests/contracts/test_sharing_contract.py tests/contracts/test_identity_contract.py tests/contracts/test_privacy_contract.py tests/contracts/test_v2_generation.py -q --tb=short` | 110 passed/1既有warning/7.05s/exit0 |
| `scripts/web.ps1 -Action test` / `-Action typecheck` | 最终170前端passed/15files，Type Check exit0；notice失败仍可负向退出/撤销的回归已覆盖 |
| `scripts/web.ps1 -Action build`，进程VITE_APP_MODE=demo/auth | 两模式实际exit0；新增notice恢复修复后auth以 bundled pnpm --dir apps/web run build --outDir ../../.cache/t09-auth-policy-recovery-dist 又实际构建 |
| `node scripts/sharing_t09_browser_smoke.mjs` | 最终完整10checks/exit0、0page_errors/0externalrequests；desktop/mobile面板实际查看；合成本机Edge/IdP/SQLite，非真实Keycloak |
| `python scripts/generate_contracts.py --profile identity --check`；默认`--check`；`python scripts/verify_contract.py`；`python scripts/verify_originals.py` | 两profile与M0契约/两原始输入通过；生成LF、foundation原字节保留 |
| Python memory compile、`node --check scripts/sharing_t09_browser_smoke.mjs`、范围/历史文档/链接/暂存审查及`git diff --check` | 单列最终检查输出，不作为Lint或Python静态类型通过 |

第一次完整回归1482 passed/1 failed/1warning/322.66s/exit1：旧T08迁移测试把current head等同T08表集合，新增T09后断言过时；仅改成明确0004 milestone并追加current升级保留验证，专项1通过后整套1483通过。初轮没有记为通过。全Python通过后只补前端notice失败管理列表回归及合成浏览器fixture的notice破坏开关；生产Python实现及生成契约未改变，前端与浏览器相关检查重新执行。

未执行：Lint（前端无lint script，Python无ruff）、Python静态类型（mypy/pyright未配置）；真实Keycloak/MFA/恢复/生产TLS、正式运营主体/告知与法律审查、真实学生/真实协作、生产数据库GRANT/RLS、保留删除清理/备份恢复、部署。已有Starlette AnyIO alias弃用warning保留。可信SQL维护、raw SQL/本地恶意Python不属于权限沙箱；readonly execute seam不能承诺跨系统副作用原子性。

## 变更文件

51路径（28旧改/23新），无依赖新增；原始两份输入、旧迁移/旧验收、M0及其他66主Task卡保留。

- `AGENTS.md`
- `README.md`
- `apps/web/src/features/auth/AuthView.vue`
- `apps/web/src/features/sharing/SharingPanel.vue`
- `apps/web/src/features/sharing/client.ts`
- `apps/web/src/features/sharing/useSharing.ts`
- `apps/web/tests/SharingPanel.test.ts`
- `apps/web/tests/sharing-client.test.ts`
- `apps/web/tests/sharing-state.test.ts`
- `apps/web/tests/sharingFixtures.ts`
- `config/identity/README.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T09_explicit_sharing.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/authorization.md`
- `docs/database.md`
- `docs/identity.md`
- `docs/privacy.md`
- `docs/requirements.md`
- `docs/sharing.md`
- `docs/tasks.md`
- `packages/contracts/v2/identity/generated.ts`
- `packages/contracts/v2/identity/openapi.json`
- `scripts/generate_contracts.py`
- `scripts/sharing_t09_browser_smoke.mjs`
- `services/api/app/api/identity.py`
- `services/api/app/auth/grants/__init__.py`
- `services/api/app/auth/grants/models.py`
- `services/api/app/auth/grants/policy.py`
- `services/api/app/auth/grants/router.py`
- `services/api/app/auth/grants/schemas.py`
- `services/api/app/auth/grants/service.py`
- `services/api/app/auth/store.py`
- `services/api/app/privacy/proofs.py`
- `services/api/app/privacy/service.py`
- `services/api/auth_migrations/env.py`
- `services/api/auth_migrations/versions/0005_shared_grants_t09.py`
- `tests/contracts/test_identity_contract.py`
- `tests/contracts/test_sharing_contract.py`
- `tests/e2e/sharing_t09_fixture.py`
- `tests/integration/auth/test_persistence.py`
- `tests/integration/authorization/test_http_dependencies.py`
- `tests/security/auth/test_postgresql.py`
- `tests/security/authorization/test_http_postgresql.py`
- `tests/security/authorization/test_postgresql.py`
- `tests/security/grants/conftest.py`
- `tests/security/grants/test_t09_adversarial.py`
- `tests/security/grants/test_t09_service.py`
- `tests/security/privacy/test_persistence.py`
