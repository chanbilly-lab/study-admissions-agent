# T06 · 会话撤销与 CSRF

> Privacy note (2026-10-14): private account/resource identifiers and personal home paths have been redacted for the public-release candidate. Historical outcomes are unchanged; placeholders are not live targets.

日期：2026-10-02。实施前 Git：`a987e9a77d3f749ded18be92924358c432976d45`，149 个跟踪文件，工作区及暂存为空；工作分支 `codex/t06-session-csrf`。本 Task 验收后提交推送并停止，不执行 T07、不部署。

## 实施前数据契约

- 保留 T05 登录、回调和 session wire；新增 `GET /v2/auth/csrf`，无 query，必须有有效 Cookie，返回 Envelope data `{csrf_token, expires_at}`。token 为每会话稳定高熵随机值，只在浏览器内存使用；服务端存目的隔离摘要及 Fernet 密文，不存明文。已有会话通过锁行初始化，绝对到期不延长。
- 新增 `POST /v2/auth/logout`，无 query/body，唯一 `X-CSRF-Token`、唯一 `Origin` 与当前会话必须有效。200 Envelope data `{logged_out:true}` 表示服务端已撤当前应用会话并清 Cookie；无效/过期/已撤会话 401 并清 Cookie，重复退出不创建任何数据。403/503/网络失败不能宣称退出已确认。不退出 Keycloak SSO，不实现退出所有设备 HTTP API。
- 固定可信 Origin 从服务器注册的 redirect_uri 产生，不能来自请求 Host、Forwarded 或客户端配置。所有 Cookie 身份写方法 POST/PUT/PATCH/DELETE 默认经过中央校验，包括以后新增而遗漏 route dependency 的路由；state/nonce/PKCE 登录 GET 回调保持专用验证。错误仍为安全 v2 envelope/request_id；私有和拒绝写响应 no-store。
- 可信内部执行引用由当前认证生成，执行时重新读取会话 owner、账户状态、撤销及绝对到期，并调用显式服务器权限检查；缺少权限检查即拒绝。T07 角色/grant/真实业务与后台队列未实现，不把会话有效等同于业务授权。
- 管理员认证强度策略默认 disabled。显式启用必须配置可信 issuer、独立 admin client、student client、acr allowlist、required amr 和最大认证年龄；只使用经过固定签名/issuer/audience/nonce/时效验证的 JWT 中 acr/amr/auth_time 与固定服务端来源，缺少、陈旧、错 client/策略失效均拒绝。不按 acr 名称排序，不用 iat 代替 auth_time，不授予管理员角色。实际 tenant/MFA/recovery 配置仍待 D04 验收，无 HTTP 管理入口。
- 独立认证链增量 `0002_auth_t06`：CSRF nullable pair 与签名认证强度/来源字段，旧会话普通读取保留、管理员拒绝。冻结 `0001_auth_t05` 与 M0 迁移；启动只检查 schema，不自动升级或创建账户。

## 修改范围

认证 config/models/store/service/oidc 与新 assurance/HTTP 安全 helper；identity router/factory、identity profile 生成器与生成 JSON/TS；auth 前端及测试、新 T06 离线浏览器夹具/脚本；独立单测、HTTP/安全/PostgreSQL 用例及少量受新增 logout/schema 影响的旧断言。治理及受影响 README、身份/API/数据库/架构/需求文档同步。无新增依赖，不改原始输入、docs/01–05、旧验收、T04 schema/provider、旧迁移、M0/研究夹具和默认 foundation contract。

## 实施前验收用例

1. 有效退出后旧 Cookie 读取/写入失效；重复退出 401，无新账号或会话；其他会话/用户不受当前退出影响；到期/禁用/撤销即时拒绝，不滑动 TTL。
2. 缺失、错误、重复、跨会话 CSRF，query/body/Cookie 替代 token，缺失/null/错误/重复 Origin 均拒绝；Host/Forwarded 不能改变可信 Origin。
3. standalone、mounted、尾斜杠及动态添加测试写路由的所有 unsafe 方法受中央保护；错误 ID 一致、敏感内容不回显、no-store。
4. 新迁移/旧会话升级、nullable pair 约束、并发初始化/撤销、未升级启动拒绝及无 DDL，用全新隔离 PostgreSQL 验收；SQLite 仅快速离线替身。
5. 执行引用 owner 篡改、账户禁用/会话撤销/到期、权限回调撤权或缺失均不执行副作用。管理员默认关闭、缺/错/陈旧签名认证依据、客户端不匹配/策略失效拒绝；明确合成配置的完整依据正例通过强度检查但不产生角色。
6. 前端 token 仅内存，退出请求防重入、旧异步读取不能恢复身份，失败诚实显示；真实浏览器 Cookie/CSRF/退出/刷新与窄屏通过，所有 IdP/学生均为合成离线夹具，禁止外网。
7. 相关单测/实库/回归、前端 Unit/Type Check/Build、生成漂移、原文/历史/范围检查记录实际结果。无已配置 Lint 或 Python 静态类型入口时标注未执行，不安装无关工具。不执行真实 Keycloak、MFA/recovery、生产 TLS、注册/部署。

