# T33 计划与进度工作台验收

2026-10-04源码与合成隔离验收完成；PRIVATE源码上传以后续实际Git核对为准，真实处理关闭。

## 基线与范围

PRIVATE T32 b90ad683990b8bd673fa1b7d50b9ae8f12f78b82，616tracked；codex/t33-plan-progress-workspace，初索引/工作区为空。开始前读取治理/原始两spec/docs01–05/API/DB/T32/T29/T24和相关模块/Git，冻结[契约](../plan_workspace.md)/ADR046；九旧允许/607其他tracked保护。只两旧Vue接缝、新前端/测试与治理，不改backend/API/DB/生成工件/依赖/旧迁移/原规格/旧验收。

## 实际检查

- `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/unit/plan_execution tests/contracts/test_t32_plans_generation.py -q --tb=short`：56 passed/9.64秒/exit0/1既有Starlettewarning，相关旧Python，不算新T33测试。首次误用tests/contracts/test_v2_plans.py导致exit1/no tests ran，rg纠正后执行真实路径。只读曾猜CatalogWorkspace.vue/draft_plans/models.py缺失，已读rg真实清单/CatalogView/plans/models，非应用测试。
- bundled Node24进程PATH下，fallback/pnpm.cmd `--dir apps/web exec vitest run tests/plansForm.test.ts tests/plansClient.test.ts tests/plansWorkspace.test.ts tests/PlanView.test.ts`：37 passed/4.31秒/exit0，无warning/skip；首35passed/2failed为真实mounted profile/context竞态及history未等WebCrypto测试前提，分别修源/修新test。
- cwd apps/web，bundled `node.exe node_modules/vitest/vitest.mjs run tests/plans-workspace-safety.test.ts --reporter=dot`：末79 passed/6.78秒/exit0，无warning/skip；前13为12/1（坏200误归网络，2.63秒），70为48/22（18独立fixture前提，3.29秒）、66/4（3.29秒），79为75/4（3.31秒）；四实际week/完成上界/零里程碑时刻/profile root关联缺口修后79/3.73秒，再以末source/privateScope代际源码复验79/6.78秒。重复不累计数量。无官方招生事实/真实学生fixture。
- `.cache\run-web-checks.ps1 -TaskId T33`：完整590 passed/37files/20.28秒/exit0（474旧＋116新增）；Type Check `scripts/web.ps1 -Action typecheck` exit0；demo/auth `pnpm --dir apps/web run build --outDir ../../.cache/t33-<mode>-frontend-validation`均exit0，Vite1.38/1.76秒/112modules，finalAuthView-CH-Qa0DN.js。早期独立Type0及auth1.78秒也实际执行，但包含尚未修mount竞态，不冒充最终版。Vite outDir在项目外不清空提示为隔离.cache产物行为，非错误；没有Lint入口。
- 八profile `scripts/generate_contracts.py --profile <foundation|identity|public_catalog|admin|admin_review|profiles|assessments|plans> --check`全部exit0；`scripts/verify_originals.py`exit0/两原文未变；`scripts/verify_contract.py`exit0/M0契约一致。中途保护607tracked未变、索引仍空，最终范围/历史/链接/实际cached/private检查另核。

## 真实 PostgreSQL 与 Edge

完整实际调用各轮同为：

```powershell
& '.\.cache\t23-postgres\run-tests.ps1' -PytestArguments @('tests/integration/plans_ui','-q','--tb=short','-s')
```

独立study_t23_20261003/127.0.0.1:55438，plans_ui_t33_UUID随机自有schema，实际十三级旧链与T32、owned teardown。旧T29 Origin透明桥接只读复用，真实Edge→HTTP→ASGI→PG，无API mock/商业API/外网；cookie只stdin、安全env不带DSN/provider，输出检查无cookie。fixture只合成profile/资料/规则，初六计划/评估表为空，实际Catalog eval/history明确交接创建与执行。

