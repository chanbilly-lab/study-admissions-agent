# T28 四态评估与重放验收

2026-10-03源码及合成隔离验收完成；本文件保留实际中间失败与最终检查。源码PRIVATE保存另以Git实际SHA核对，不把文档当上传证据。

## 基线与实施前契约

起点PRIVATE T27 `0f61760955f32d4822e637ec22ef41de23f17a97`，524 tracked、工作区/索引空；新分支`codex/t28-eligibility-assessments`。必读治理、原两份规格及画像/规则/范围/后补/发布/公共证明/授权/幂等/API/数据库代码文档核对后先冻结[契约](../assessments.md)与ADR-041。基线/读取哈希保存在忽略缓存，不作为招生原文哈希。只T28，不同时T29。

真实规则发布链尚不存在：T19 ruleset_version=null、T26/T27 real开关关闭。本Task实际PG合成规则绑定不表示正式领域审核或2027专业覆盖；正式处理、未成年私有、模型live和部署保持关闭。无新依赖，不改旧迁移/旧六生成产物/原文/M0。

## 已执行检查

- 根实际 `.venv/Scripts/python.exe -X utf8 -B scripts/generate_contracts.py --profile profiles --check`：exit0，修改生成器后旧profile字节保持。
- 本轮另实际六个profile分别执行同Python flags `scripts/generate_contracts.py --profile foundation|identity|public_catalog|admin|admin_review|profiles --check`：全部exit0；`scripts/verify_originals.py`两原文UNCHANGED、`scripts/verify_contract.py`M0 PASS，各exit0。
- 本轮内存哈希守卫：513个范围外旧tracked字节保持；`git diff --check`exit0（生成脚本受既有autocrlf提示，不是测试warning/失败）。
- 根实际 `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/unit/dates tests/unit/evidence tests/unit/rules tests/unit/adapters tests/unit/catalog tests/unit/profiles tests/contracts/test_t23_profiles_generation.py tests/security/test_mode_isolation.py -q --tb=short`：**764 passed/21.07s/exit0**，1既有Starlette TestClient弃用warning，无skip。这是既有相关层，不计成T28新增检查。

查找时曾用不存在的rules/schemas.py及tests/backend profile路径，已纠正到expression.py和tests/contracts；只读路径查找失败不当作应用测试，也不隐瞒为通过。

## 中间待执行项（后文记录最终结果）

新增完整四态/独立金标准、实际PG迁移/同事务证明/重放/权限/HTTP/最终等待；新profile生成与TS负例、相关回归、前端Unit/Type Check/两模式Build、原文/M0/文档治理和实际暂存diff/PRIVATEpushSHA。

Lint/Python静态类型没有已配置入口，标未执行；正式身份、真实学生、全国/英国规则领域审核、法律适用性、SQL GRANT/RLS、生产清理/备份/部署未执行，不宣称全部通过。

## 新契约与纯引擎中间检查

新profile实际generate exit0；根首`pytest tests/contracts/test_t28_assessments_generation.py -q --tb=short`：9 passed/2 failed/4.51s，1既有warning，新const1超旧M0 parser子集。只在新test局部增加精确1字面及bool/float负例，旧parser不改；复验12 passed/4.04s/exit0、1既有warning。随后追加replay必需body负例，待最终复验，不将12当新版本最终结果。

根`pytest tests/unit/eligibility -q --tb=short`（同UTF8/B flags）：104 passed/8.76s/exit0、无warning/skip；实现者29/0.41s、独立75/9.65s最后复验，首75/8.12s为中间，不累计重复次数。

根`.cache/run-web-checks.ps1 -TaskId T28`首：Vitest348 passed/28files/37.07s；vue-tsc exit2，3项新compile-only断言失败（两个新默认字段生成optional、两个路径interface union匿名Equal问题）。双Build因脚本停止而本轮未执行。新DTO必需字段与新路径断言将精确修正后复验，不以历史Build冒称本轮。

## 当前契约及前端复验

补必需replay body白名单、两个新DTO必需字段和分开路径类型断言后，根实际generate assessments exit0，`pytest tests/contracts/test_t28_assessments_generation.py -q --tb=short`同flags：13 passed/4.28s/exit0、1既有Starlette warning。新测试局部只扩精确1字面，旧M0 verifier保持原字节。

根实际`.cache/t28-types-build.ps1`：暂时Node24 PATH，`scripts/web.ps1 -Action typecheck`exit0；pnpm11.19 `--dir apps/web run build --outDir ../../.cache/t28-demo-frontend-validation`及auth对应目录exit0，Vite1.73s/1.44s、73modules；两模式VITE_APP_MODE及PATH恢复。Vitest仍以上实际348/37.07s，本次未无理由重复运行；缓存产物不提交。

## 相关实库命令记录

根首次`.cache/t23-postgres/run-tests.ps1 -PytestArguments @(tests/integration/profiles/test_t23_http.py,tests/integration/profiles/test_t23_service.py,tests/integration/public_catalog/test_t20_reader.py,-q,--tb=short)`退出1：no tests ran，末项路径不存在。随后先rg核对并改成实际`tests/integration/public_catalog/test_t20_public_catalog.py`运行；结果待完成记录。这不是应用断言失败，也不将首轮称执行通过。专库仅loopback55438/study_t23_20261003及随机schema，凭据未输出/提交。

根相关正确命令最终：63 passed/363.48s/exit0，1既有Starlettewarning、无skip；这63是旧profileHTTP/service/public_catalog回归，不计成新增T28PG。

