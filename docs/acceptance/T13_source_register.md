# T13 来源登记验收

2026-10-03，状态：源码、合成及隔离实库已完成。分支codex/t13-source-register；基线fb1554fd31f30181def698148ebaf6eb643fcaa4，268tracked，初始工作区/索引干净。仅T13相关改动，D03正式责任人待答且真实来源仍关闭。

先读AGENTS/六必读/API/数据库/authorization/audit/data_strategy、原始两规格及相关auth/catalog代码，冻结[sources契约、范围与测试](../sources.md)和ADR-024。URL仅元数据，没有fetch、研究文件导入、真实注册或事实发布。

## 实现与边界

独立SourceBase两表、catalog新0003；根与版本复合FK，声明/三许可/basis/ref/服务器责任和复查期限分开。SourcePolicy默认关闭，真实路径需正式负责人配置；本人修订防隐式责任转交。SourceService同Session/TX当前data_admin+签名MFA，expected revisions防覆盖，成功最小administrator.action审计，flush后重验时效。历史metadata可读，enabled快照不能代替T15/T19当前许可验证。旧require_capability、M0/auth0006/identity v2.t09与前端保持；POLICY_VERSION T13_owner_v2失效旧缓存。

## 实际检查

专用空库source_t13_test，loopback55438/PG16.15，每例随机schema；只清理本轮schema。helper注入/恢复9个专用URL，凭据仅忽略缓存且未打印。

| 实际命令 | 本轮结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe -B -m pytest tests/unit/sources/test_t13_schemas.py -q` | 最终31 passed，0.76s，exit0；首30passed后补协议case回归 |
| `.\.cache\t13-postgres\run-tests.ps1 -PytestArguments @('tests/integration/sources','-q','--tb=short')` | 首轮7passed/11failed25.78s exit1；修复新ORM跨metadata string FK与helper捕获AuthFlowError后，18passed21.67s exit0 |
| 同helper `tests/security/authorization tests/integration/authorization tests/security/audit tests/unit/catalog tests/unit/dates tests/integration/catalog tests/integration/dates -q --tb=short` | 542passed/1已有warning，143.65s，exit0 |
| `.\.venv\Scripts\python.exe -m pytest tests/contracts tests/security/test_mode_isolation.py -q --tb=short` | 333passed/1已有warning，13.89s，exit0 |
| `.\.cache\run-web-checks.ps1 -TaskId T13` | 前端170passed/15files8.23s、Type Check、demo/auth两Build全部exit0；恢复PATH/VITE_APP_MODE |
| `.\.venv\Scripts\python.exe scripts/generate_contracts.py --check` 及 `--profile identity --check` | 两profile无drift，exit0 |
| `.\.venv\Scripts\python.exe scripts/verify_contract.py`、`scripts/verify_originals.py` | M0 wire一致/两原始输入原字节不变，均exit0 |

来源PG18涵盖版本历史/责任与真实关闭、角色/签名来源与MFA、caller rollback/审计失败、全部mapper错engine零连接、并发版本冲突、复合FK/CHECK、坏持久URL安全拒绝，以及成功audit INSERT真实锁等待后session/role/MFA/新许可期限重验。fixture数据库中固定的合成签名声明不是本轮真实Keycloak联调。两个旧T12历史测试明确002target；0003升级/重复与隔离降级恢复保留M0/auth/catalog/date既有数据。

## 变更文件与文档

28路径（16旧/12新）：旧AGENTS/README/requirements/architecture/database/api/tasks/CHANGELOG/DECISIONS/authorization/audit十一文档，authorizer、catalog store/DateStore/env及旧T12测试；新docs/sources.md/本验收、admin namespace/sources六文件、0003、unit一/PG两测试。无新依赖/HTTP/生成产物/UI/原始规格/旧迁移/研究修改。CHANGELOG/tasks及受影响文档、ADR-024同步。

## 未执行与已知限制

Lint/Python静态类型未执行：项目没有对应入口；Vue Type Check实际执行。browser无UI变化未执行；全项目所有PG不重复跑，只上述相关选择。真实Keycloak、法律/正式负责人审核、生产GRANT/RLS/TLS、生产备份/恢复、部署、真实招生来源或证据人工抽查未执行。SourceStore是可信内部入口而非恶意SQL防护，无DB不可变trigger。D03责任人与T49 TTL待答，产品配置不是法律许可证明；真实处理和发布门槛保持。

范围检查：`.\.venv\Scripts\python.exe -B .cache/check_task.py T13`退出0，28路径/16旧/12新、252范围外tracked哈希、66其他卡、247本地链接、15Python内存编译、历史日志/ADR/凭据形态与生成LF通过；临时数据库/日志/构建均未纳入提交。普通push并核对远程SHA后进入已授权T14。
