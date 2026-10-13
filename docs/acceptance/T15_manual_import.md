# T15 人工导入验收

2026-10-03，已完成源码与隔离实库验收。分支codex/t15-manual-import；基线f51574d89bf238780048eb951ce0ad176503c184，312 tracked/开始index与工作区干净。先读必读与当前相关文档/原规格/source/storage/idempotency/catalog代码，再冻结[数据/范围/测试](../imports.md)，单独开始T15。专用loopback import_t15_test及env恢复helper准备成功；无凭据输出，不修改旧测试库。

已实际执行：

- `.cache/t15-postgres/run-tests.ps1 -PytestArguments @('tests/unit/storage','tests/security/storage','tests/unit/idempotency','tests/integration/idempotency','tests/integration/sources','-q','--tb=short')`：145 pass/1 skip76.35s，exit0。skip为真实symlink创建Win1314；旧受影响父域代码无修改。
- `.\.venv\Scripts\python.exe -m pytest tests/contracts tests/security/test_mode_isolation.py -q --tb=short`：333 pass/1既有warning14.33s，exit0。
- `.cache/run-web-checks.ps1 -TaskId T15`：170 pass/15 files8.27s、Type Check/demo/auth Build exit0；产物只忽略缓存，常规outDir warning。
- parser首44 pass0.93s，扩DTO位置与copy重验后46 pass0.94s，均exit0，无首轮失败。只读复核中逐行ParsedImport构造会误拒绝>=3逻辑位置，要求改全batch复验；多字段同source record不额外唯一。此问题在最终store整批复验修正，PG三行JSON/CSV及同record多字段已实测。

- root末次 .venv/Scripts/python.exe -B -m pytest tests/unit/ingestion -q：46 passed0.92s，exit0。
- .cache/t15-postgres/run-tests.ps1 -PytestArguments @('tests/integration/imports','-q','--tb=short')：首轮17 passed/2 failed59.94s exit1；最后19 passed65.87s exit0。原资产拒绝被T49包装503，仅本新service记录封闭领域错误并在回滚后恢复；未知异常仍503。另一失败为测试将MFA age==max当过期，改advance61，不改既有T06策略。
- 两profile scripts/generate_contracts.py --check、scripts/verify_contract.py、-X utf8 scripts/verify_originals.py：exit0，原字节/生成文件保留。
- .cache/check_task.py T15：范围/67卡/历史记录/本次Python编译/链接与凭据形状检查；其他66任务卡不改。

19PG含三行JSON/CSV、重复record多字段、自然去重/receipt到期/副本、真实唯一锁竞争、audit及真实deferred COMMIT失败回滚/重试、最终audit等待后当前MFA/文件重验、当前角色/session/manual许可、exact source/file/hash/年/版本、mapper/复制DTO、默认关闭和独立迁移保留旧域。上传者UUID仅溯源，当前source责任人及T14 proof决定读取；强管理员角色本身不授予该资产。

Lint/Python静态Type Check没有配置入口，未执行；前端Type Check实际执行。无UI改动，browser未执行；全体PG、POSIX、真实身份/招生事实/正式TTL/清理/备份/部署未执行。Storage10MiB与同步parser1MiB分别保留；PDF不由T15解析。真实门槛未解除，源码通过不代表公开事实。无新依赖、HTTP、UI或旧head改动。

完整变更清单：
- `AGENTS.md`
- `README.md`
- `docs/tasks.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/api.md`
- `docs/database.md`
- `docs/architecture.md`
- `docs/requirements.md`
- `docs/imports.md`
- `docs/acceptance/T15_manual_import.md`
- `services/api/app/ingestion/__init__.py`
- `services/api/app/ingestion/schemas.py`
- `services/api/app/ingestion/structured.py`
- `services/api/app/admin/imports/__init__.py`
- `services/api/app/admin/imports/models.py`
- `services/api/app/admin/imports/store.py`
- `services/api/app/admin/imports/service.py`
- `services/api/imports_alembic.ini`
- `services/api/imports_migrations/env.py`
- `services/api/imports_migrations/versions/0001_imports_t15.py`
- `tests/unit/ingestion/test_t15_structured.py`
- `tests/integration/imports/conftest.py`
- `tests/integration/imports/test_t15_imports.py`

保存前 git diff --cached --check 首次退出1：本Task新SQL literal行尾空格；只修此新迁移格式，无语义改动。复验迁移及暂存检查后保存，不改旧迁移。
迁移复验命令同PG helper仅 -k independent_imports_migration：1 passed/18 deselected3.42s exit0。范围QA：24路径（9旧/15新）、303保护文件、66其他卡、262链接、12Python编译通过。
