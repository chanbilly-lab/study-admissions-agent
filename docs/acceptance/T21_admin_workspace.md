# T21 来源与导入管理页面验收

2026-10-03，Asia/Hong_Kong。源码及合成隔离验收完成，真实处理关闭。

开始基线：clean/index空，codex/t20-public-catalog，HEAD77d473187438c557f11388712fcd6b93f497aab0；401 tracked。工作分支codex/t21-source-import-admin。用户授权逐Task至T40，每项验收、文档同步、私有保存后继续；不部署。

实施前契约/范围/测试：[admin_workspace](../admin_workspace.md)。独立admin profile复用16身份路径，增加6管理路径/7操作。所有管理操作即时验证强data_admin、来源责任、CSRF及当前期限；URL只显示文字、不会抓取。来源CAS、上传和导入分别确认；导入失败零候选，staged明确未审未发布。生成契约只有显式白名单body/header，无任意any。

首次HTTP暴露涉及T15一个必要局部修复：T49调用与最终源/文件/身份期限验证位于同一自有事务，最后SQL等待后使用新时钟再检查，失败回滚候选和回执；同hash不同原资产亦检查。无新依赖、迁移或旧profile改变。六个旧生成产物字节与基线一致。

## 实际命令与结果

| 命令 | 最终实际结果 |
| --- | --- |
| `.venv/Scripts/python.exe -X utf8 -m pytest tests/contracts tests/security/test_mode_isolation.py -q --tb=short` | 368 passed、1既有Starlette warning、19.14s、exit0 |
| `.venv/Scripts/python.exe -B -m pytest tests/unit/admin_http -q --tb=short` | 9 passed、1既有warning、2.17s、exit0 |
| `.cache/t21-postgres/run-tests.ps1 -PytestArguments @('tests/integration/admin_http/test_t21_facade.py','-q','--tb=short')` | 7 passed、1既有warning、24.36s、exit0；含三实际PG等待/时效/回滚用例 |
| `.cache/t21-postgres/run-tests.ps1 -PytestArguments @('tests/unit/ingestion','tests/integration/imports','-q','--tb=short')` | 最终T15补丁后65 passed（46pure/19PG）、85.68s、exit0 |
| `.cache/run-web-checks.ps1 -TaskId T21` | `scripts/web.ps1 -Action test`：222 passed/18files、11.42s；`-Action typecheck`：exit0；pnpm build两轮VITE_APP_MODE=demo/auth到隔离cache：均exit0；环境恢复 |
| `.cache/t21-postgres/run-tests.ps1 -PytestArguments @('tests/integration/admin_http/test_t21_browser.py','-q','--tb=short','-s')` | 1 passed、1既有warning、12.02s、exit0、无skip；1用例内9个Edge检查，不称9个pytest |
| `.venv/Scripts/python.exe -X utf8 scripts/generate_contracts.py --profile admin`及`pytest tests/contracts/test_t21_admin_generation.py -q --tb=short` | 生成exit0；11 passed/3.66s，已包含于368，不相加 |
| `scripts/generate_contracts.py --profile foundation/identity/public_catalog/admin --check`（逐profile） | 四个exit0 |
| `scripts/verify_contract.py`、`scripts/verify_originals.py`、`git diff --check` | exit0；原两份输入未改变；LF属性仅精确增加新admin产物 |
| Python模块内存编译、Node `--check scripts/admin_t21_browser_smoke.mjs` | exit0；不是Lint或Python静态类型检查 |

上述全部离线/localhost，合成身份、隔离PG，未用真实学生或API密钥。Edge154.0.4258.48通过实际ASGI接口/真实PG服务，无API路由mock。检查学生403、键盘登记、恶意URL作为文字、BOM JSON原样422、CRLF错误拒绝/零候选、三行staged、幂等回放/无CSRF403、桌面及390px、撤角色后清旧回执。页面错误0、外部请求0、浏览器local/sessionStorage空。测试结束SQL核对1source/1version/2files/2batches/3candidates及原hash/责任绑定；source_quarantine owner为NULL，责任来自source version。

