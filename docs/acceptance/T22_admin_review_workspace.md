# T22 审核与发布工作台验收

2026-10-03，源码与合成离线/隔离实库验收完成；正式处理/发布关闭。

基线PRIVATE T21 ed4defaf786b6798acd3a875add8adcdc638e6cf/远程一致/clean/index空、425tracked；codex/t22-review-release-admin；只T22，其他66任务卡冻结。[代码前范围/契约/用例](../admin_review_workspace.md)。

必读当前治理/相关审核发布/证据事实与原两份规格，原两文SHA保持；无用户已有修改。复用自有127.0.0.1:55438 PG16.15；显式新建隔离study_t22_20261003，保留旧库/全部环境变量，脚本退出恢复进程env，秘密不输出/提交。

准备检查：旧四profile `scripts/generate_contracts.py --profile foundation/identity/public_catalog/admin --check`逐一exit0，`scripts/verify_originals.py`两文件不改。生成器初次相关回归368 passed/1既有warning/18.45s；这是中间结果，末源码验收另记录，不冒称已覆盖T22。

## 实现与边界

独立`admin_review` profile增加14项有界操作；来源/原候选发现后由人工分别准备文档、版本、片段与类型化事实，复用T16–T19事务。角色、owner和当前权限不取客户端参数；十项审核及所有冲突选择没有默认勾选，自审拒绝，CAS不覆盖并发决定。预检不写release/receipt且不构成永久授权，提交重验；相同有效载荷可用同key回放，变化必须重新确认。撤回无需恢复已失效的旧来源正许可。

`/public/v2`复用T20匿名reader，UI请求不带Cookie，读取当前release；替代/撤回立即反映公共结果。原文只显示有界且已核对的片段，Vue转义文本；不返回源文件全部字节或存储路径。真实模块默认关闭、正向仅显式合成test_fixture。无新表/迁移/依赖；M0、旧服务及四个旧生成profile保持。

## 已执行检查

命令均在`D:\Projects\study`执行；`.cache`中的helper仅准备本次隔离环境，不提交秘密、数据库或构建产物。

| 实际命令 | 结果 |
| --- | --- |
| `.venv/Scripts/python.exe -X utf8 scripts/generate_contracts.py --profile admin_review` | exit0；新OpenAPI/TS生成；随后新生成专项15 passed，5.63s |
| `.venv/Scripts/python.exe -X utf8 -m pytest tests/contracts tests/security/test_mode_isolation.py -q --tb=short` | 383 passed，23.48s，exit0；1条既有Starlette warning。包含新生成专项，不再重复计数 |
| `.venv/Scripts/python.exe -m pytest tests/unit/admin_review_http -q --tb=short` | 13 passed，1.33s，exit0；1条既有warning |
| `.cache/t22-postgres/run-tests.ps1 -PytestArguments @('tests/integration/admin_review_http/test_t22_facade.py','-q','--tb=short')` | 最终8 passed，91.38s，exit0，无skip；包含实际数据库等待后源/冲突文件到期、准备分页失效、现有date证据、策略关闭、自审与审核CAS、延迟COMMIT约束失败整体回滚 |
| `.cache/t22-postgres/run-tests.ps1 -PytestArguments @('tests/unit/reviews','tests/unit/releases','tests/integration/reviews','tests/integration/releases','-q','--tb=short')` | 100 passed（55纯/45PG），486.09s，exit0，无skip；旧审核/发布回归未改 |
| bundled `pnpm --dir apps/web test`指定六个新增测试文件 | 首次56 passed/6 files，4.35s，exit0 |
| `.\scripts\web.ps1 -Action typecheck` | 首次exit0，4.70s |
| `.cache/run-web-checks.ps1 -TaskId T22` | 首完整回归277 passed/1 failed；既有AuthView匿名页“无input”断言与新公共年度输入不兼容。退出1，后续Type Check/两Build该轮未运行，不能计通过；修复后结果另记 |
| 同一完整前端命令，兼容修复后 | 最终279 passed/24 files，13.22s；Vue Type Check exit0，demo/auth Build分别exit0（Vite1.06s/1.25s），整体exit0。构建只写ignored缓存，环境退出恢复 |
| bundled `pnpm --dir apps/web run build --outDir ../../.cache/t22-auth-frontend-validation`，`VITE_APP_MODE=auth` | 首次exit0，61 modules；环境变量与PATH退出恢复 |
| `.cache/t22-postgres/run-tests.ps1 -PytestArguments @('tests/integration/admin_review_http/test_t22_browser.py','-q','--tb=short','-s')` | 首次1 passed，60.10s，exit0；Edge154.0.4258.48内13项检查（只计1个PG用例）；应用兼容修复后须重跑 |
| 同一浏览器命令，最终auth构建重验 | 最终1 passed，49.84s，exit0；1条既有warning；仍13项内部检查，不将两轮当两个不同用例累加。6次公共请求无Cookie，0页面错误/外部请求；初始无input且展开入口可发现 |
| 五个profile逐一`generate_contracts.py --profile <profile> --check`；`scripts/verify_contract.py`；`scripts/verify_originals.py` | 全部exit0；M0契约一致、两份原规格未变 |

