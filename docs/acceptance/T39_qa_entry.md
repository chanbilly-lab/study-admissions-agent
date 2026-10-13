# T39 有限公开证据问答入口验收

2026-10-04源码及合成隔离验收完成；PRIVATE保存以后续实际Git核对为准，真实处理关闭。

## 基线与范围

PRIVATE cdcae7b13df452a11b6adb61d043f6396ae3102e/745tracked，codex/t39-evidence-qa-entry；初工作区/索引为空。必读治理/原规格/docs01–05/相关模块已核，代码前冻结[契约](../qa_entry.md)。13旧路径允许、732其他tracked保护，旧head/原规格/M0/历史保持。

## 实际检查

- `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/unit/qa tests/evals/test_t38_golden.py tests/unit/public_catalog tests/unit/facts tests/unit/evidence tests/unit/model_gateway tests/contracts -q --tb=short`：最终704 passed/57.12s/exit0，1既有Starlette warning。此前分开相关360 passed/11.84s、契约342 passed/48.19s为末guard前轮次，保留且不相加重复节点。新T39 pure61（27owned/34独立）与契约9在最终704之内。

- 同Python `-m pytest tests/security/test_mode_isolation.py tests/backend/test_api.py::test_mock_complete_flow_and_evidence tests/backend/test_api.py::test_live_mode_explicitly_unavailable_without_fallback -q --tb=short`：143 passed/3.88s/exit0，1既有warning；QA与gateway旧范围同Python `-m pytest tests/unit/qa/test_t38_retrieval.py tests/unit/qa/test_t38_safety.py tests/evals/test_t38_golden.py tests/unit/model_gateway tests/integration/model_gateway -q --tb=short`：196 passed/6.40s/exit0。后者已与最终范围重叠，不累总数。

- `.cache\run-web-checks.ps1 -TaskId T39`：实际调用`scripts/web.ps1 -Action test/typecheck`，742 passed/46files/24.56s、Vue TypeCheck exit0；demo1.44s/auth1.99s Build均exit0/131modules。随后仅QA客户端optional-keywords必要补丁：scoped Node24/pnpm `pnpm --dir apps/web exec vitest run tests/qa-client.test.ts tests/qa-state.test.ts tests/qa-panel.test.ts`最终59 passed/3files/3.48s（首58/3.57s，无失败轮）；`pnpm --dir apps/web run typecheck`exit0；`VITE_APP_MODE=demo/auth`顺序`pnpm --dir apps/web run build --outDir ../../.cache/t39-{demo,auth}-frontend-validation`最终demo1.48/auth1.98s、各131modules/exit0。PATH与VITE_APP_MODE finally恢复，auth546.48kB/外根cache提示保留。不能把补丁后的59说成再次完整回归。

- 十一profile逐个同Python `scripts/generate_contracts.py --profile <foundation/identity/public_catalog/admin/admin_review/profiles/assessments/plans/revisions/notifications/qa> --check`均exit0；`scripts/verify_contract.py`M0一致/exit0；`scripts/verify_originals.py`两原文UNCHANGED/exit0。旧20生成工件字节未变。

- owned同Python `-m pytest tests/unit/qa/test_t39_http.py tests/contracts/test_t39_qa_contract.py -q --tb=short`：首35 passed/3.62s、中35/3.86s、末guard36/3.65s、最终36/3.61s（27pure/9contract），各exit0/1旧warning。独立同Python `-m pytest tests/unit/qa/test_t39_safety.py -q --tb=short`首6pass1fail/2.77s（未挂载v1误要求v2 envelope），扩30pass3fail/3.00s（model_construct丢弃extra的测试前提），修后33/2.27s；最后header回归34 passed/2.40s/exit0/1旧warning。保留原失败，不重复计数。

