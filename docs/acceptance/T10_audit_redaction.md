# T10 审计与日志脱敏验收

日期：2026-10-03。状态：已完成源码、合成与隔离实库验收；首轮失败及后续修复过程保留，最终命令/结果见下文，真实资料处理和部署关闭。

实施前已核对AGENTS、六份治理文档、API/数据库/身份/隐私/共享模块与T10卡、原始规格；T07与D06产品依赖满足，正式责任/法律/真实处理门槛不解除。只T10，无新依赖、真实资料或部署。

Git基线：a34cf5270a81238b3750f75d046af483262fbdbe；分支codex/t10-audit-redaction，初始工作区/索引干净，230tracked原哈希保存于忽略缓存。代码前冻结[数据契约、范围与验收](../audit.md)，ADR-021。

本记录只汇总本Task实际检查，不引用T09为本次通过。以下保留收敛过程及当时待完成项，最终验收/文档同步见末节；Lint/Python静态类型仍无入口。

## 实际过程

新建专用audit_t10_test空库，PostgreSQL16.15/loopback55438；复用本批自有测试cluster，各专项随机schema，不接生产或旧用户库。.cache/t10-postgres/run-tests.ps1过程注入6个专用测试URL并恢复，凭据只在忽略缓存，不打印/上传。原始输入verify_originals退出0。

本Task新实跑：scripts/web.ps1 -Action test →170 passed/15files；-Action typecheck退出0；分别VITE_APP_MODE=demo/auth及bundled pnpm --dir apps/web run build --outDir ../../.cache/t10-{demo|auth}-frontend-validation →两次退出0。变量以try/finally恢复，前端/依赖未改；cache外outDir正常不自动清空提示，无构建失败。尚无本Task新browser，因HTTP wire/UI无变化。

独立纯安全首轮：`python -m pytest tests/security/audit/test_t10_adversarial.py -m 'not postgres' -q --tb=short` →124 passed/1.37s/exit0。后续只读subprocess probe证实合法extra的foreign request_id会覆盖当前server context，虽未泄漏原msg，仍属关联Bug，已反馈修复并补专项；首轮不据此宣称最终全部安全验收。PG/业务审计接线尚待完成。

追加两条明确攻击后的同独立纯安全命令实际124 passed/2 failed，1.70s/exit1；失败证明合法foreign关联ID覆盖当前server context、触碰旧canonical日期日志延长30天上限。均交实现修复，不把首轮124通过等同最终完成。新增审计flush等待后的权限到期回滚检查，尚待PG接线。

## 已执行的后续专项与失败记录

以下纯测试早期命令的文件尚未加入PG用例；随后明确的`-m 'not postgres'`运行不计被排除的PG为通过。命令中的Python均使用本项目`.venv/Scripts/python.exe`；日志配置组合命令由该维护者的实际回报记录。

| 实际命令/阶段 | 结果 | 解释与修正 |
| --- | --- | --- |
| `python -m pytest tests/security/audit/test_t10_adversarial.py -q --tb=short`，首批纯模型/关联/日历 | 95 passed，0.45s，exit0 | 模型输入、上下文隔离、日历边界；尚无完整日志与PG接线 |
| 同命令，补位置/关键字外部Session | 97 passed，1.17s，exit0 | 证明active caller-owned事务期间不启动另连接失败Writer |
| 同文件纯日志矩阵 | 124 passed，1.37s，exit0 | 当时矩阵通过；后来发现两项新攻击，不能称安全检查全过 |
| 同文件补foreign关联ID与触碰日志日期 | 124 passed / 2 failed，1.70s，exit1 | 实际暴露服务器关联ID被extra替换、旧日期文件mtime延长上限；均在当前T10实现修正 |
| 同文件补scan_limit与上述修正 | 127 passed，1.28s，exit0 | 实际扫描次数有界，包括不匹配文件；按canonical UTC日期清理 |
| 同文件补无上下文`_audit_server_request_id`攻击 | 127 passed / 1 failed，1.05s，exit1 | 不可信内部样式extra触发ValidationError；改为只信任服务器ContextVar、先清原msg/args/异常再解析extra |
| `python -m pytest tests/security/audit/test_logging_config.py tests/security/audit/test_t10_adversarial.py -m 'not postgres' -q` | 131 passed / 22 deselected，exit0 | 128纯攻击＋3真实dictConfig/Uvicorn配置及无副作用子进程检查；22PG未在此命令执行，不计通过 |

