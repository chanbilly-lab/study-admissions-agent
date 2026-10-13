# T49 持久幂等验收

2026-10-03：已完成源码/合成与隔离实库验收。分支codex/t49-persistent-idempotency，基线207f7ea7b831bf57bdce2a5df96bc4b1614222af，297 tracked/初始索引与工作区干净。T14已上传后才单列T49；先读必读、API/DB/授权/隐私/审计/存储/来源、原规格与相关代码，确认依赖与[冻结契约](../idempotency.md)。准备helper未禁quotepath导致非ASCII路径失败、encoding alias和默认GBK读取失败，改当前参数/显式UTF-8后成功，失败未覆盖文件；编码期间读取未落盘目录rg退出1不算应用测试。

## 行为与验证

独立0001/idempotency_alembic_version只依赖auth0006，不改旧head。actor/op/key SHA256唯一，payload只有有界规范SHA256，resources只有closed kind/UUID/version，不缓存body或权限。真实默认关闭/TTL必填；合成fixture24h不冒充D06决定。same-TX processing→completed，deferred trigger读取当前row，在真实COMMIT拒绝unfinished；rollback释放唯一竞争。ownTX提交后返回，callerTX不得提前发送结果并须异常rollback。当前身份/角色/core、强管理员MFA及领域verifier在创建/重放、等待、审计后重验，资源删除/撤权不靠旧缓存绕过；payload与receipt动态修改亦拒绝。

19 PG包含2直接store唯一索引竞争commit/rollback（实际pg_stat_activity/pg_blocking_pids观察，未持Auth锁），另2服务账户锁竞争，两个机制分开。真实deferred失败使回执/业务/成功审计一起rollback；raw processing无法COMMIT；exact expiry只换回执不删旧资源。最末audit触发器仅在本actor receipt completed才阻塞，确实perform后审计等待，再推进session/role/core/receipt期限拒绝。当前用途/notice/年龄/owner/deleted重放检查；错mapper/calleractor、跨actor/operation、当前MFA、独立迁移重复/降级保留父域。资源verifier是可信应用组合协议，未来import/release/profile/plan仍须领域实现，不称真实业务已开。

## 实际命令

- `.\.venv\Scripts\python.exe -B -m pytest tests/unit/idempotency -q`：root最终48 pass2.69s，exit0；canonical24+contracts24，无skip或失败。先独立canonical24 pass1.58s。7后端py_compile与3前端owned memory compile退出0。
- `.cache/t49-postgres/run-tests.ps1 -PytestArguments @('tests/integration/idempotency','-q','--tb=short')`：19 pass23.04s，exit0，首轮专项无失败。仅专用loopback idempotency_t49_test/随机schema，拒外部socket/DNS，fixture清理。
- 同helper `-PytestArguments @('tests/integration/authorization','tests/security/privacy','tests/security/audit','-q','--tb=short')`：450 pass、1既有warning114.89s，exit0。
- `.\.venv\Scripts\python.exe -m pytest tests/contracts tests/security/test_mode_isolation.py -q --tb=short`：333 pass、1既有warning17.60s，exit0。
- `.cache/run-web-checks.ps1 -TaskId T49`：170 pass/15 files8.80s、Type Check/demo/auth Build exit0，产物只在忽略缓存，常规outDir warning。
- `scripts/generate_contracts.py --check`两foundation/identity profile、`scripts/verify_contract.py`、`-X utf8 scripts/verify_originals.py`：全部exit0，原规格和wire保留。
- `.\.venv\Scripts\python.exe .cache/check_task.py T49`及显式暂存blob/范围/历史/链接/凭据检查、普通Git提交推送与remote SHA核对在保存步骤运行，Git保存不表示部署。

## 未执行与已知限制

无Lint/Python静态类型入口未执行；browser无UI变化未执行；未重跑全体PG而执行受影响专项/相关回归。真实Keycloak/MFA/GRANT/RLS、正式TTL政策、真实领域数据、法律/权利渠道、物理摘要清理/备份恢复及部署未执行。没有worker或外部副作用原子承诺；期限仅重放窗口，未请求过期摘要待后续维护/删除验收，不能称D06留存合规。

## 文件与同步

24路径（9旧/15新）：

- `AGENTS.md`
- `README.md`
- `docs/tasks.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/api.md`
- `docs/database.md`
- `docs/architecture.md`
- `docs/requirements.md`
- `docs/idempotency.md`
- `docs/acceptance/T49_persistent_idempotency.md`
- `services/api/app/api/v2/idempotency_canonical.py`
- `services/api/app/idempotency/__init__.py`
- `services/api/app/idempotency/schemas.py`
- `services/api/app/idempotency/models.py`
- `services/api/app/idempotency/store.py`
- `services/api/app/idempotency/service.py`
- `services/api/idempotency_alembic.ini`
- `services/api/idempotency_migrations/env.py`
- `services/api/idempotency_migrations/versions/0001_idempotency_t49.py`
- `tests/unit/idempotency/test_t49_canonical.py`
- `tests/unit/idempotency/test_t49_contracts.py`
- `tests/integration/idempotency/conftest.py`
- `tests/integration/idempotency/test_t49_idempotency.py`

CHANGELOG/tasks及受影响文档已同步；范围保护以本轮297基线/9allowed审查计算，原规格/旧迁移/历史验收/其他66卡保持。下一是已授权T15，正式门槛不解除。