## 新实库失败轮次（保留）

实现者实际helper `tests/integration/eligibility/test_t28_service.py::test_actual_published_binding_is_persisted_and_replays_minimal_original_context -q --tb=short` 首及两次定位各1 failed，13.27/17.02/15.76s；只输出固定cause类型/loc无input，底层为本新service向T26错传bundles参数，修成最小provider closure，旧T26不改。

实现者首完整 `test_t28_service.py`：8 failed/136.80s/1既有Starlettewarning，resultSHA在UTC isoformat+00:00与DTO json Z之间不一致；该进程已加载旧代码，修复后须新进程。采用完整DTO先validate→实际json→hash→再validate，不跳过校验。独立PG首`test_t28_independent_pg.py`（当时14case）：4 passed/10 failed/234.66s/exit1、无warning/skip，正例旧_rules安全503含未走到真正wait的case，不把它们算期限通过。

已追加原文descriptor的stage/window/ruleset/scope/offering/reference绑定，防未改已审原文却换适用元数据；当前spec独立15case与实现者新8case等待最终结果，不用首轮结果冒称完成。

## 最终修复与实库结果

实现者修复SHA后追加smoke曾1 failed/16.21s：测试错误的字符串file_id匹配到了profile_id，真实存储/重放已成功；改为精确键。第二完整8case为4 passed/4 failed/123.92s，三项测试前提修正，一项真实HTTP500定位到旧ProfileEnvelope别名校验拒绝新的data形状；新增独立AssessmentEnvelope及实际profile metadata校验，旧ProfileEnvelope保持。最终实际命令：

`& '.\.cache\t23-postgres\run-tests.ps1' -PytestArguments @('tests/integration/eligibility/test_t28_service.py','-q','--tb=short')`

**8 passed/127.80s/exit0**，1既有Starlette弃用warning，无skip。9个新增Python模块内存编译exit0。

独立最终实际同helper `-PytestArguments @('tests/integration/eligibility/test_t28_independent_pg.py','-q','--tb=short')`：**15 passed/232.48s/exit0**，无warning/skip；实际新链往返、不可UPDATE/可信DELETE、owner/原同意/过期、无真实rule binding、descriptor元数据、nested AST及微秒、SQL阻塞越过必要policy截止409回滚、未用any policy不影响eligible、文件最终到期回滚。补真实T19替代/撤回历史断言后仅重跑`tests/integration/eligibility/test_t28_independent_pg.py::test_nested_ast_survives_commit_and_replay_keeps_original_microsecond_time_and_minimal_context`：**1 passed/18.16s/exit0**，无warning/skip；不将重复node计为第16个独立case。两种历史标记及旧release新eval409、原AST/time/hash不变实际通过。

实现者和前端交叉只读检查无新增阻断，未冒称再跑测试；源码与测试冻结。

## 最终契约与前端

独立Envelope后实际生成assessments exit0；新契约中间13 passed/4.37s，新增实际positive envelope/meta错绑负例后最终14 passed/4.62s，均同Python flags、1既有warning。`scripts/generate_contracts.py --profile assessments --check`exit0。最终根 `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/contracts -q --tb=short`：**284 passed/30.08s/exit0**，1既有Starlettewarning，无skip，覆盖所有已有和新生成契约。

最终 `.cache/t28-types-build.ps1`：typecheck exit0、demo/auth两Build exit0，Vite1.20s/1.55s、73modules；与前次结果分开保留，构建缓存不提交。实际Vitest348/28files/37.07s仍有效，新增compile-only契约不改UI运行代码，未无理由重复全前端。

## 限制与保存边界

正式规则/政策发布链、真实学生/身份、全国及英国2027具体专业领域审核、法律适用性、正式SQL GRANT/RLS、生产清理恢复及部署未执行；模型live和未成年私有继续关闭。T25时间只支持minute/second，服务端真实微秒不截断，不能精确表达时相关时间谓词unknown。正式facts-only无ruleset不冒充资格。Lint/Python静态类型没有配置入口，明确未执行。独立HTTP/PG实际跑过，未另跑浏览器（本Task无页面变化）或uvicorn烟测。

## 本Task变更清单

33路径（11旧/22新）；513个范围外旧tracked字节保护，另66Task卡及历史CHANGELOG/ADR保留。

- `.gitattributes`
- `AGENTS.md`
- `README.md`
- `apps/web/tests/assessments-contract-types.ts`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T28_assessments.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/assessments.md`
- `docs/database.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `packages/contracts/v2/assessments/generated.ts`
- `packages/contracts/v2/assessments/openapi.json`
- `scripts/generate_contracts.py`
- `services/api/app/api/assessments.py`
- `services/api/app/assessments/__init__.py`
- `services/api/app/assessments/models.py`
- `services/api/app/assessments/store.py`
- `services/api/app/rules/assessment_engine.py`
- `services/api/app/rules/router.py`
- `services/api/app/rules/schemas.py`
- `services/api/app/rules/service.py`
- `services/api/assessments_alembic.ini`
- `services/api/assessments_migrations/env.py`
- `services/api/assessments_migrations/versions/0001_assessments_t28.py`
- `tests/contracts/test_t28_assessments_generation.py`
- `tests/integration/eligibility/conftest.py`
- `tests/integration/eligibility/test_t28_independent_pg.py`
- `tests/integration/eligibility/test_t28_service.py`
- `tests/unit/eligibility/test_t28_engine.py`
- `tests/unit/eligibility/test_t28_independent.py`