首次完整独立PG/安全命令为：

```powershell
& '.\.cache\t10-postgres\run-tests.ps1' -PytestArguments @('tests/security/audit/test_t10_adversarial.py','-q','--tb=short')
```

- 首轮实际142 passed / 8 failed，57.83s，exit1。一个role回滚用例把夹具早已存在的成功事件当成本次成功；两个拒绝helper只捕获AuthorizationError而实际安全父类为AuthFlowError；五个PG锁等待用例重复读取同一事务的统计快照，未观察到线程后来形成的真实阻塞。修正只在测试基线、异常父类及autocommit/刷新统计快照，未放宽安全断言；这八项不能冒称实现Bug或已通过。
- 修正后同命令实际150 passed，16.50s，exit0：128纯测试＋22真实PG测试。包含五种业务写的必需audit INSERT失败回滚、失败Writer在原账户锁释放后才启动、foreign/missing对象拒绝不保存请求ID、当前operations/MFA/provenance与清理边界、六项真实PG表锁阻塞后会话/角色/管理员强度到期使read/purge回滚。PG用例只访问本Task专库随机schema；外部网络禁止。
- 随后只读审查发现登录成功auditflush新I/O可能跨登录context截止：旧代码只在建立会话前复核。实现最小新增事务内最终clock/context/sessiondeadline复核，以及已消费state后换码前fresh检查；无JWT/schema/wire变化。新增回归测试首跑前修复已经落盘，因此本记录没有旧实现下这三项红测，不补造“先失败后通过”。

新登录专项实际命令：

```powershell
& '.\.cache\t10-postgres\run-tests.ps1' -PytestArguments @('tests/security/audit/test_t10_adversarial.py::test_real_signed_login_audit_wait_never_mints_session_after_deadline','-q','--tb=short')
```

结果3 passed，2.59s，exit0。合成IdP用真实RS256签名和PKCE、httpx.MockTransport；真实PG pending auditflush后推进clock。consume阶段context到期不向token端点发请求；complete阶段跨context300秒/绝对session3600秒截止均不提交新会话或成功完成事件，state保持已消费。仅离线协议验收，不是真实Keycloak连接。

加入这三项后，最终独立文件同完整helper命令实际153 passed，19.77s，exit0（128纯＋25PG）；独立文件已冻结。此153不是项目整套通过数量。

### 其他维护者本Task实际结果

```powershell
& '.\.cache\t10-postgres\run-tests.ps1' -PytestArguments @('tests/security/audit/test_t10_service.py','-q','--tb=short')
```

后端基础21 passed，14.74s，exit0（此前同命令21 passed，13.72s）。增量迁移、旧账户/会话保留与降到0005再升级、无审计引用FK、固定数据库白名单、同事务提交/回滚、隐私失效/共享生命周期与默认审计读取关闭实际检查；显式compileall退出0，不等同Lint/静态类型检查。

```powershell
& '.\.cache\t10-postgres\run-tests.ps1' -PytestArguments @('tests/integration/auth/test_persistence.py','tests/security/auth/test_postgresql.py','tests/security/authorization/test_postgresql.py','-q','--tb=short')
```

主代理兼容专项54 passed，1既有warning，45.92s，exit0；必要current-head/table断言按0006增量更新，不改旧迁移。本Task新的前端170/15files、Type Check、demo/auth两Build命令与结果见上文，未修改前端实现或依赖。

## 当前源码与审查文件

源码行为与范围见[当前审计契约](../audit.md)。当前已审查的新源码/测试为：

