# T17 类型化候选事实验收

2026-10-03源码与合成隔离实库验收完成。独立codex/t17-typed-facts，基线d53a363fffbf391e99aaf4f8273543657f19d1fe；343 tracked/开始Git与index干净。已读AGENTS/必读/API/DB/原始两份规格与T12/T15/T16相关代码；先冻结[facts契约](../facts.md)。专用loopback facts_t17_test/randomschema，不打印凭据。纯契约、后端与实库检查在同一Task分工，下一Task未开始。

实际命令与结果待执行后逐项记录；不能把实施中当完成。无HTTP/UI/依赖变化，旧heads保留，真实处理/审核与公众发布未执行。

已实际执行（尚非T17专项完成）：
- .cache/t17-postgres/run-tests.ps1 -PytestArguments @('tests/unit/ingestion','tests/unit/evidence','tests/unit/dates','tests/integration/imports','tests/integration/evidence','-q','--tb=short')：160 passed138.81s exit0，无skip。
- .venv/Scripts/python.exe -m pytest tests/contracts tests/security/test_mode_isolation.py -q --tb=short：333 passed17.96s exit0，1既有Starlette/anyio warning。
- .cache/run-web-checks.ps1 -TaskId T17：170 passed/15files8.65s，vue Type Check、demo/auth Build exit0；仅忽略缓存产物，outDir常规warning。
- .venv/Scripts/python.exe scripts/generate_contracts.py --check、--profile identity --check、scripts/verify_contract.py、-X utf8 scripts/verify_originals.py：全部exit0。

Lint与Python静态Type Check无现有入口，未执行；browser/UI无变更未执行。全体PG、POSIX、真实身份/原文件物理恢复/真实事实处理/部署/清理备份未执行。前端Type Check已执行，不能代替Python静态检查。

只读审查发现并在本Task修正：同logical key查询须SQL内过滤差值/最多201，不先加载全部等值历史；最终锁/审计/身份查询后用已锁时间证明再检查原source/file到期，特别是无evidence日期候选；callerTX异常不能留下可提交的部分修改。纯模块首root35 passed1.04s，代理冻结版同35 passed1.05s exit0及3模块内存compile exit0，不累加成70项。

任务外记录：T15旧_current_file/_verify_batch在最后身份查询后没有额外本地原file期限比较；真实处理关闭，本Task不改旧服务。T17自行保留最终时间证明并复查；该旧路径应在正式处理验收前单独复核，不将本次修正宣称覆盖T15全部路径。

首PG实际命令`.cache/t17-postgres/run-tests.ps1 -PytestArguments @('tests/integration/facts','-q','--tb=short')`：23 passed/2 failed168.13s exit1，1既有Starlette warning。失败为两处测试前提：将expires_at设为created_at违反旧T14正留存约束，以及date锁探针捕获主线程自身而不是worker；只修本Task测试，旧存储/日期未改。首轮模块在最后value_kind指纹补丁前加载，不能充当最终覆盖。完整25项复验待实际记录。

最后root内存编译实际命令：`.venv/Scripts/python.exe -B -c "from pathlib import Path; paths=list(Path('services/api/app/facts').glob('*.py'))+list(Path('services/api/facts_migrations').rglob('*.py')); [compile(p.read_text(encoding='utf8'),str(p),'exec') for p in paths]; from services.api.app.facts.service import FactService; from services.api.app.facts.models import FactsBase; assert len(FactsBase.metadata.tables)==2; print(str(len(paths))+' modules compiled; service import and 2-table metadata passed')"`：8 modules/import/2-tablemetadata通过，exit0/2.99s，覆盖value_kind指纹补丁。

完整当前Task范围（未包含忽略缓存、凭据或构建产物）：
- `AGENTS.md`
- `README.md`
- `docs/tasks.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/api.md`
- `docs/database.md`
- `docs/architecture.md`
- `docs/requirements.md`
- `docs/facts.md`
- `docs/acceptance/T17_typed_facts.md`
- `services/api/app/facts/__init__.py`
- `services/api/app/facts/schemas.py`
- `services/api/app/facts/typing.py`
- `services/api/app/facts/models.py`
- `services/api/app/facts/store.py`
- `services/api/app/facts/service.py`
- `services/api/facts_alembic.ini`
- `services/api/facts_migrations/env.py`
- `services/api/facts_migrations/versions/0001_facts_t17.py`
- `tests/unit/facts/test_t17_typing.py`
- `tests/integration/facts/conftest.py`
- `tests/integration/facts/test_t17_facts.py`

最终专项：`.cache/t17-postgres/run-tests.ps1 -PytestArguments @('tests/integration/facts','-q','--tb=short')`：25 passed162.52s exit0，1既有Starlette warning，无skip，覆盖最后value_kind/finalguard/callerrollback及payload262144。首轮失败过程保留，纯35+PG25为60项专项；不累加重跑次数。
25项含JSON/CSV、minimum/typical/historical分离、64字符相邻/等价精度、缺失/未知/原脚注/原类型、>32KiB合法转义payload、immutable两表、同hash副本不能续原file绑定、当前身份/MFA/最新许可/原文件、native日期及指纹、错mapper/scope、audit/真正deferredCOMMIT回滚、date/audit真实锁等待后到期、两会话去重/冲突及不同管理员/来源/批次共同scope锁、独立迁移重复/降级恢复/旧域保护、现有公开foundation仍空且facts路径不存在。仅合成、不是正式事实审核。

CHANGELOG/tasks及受影响文档已同步，其他66卡保留，普通提交/推送前保护QA待实际输出；下一单独T18属于既有授权，T21不开始。真实资料/身份/SQL GRANT/RLS、物理恢复、清理备份和部署门槛仍未执行。

实际保存前QA：`.venv/Scripts/python.exe .cache/check_task.py T17`：23路径（9旧/14新）、334保护tracked、66其他卡、283本地链接、11Python内存compile、历史/凭据形状检查exit0；`git -c safe.directory=D:/Projects/study diff --check` exit0。最后代理stdin将新冻结DDL两表/两Index与model逐行rstrip精确比对、四ownedPython AST/行尾检查exit0；不把该静态检查替代实库。无既有暂存/用户变更；仅当前Task审查路径上传。
