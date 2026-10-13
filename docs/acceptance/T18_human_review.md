# T18 人工审核决定验收

2026-10-03源码/合成隔离实库验收完成。codex/t18-human-review，基线94daf36ada372d3c7d9ef4a59b54d2d7ba8a6f0e，357 tracked/开始Git与index干净。已读必读/原规格/API/DB与facts/evidence/audit/source相关代码；先冻结[review契约](../reviews.md)。第一次原规格读取探针encoding拼写错误无修改，修正后完整读取并记录baseline。专用loopback reviews_t18_test/randomschema，无外网/真实用户/正式事实；本Task测试中的人工角色由合成fixtures模拟，不声称实际真实事实已人工审核。

以下为本Task实际检查，分别保留专项与回归范围。旧heads/facts/HTTP/deps保持，T19未开始。

已实际执行（不能替代T18专项）：
- .cache/t18-postgres/run-tests.ps1 -PytestArguments @('tests/unit/facts','tests/integration/facts','tests/unit/evidence','-q','--tb=short')：93 passed178.40s exit0，1既有Starlette/anyio warning，无skip。
- .venv/Scripts/python.exe -m pytest tests/contracts tests/security/test_mode_isolation.py -q --tb=short：333 passed17.83s exit0，1既有warning。
- .cache/run-web-checks.ps1 -TaskId T18：170 passed/15files8.60s，Vue Type Check及demo/auth两Build exit0；仅忽略缓存产物，outDir常规warning。
- .venv/Scripts/python.exe scripts/generate_contracts.py --check、--profile identity --check、scripts/verify_contract.py、-X utf8 scripts/verify_originals.py：全部exit0。

Lint/Python静态Type Check无入口未执行；browser/UI无变更未执行；全项目PG回归、POSIX、正式身份/真实事实人类审核、来源权利/运营法律验收、物理恢复/清理备份/部署未执行。前端类型已检查，不能代替Python静态检查。T15任务外时效跟进保留T17记录，不修改旧服务。

## 专项实际执行与失败轨迹

- `.venv/Scripts/python.exe -B -m pytest tests/unit/reviews -q`：最终31 passed1.06s exit0（此前28/30项仅为旧稿结果，最终加入Unicode数字/符号和中文单位边界）。
- `.cache/t18-postgres/run-tests.ps1 -PytestArguments @('tests/integration/reviews','-q','--tb=short')`：第一轮21 passed/2 failed163.49s exit1；两处本新测试前提错误（source permission撤回的409受限历史投影应False，合成MFA auth_time刷新时旧Session.created_at未同步）。第二轮22 passed/1 failed163.87s exit1：新增file过期期望False，与冻结契约仅409 fallback不符，旧T16返回404应拒绝。修正本新测试，不改旧服务/模型；最终完整复验23 passed163.44s exit0，无skip/无warning。
- Python stdin对reviews六模块、reviews_migrations/env及0001共8模块内存compile，import ReviewService/ReviewsStore、断言ReviewsBase三表：exit0。

## 边界与变更文件

每logicalkey一个当前胜者，全部冲突ID显式处理、十项检查与原literal/单位/脚注定位；导入者与审核者按账户UUID隔离。新冲突或退回使当前批准失效；历史不可变。source/file当前proof409且已有case仅返回受限引用current_approved=False；原file过期/删除若T16返回404则拒绝，未知404不转成历史。caller异常整TXrollback、审计/deferredCOMMIT失败不部分成功。测试人工角色为合成模拟，不代表真实领域审核。

23路径（9旧/14新）；完整清单：

- `AGENTS.md`
- `README.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/tasks.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/api.md`
- `docs/database.md`
- `docs/reviews.md`
- `docs/acceptance/T18_human_review.md`
- `services/api/app/reviews/__init__.py`
- `services/api/app/reviews/schemas.py`
- `services/api/app/reviews/validation.py`
- `services/api/app/reviews/models.py`
- `services/api/app/reviews/store.py`
- `services/api/app/reviews/service.py`
- `services/api/reviews_alembic.ini`
- `services/api/reviews_migrations/env.py`
- `services/api/reviews_migrations/versions/0001_reviews_t18.py`
- `tests/unit/reviews/test_t18_validation.py`
- `tests/integration/reviews/conftest.py`
- `tests/integration/reviews/test_t18_reviews.py`

最终源冻结后4 Python AST/DDL/空白及literal三表/index/deferredFK与models逐项比对exit0；Git旧迁移无diff。`.venv/Scripts/python.exe .cache/check_task.py T18`：23路径、348旧tracked保护、66其他任务卡/历史不变、291本地链接、11Python内存compile及凭据/范围检查exit0；CHANGELOG/tasks一致。
