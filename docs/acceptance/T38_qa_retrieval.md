# T38 范围检索与严格引用验证验收

2026-10-04源码及合成隔离验收完成；PRIVATE保存以后续实际Git核对为准，真实处理关闭。

## 基线与范围

PRIVATE fa40c80b113de048f2358137aa5b88fc935a8220/731tracked，codex/t38-scoped-citations；初工作区/索引为空。必读治理/原规格/docs01–05/相关模块已核，代码前冻结[契约](../qa_retrieval.md)。8旧路径允许、723其他tracked保护，旧head/原规格/M0/历史保持。

## 实际检查

- `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/unit/public_catalog tests/unit/facts tests/unit/evidence tests/unit/model_gateway tests/contracts -q --tb=short`：528 passed/64.39s/exit0，1既有Starlette warning。

- `.cache\run-web-checks.ps1 -TaskId T38`：实际` scripts/web.ps1 -Action test/typecheck`与scoped Node24/pnpm两模式Build；684 passed/43files/46.45s，Vue TypeCheck exit0；demo Build1.79s/auth2.12s/125modules exit0。auth522.75kB及cache outDir提示保留。

- 同.venv Python `-m pytest tests/security/test_mode_isolation.py tests/backend/test_api.py::test_mock_complete_flow_and_evidence tests/backend/test_api.py::test_live_mode_explicitly_unavailable_without_fallback -q --tb=short`：143 passed/4.14s/exit0，1既有Starlette warning。

- 十profile逐个`scripts/generate_contracts.py --profile <foundation/identity/public_catalog/admin/admin_review/profiles/assessments/plans/revisions/notifications> --check`均exit0；`scripts/verify_contract.py` M0一致/exit0；`scripts/verify_originals.py`两原文UNCHANGED/exit0。

- 独立纯首次`pytest tests/unit/qa/test_t38_safety.py -q --tb=short`（同.venv Python）：57 passed/2.24s/exit0/no warning/skip。先前合法bundle probe发现_native ancestor marker错误不是额外pytest节点；新源码修复后实际通过。owned纯首次7passed/10failed1.14s、第二7/10fail1.12s，均新fixture漏/写错EvidenceLocator.location_kind；修合法utf8_byte_lines后17passed0.80s。整体quota必要新负例后18passed2.15s，组合75passed2.51s。不累计重复复验。

- fixed-gold专项`pytest tests/evals/test_t38_golden.py -q --tb=short`：首30passed3.93s/最终30passed3.83s；CLI`scripts/verify_qa_golden.py`实际24/24匹配（8接受/16拒绝/1unknown接受），exit0。脚本输入/预期闭合、SHA抗篡改、无DB/network/model/retriever；标记当前权威/领域人工审阅false。

- 最终root `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/unit/qa tests/evals/test_t38_golden.py -q --tb=short`：105 passed/6.17s/exit0，无warning/skip（18owned/57独立/30eval）；随后同Python `scripts/verify_qa_golden.py`再24/24/exit0。gold 24样本不是额外24个pytest。

- owned实际PG首`.cache\t23-postgres\run-tests.ps1 -PytestArguments @('tests/integration/qa/test_t38_retrieval.py','-q','--tb=short')`：5 setup errors/29.25s/exit1，专用55438失联，未建schema或进入业务。root核无postgres/端口不通，仅复启已验证.cache测试cluster；首次漏显式端口启动5432，立即停同cluster并显式`pg_ctl -D <已核测试cluster> -o "-p 55438 -h 127.0.0.1" -w start`；正确`pg_isready -h127.0.0.1 -p55438` accepting/exit0，用户DB/Docker未修改。

- 恢复后owned实际PG5failed56.57s、独立5failed36.00s/exit1：全部新qa_case_factory重复旧request namespace字段，尚未进入QA业务；只新conftest合并dict覆盖后重新执行。独立此前collect-only5/0.24s仅收集，非通过。

- 最终owned同实际PG命令：5 passed/63.16s/exit0/no warning/skip；当前公开正例、完整范围/先scope后keyword、无公开quote与撤回、等待后替代、default/config漂移前零SQL。SQL只SELECT、无Student/Auth读取或业务写。

- 最终独立`.cache\t23-postgres\run-tests.ps1 -PytestArguments @('tests/integration/qa/test_t38_safety.py','-q','--tb=short')`：5 passed/80.70s/exit0/no warning/skip。真实T37 offline async Event等待中的撤回/替代/来源到期（三节点）重新取证整答409，发布变化能等待中提交；真正laterSource FOR UPDATE+pg_blocking_pids SQL阻塞（二节点）跨过首source/file期限后零引用/原子，原表摘要不变。合计10 distinct PG，不累计失败/重复轮次。


- 暂存实际diff复核发现atom_value宽捕ValueError可能把损坏字段伪报quota；单atom超2000改专用ProjectionLimit且retrieve只捕该异常，新增坏字段拒绝负例。最终root同纯命令：106 passed/5.95s/exit0（19owned/57独立/30eval），无warning/skip。随后实际PG同helper只跑`tests/integration/qa/test_t38_retrieval.py::test_current_publication_is_exact_and_anonymous_without_writes_or_student_sql`：1 passed/11.31s/exit0；是前10节点之一的必要复验，不增加distinct计数。

- `.cache/check_task.py T38` 首核22paths/8old14new/723其他tracked/66其它卡/401本地links/11Python内存compile/历史与秘密检查exit0。stage已核实际8旧路径diff及新retrieval/validation完整cached diff；gold staged blob SHA/LF保持，旧API/DB/TS/前端/研究工件无改。

## 未执行与已知问题

Lint/Python静态Type Check：项目无配置入口，未执行；Vue Type Check实际执行。T38不增加HTTP/UI/数据库迁移，未执行新HTTP/浏览器/迁移检查；实际PG当前证明与锁等待已执行。真实领域审核、live供应商调用/数据流/采购、法律/正式身份/部署/SQLGRANT-RLS及生产备份恢复未执行。

真实事实与live仍关闭；gold只有24合成案例，current_authority_established/manual_domain_review_completed均false，不能代正式领域审阅。日期计算候选与官方精确期限分开，官方UTC仍未知；超有限投影整体返回LIMIT_EXCEEDED。现有auth522.75kB包体提示与Starlette警告保留。D01/D07/D08补充选择尚待用户回复，不在T38中代猜。

## 修改文件

- `.gitattributes`
- `AGENTS.md`
- `README.md`
- `data/evals/qa/t38_golden.json`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T38_qa_retrieval.md`
- `docs/architecture.md`
- `docs/qa_retrieval.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `scripts/verify_qa_golden.py`
- `services/api/app/qa/__init__.py`
- `services/api/app/qa/retrieval.py`
- `services/api/app/qa/schemas.py`
- `services/api/app/qa/validation.py`
- `tests/evals/test_t38_golden.py`
- `tests/integration/qa/conftest.py`
- `tests/integration/qa/test_t38_retrieval.py`
- `tests/integration/qa/test_t38_safety.py`
- `tests/unit/qa/test_t38_retrieval.py`
- `tests/unit/qa/test_t38_safety.py`
