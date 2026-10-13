# T24 画像编辑与确认页面验收

2026-10-03源码与合成离线/隔离PostgreSQL验收完成。实施前[冻结契约](../profile_workspace.md)；以下保留分轮实际记录，最终结论见末尾。不开放真实处理、规则评估或部署。

基线PRIVATE T23 `f901ab2e406d42e93fec23f28df6a814fb6d6765`，481tracked/工作区和索引空，新codex/t24-profile-confirmation-ui。读取治理/原两规格/T24卡/相关Auth/Privacy/T23/M0代码与文档后，只前端及本Task合成浏览器桥接。无后端业务/迁移/API/生成/依赖改变。

前置只读实际检查owned `study_t23_20261003`（127.0.0.1:55438）使用transaction_read_only=on，URL只内部parse ignored配置、无凭据输出：custom_schemas=0、public_tables=0、other_database_sessions=0、profiles_t23_% schemas=0，exit0。这为T24前置，不改写已保存T23历史。浏览器将复用自有PG隔离随机schema并在case后清理；无真实账号/学生/外网模型。

## 检查记录

本Task已实际执行两条相关回归：`.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/unit/profiles','tests/integration/profiles','-q','--tb=short')`：99 passed、1既有warning、75.35s、exit0，无skip；`.venv/Scripts/python.exe -B -m pytest tests/contracts tests/security/test_mode_isolation.py -q --tb=short`：411 passed、1既有warning、31.89s、exit0。旧后端/契约原字节保持。应用首版Type Check已实际exit0、5.60s（新tests尚未齐）；为浏览器单独执行auth准备build `pnpm --dir apps/web exec vite build --outDir ../../.cache/t24-auth-frontend-validation`，exit0、3.34s壁钟/Vite1.40s，73modules。它不含最后测试Type Check，不替代最终完整构建。尚未完成T24新UI专项、实际浏览器或完整前端验收，不引用T23历史通过当本Task结果。Lint与Python静态类型无入口，真实身份/法律/生产权限/清理恢复/部署未执行。

浏览器首两轮实际相同命令 `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/profiles_ui','-q','--tb=short','-s')` 分别1 failed/34.34s、1 failed/34.65s，均1既有warning；新driver等待错年龄声明路径，UI实际请求已200而等待30秒超时。先误改仍含privacy前缀，再逐行核既有client/router更正为`/v2/me/age-declarations`、`/v2/me/consents`，未修改业务/API。失败cache分别`.cache/t24-ui/a4bb9976-de0b-4f02-9970-054ac3968dec`及`92c1d42f-8e13-4384-8b16-55a025592d01`，report保留ignored。

新前端专项实际 `pnpm exec vitest run tests/profiles-form.test.ts tests/profiles-client.test.ts tests/profiles-state.test.ts tests/profiles-view.test.ts`：69 passed/4文件/5.02s（17表单、25client、16状态、11组件），随后 `pnpm exec vue-tsc --noEmit` exit0，无诊断。完整前端回归与最终双构建仍待执行。

同一实际浏览器命令第三轮1 failed/602.58s，Node总超时600s且无最终report；第四轮1 failed/291.20s，核对唯一自有Node PID15744及完整harness命令后主动终止，无最终report，不算通过。PG只读定位已提交1root/3versions，连接idle、无数据库锁等待；安全进度记录前五项流程已执行，但尚不能判断卡在external响应还是原page冲突，不能作为完整验收。已为新driver补逐阶段安全progress及Node侧有界超时，业务/准备构建保持，继续定位。

第五轮同命令1 failed/28.66s、1既有warning，精确定位原UI已收到409、正常截图显示冲突与保留草稿，无pageerror/外网；卡在Playwright读取UI未消费的错误response body。新的client非200立即抛固定status错误，故driver不再等待该body；仍验真实status/requestID/header/Origin/CSRF及全部CAS草稿、撤销确认、无自动重试断言，200成功仍严格DTO/hash/版本绑定，未改变业务。失败report与截图保留`.cache/t24-ui/b2efb841-5a73-41d6-87d8-93ce834a5137`，root实际查看截图。

最终完整前端实际 `scripts/web.ps1 -Action test`：348 passed/28文件/16.11s；`scripts/web.ps1 -Action typecheck` exit0，无诊断。bundled Node PATH临时恢复；`VITE_APP_MODE=demo pnpm --dir apps/web run build --outDir ../../.cache/t24-demo-frontend-validation` exit0/73modules/Vite1.15s（含vue-tsc），无源码变更。auth最终build及实际浏览器尚待完成，以上不代替它们。

## 最终验收

第六轮实际同browser命令1 failed/17.32s、1既有warning，11流程已执行但最后delay控制未进入真正GET，response_status=null。新root写响应先于客户端hash验证/渲染，修正driver先等待真实current UUID，再以Node侧有界轮询严格blocked=true/response_status=200，未改业务或放宽“成功GET已执行后才退出”条件。