- `services/api/app/audit/{__init__,schemas,context,retention,logging,models,service}.py`。
- `services/api/auth_migrations/versions/0006_audit_t10.py`、`config/logging/identity.json`。
- `tests/security/audit/{conftest,test_t10_service,test_t10_adversarial,test_logging_config}.py`。
- 当前改动接点为identity factory/HTTP安全与请求上下文、auth/store/service/authorization、privacy/service、auth/grants/service、认证迁移env和三个必要旧实库head断言；旧0001–0005与M0迁移/夹具、原始规格、旧验收和公开wire/生成契约保留。

此清单用于当前审查，不是最终暂存manifest或完整回归通过声明。factory全局日志配置副作用已在最后审查提出，当前代码已移除自动调用；独立factory隔离回归与其他最后日志修正的结果仍待补充。运行入口必须显式加载封闭日志配置。

## 首轮完整回归实际失败

主代理实际命令：

```powershell
& '.\.cache\t10-postgres\run-tests.ps1' -PytestArguments @('tests','-q','--tb=short')
```

session2213实际结束：19 failed / 1641 passed / 1既有warning，395.30s，共1660项，exit1。19项均为T10新日志测试捕获为空：8项knownlogger、8项malformed extra、固定operation、合法foreign关联ID和无上下文extra；本轮PG用例未失败。旧M0迁移的fileConfig会禁用此前存在的logger，T10显式configure_logging未重新启用，独立新进程专项通过未覆盖该既有进程状态。

正在本Task最小修正：日志配置恢复known logger的disabled状态，补已禁用进程状态回归；独立日志捕获夹具同时保存/恢复原disabled、handlers、propagate和level，不污染其他测试。该修正不会改旧M0迁移或数据。此处不预宣称复验通过，后续实际完整回归结果另追加。

独立捕获夹具的disabled状态保存/恢复修改后，同文件helper命令另一次实际153 passed，19.86s，exit0。该新进程专项不能替代旧M0迁移已禁用logger状态的回归，更不能替代整套复验。

## 收敛前待完成记录与未执行项目（历史过程）

- 全项目首轮Python回归已实际失败（19/1641）；必要日志修正及最终专项/完整复验待主代理追加。当前状态保持[~]；不能以153/21/54等专项替代整套必需检查。
- Lint和Python静态Type Check未执行：本项目没有已配置入口/工具；compileall只是语法/导入编译检查。
- 本Task新browser/视觉检查未执行：没有前端实现或HTTP wire变化；前端单测、Type Check和两Build已实际重跑，历史T09浏览器结果不算T10通过。
- 真实IdP/管理员MFA与恢复、正式controller/告知及法律复核、生产TLS/部署、外部日志收集器/备份留存和删除传播未执行或未实现，不作为本轮通过。正式用户处理和未来审核/导出/删除业务仍关闭。
- 最终原文/冻结旧文件/生成契约/文档链接/范围/暂存与远程SHA检查、CHANGELOG/tasks完成同步和提交推送尚待主代理执行记录；不在本记录中预宣称成功。不启动T11。

## 最终实际验收与文档同步

| 实际命令 | 结果 |
| --- | --- |
| `.cache/t10-postgres/run-tests.ps1 -PytestArguments @('tests','-q','--tb=short')` | 最终1662 passed、1既有warning、398.14s、exit0；无skip，所有专用PG变量实际注入 |
| `python -m pytest tests --collect-only -q -m postgres` | 365/1662 PG用例标记收集，1297其他；收集计数不是另一次执行，执行结果以上行为准 |
| `python -B -m pytest tests/security/audit/test_logging_config.py tests/security/audit/test_t10_adversarial.py -m 'not postgres' -q --tb=short` | 修正后133 passed/25 PG deselected，4.26s/exit0；独立fresh process测试实际JSON/Uvicorn配置、disabled恢复和默认factory隔离 |
| `python -m pytest tests/security/audit/test_t10_service.py -m 'not postgres' -q` | 2 passed/19 PG deselected；新增PG依赖测试均显式标记 |
| `scripts/web.ps1 -Action test` / `-Action typecheck` | 本Task新170 passed/15files；Type Check exit0 |
| 进程VITE_APP_MODE=demo/auth，bundled pnpm `--dir apps/web run build --outDir ../../.cache/t10-{demo\|auth}-frontend-validation` | 两Build实际exit0，变量恢复；前端源码没有改动 |
| `python scripts/generate_contracts.py --profile identity --check`；默认`--check`；`python scripts/verify_contract.py`；`python scripts/verify_originals.py` | 两profile/M0契约和两原始输入通过，identity v2.t09/foundation/生成LF保持 |
| `python -X utf8 .cache/t10-scope.py`；`.cache/t10-validate.py`；`git diff --check`及实际暂存diff审查 | 39路径（24旧改/15新）、206范围外tracked及66其他Task卡保护；历史日志/ADR/旧迁移/验收保留；Python内存语法编译、JSON和本地链接检查单列最终输出 |

