# T40 资料权利与独立删除台账验收

2026-10-04源码及合成隔离验收完成；PRIVATE保存以后续实际Git核对为准，真实处理关闭。

## 基线与范围

PRIVATE 0bcb69edeaceb1993af31318634c2fd2882038e3/768tracked，codex/t40-data-rights-restore-ledger；初工作区/索引为空。必读治理/原规格/docs01–05/相关模块已核，代码前冻结[契约](../data_rights.md)。22旧路径允许、746其他tracked保护，旧head/原规格/M0/历史保持。

## 实际检查

- `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/unit/privacy_rights -q --tb=short`：30 passed/2.73s/exit0。新unit+契约同Python `-m pytest tests/unit/privacy_rights tests/contracts/test_t40_rights_contract.py -q --tb=short`：41 passed/3.98s/exit0（30pure/11contract），最终全部包含在下面713相关检查内。

- 同Python `-m pytest tests/unit/auth tests/unit/storage tests/unit/changes tests/unit/jobs tests/unit/privacy_rights tests/contracts -q --tb=short`：最终713 passed/1 skipped/61.60s/exit0/1既有warning；此前702 passed/1 skipped/51.30s是新契约增加前轮，不与最终重复相加。skip是旧T14实际Windows symlink权限winerror1314。

- `.cache\run-web-checks.ps1 -TaskId T40`：实际`scripts/web.ps1 -Action test/typecheck`，743 passed/46files/24.08s、Vue TypeCheck exit0；demo1.47s/auth1.99s Build各131modules/exit0。前端无本Task源码变化，auth546.48kB/ignored cache外根outDir提示保持。

- 十二profile逐个同Python `scripts/generate_contracts.py --profile <foundation/identity/public_catalog/admin/admin_review/profiles/assessments/plans/revisions/notifications/qa/rights> --check`均exit0；`scripts/verify_contract.py`M0一致/exit0；`scripts/verify_originals.py`两原文UNCHANGED/exit0。十一旧profile与旧DDL字节保护。

- 实际PG统一使用`.cache\t23-postgres\run-tests.ps1 -PytestArguments @(paths...,'-q','--tb=short')`，专用loopback55438/study_t23_20261003，每个测试新rights_t40和ledger_t40隔离schema；无真实数据或外部供应商。第一PG2轮进程退出后最终输出未采集，明确不计入通过证据。已采集`tests/integration/privacy_rights/test_t40_rights.py`首2failed/35.79s，focused core1failed/18.39s：新删除running时提前清scope违反SQL不可变约束；改同completed flush后2 passed/34.77s。

- 实际新safety/HTTP首collection1error/2.03s：新harness相对import缺package，仅改绝对import；随后5pass1fail/104.63s，foreign画像测试错误传str而旧契约要SecretStr。实际restore初1fail/19.41s为同一新测试前提。更正后file+restore两节点1pass1fail/52.04s，其中真实备份恢复通过，file测试末错误期望RightsError而实际AuthFlowError403，更正测试断言。随后完整`tests/integration/privacy_rights`14节点13passed1failed/252.08s：继承公共/config正常200不承诺no-store，新harness误用私有safe断言；只修该正常响应断言，缺台账503仍要求no-store。文件删除运行约束等源码缺陷与harness前提区分记录，不删除首次结果。

- 新纯30和契约11、实际PG18是distinct节点，不把下面最终复验或上面早轮重复累加。最终focused包含完整旧备份恢复、全修订/确认/完成/替代历史、版本水位/实际台账链损坏，以及completion审计回滚后的真实文件缺失安全重试；T40其余未改source场景由前完整13pass覆盖。具体最终命令和数量见下条。

- 最终`.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/privacy_rights/test_t40_history_integrity.py','tests/integration/privacy_rights/test_t40_waits.py::test_running_http_factory_blocks_all_traffic_on_missing_latest_anchor','tests/integration/privacy_rights/test_t40_restore.py','-q','--tb=short')`：5 passed/127.04s/exit0/1既有warning，无skip；三新节点+两个原节点复验，实际旧业务备份与原文件恢复、完整旧确认和完成/替代历史导出清理、实际head/chain损坏503/拒重放、completion审计回滚后文件已缺安全重试、运行中全部流量屏障。

- 最终`.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/security/auth/test_csrf_http.py::test_logout_revokes_on_server_clears_secure_cookies_and_repeated_request_is_401','tests/security/privacy/test_service.py::test_adult_confirmation_and_idempotent_owner_withdrawal','tests/integration/authorization/test_roles_cache_execution.py::test_role_lifecycle_is_read_from_database_not_principal_snapshot','tests/security/storage/test_t14_storage.py::test_owner_can_delete_after_core_and_role_revocation_and_retry_physical_failure','tests/integration/changes/test_t34_store.py::test_receipt_and_impact_integrity_is_checked_on_repeat_and_read','tests/integration/jobs/test_t36_store.py::test_notification_durable_dedup_read_cas_and_original_rows','tests/security/grants/test_t09_service.py','-q','--tb=short')`：22 passed/65.24s/exit0/1既有warning，无skip；覆盖旧退出/同意撤回/角色生命周期/私有文件删除重试/影响回执/通知/完整grant服务回归。