第七轮最终同命令：**1 passed、1既有Starlettewarning、16.15s、exit0**。Edge154.0.4258.53、12meaningful checks；真实UI准入/完整创建/独立预测实得/清空非零/历史/双context并发CAS409/未知与HKDSE/390px键盘/撤回/重新同意不复活/明确新root/已成功GET延迟后退出。最终DB断言2root/7version（原6不可变+新root1）、同owner/synthetic、新旧consent不同、session revoked；无IdP请求、外网、pageerror或local/sessionStorage。报告及4截图保留ignored `.cache/t24-ui/953aad3e-63e6-4e53-bc68-9e5ead5a5be8`；root与backend均实际查看desktop/mobile/CAS/logout截图，布局与清理未见阻断。前六失败不算通过。

最终auth build为独立新输出目录，未重写browser冻结准备build：`VITE_APP_MODE=auth pnpm --dir apps/web run build --outDir ../../.cache/t24-auth-final-validation`，exit0/73modules/Vite1.41s，含vue-tsc。8个实际应用source SHA与准备build快照一致；最终同名AuthView JS/CSS内容一致。两次完整build均无新增依赖。

| 实际检查 | 最终结果 |
| --- | --- |
| `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/unit/profiles','tests/integration/profiles','-q','--tb=short')` | 99 passed，75.35s，1既有warning，exit0，无skip |
| `.venv/Scripts/python.exe -B -m pytest tests/contracts tests/security/test_mode_isolation.py -q --tb=short` | 411 passed，31.89s，1既有warning，exit0 |
| `pnpm exec vitest run tests/profiles-form.test.ts tests/profiles-client.test.ts tests/profiles-state.test.ts tests/profiles-view.test.ts` | 69 passed/4 files，5.02s，包含在348完整前端中 |
| `scripts/web.ps1 -Action test` / `scripts/web.ps1 -Action typecheck` | 348 passed/28 files，16.11s；typecheck exit0，无诊断 |
| `VITE_APP_MODE=demo pnpm --dir apps/web run build --outDir ../../.cache/t24-demo-frontend-validation` / 上述auth最终build | 两项exit0，Vite1.15s/1.41s，均含vue-tsc；PATH与mode恢复 |
| `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/profiles_ui','-q','--tb=short','-s')` | 最终1 passed/12实际Edge checks/16.15s；前6失败逐轮保留 |
| `.venv/Scripts/python.exe -B scripts/generate_contracts.py --profile <foundation/identity/public_catalog/admin/admin_review/profiles> --check` | 六个独立实际命令exit0，生成未改 |
| `.venv/Scripts/python.exe -B scripts/verify_originals.py` / `scripts/verify_contract.py` | 两项exit0，原始两规格/旧M0契约保持 |
| bundled `node --check scripts/profiles_t24_browser_smoke.mjs`、两Python模块内存compile | exit0；不生成缓存产物 |
| 自有T23专库/精确driver进程只读残留检查 | profiles_t23_* schema=0、其他DB连接=0、driver Node进程=0；未停其他用户进程/PG |

Lint/Python静态Type Check无配置入口，**未执行**；全项目PostgreSQL回归未执行（只前端及新harness，相关99+browser已运行，旧后端原字节保护）；真实Keycloak/MFA/恢复、真实学生/资料、正式隐私主体告知/法律适用性、生产GRANT/RLS、物理清理/备份恢复、业务部署**未执行**。生成与Type Check不冒充真实服务验收。

## 变更文件与结论

25路径（9旧/16新），472其他tracked冻结保护，66其他Task卡及旧日志/ADR保留。无API/数据库/迁移/依赖变化，对应文档无需变更。前端实际源码与契约一致；CHANGELOG/tasks同步，T24标完成，成功PRIVATE普通保存及SHA核对后才下一T25；完成T40后停止。

- `AGENTS.md`
- `README.md`
- `apps/web/src/features/auth/AuthView.vue`
- `apps/web/src/features/privacy/PrivacyPanel.vue`
- `apps/web/src/features/profiles/ProfileForm.vue`
- `apps/web/src/features/profiles/ProfileVersionSummary.vue`
- `apps/web/src/features/profiles/client.ts`
- `apps/web/src/features/profiles/form.ts`
- `apps/web/src/features/profiles/useProfiles.ts`
- `apps/web/src/views/ProfileView.vue`
- `apps/web/tests/profiles-client.test.ts`
- `apps/web/tests/profiles-form.test.ts`
- `apps/web/tests/profiles-state.test.ts`
- `apps/web/tests/profiles-view.test.ts`
- `apps/web/tests/profilesFixtures.ts`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T24_profile_workspace.md`
- `docs/architecture.md`
- `docs/profile_workspace.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `scripts/profiles_t24_browser_smoke.mjs`
- `tests/integration/profiles_ui/conftest.py`
- `tests/integration/profiles_ui/test_t24_browser.py`