首整套19failed/1641passed已定位为旧迁移禁用logger后显式helper没有恢复，修正`disabled=False`及实际audit/engine子logger，补从disabled+ERROR进程状态的输出回归；日志fixture保存/恢复全部修改状态。移除默认factory自动配置，fresh process验证关闭/schema factory不改变进程logger且不导入数据库/M0。源码冻结后整套复验通过，不把首轮结果抹掉。

未执行：Lint（前端无lint script/Python无ruff）、Python静态类型（无mypy/pyright）；本Task新browser（HTTP wire/UI无变化，历史T09浏览器不能算本次）；真实Keycloak/MFA/恢复/生产TLS/GRANT/RLS、正式主体/告知/法律审查、真实学生资料、生产收集器/备份/恢复删除传播和部署。已有Starlette AnyIO alias弃用warning未顺带修复。审核发布、导出、删除仅固定动作probe，相应业务尚未实现；可信维护SQL、其他进程和后来附加handler不在代码保证范围。

CHANGELOG/tasks及受影响文档已同步T10源码完成状态，历史失败记录保留；源码提交/普通push按持续授权执行并在用户报告核对远程。验收保存后进入已授权T11，不能以推荐擅自越出T20批次。

## 最终变更文件

最终文档/范围脚本实际退出0：39路径、24旧改/15新、206范围外tracked和66其他主Task卡保留，239个本地文档链接存在，23个Python文件内存语法编译及日志JSON解析通过；旧CHANGELOG和ADR历史、生成契约LF保留。`git diff --check`退出0，仅现有LF/CRLF提示。完成文档脚本曾给出缓存脚本`\|`转义SyntaxWarning，完成逻辑正常退出0；不把它当应用测试失败或Lint结果。

39路径（24旧改/15新），无依赖新增：

- `AGENTS.md`
- `README.md`
- `config/identity/README.md`
- `config/logging/identity.json`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T10_audit_redaction.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/audit.md`
- `docs/authorization.md`
- `docs/database.md`
- `docs/identity.md`
- `docs/privacy.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `services/api/app/api/identity.py`
- `services/api/app/audit/__init__.py`
- `services/api/app/audit/context.py`
- `services/api/app/audit/logging.py`
- `services/api/app/audit/models.py`
- `services/api/app/audit/retention.py`
- `services/api/app/audit/schemas.py`
- `services/api/app/audit/service.py`
- `services/api/app/auth/authorization.py`
- `services/api/app/auth/grants/service.py`
- `services/api/app/auth/http_security.py`
- `services/api/app/auth/service.py`
- `services/api/app/auth/store.py`
- `services/api/app/privacy/service.py`
- `services/api/auth_migrations/env.py`
- `services/api/auth_migrations/versions/0006_audit_t10.py`
- `tests/integration/auth/test_persistence.py`
- `tests/security/audit/conftest.py`
- `tests/security/audit/test_logging_config.py`
- `tests/security/audit/test_t10_adversarial.py`
- `tests/security/audit/test_t10_service.py`
- `tests/security/auth/test_postgresql.py`
- `tests/security/authorization/test_postgresql.py`
