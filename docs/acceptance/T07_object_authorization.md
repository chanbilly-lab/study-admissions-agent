# T07 · 对象级授权基础

实施前日期：2026-10-03，Asia/Hong_Kong。Git基线`0b09eaefe93ba3f445f8c42e4c58dd34ec7226bb`，工作区/索引为空；工作分支`codex/t07-object-authorization`。先读取治理、原规格、相关代码并冻结本契约，再实施。只执行T07，验收后按持续授权保存源码并停止。

## 实施前契约

1. `Principal`是服务器内部冻结对象：UUID user/session、当前有效roles、is_synthetic、绝对expires_at和授权上下文摘要。只从经验证Cookie及数据库角色生成，每次对象访问/缓存/执行重新验证，忽略传入快照中的roles。IdP roles、客户端body/query/header owner/role、模型和前端角色都不能赋权。旧账户默认无角色，登录/退出保持有效但不自动获得业务权限。
2. 角色固定`student/data_admin/operations`，由受信任服务端登记，具granted_at、可空expires_at和revoked_at；角色缺失、未生效、到期、撤销均拒绝。student只走本人私有资源通道；data_admin管理公共事实需当前应用角色和T06签名强度，两者缺一不可；operations只允许非个人的`operations.status`能力。混合角色可以凭student访问本人，但任何管理角色都不能跨用户读取。未实现的T09共享grant保持关闭。
3. 增量`0003_auth_t07`新增`auth_user_roles`和`auth_owned_resources`。后者仅UUID/type/owner/state/version/is_synthetic/parent权限元数据，无成绩、画像、计划内容、文件路径/字节。kind固定profile/plan/attachment/export/job；profile/plan为根，parent为空；附件/export/job必须指向同owner且active的profile/plan根，复合FK防跨owner父关系。id/type/owner/parent/synthetic不可由通用修改命令改变。未来业务必须同事务登记/关联唯一归属依据，不保留可自由修改的owner副本。
4. 固定动作矩阵：所有kind允许student-own read/list；write仅profile/plan；download仅attachment/export；export仅profile/plan；execute仅job。未知kind/action或不支持组合拒绝。列表SQL按owner/type/active/parent/角色过滤后才计数/分页，禁止先读取所有用户再Python删记录。无认证401、缺功能角色403、foreign/missing/deleted对象统一404；受限元数据版本touch使用expected_version，旧版本409。不实现真实业务编辑。
5. 授权读取、受限元数据写入及本地同步执行使用同一数据库事务读取当前会话/角色/对象，锁账户/角色/资源及父对象，锁后复核当前时效；角色撤销入口遵循同一账户锁顺序。执行回调使用同一SQLAlchemy Session，检查与本地提交一致，不用T06另连接permission callback冒充原子性。延迟引用只是服务器内部对象，不是HTTP凭据；执行时重新读权限/归属/状态。不建立持久worker、跨系统副作用事务或owner迁移API。
6. 缓存scope由重新授权的actor/session、当前roles/context、固定policy版本、kind/action、资源ID/version和明确过滤条件组成；缓存命中前重验，不把key当许可。不引入Redis/缓存系统或浏览器私有持久缓存。
7. 默认/production入口、T06 session wire、OpenAPI/TS/UI保持；`private_business_available=false`，不挂正式画像/计划/附件/导出/作业/权限管理端点。测试实例可添加probe来实际验HTTP依赖、CSRF和SQL授权，但probe绝不进运行factory/schema。T08准入、T09grant、T10审计、T24画像、T30计划等未启动。`app/planning.py`是既有M0模块，禁止创建同名planning包遮蔽它。

## 修改范围

auth/authorization.py、角色/资源ORM、store/service最小集成、新0003迁移、轻薄HTTP认证依赖与显式identity assembly；新独立授权单元/集成/安全/PG测试，少量受新head/table集合影响的现有断言。同步AGENTS/README、tasks/CHANGELOG/ADR-018、API/数据库/架构/需求/身份运行文档。无新依赖、不改前端源码/默认契约、不改原始输入、docs/01–05、旧验收、M0及0001/0002迁移。