- owned实际 `.cache\t23-postgres\run-tests.ps1 -PytestArguments @('tests/integration/qa/test_t39_http.py','-q','--tb=short')` 首2pass1fail/33.09s/exit1，新测试误把quota漂移BUDGET_UNAVAILABLE写为QA_UNAVAILABLE；新前提修后3 passed/35.17s/exit0。最终source保护补丁后同helper `tests/integration/qa/test_t39_http.py::test_real_current_http_typed_answer_and_closed_parser_do_not_write_or_read_students`复验1 passed/11.79s/exit0；是前3之一。实际公开positive、16KiB/重复keys/NaN/media/extra/query/idempotency拒绝、只SELECT无StudentSQL、unknown零provider/quota、漂移前零SQL均通过。

- 独立实际同helper `@('tests/integration/qa/test_t39_safety.py','-q','--tb=short')` 首4pass2fail/85.63s/exit1，新测试错用cookie_name及取消完成回调前断言；仅修真实cookie常量与有限等待provider finally，最终6 passed/82.84s/exit0。真实两owner匿名相同公开读且无Student/Auth表或写；无atom零quota clock；模型wait时真实提交撤回/替代分别整答409；pg_blocking_pids观察真实later-member SQL等待跨first-file期限409；failure/timeout/wrongcite/cancel保守扣量不外泄。各1既有warning/no skip。

- root实际同helper `@('tests/integration/qa/test_t39_browser.py','-q','--tb=short')` 首1failed/16.04s/exit1：业务八检查点已实际执行，末网络断言漏已有匿名告知/共享配置GET，误将全部/api路径当学生读取；只新harness纠正精确三个配置/身份GET，业务及构建不变。最后实际结果由本报告生成脚本从passed报告与真实pytest结果登记，见下条。

- 最终root同实际PG-browser命令：1 passed/15.78s/exit0/1既有warning；Edge 154.0.4258.53 八检查点、真实当前公开项目、明确cap/mock、600.00原值、纯文本原文、费用无依据unknown、真正完成HTTP200在切换意图后迟到拒绝、卸载零持久缓存、无页面错误/外网请求。QA三次POST中只有两次模型dispatch，unknown不耗模型预算。新增PG合计10 distinct（3owned/6独立/1Edge），八检查点不是八pytest节点。


## 未执行与已知问题

Lint/Python静态Type Check：项目无配置入口，未执行；Vue Type Check实际执行。没有数据库迁移，未执行新DDL验收。真实Keycloak/学生/领域责任审核/live供应商/采购/法律/生产SQLGRANT-RLS/部署与生产备份恢复未执行。实际专用PG、HTTP和Edge已执行。

真实模型/资料/公众部署保持关闭，合成引用不能当真实官方事实；预算为有界进程内保守UTF8计量，持久全局运行配额属T46。现有Starlette warning、auth546.48kB与ignored outDir构建提示保留。D01/D07/D08补充选择待用户回复。

## 修改文件

- `.gitattributes`
- `AGENTS.md`
- `README.md`
- `apps/web/src/features/auth/AuthView.vue`
- `apps/web/src/features/qa/QAPanel.vue`
- `apps/web/src/features/qa/client.ts`
- `apps/web/src/features/qa/useQA.ts`
- `apps/web/src/features/qa/validation.ts`
- `apps/web/src/views/CatalogView.vue`
- `apps/web/tests/qa-client.test.ts`
- `apps/web/tests/qa-panel.test.ts`
- `apps/web/tests/qa-state.test.ts`
- `apps/web/tests/qaFixtures.ts`
- `apps/web/vite.config.ts`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T39_qa_entry.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/qa_entry.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `packages/contracts/v2/qa/generated.ts`
- `packages/contracts/v2/qa/openapi.json`
- `scripts/generate_contracts.py`
- `scripts/qa_t39_browser_smoke.mjs`
- `services/api/app/api/qa.py`
- `services/api/app/qa/http_schemas.py`
- `services/api/app/qa/router.py`
- `services/api/app/qa/service.py`
- `tests/contracts/test_t39_qa_contract.py`
- `tests/integration/qa/test_t39_browser.py`
- `tests/integration/qa/test_t39_http.py`
- `tests/integration/qa/test_t39_safety.py`
- `tests/unit/qa/test_t39_http.py`
- `tests/unit/qa/test_t39_safety.py`