首1failed/120.08秒/1既有Starlettewarning：旧build真实profile/context初始化竞态，Catalog eval/history/context均200，但目标不显示，0page error/0外网；组件回归真实捕获后修复，不弱化断言。第二finalbuild：1passed/156.02秒/同warning/exit0，Edge154.0.4258.53，15检查点仍1distinctpytest；5public请求均不带cookie，0page error/0外网。第三轮只补聚焦截图，业务源/断言/build不变：1 passed/155.96秒/1同既有Starlettewarning/exit0；原15检查点仍1distinct pytest，不重复累计。只新增局部截图及退出viewport，实际业务源/断言/最终authbuild未改。

15检查点包括actual history读取同画像→选择目标、0/null/weekly0、6小数UTC/IANA、真实外部CAS→409保留local/显式reload、不自动retry、双确认未知期限、依赖/CSRF拒绝、零里程碑也手工完成、原key确认重放和originalCAS完成重放显示currentprogress、readonly state1独立、keyboard/390px、三真实成功GET200延迟跨actor/core撤回/logout无复活，Bfacts-only unknown只VERIFY_UNKNOWN。不是过期来源当前资格或官方精确deadline正例。实际A只1confirmation/2unique student_declared completion、state_version9，T30root/registryversion仍1。

## 图片人工核与未执行

首整页mobile390×20725被查看工具缩到39×2048，无法读字，没有伪称人工通过；因此补局部截图并复验同节点。Root通过view_image实际查看最新cache的plans-mobile-current.png、plans-desktop-current.png、plans-cas-conflict-focused.png、plans-cleared.png：390px当前确认/来源SHA/六位UTC、constraints_complete=false/年度缺失、student_declared完成时间与状态v8/v9、0/0.2只读保留和明确reload、退出无私有计划均可读，无重叠/截断。截图仅合成资料，不上传Git。

Lint和Python静态Type Check无配置入口，未执行；前端Type Check实际已执行。官方精确deadline正例（T12仍未知）、真实规则审核/全国覆盖、真实身份/未成年核验/法律/SQL登录角色GRANT_RLS/代理HTTPS/公众部署/生产备份恢复未执行，不宣称全部生产检查通过。

忽略目录finalize_t33辅助脚本首次纯语法检查exit1（多一个右括号，未执行/未改项目），修后compile exit0；正式执行与范围校验独立记录。

## 已知问题

浏览器ICU与服务端tzdata2026.4差异时可保守bad200，IANA仅展示一致性校验，不改原UTC提交。PlanAssessmentRef没有entry_year，界面明确此引用未提供年度；不从设备或模型补年度。草案到期取来源评估记录期限最小值，不代替证据/规则当前证明；每次操作fresh重验。官方期限仍未核验，真实处理关闭。既有Starlettewarning/隔离outDir提示保留。

## 修改文件

- `AGENTS.md`
- `README.md`
- `apps/web/src/features/auth/AuthView.vue`
- `apps/web/src/features/plans/PlanSchedule.vue`
- `apps/web/src/features/plans/PlanTaskList.vue`
- `apps/web/src/features/plans/PlanWorkspaceForm.vue`
- `apps/web/src/features/plans/client.ts`
- `apps/web/src/features/plans/form.ts`
- `apps/web/src/features/plans/presentation.ts`
- `apps/web/src/features/plans/usePlans.ts`
- `apps/web/src/features/plans/validation.ts`
- `apps/web/src/views/CatalogView.vue`
- `apps/web/src/views/PlanView.vue`
- `apps/web/tests/PlanView.test.ts`
- `apps/web/tests/plans-workspace-safety.test.ts`
- `apps/web/tests/plansClient.test.ts`
- `apps/web/tests/plansFixtures.ts`
- `apps/web/tests/plansForm.test.ts`
- `apps/web/tests/plansWorkspace.test.ts`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T33_plan_workspace.md`
- `docs/architecture.md`
- `docs/plan_workspace.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `scripts/plans_t33_browser_smoke.mjs`
- `tests/integration/plans_ui/conftest.py`
- `tests/integration/plans_ui/test_t33_browser.py`