## 实施前验收矩阵

- 两合成学生逐kind覆盖列表/计数/分页/单对象、父子附件、导出、作业执行；跨用户内容/存在性/计数不泄露，missing与foreign均404，无副作用。
- 匿名、无role、角色到期/撤销、账号禁用、会话到期/撤销、伪造Principal.roles/user/session、客户端owner/role、未知动作/type及错误parent均拒绝。混合student+admin仅本人；管理和运营默认不能看学生资料。
- 管理能力要求应用data_admin及当前T06强度，普通客户端/缺/旧proof/禁用策略拒绝；operations只有固定状态能力。真实MFA配置仍未验收。
- standalone/mounted HTTP probe复用T06中央CSRF/Origin、统一错误/request_id/no-store，body/query不接受owner/role；实际运行schema不含probe/新业务路径。
- 缓存跨用户/会话/动作/类型/版本/过滤不共用，缓存命中仍重读权限；引用在角色撤销/对象删除/父对象失效/账户禁用/会话撤销后拒绝，错误不执行operation。
- 新独立PG验证0002→0003保留会话/CSRF/assurance、角色FK/白名单/时效/唯一约束、同owner父FK、真实SQL过滤及角色撤销与本地执行的串行化；用barrier/实际锁等待证明竞态，不凭sleep猜测。未升级启动503且DDL0，旧迁移/M0保留。新cluster不访问旧验收库。
- 执行相关Unit/Integration/全回归、前端Unit/Type Check/M0和auth Build、当前浏览器回归、契约/语法/原文/范围/历史/文档/暂存检查。Lint或Python静态类型入口不存在时明确未执行，不称历史结果为本轮通过。不进行真实用户/Keycloak/TLS/部署/事实发布。

## 实际验收

本轮先冻结契约和范围，再实现及真实测试；最终整合验收已完成。当前身份schema仍v2.t06且七路径不变，foundation和M0契约未漂移；无前端/依赖改动。

### 隔离环境及运行

新PostgreSQL16.15 cluster位于`.cache/t07-postgres/run-21b7e2e7ca8849549cb78c2e6c19ab65/cluster`，仅监听127.0.0.1:55437；新三个空库auth_t05_test/auth_t06_test/auth_t07_test。只复用已核验的程序，未使用旧T01/T05/T06 cluster或真实库/用户。测试每次创建并清理随机schema，外部socket/DNS拒绝；生产样式测试中的false字段也是隔离随机合成存根，不代表真实注册或数据审核。配置/URL/临时secret只在ignored.cache，不推送。

本轮`.cache/t07-postgres/run-tests.ps1`读取ignored environment.json并只向子进程注入TEST_POSTGRES_URL、T06_TEST_POSTGRES_URL、T07_TEST_POSTGRES_URL。它是本次隔离辅助，不是部署/永久测试依赖；重新运行需新建本机专用空库、按三个固定库名注入受保护URL，pytest会自建随机schema。无URL会明确失败而不跳过必需PG项。

```powershell
# 非PG合成专项（SQLite仅替身）
.\.venv\Scripts\python.exe -m pytest tests/integration/authorization -q --tb=short
# 配置本机独立 auth_t07_test，T07_TEST_POSTGRES_URL须postgresql+psycopg且127.0.0.1
.\.venv\Scripts\python.exe -m pytest tests/security/authorization -q --tb=short
# 完整回归须同时配置三个专用库URL，绝不能指向生产/已有业务库
.\.venv\Scripts\python.exe -m pytest -q --tb=short
```

真实维护迁移需另外受保护配置和备份流程，`alembic -c services/api/auth_alembic.ini upgrade head/current`当前目标0003；应用启动不做DDL/seed。新迁移往返、旧M0/认证行保留由测试实际执行，未在未知用户库执行降级。

### 精确变更清单

33个路径（17旧文件修改、16新增），其余148个基线跟踪文件原字节不变；两个原始输入、docs/01–05、旧迁移/验收、研究资料、前端和依赖保持。