## 实际验收

完成日期：2026-10-03（Asia/Hong_Kong）；2026-10-02开始，未将历史测试视为本次通过。T01–T06共6个主Task完成，61个未开始；不执行T07。

### 实际命令与结果

所有Python检查使用现有`.venv`，测试外网/DNS被fixture拒绝；IdP/账户/强度策略均合成。全新PostgreSQL16.15监听127.0.0.1:55436，独立cluster在`.cache/t06-postgres/run-a50c39542695444986b31b6e89b12dfc/cluster`；未启动/改动旧T01/T05库。专用新auth_t05_test兼容旧测试，新auth_t06_test用于T06，每测试随机schema及finally清理。秘密URL仅在ignored environment.json，通过helper注入TEST_POSTGRES_URL/T06_TEST_POSTGRES_URL，不打印或提交。

| 实际命令 | 实际结果 |
| --- | --- |
| `.\.cache\t06-postgres\run-tests.ps1 -PytestArguments @('-q','--tb=short')`（helper最终运行`.\.venv\Scripts\python.exe -m pytest -q --tb=short`） | 929 passed，1条既有Starlette/AnyIO弃用warning，87.88s，exit0；包含792非PG/137真实PG，无skip/deselection |
| 同helper：`-PytestArguments @('tests/security/auth','-q','--tb=short')` | 132 passed（40非PG/92PG），1上述warning，45.85s，exit0；首版112通过，补充后132通过 |
| 同helper：`tests/security/auth/test_postgresql.py::test_unupgraded_schema_readiness_is_503_and_does_not_run_ddl -q --tb=short` | 最终追加真实factory无DDL断言后1 passed/2.47s/exit0；full已加载旧函数，故单独复验最终追加断言，仍属于132中的同一用例 |
| `.\.venv\Scripts\python.exe -m pytest tests/unit/auth -q` | 165 passed（T04原131＋T06新34），1上述warning，exit0；新session_security单独34 passed/exit0 |
| `.\.venv\Scripts\python.exe -m pytest tests/contracts/test_identity_contract.py tests/contracts/test_v2_generation.py -q` | 中间60 passed/exit0；随后补4个父层拒绝写响应测试，均纳入最终929 |
| `.\scripts\web.ps1 -Action test` | 8文件/62 passed，exit0；新增退出专项20，其余42保持 |
| `.\scripts\web.ps1 -Action typecheck` | vue-tsc --noEmit通过，exit0 |
| `.\scripts\web.ps1 -Action build` | 默认M0构建通过，exit0 |
| `$env:VITE_APP_MODE='auth'`后`.\scripts\web.ps1 -Action build` | 显式auth vue-tsc/Vite构建通过，exit0；构建产物不入Git |
| `& '<USER_HOME>/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' scripts/auth_t06_browser_smoke.mjs` | 12 checks passed，exit0；Edge154.0.4258.48，page_errors/blocked_requests为空；390px无横向溢出，桌面及窄屏实际视觉检查 |
| `.\.venv\Scripts\python.exe scripts/generate_contracts.py --check`与`--profile identity --check`（分别执行） | 两profile漂移检查均exit0；identity v2.t06有7路径，foundation原产物不变 |
| `.\.venv\Scripts\python.exe -X utf8 scripts/verify_contract.py` / `scripts/verify_originals.py` | M0 TS/OpenAPI契约、原始两文档保护均exit0 |
| 24个新/改Python文件逐个`py_compile.compile(path,doraise=True)`；pytest --collect-only -q计数 | 24模块通过/exit0；929项目137PG/792非PG，T06安全132，与实际运行数量一致 |
| `& '<USER_HOME>\.local\bin\uv.exe' pip check` | 35包兼容，exit0；无新增依赖或锁文件变化 |
| 两个新库残留检查后`.\.cache\t06-postgres\stop.ps1` | 自有schema残留0、public表0；仅停止本次cluster，exit0；浏览器三个端口无残留服务 |

浏览器报告/截图：`.cache/t06-browser/942abf5a-fb11-45d7-879a-07d261ccc3d0/`（ignored）。验证固定RSA登录链、Secure/HttpOnly Cookie实际发送、内存CSRF、缺/错token403不撤销、实际GET200晚到但退出后不回填、logout200后旧cookie读/写401、刷新不能恢复、新登录、未登记403、到期401、关闭503和无外网。旧T05脚本/夹具保留历史，其“无退出按钮”断言不适用于T06，没有宣称重跑该旧脚本。

### 首次失败、修复与未执行项