第一次PG运行前代码审查纠正了本Task新草稿误用不存在的date时间字段、原候选locator缺失与已定位证据混淆、RFC3339偏移归一和前端rows exact-key；这些在执行测试前修正，不编造失败测试轮次。后端首次纯/PG执行没有失败，6用例中间轮随后扩展为上述8用例。

完整前端失败后仅修改本Task新增公共预览及新测试：初始入口可发现，明确展开才出现年度输入，收起取消请求/清结果防陈旧响应。旧AuthView测试保持原字节。修复后的专项62 passed/7 files，5.08s；修补新mock时首次Type Check因未声明参数导致Tuple类型错误退出1，已按接口Parameters显式声明，随后Type Check exit0（5.14s），最终完整命令亦exit0。未隐藏或改写历史失败。

实际浏览器从空候选库开始，两合成管理员Cookie只通过stdin给驱动；HTTP自行发现所有row/evidence/fact/decision/release ID。执行自审拒绝、缺证据拒绝、并发CAS、十项未选、确认清除、幂等回放、替代和撤回。最终数据库2个release状态分别replaced/withdrawn，4个ChangeEvent及4个pending outbox；失败操作不新增记录。首次截图已检查桌面和390px窄屏，无溢出、原文XSS按字面显示；0页面错误/0外部请求，6次公共请求无Cookie。截图/报告在`.cache/t22-ui/07954165-583c-437c-aeaa-642bab172806`，不提交。

最终截图/报告在`.cache/t22-ui/bfe3c00c-3024-4932-9d03-a194adeaee09`；已实际查看桌面、公共当前和390px三张图，展开/收起可发现、窄屏无横向溢出。原文仍按字面转义，替代后新release、撤回后空目录实测一致。截图不纳入Git。

`.venv/Scripts/python.exe -X utf8 .cache/check_task.py T22` exit0：44必要路径/12旧32新、413范围外tracked哈希、其他66任务卡、全部旧CHANGELOG/ADR历史保持；328本地文档链接、11 Python文件内存编译、清单/秘密形态检查通过。全部旧contracts字节不变，新admin_review产物LF；`git diff --check`和新Node脚本`--check`退出0。当前Task与CHANGELOG/受影响文档状态一致。只暂存已审44路径，推送前仍核实PRIVATE origin/分支，普通推送后核对SHA及干净状态；不把源码保存等同部署。

## 未执行及剩余边界

Lint、Python静态Type Check未执行：项目尚无对应入口/工具配置；不新增无关依赖。全项目PG、真实Keycloak/MFA/恢复、自然人多账号关系、正式来源使用权/法律/责任、SQL GRANT/RLS、物理清理/备份恢复、生产TLS与部署未执行，超出本Task且默认门槛未解除。离线/合成通过不代表已审核真实招生资料或允许真实公众发布。

日期编辑/自动抽取/PDF准备不在T22；没有适用已准备T12日期的候选继续draft/缺口，不自动发明日期。全国2026/各省/英国2027及剑桥、曼彻斯特仍只是覆盖目标；facts-only release没有已编译规则，`ruleset_version=null`。Outbox仍pending，无消费者。最终浏览器重验通过，治理和暂存清单检查通过后按持续授权私有保存；只有远程SHA与干净状态核对后才进入T23。

## 变更清单

44路径（12旧/32新）；只包含本Task代码、测试、生成契约与文档，无缓存、数据库、密钥或构建产物。

- `.gitattributes`
- `AGENTS.md`
- `README.md`
- `apps/web/src/features/admin/preparation/PreparationPanel.vue`
- `apps/web/src/features/admin/preparation/usePreparation.ts`
- `apps/web/src/features/admin/releases/PublicReleasePreview.vue`
- `apps/web/src/features/admin/releases/ReleasePanel.vue`
- `apps/web/src/features/admin/releases/publicClient.ts`
- `apps/web/src/features/admin/releases/useRelease.ts`
- `apps/web/src/features/admin/reviews/ReviewPanel.vue`
- `apps/web/src/features/admin/reviews/client.ts`
- `apps/web/src/features/admin/reviews/useReview.ts`
- `apps/web/src/features/auth/AuthView.vue`
- `apps/web/src/views/admin/ReviewReleaseView.vue`
- `apps/web/tests/preparation-state.test.ts`
- `apps/web/tests/public-release-preview.test.ts`
- `apps/web/tests/release-state.test.ts`
- `apps/web/tests/review-release-view.test.ts`
- `apps/web/tests/review-state.test.ts`
- `apps/web/tests/review-workspace-client.test.ts`
- `apps/web/tests/reviewReleaseFixtures.ts`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T22_admin_review_workspace.md`
- `docs/admin_review_workspace.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `packages/contracts/v2/admin_review/generated.ts`
- `packages/contracts/v2/admin_review/openapi.json`
- `scripts/admin_t22_browser_smoke.mjs`
- `scripts/generate_contracts.py`
- `services/api/app/admin/review_http/__init__.py`
- `services/api/app/admin/review_http/facade.py`
- `services/api/app/admin/review_http/router.py`
- `services/api/app/admin/review_http/schemas.py`
- `services/api/app/api/admin_review.py`
- `tests/contracts/test_t22_admin_review_generation.py`
- `tests/integration/admin_review_http/conftest.py`
- `tests/integration/admin_review_http/test_t22_browser.py`
- `tests/integration/admin_review_http/test_t22_facade.py`
- `tests/unit/admin_review_http/test_t22_contracts.py`