- `AGENTS.md`
- `README.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T07_object_authorization.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/authorization.md`
- `docs/database.md`
- `docs/identity.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `services/api/app/api/identity.py`
- `services/api/app/auth/authorization.py`
- `services/api/app/auth/dependencies.py`
- `services/api/app/auth/http_security.py`
- `services/api/app/auth/models.py`
- `services/api/app/auth/service.py`
- `services/api/app/auth/store.py`
- `services/api/auth_migrations/versions/0003_auth_t07.py`
- `tests/integration/auth/test_persistence.py`
- `tests/integration/authorization/__init__.py`
- `tests/integration/authorization/conftest.py`
- `tests/integration/authorization/test_http_dependencies.py`
- `tests/integration/authorization/test_owned_service.py`
- `tests/integration/authorization/test_roles_cache_execution.py`
- `tests/security/auth/test_postgresql.py`
- `tests/security/authorization/__init__.py`
- `tests/security/authorization/conftest.py`
- `tests/security/authorization/test_concurrency.py`
- `tests/security/authorization/test_http_postgresql.py`
- `tests/security/authorization/test_postgresql.py`
- `tests/security/authorization/test_production.py`

### 实际命令与结果

- `.\.venv\Scripts\python.exe -m pytest tests/integration/authorization -q --tb=short`：修后125 passed，退出0；后续高风险补测以最终整合记录为准。
- `& '.\.cache\t07-postgres\run-tests.ps1' -PytestArguments @('tests/security/authorization','-q','--tb=short')`：首轮56 passed，列表补测第二轮61 passed，均退出0；最终窗口/production补测待最终记录。
- 同helper `-PytestArguments @('tests/unit/auth','tests/security/auth','tests/integration/auth','tests/contracts/test_identity_contract.py','-q','--tb=short')`：450 passed，退出0。
- 同helper `-PytestArguments @('-q','--tb=short')`：第一轮1115 passed，退出0；该轮未包含最后追加的生产/登记事务/新窗口边界，最终全回归将另记。
- `.\scripts\web.ps1 -Action test`：62 passed，退出0；`-Action typecheck`退出0；`-Action build`默认M0退出0，另显式VITE_APP_MODE=auth相同build退出0。
- 当前进程PATH加入bundledNode后 `node scripts/auth_t06_browser_smoke.mjs`：当前T06浏览器回归12 checks，退出0；Edge154.0.4258.48，新本机合成上下文，页面错误/外网请求0。隔离证书/私钥/SQLite在ignored .cache/t06-browser/49ffdd01-6019-4354-a3cd-18283a679c56，脚本已停止自有helper；没有复用旧T05“无退出按钮”断言。
- `.\.venv\Scripts\python.exe -X utf8 scripts/verify_contract.py`、`scripts/generate_contracts.py --check`及`--profile identity --check`：全部退出0，M0一致，两生成profile原字节不变。
- `python -X utf8 scripts/verify_originals.py`：退出0，两份原文未变；`uv pip check`退出0，35依赖兼容；最终所有变更Python语法/范围/历史/文档/暂存审查在下方最终记录。

### 实際发现与修复

初专项118 failed/5 passed：新fixture误用不存在Authorizer.get_principal，改为AuthService；直接service异常被原foundation通用500处理，identity增加安全AuthFlowError handler，测试移除自制翻译而实际验证应用。慢cache次要角色到期新2例真实失败，修final上下文key重算后125通过。审查发现T06 joined锁与T07账户优先锁风险，最小统一AuthUser→AuthSession；PG真实Lock等待验证退出/撤权串行。列表初实现未锁窗口及父，补锁后又发现重填窗口可能未锁新候选，采用bounded稳定窗口，等待后重读scope/count；最终新窗口实锁负例验证后才验收。历史测试只更新当前head/table集合断言，无旧迁移/验收改写。

读取辅助最初使用了错误的app相对路径，以及rg误把PowerShell参数作为flag，均明确失败后改正确路径/命令；未将这两项视为应用测试通过。一个已有Starlette/AnyIO DeprecationWarning保留，不为T07升级依赖。

### 未执行与限制

Lint没有配置脚本/规则，Python静态Type Check没有入口/安装工具（ruff/mypy/pyright检测均false），未执行；AST/py_compile不冒称类型检查。TypeScript已实际vue-tsc通过。真实Keycloak/账号/tenant、管理员MFA/recovery、生产TLS、Keycloak SSO/所有设备退出、业务部署/公众发布、真实学生/招生资料均未执行，范围外。T08准入、T09grant、T10审计、领域画像/计划/附件payload/导出/持久worker/跨系统副作用事务未实现；current public私有业务仍false。内部Principal不是HTTP凭据，可信callback不是SQL沙箱；无RLS或DB immutable trigger，不防恶意维护SQL。D01–D08既有待决不解除，不自动开始下一Task。


### 最终整合与停止

代码/测试最终冻结后，`& '.\.cache\t07-postgres\run-tests.ps1' -PytestArguments @('-q','--tb=short')` 实际退出0：**1123 passed，1既有warning，151.48s**，无失败/skip；`python -m pytest --collect-only -m postgres -q`退出0确认200/1123个PG项、923 deselected仅收集筛选，不能把923写成运行skip。最终新专项同路径131集成（8.96s）/63实际PG（46.71s），均退出0；131包含最后6项同TX登记/调用方回滚/错误Engine/无事务/immutable变更整体回滚，63包含新窗口实锁及production正常组装的合成对象/父/用户拒绝。

最终21个变更Python模块AST语法检查退出0。旧认证450、前端62、Type Check、两模式Build、浏览器12及契约/原文/依赖一致性结果如上；这些命令均本轮重新执行。完整范围/历史/文档同步与暂存审查见下方保存记录。

只读残留检查命令：PowerShell单引号here-string经`.\.venv\Scripts\python.exe -`，只从ignored environment.json读并校验三URL的loopback55437/专用库名，查pg_namespace、information_schema.tables和pg_stat_activity（排除当前QA连接），退出0。auth_t05_test/auth_t06_test/auth_t07_test的custom_schema/public_table/residual_client_session计数全0。之后`.\.cache\t07-postgres\stop.ps1`退出0，仅停本cluster；`pg_ctl -D 本cluster status`预期退出3确认停止，Get-NetTCPConnection确认55437无监听；本轮浏览器自有8000/5186/9444已停止，不终止用户服务。

CHANGELOG/tasks、ADR-018与受影响文档同步：T07已完成，67主Task中T01–T07完成、60未开始。没有开始T08或解除D01–D08待决、没有部署或注册/采集真实资料。

### 范围、历史与源码保存

`.\.venv\Scripts\python.exe -X utf8 .cache/t07_validate.py`实际退出0：33审查路径、148范围外跟踪文件原字节、21 Python语法、181本地文档链接、7完成/60未开始、历史Task卡/ADR-001–017/旧日志/D01–D08及M0 wire均保持；`git diff --check`退出0。两原始输入、旧0001/0002/M0迁移、旧验收和前端/契约/依赖/研究文件保护通过。

本轮开始时工作区/索引为空，Git基线0b09eaefe93ba3f445f8c42e4c58dd34ec7226bb；新当前分支codex/t07-object-authorization。`gh repo view chanbilly-lab/study-admissions-agent --json nameWithOwner,isPrivate,url`退出0，确认仓库仍私有；`git remote get-url origin`核对既定HTTPS remote，无替换。按持续授权只逐路径暂存上述33已核对文件，审查实际暂存diff；秘密/禁入路径/原文/LF生成物检查使用同validator --stage。无.env、APIkey/token/私钥、真实学生附件、DB/备份/WSL盘、node_modules/构建/cache入仓。普通提交及推送仅本分支，上传不是部署；实际commit与推送后local/remote SHA核对以最终报告为准，不预写未来成功。
