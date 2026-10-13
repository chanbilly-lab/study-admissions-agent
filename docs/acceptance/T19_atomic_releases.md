# T19 不可变发布与撤回验收

2026-10-03源码与合成隔离实库验收完成，codex/t19-atomic-releases基线b3cab25baf34951eab16547d382e9e3ddc8e3fa4；371tracked/初始干净。先读必读/原始两规格/docs01–05与模块代码，冻结[契约](../releases.md)。以下为本Task真实结果，不冒充正式事实发布。

## 已执行相关回归

- `.cache/t19-postgres/run-tests.ps1 -PytestArguments @('tests/unit/reviews','tests/integration/reviews','tests/unit/facts','-q','--tb=short')`：89 passed165.71s exit0，无skip/warning；仅所列范围，非全项目回归。
- `.venv/Scripts/python.exe -m pytest tests/contracts tests/security/test_mode_isolation.py -q --tb=short`：333 passed20.19s exit0，1既有Starlette/anyio warning。
- `.cache/run-web-checks.ps1 -TaskId T19`：170 passed/15files9.43s；Vue Type Check、demo/auth两Build exit0。outDir常规warning，构建产物仅忽略缓存。
- `.venv/Scripts/python.exe scripts/generate_contracts.py --check`、`--profile identity --check`、`scripts/verify_contract.py`、`-X utf8 scripts/verify_originals.py`：全部exit0，原规格字节不变。

Lint/Python静态Type Check无入口未执行；browser/UI未变未执行；全项目PG、POSIX、真实正向发布/人工领域事实/资料权利、正式身份/法律/SQLGRANT/RLS/清理备份/部署未执行。test_fixture不能作为正式验收事实；真实未审/缺失不能由模型或DEMO填补。T15任务外时效记录保留。

实施契约澄清已在代码前同步：每dataset/year唯一当前published，替代需显式CAS；test环境verified身份加demo数据集合法，正式verified数据集/production不能接test_fixture。member只保存fact/片段有限快照及source/file指纹。

专项纯测试：`.venv/Scripts/python.exe -B -m pytest tests/unit/releases -q` 首轮23 passed/1 failed+1warning（本新fixture误将安全hashhelper错误预期为DTO ValidationError、测试使用instance model_fields弃用）；改本新测试后最终24 passed1.65s exit0无warning，3模块内存compile exit0。

## 发布专项首轮（未代替最终验收）

`.cache/t19-postgres/run-tests.ps1 -PytestArguments @('tests/integration/releases','-q','--tb=short')` 首轮18 passed/4 failed283.51s exit1：维护改父Offering.entry_year后的旧T15安全503与本新测试409预期不符；三项post-idem双成员审计barrier在5秒内未到，诊断中，不能记时效通过。先定位worker错误/实际处理时间，修本新测试harness，不擅改旧模块。最终完整结果待复验。

源码就绪后Python stdin：releases六模块+env/0001共8模块compile、import Service/Store、5表assert exit0。末尾同fresh now重验locked角色/会话/签名MFA及全部source/file期限、无后续SQL；结构审查不代替上述真实等待测试。

四失败选择项复验：`.cache/t19-postgres/run-tests.ps1 -PytestArguments @('tests/integration/releases','-k','exact_dataset or real_audit_wait','-q','--tb=short')`：4 passed/18 deselected64.48s exit0。维护改父year允许既有安全503并核零发布；三等待harness改有界20s arrival且会暴露worker早失败，均实际观测pg_stat_activity Lock/pg_blocking_pids、推进Fakeclock后拒绝并整笔回滚，证实原5s测试前提过短。生产源码未因此改动。最终完整22项正在执行，不能用此4项宣称全过。

最终纯重复执行24 passed1.67s exit0（不与1.65s旧结果相加）；store交接后的4modulecompile/import exit0。五表/partial index共6条PostgreSQL DDL compile exit0，仅结构检查非迁移实测。

## 最终验收与文件范围

最终完整PG同命令：22 passed289.46s exit0，无skip/warning。首18/4和选择4/18deselected保留，不相加。源ready后冻结，未因四测试前提修正修改旧/新生产源。已验证唯一头/固定成员、审计/outbox/true deferredCOMMIT全回滚、自然去重/receipt TTL、独立来源公开权利、实际并发/CAS、多文件首成员时效、撤回/替代与历史不可变/迁移往返；正向均明确DEMO test_fixture。

23路径（9旧/14新），完整清单：

- `AGENTS.md`
- `README.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/tasks.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/api.md`
- `docs/database.md`
- `docs/releases.md`
- `docs/acceptance/T19_atomic_releases.md`
- `services/api/app/releases/__init__.py`
- `services/api/app/releases/schemas.py`
- `services/api/app/releases/validation.py`
- `services/api/app/releases/models.py`
- `services/api/app/releases/store.py`
- `services/api/app/releases/service.py`
- `services/api/releases_alembic.ini`
- `services/api/releases_migrations/env.py`
- `services/api/releases_migrations/versions/0001_releases_t19.py`
- `tests/unit/releases/test_t19_validation.py`
- `tests/integration/releases/conftest.py`
- `tests/integration/releases/test_t19_releases.py`

`.venv/Scripts/python.exe .cache/check_task.py T19`：23路径、362旧tracked保护、66其他任务卡/历史不变、300本地链接、11Python内存compile及范围/凭据检查exit0；CHANGELOG/tasks一致。
