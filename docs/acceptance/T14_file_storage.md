# T14 文件存储验收

2026-10-03：已完成源码/合成与隔离实库验收；分支codex/t14-file-storage，基线9cad51cb65bc16c6cb0842a1bac7749f952f05b3，280 tracked，开始索引/工作区干净。先读必读及相关文档、原规格、权限/隐私/来源/审计代码，确认T07/T10与D06依赖，再冻结[契约、范围与测试](../storage.md)。准备读取两次rg未展开Windows通配路径退出1，改目录+glob正常，不计应用测试。

## 实现与验收范围

两个UUID命名空间与StorageBackend接口；只接受PDF/UTF-8 CSV/JSON，1..10MiB；有界格式检查、随机无覆盖路径、祖先/文件reparse与hardlink拒绝。PDF仅浅签名检测，全部quarantined。一次完整有界read后核对size/hash，再重验权限与必要审计，commit后返回；没有HTTP下载、signed URL或公开原文。

私有附件结合当前owner/root、年龄/core/notice/session/role；metadata共享不授权bytes。来源结合强管理员MFA、当前版本、责任人、manual_import许可与期限，调用者预期dataset/source/version必须成组精确匹配。Storage独立0001与版本表，auth0006/catalog0003不变；同引擎mapper逐项防绕过。上传审计与元数据同事务，已验证exact receipt才补偿；崩溃/清理失败孤儿不具有业务读取资格。逻辑删除先持久pending/审计，再物理删除及完成事务；后者提交失败如实pending，允许重试。

## 实际命令与结果

- `.\.venv\Scripts\python.exe -B -m pytest tests/unit/storage -q`：最终43 passed /1 skipped，2.91s，exit0。首轮39 pass/1 fail/1 skip：真实Windows目录句柄未阻止rename；GENERIC_READ修复后40/1skip，再增hardlink/10MiB/import边界最终43/1skip。FileDispositionInfo BOOLEAN ABI已核对。
- `.cache/t14-postgres/run-tests.ps1 -PytestArguments @('tests/security/storage','-q','--tb=short')`：首17 pass29.36s；只读复核发现完成事务回滚时DTO过早标deleted，修正并新增真实PostgreSQL延迟UPDATE触发器COMMIT失败断言，最终17 pass29.34s，exit0。包含真实INSERT COMMIT失败补偿、cleanup失败孤儿、read后fresh proof、audit等待、当前许可/权限、hash篡改、mapper、独立迁移与旧五域保留。来源前置审计可能先阻在读bytes前，不称全部锁测试均读后等待。
- 同helper `-PytestArguments @('tests/security/authorization','tests/integration/authorization','tests/security/audit','tests/security/privacy','tests/integration/sources','-q','--tb=short')`：531 pass、1既有warning，200.17s，exit0。
- `.\.venv\Scripts\python.exe -m pytest tests/contracts tests/security/test_mode_isolation.py -q --tb=short`：333 pass、1既有warning，13.73s，exit0。
- `.cache/run-web-checks.ps1 -TaskId T14`：170前端测试/15 files8.36s；Type Check、demo/auth双Build退出0，产物在忽略缓存；常规outDir警告非失败。
- `.\.venv\Scripts\python.exe scripts/generate_contracts.py --check`、同命令`--profile identity --check`、`scripts/verify_contract.py`、`-X utf8 scripts/verify_originals.py`：全部exit0，M0/两v2 profile与原始两输入保持。
- 八后端模块py_compile及fresh-process纯DTO导入/4严格负例exit0；统一范围、历史卡/日志/ADR、本地链接、凭据形态、memory compile与暂存清单检查见保存记录。

## 未执行、跳过与限制

文件symlink创建因Windows1314权限跳过1项；真实junction、hardlink、目录rename及部分写失败均实际运行。POSIX代码分支未在此Windows执行。Lint/Python静态类型无项目入口未执行；browser无UI变化未执行；未重跑全体PG，已执行受影响专项与相关回归。真实Keycloak/MFA、OS ACL、SQL生产GRANT/RLS、法律/权利渠道、扫描、自动清理/备份恢复、部署与真实资料发布均未执行。来源fixture TTL1天不冒充用户选择的正式TTL，生产配置仍必填/默认关闭；D06只是产品上限。FS/DB补偿非两阶段保证。

## 修改清单与保存

31路径（14旧/17新）：

- `AGENTS.md`
- `README.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/api.md`
- `docs/tasks.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/authorization.md`
- `docs/audit.md`
- `docs/privacy.md`
- `services/api/app/auth/authorization.py`
- `docs/sources.md`
- `docs/acceptance/T14_file_storage.md`
- `docs/storage.md`
- `services/api/app/storage/__init__.py`
- `services/api/app/storage/local.py`
- `services/api/app/storage/models.py`
- `services/api/app/storage/protocol.py`
- `services/api/app/storage/schemas.py`
- `services/api/app/storage/service.py`
- `services/api/app/storage/store.py`
- `services/api/app/storage/validation.py`
- `services/api/storage_alembic.ini`
- `services/api/storage_migrations/env.py`
- `services/api/storage_migrations/versions/0001_storage_t14.py`
- `tests/security/storage/conftest.py`
- `tests/security/storage/test_t14_storage.py`
- `tests/unit/storage/test_t14_local.py`
- `tests/unit/storage/test_t14_validation.py`

仅本Task内容，保护原规格、旧迁移/验收、其他66卡及范围外tracked。CHANGELOG/tasks与当前文档同步；随后按持续授权审查暂存并普通提交/推送本分支，远程SHA单独核对。Git保存不代表部署或真实发布。