桌面和窄屏图片由独立agent实际查看，无溢出/重叠，合成与未审提示明确。图及报告仅忽略cache，不提交用户附件或浏览器cookie。

## 失败和准备问题

首次四个纯PG基础用例通过；增加等待测试时4pass/2fail：测试event listener提前移除导致deque变化，harness修正后最终7通过。契约首次两次生成exit1分别因幂等header未白名单和schema UUID格式缺失；显式补齐后通过，未部分覆盖旧产物。前端首typecheck五个新mock类型错误，修正vi.mocked后通过。

浏览器首1failed/7.74s因Playwright cookie参数组合，测试改明确domain/path、secure仍true；第二1failed/12.27s，九浏览器检查已通过但PG断言误认为source file有owner，修正为旧T14实际NULL并核对来源责任；最终1通过。应用Origin/Cookie/CSRF边界未为测试放松。BOM JSON由既有T14拒绝，不把“传输原字节”误称“解析接受BOM”。

隔离PostgreSQL16.15复启首次遗漏原port参数监听5432，已停止确切自有实例并用-p55438/-h127.0.0.1重启，未修改用户Docker/其他库。首次库准备连接失败不计测试；随后独立study_t21_20261003准备完成，URL秘密不输出或提交。

## 未执行及已知限制

Lint未执行：Python/前端没有配置入口。Python静态类型未执行：无配置入口；TS Type Check已实际执行。全项目PG回归未执行：执行当前HTTP、相关T15及契约/前端回归。真实Keycloak登录/MFA/恢复、真实来源/许可/人工审核、真实学生、法律责任、生产SQL GRANT/RLS、物理清理/备份/TLS/部署未执行：本任务仅合成及隔离环境，对应门槛未解除。

上传限同步JSON/CSV净1MiB（wire有界转义预算），PDF/后台导入另Task；默认源/存储/导入能力关闭。source/upload网络结果未知不自动重试；幂等导入只重放相同确认payload，版本变化须重确认。T22审核/发布尚未开始。当前没有新增应用阻断问题；产品覆盖目标（ADR-034）不代表规则/资料已经覆盖。

## 变更清单与保护

37路径，13旧/24新；388范围外tracked和其他66任务卡保护；原规格、docs01–05、旧迁移/fixture与旧验收不改。CHANGELOG/tasks/ADR033/ADR034及受影响当前文档同步。私有提交推送之后核对本地/远程SHA，Git命令日志保留忽略cache；提交不是部署。

- `.gitattributes`
- `AGENTS.md`
- `README.md`
- `apps/web/src/features/admin/client.ts`
- `apps/web/src/features/admin/imports/ImportPanel.vue`
- `apps/web/src/features/admin/sources/SourceForm.vue`
- `apps/web/src/features/admin/useAdmin.ts`
- `apps/web/src/features/auth/AuthView.vue`
- `apps/web/src/views/admin/AdminView.vue`
- `apps/web/tests/admin-client.test.ts`
- `apps/web/tests/admin-state.test.ts`
- `apps/web/tests/admin-view.test.ts`
- `apps/web/tests/adminFixtures.ts`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T21_admin_workspace.md`
- `docs/admin_workspace.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `packages/contracts/v2/admin/generated.ts`
- `packages/contracts/v2/admin/openapi.json`
- `scripts/admin_t21_browser_smoke.mjs`
- `scripts/generate_contracts.py`
- `services/api/app/admin/http/__init__.py`
- `services/api/app/admin/http/facade.py`
- `services/api/app/admin/http/router.py`
- `services/api/app/admin/http/schemas.py`
- `services/api/app/admin/imports/service.py`
- `services/api/app/api/admin.py`
- `tests/contracts/test_t21_admin_generation.py`
- `tests/integration/admin_http/conftest.py`
- `tests/integration/admin_http/test_t21_browser.py`
- `tests/integration/admin_http/test_t21_facade.py`
- `tests/unit/admin_http/test_t21_contract.py`