- 首轮旧认证＋契约：148 passed/1 failed，旧迁移head断言仍是0001；仅改到0002，单项1 passed，最终全回归通过。
- 首次full收集：auth.conftest与新security/auth同名，1 collection error；新增tests/security/__init__.py隔离包名，最终929通过。没有修改全局pytest导入策略。
- 前端新增测试首次Type Check：DOM wrapper get().exists TS2339；改为find()后typecheck/构建通过，没有绕过类型。
- 审查在最终验收前修复锁等待跨绝对expiry、权限回调后的旧assurance、最终持锁权限重验，以及父层提前拒DEMO写入缺no-store；独立正/负/实际PG竞态和4个父层HTTP测试纳入最终回归。
- 暂存首次diff --check发现验收文档末尾多余空行（exit2），已去除后重新检查；基线辅助首次Git中文路径被引用、配置README插入位置假设错误分别失败，改用-z/真实标题位置后完成；一次误调用不存在的辅助路径退出1，无文件改动，随后使用正确helper。应用验收不以辅助失败冒充通过。
- **未执行Lint**：项目没有Python/前端Lint配置或script，ruff未安装；**未执行Python静态Type Check**：没有配置入口且mypy未安装。不为本Task新增无关工具；Python语法检查不称作Lint/静态类型。
- **未执行**：真实Keycloak tenant/client/管理员MFA与恢复、生产TLS、正式注册、部署、公开事实发布、Keycloak全局SSO/所有设备退出；未实现的T07对象grant/实际后台队列不作为本次通过。

### 文件与保护

精确45路径（29旧改＋16新增），120个其余跟踪路径内容未变；原始两文档、docs/01–05、旧验收、旧迁移、M0及研究夹具保留。默认foundation schema/TS和M0 OpenAPI保持；无新增依赖。全部必要路径逐项审查后才暂存，原索引为空，禁止将cache/秘密/构建产物入Git。最终范围、历史记录、本地链接及暂存内容检查以完成前实际命令核对。

```text
AGENTS.md
README.md
apps/web/src/features/auth/AuthView.vue
apps/web/src/features/auth/client.ts
apps/web/src/features/auth/useSession.ts
apps/web/tests/AuthView.test.ts
apps/web/tests/auth-session.test.ts
apps/web/tests/auth-logout.test.ts
config/identity/README.md
docs/CHANGELOG.md
docs/DECISIONS.md
docs/api.md
docs/architecture.md
docs/database.md
docs/identity.md
docs/requirements.md
docs/tasks.md
docs/acceptance/T06_session_csrf.md
packages/contracts/v2/identity/generated.ts
packages/contracts/v2/identity/openapi.json
scripts/generate_contracts.py
scripts/auth_t06_browser_smoke.mjs
services/api/app/api/identity.py
services/api/app/auth/config.py
services/api/app/auth/models.py
services/api/app/auth/oidc.py
services/api/app/auth/router.py
services/api/app/auth/service.py
services/api/app/auth/store.py
services/api/app/auth/assurance.py
services/api/app/auth/http_security.py
services/api/auth_migrations/versions/0002_auth_t06.py
tests/contracts/test_identity_contract.py
tests/integration/auth/test_http_session.py
tests/integration/auth/test_persistence.py
tests/e2e/auth_t06_fixture.py
tests/security/__init__.py
tests/security/auth/__init__.py
tests/security/auth/conftest.py
tests/security/auth/test_assurance.py
tests/security/auth/test_csrf_http.py
tests/security/auth/test_execution.py
tests/security/auth/test_postgresql.py
tests/security/auth/test_unsafe_routes.py
tests/unit/auth/test_session_security.py
```

范围/文档实际命令`.\.venv\Scripts\python.exe .cache/t06_validate.py`已exit0：45路径、120其他跟踪路径保护、166本地链接存在、67主Task中6完成/61未开始；旧Task卡/ADR-001–016/旧日志/无关待决行及M0 OpenAPI保留。验收与CHANGELOG/tasks的Task ID、完成状态、文件清单及929/62/12结果一致。仓库`gh repo view --json nameWithOwner,isPrivate,url`实际isPrivate=true，origin精确匹配授权URL，原暂存内容为空。

最终暂存命令只包含上述45个明确路径；`.\.venv\Scripts\python.exe .cache/t06_validate.py --stage`修正末尾空行后已exit0：范围/历史/状态/166链接、秘密模式/禁止路径、原输入index原字节、四份生成契约LF及`git diff --cached --check`通过。未纳入任何.env/凭据/cache/数据库/备份/node_modules/dist；当前Task开始前没有用户暂存内容。

### 已知问题与完成边界

无T06阻断项。1条既有依赖弃用warning保留；真实D04 tenant/版本/地域/管理员MFA/恢复、D02准入、D06正式留存/清理与公众发布门槛未解除。执行helper只保证当前会话及本地同步检查边界，T07 action/owner/grant跨资源一致性、持久worker和跨系统副作用仍未实现。默认管理员策略关闭，离线强度正例不代表真实MFA联调。

CHANGELOG、tasks及受影响API/数据库/架构/需求/身份运行文档同步；ADR-017说明新增决策。私有origin已读核实，验收后按持续授权普通提交/推送codex/t06-session-csrf，具体commit与远程SHA核对由Git与最终报告提供；不部署，不继续后续Task。