- 提交前复核补旧会话轮换精确session_revoked台账接缝，末实际同PG helper `@('tests/integration/privacy_rights/test_t40_history_integrity.py::test_login_rotation_records_exact_previous_session_reduction','tests/integration/auth/test_http_session.py::test_login_rotates_real_previous_session_and_rejects_fixed_attacker_cookie','-q','--tb=short')`：最终2 passed/17.48s/exit0/1既有warning。首1failed1passed/6.06s（新harness错误import），中1failed1passed/18.17s（合成fixture只建session没有identity），后1failed1passed/17.96s（新测试issuer非法下划线）；仅修harness预登记身份/合法synthetic.invalid URL/created_at，新接缝最终留准确旧session引用，旧真实RS256登录轮换保持。源分支条件在运行前自查修为validate后显式guard非None，未把未执行分支称通过。

- 最后该接缝后同Python `-m pytest tests/unit/auth tests/unit/privacy_rights tests/contracts/test_t40_rights_contract.py -q --tb=short`：206 passed/6.03s/exit0/1既有warning，是先前713的子集，不额外累计。最终新PG为18 distinct，相关旧PG22加此处旧轮换1；重复回归轮次不累总数。

## 未执行与已知问题

Lint/Python静态Type Check：无配置入口，未执行；Vue Type Check已执行。T40无UI变更，未执行新浏览器验收（T41另做）；已执行实际HTTP/PG/pg_dump/pg_restore及原文件恢复。真实Keycloak/学生/供应商/采购/法律与正式权利渠道、production SQL权限/TLS/部署/正式备份恢复未执行。Windows旧T14 symlink用例winerror1314跳过，不能宣称无skip。

仅合成专用PG/本地文件维护装配；生产锚点ACL、独立SQL凭据/GRANT-RLS、加密备份/完整RPO-RTO、到期物理备份及ledger清理未验收。无外部cache/vector，不声称清理此类未配置服务；不声称WAL/磁盘安全擦除或全部备份消失。导出10MiB、scope5000行/256KiB和台账10000条有界，超过明确关闭，不截断。锚点或外台账提交后业务失败须可信重放；锚点自身损坏无自动猜测修复。D01用户答待定；D07提议目标被拒绝，替代目标未定；D08确认T50首批34地区×2026登记/小合成夹具，正式审核和发布负责人未定。既有Starlette warning/auth546.48kB构建提示保留。

## 修改文件

- `.gitattributes`
- `AGENTS.md`
- `README.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T40_data_rights.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/data_rights.md`
- `docs/database.md`
- `docs/identity.md`
- `docs/privacy.md`
- `docs/requirements.md`
- `docs/sharing.md`
- `docs/storage.md`
- `docs/tasks.md`
- `packages/contracts/v2/rights/generated.ts`
- `packages/contracts/v2/rights/openapi.json`
- `scripts/generate_contracts.py`
- `services/api/app/api/rights.py`
- `services/api/app/auth/grants/service.py`
- `services/api/app/auth/service.py`
- `services/api/app/auth/store.py`
- `services/api/app/changes/service.py`
- `services/api/app/changes/store.py`
- `services/api/app/privacy/rights/__init__.py`
- `services/api/app/privacy/rights/guard.py`
- `services/api/app/privacy/rights/ledger.py`
- `services/api/app/privacy/rights/models.py`
- `services/api/app/privacy/rights/resources.py`
- `services/api/app/privacy/rights/router.py`
- `services/api/app/privacy/rights/schemas.py`
- `services/api/app/privacy/rights/service.py`
- `services/api/app/privacy/rights/store.py`
- `services/api/app/privacy/service.py`
- `services/api/app/storage/service.py`
- `services/api/rights_alembic.ini`
- `services/api/rights_ledger_alembic.ini`
- `services/api/rights_ledger_migrations/env.py`
- `services/api/rights_ledger_migrations/versions/0001_ledger_t40.py`
- `services/api/rights_migrations/env.py`
- `services/api/rights_migrations/versions/0001_rights_t40.py`
- `tests/contracts/test_t40_rights_contract.py`
- `tests/integration/privacy_rights/conftest.py`
- `tests/integration/privacy_rights/test_t40_history_integrity.py`
- `tests/integration/privacy_rights/test_t40_http.py`
- `tests/integration/privacy_rights/test_t40_restore.py`
- `tests/integration/privacy_rights/test_t40_rights.py`
- `tests/integration/privacy_rights/test_t40_safety.py`
- `tests/integration/privacy_rights/test_t40_waits.py`
- `tests/unit/privacy_rights/test_contracts.py`
