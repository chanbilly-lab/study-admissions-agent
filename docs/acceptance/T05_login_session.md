# T05 登录与服务端会话（2026-10-02）

> Privacy note (2026-10-14): private account/resource identifiers and personal home paths have been redacted for the public-release candidate. Historical outcomes are unchanged; placeholders are not live targets.

状态：已完成。用户明确授权执行T05，依赖T04已完成。Git基线为`319b04849a1dd6692f914d9e0264a5c70e77ed80`，原工作分支`codex/t04-identity-boundary`，工作区/暂存为空；本轮分支`codex/t05-login-session`。实施前已阅读AGENTS、README、requirements、architecture、tasks、CHANGELOG、DECISIONS、identity、API、数据库、原始规格及相关代码。原始两文件哈希检查退出0、UNCHANGED。

## 实施前数据契约

- 新的显式身份入口仍只挂`/v2`。既有M0与默认production foundation保持原契约；身份入口默认关闭，不连接数据库，认证路由返回503。单独身份OpenAPI/TS由离线工厂生成，不实例化数据库或供应商。
- `GET /v2/auth/login`不接受查询参数。服务器固定issuer/client/redirect、S256、nonce和openid；302到固定供应商。事务state与独立浏览器绑定值随机生成，独立索引列只保存摘要；完整LoginContext（含state、PKCE verifier与nonce）加密保存。绑定Cookie使用`__Host-admissions-login`、Secure、HttpOnly、SameSite=Lax、Path=/、无Domain。
- `GET /v2/auth/callback`只允许唯一的`code/state/error/iss`，拒绝重复、任意issuer/JWKS/nonce/verifier/role/return URL等参数。必须匹配未过期state与绑定Cookie；事务在外部I/O之前一次性消费，失败也不可重放，错浏览器不消费。只有code成功路径可以换码；供应商error不回显。
- JWT仅接受固定RS256及固定JWKS，验证签名、issuer、audience/azp、nonce、exp/iat/nbf和精确subject；禁止按token地址取密钥。token仅用于本次服务器验证，不持久化，也不交给浏览器。
- 登录只映射精确`(issuer,subject)`预登记、启用账户；不按email合并，不自动注册，不从IdP roles授予业务权限。成功撤销请求携带的旧会话并生成新随机会话，数据库仅保存摘要。成功303到固定`/`。
- 会话Cookie为`__Host-admissions-session`、Secure、HttpOnly、SameSite=Lax、Path=/、无Domain。`GET /v2/auth/session`响应现有v2 envelope，data为`authenticated=true`、UUID `user_id`、UTC `expires_at`、`is_synthetic`、`private_business_available=false`；不含姓名、email、issuer、subject、角色或token。每次检查账户状态、撤销和绝对到期。
- 错误复用v2的401 UNAUTHORIZED、403 FORBIDDEN、422 VALIDATION_ERROR、503 SERVICE_UNAVAILABLE等安全响应；认证响应禁止缓存、Referrer-Policy=no-referrer。默认登录事务300秒/会话3600秒是可配置测试运行参数，不替代D06正式留存或会话政策。
- 前端`VITE_APP_MODE=auth`明确启用独立登录页，同源Cookie与顶层授权跳转；默认仍M0。仅登录/会话显示/刷新，不开放注册、画像、退出或管理入口。

## 修改范围

新增auth配置、Keycloak换码/JWT适配、四表、存储、服务及路由，新的identity应用入口，独立`auth_alembic.ini`/`auth_migrations`及`auth_alembic_version`，离线身份契约生成与产物，auth前端和专项单元/集成/PG/浏览器测试。仅修改必要入口、生成器支持与依赖锁；新增joserfc用于标准JOSE验证、cryptography用于加密上下文和签名夹具。同步AGENTS/README、requirements/architecture/database/api/identity、tasks/CHANGELOG/DECISIONS和本验收记录。

不改原始输入、docs/01–05、旧验收、旧迁移、DEMO夹具/研究事实和既有M0行为；不部署、不注册真实账户、不启动T06。独立迁移理由与发布边界记录ADR-016。

## 可测试验收矩阵

1. 固定配置、启动冻结、关闭时无DB/JOSE导入、生产禁止测试传输/合成账户；默认foundation和M0回归不变。
2. 真实RSA签名离线IdP成功；篡改签名、none/HS算法、错误issuer/aud/azp/nonce、过期/未来/缺少claims、异常JWKS、重定向/超时/异常token响应全部拒绝且无敏感回显；不访问外部网络。
3. state与浏览器绑定、重复/额外参数、错误回调、到期、重放、IdP失败后再次消费、会话固定攻击、旧会话失效、账户禁用/未登记/精确身份区分。
4. PostgreSQL隔离库迁移/重复升级、约束、状态单次消费并发、会话轮换；旧M0四项实库验收另运行，旧七表/迁移不改变。应用启动不创建表/夹具。
5. 前端离线单元测试、TS类型和两模式build；浏览器经过本机TLS离线授权页、真实签名回调、安全Cookie、刷新和到期。禁止外部浏览器请求，测试证书/私钥/库仅放忽略缓存。
6. 离线回归、契约生成check、原文与范围/历史/文档链接/同步检查、暂存秘密检查。Lint/Python静态类型如无入口明确未执行；真实Keycloak、生产TLS、部署、MFA/恢复均不伪称通过。

## 实际执行结果

所有命令为本轮实际执行；最终源代码冻结后完整Python与浏览器重跑。认证单元/集成均阻断外部网络，PG在127.0.0.1:55435的全新auth_t05_test、每用例随机schema；数据库密码仅ignored environment.json，不在输出/源码。仅复用旧T01 PostgreSQL16.15 binaries，未启动或修改旧cluster；无Docker操作/下载/真实Keycloak。

| 实际命令/环境 | 结果 |
| --- | --- |
| `uv --cache-dir .cache/uv pip compile requirements.in --generate-hashes --output-file requirements.txt --quiet` | 退出0；新增joserfc1.7.5/cryptography50.0.2及cffi2.1.1/pycparser3.0，旧pin不变 |
| `uv --cache-dir .cache/uv pip sync --python .venv/Scripts/python.exe --require-hashes requirements.txt` | 退出0，安装4个新增依赖 |
| `uv --cache-dir .cache/uv pip check --python .venv/Scripts/python.exe` | 退出0，35包兼容 |
| `python -m pytest tests/contracts/test_identity_contract.py -q --tb=short` | 修正短参数ID后20 passed/1既有warning；mounted/header与服务装配补强进入最终完整回归 |
| `python -m pytest tests/contracts/test_v2_generation.py tests/contracts/test_identity_contract.py -q --tb=short` | 59 passed/1既有warning/退出0 |
| `python -m pytest tests/integration/auth -q`，从ignoredJSON设置TEST_POSTGRES_URL | 最终128 passed/1既有warning/退出0（24.83s；87非PG、41真PG）；含最后时效与production SQLite修复 |
| `python -m pytest -m postgres -q --tb=short`，同一独立PG环境 | 45 passed、712 deselected、1既有warning/退出0（28.45s；新auth41＋旧M0四项） |
| `python -m pytest -m 'not postgres' -q --tb=short` | 初次3 failed/709 passed/45排除；修复生成器兼容后712 passed/45排除/1warning，之后新增一项生产SQLite负例 |
| **`python -m pytest -q --tb=short`**，同一独立PG环境 | **最终758 passed、1既有warning、退出0（54.73s，无跳过/排除；713非PG＋45 PG）** |
| `.\scripts\web.ps1 -Action test` | 7文件42 passed/退出0：原18＋新增auth24 |
| `.\scripts\web.ps1 -Action typecheck` | 退出0，vue-tsc --noEmit |
| `.\scripts\web.ps1 -Action build`，未设置VITE_APP_MODE | 默认M0构建退出0 |
| `pnpm --dir apps/web exec vue-tsc --noEmit`；`pnpm --dir apps/web exec vite build --outDir D:/Projects/study/.cache/t05-auth-dist/20261002-2258`，进程VITE_APP_MODE=auth、VITE_AUTH_API_BASE_URL=/api | auth类型/构建均退出0；使用现有bundled pnpm，不新增依赖 |
| `node --check scripts/auth_browser_smoke.mjs`、`python -B -m py_compile tests/e2e/auth_fixture.py` | 均退出0 |
| `node scripts/auth_browser_smoke.mjs`，Node24.19.0/bundled Playwright1.62.1/Edge154.0.4258.48 | 最终8项passed、page_errors/blocked_requests空、退出0；完整签名登录、真正HTTP携带Secure Cookie、刷新、390px、未登记403、到期401、关闭503 |
| 内联`python -X utf8 -`逐一py_compile新/改.py | 19模块退出0；缓存python-files.json保留清单 |
| `python -X utf8 scripts/generate_contracts.py --profile identity --check` | 退出0，identity两产物匹配 |
| `python -X utf8 scripts/generate_contracts.py --check` | 退出0，旧foundation原字节仍匹配 |
| `python -X utf8 scripts/verify_contract.py` | 退出0，M0 TS/OpenAPI一致 |
| `python -X utf8 scripts/verify_originals.py` | 退出0，两原始文件UNCHANGED |
| `python -X utf8 .cache/t05_validate_20261002.py` | 退出0：46路径、103 tracked保护、152本地链接、5已完成/62未开始，旧日志/ADR/Task/M0 wire不变 |
| `python -X utf8 .cache/t05_validate_20261002.py --stage`＋`git diff --cached --check`与实际暂存diff审查 | 退出0；仅46已审查路径，无秘密/私钥/缓存/构建产物，原文字节与两profile LF通过 |
| `gh repo view chanbilly-lab/study-admissions-agent --json isPrivate,nameWithOwner,url` | 退出0，确认已授权origin私有 |
| `pg_ctl -D <本Task新cluster> -m fast stop`＋自有55435/8000/5185/9443监听断言 | 退出0；停止本Task测试库/helper，不杀用户进程、不碰旧T01cluster |

执行以上Python命令的实际前缀为`.\.venv\Scripts\python.exe`；uv为`<USER_HOME>\.local\bin\uv.exe`；最终浏览器使用`<USER_HOME>\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe`。PG环境命令为读取`.cache/t05-postgres/environment.json`到任务变量并设置`$env:TEST_POSTGRES_URL`，不打印DSN；测试库只读专项检查曾确认剩余owned schema=0，最终teardown与监听停止通过。迁移/readiness/唯一CHECK/FK/精确collation/并发单胜者/提交claim后才I/O/安全HTTP等以41个PG用例验证。

最终浏览器报告和已人工查看的桌面/390px截图位于忽略缓存`.cache/t05-browser/daf346d0-1c66-4b80-b11f-6c050b5ac28b/`；此前成功截图也保留。截图明示DEMO合成身份验收，storage/可读cookie空。临时TLS私钥/签名私钥/SQLite库不上传。

## 首次失败与修正

- root新契约首轮19 passed/2 setup errors：65KiB负例自动参数ID导致Windows临时路径过长；改短id后20 passed，不删负例。路由首次独立import probe退出1，因ERROR_RESPONSES/REQUEST_ID_HEADER实际位于v2.router而非schemas/errors，纠正后schema成功；不是外部IdP失败。
- 完整离线初轮3 failed/709 passed：默认generator.main给已存在的zero-argument loader传profile位置参数；保持旧调用签名，原测试不改，59契约与最终758通过。
- PG持久化首轮12 passed/1 failed：负例字符串17字符先触发VARCHAR16 DataError，改14字符准确验证CHECK，非放宽数据约束；最终128专项通过。
- 浏览器首轮timeout：测试IdP CSP form-action self拦跨origin303，仅夹具加精确web origin后成功；未关闭生产安全Cookie/CSP或扩大任意回调。
- 审查补强JWT在token/JWKS/签名耗时后的monotonic时效、session完成时TTL、mounted no-store/referrer、生产SQLite与构造时注入重验。补负例，最后代码冻结后758回归及8项浏览器再通过。
- 配置/依赖工具、路径/属性/patch锚等只读或辅助检查曾有非0，按真实API纠正，没有将其当测试通过。Lint入口rg未匹配返回1、ruff/mypy显示False，见下方未执行项。

## 未执行、已知问题与停止边界

- **Lint未执行**：当前pyproject/package.json无lint入口，ruff未安装；未假称py_compile等于Lint。
- **Python静态类型检查未执行**：无配置入口且mypy未安装。前端TS typecheck已执行。Python无打包build配置，19模块语法/运行测试已执行；未把它宣称为Python发布构建。
- **真实Keycloak/生产TLS/部署/版本地域/管理员MFA与恢复未执行**：本轮无服务购买、安装、真实账号/tenant。测试真实RSA签名不等于真实Keycloak联调，本机临时TLS不等于生产HTTPS验收。
- D02准入、D04实际注册/恢复强认证、D06正式留存/清理及其他公众门槛仍未决；本轮不自动注册、不开放画像/写业务。T06注销/CSRF/管理员策略、T07对象授权尚未实现。
- 1条既有Starlette/AnyIO BlockingPortal弃用warning未顺带升级；不影响本轮通过，不称零warning。真实招生资料、概率、爬虫/自动申请及后续Task不在范围。

## 范围、文档与源码保存

46路径（16旧改/30新增），103范围外原tracked文件保护，152本地文档链接核对通过。旧Task卡（除T05）、CHANGELOG T04及以前、ADR-001–015、D01–03/D05–08、原始规格、docs/01–05、旧验收、M0/v2 foundation、旧迁移/DEMO/研究保留。API/DB/架构/需求/identity/README/AGENTS与ADR-016已同步；tasks和CHANGELOG均T05已完成、测试758/42/8一致。单独新生成产物LF由.gitattributes保障，原两文件原字节规则不变。

精确文件清单如下；提交只暂存这些人工审查路径，不纳入.cache/秘密/私钥/真实学生/构建产物。暂存diff、秘密哨兵、原文字节和LF已复核通过；按持续授权普通push到已核实私有origin与codex/t05-login-session。commit/上传SHA以实际Git核对和最终报告为准，不提前编造；本轮保存后停止，不启动T06。

- `.gitattributes`
- `AGENTS.md`
- `README.md`
- `apps/web/src/features/auth/AuthView.vue`
- `apps/web/src/features/auth/client.ts`
- `apps/web/src/features/auth/useSession.ts`
- `apps/web/src/main.ts`
- `apps/web/tests/AuthView.test.ts`
- `apps/web/tests/auth-client.test.ts`
- `apps/web/tests/auth-session.test.ts`
- `config/identity/README.md`
- `config/identity/session.example.json`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T05_login_session.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/identity.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `packages/contracts/v2/identity/generated.ts`
- `packages/contracts/v2/identity/openapi.json`
- `requirements.in`
- `requirements.txt`
- `scripts/auth_browser_smoke.mjs`
- `scripts/generate_contracts.py`
- `services/api/app/api/identity.py`
- `services/api/app/auth/config.py`
- `services/api/app/auth/models.py`
- `services/api/app/auth/oidc.py`
- `services/api/app/auth/router.py`
- `services/api/app/auth/service.py`
- `services/api/app/auth/store.py`
- `services/api/auth_alembic.ini`
- `services/api/auth_migrations/env.py`
- `services/api/auth_migrations/versions/0001_auth_t05.py`
- `tests/contracts/test_identity_contract.py`
- `tests/e2e/auth_fixture.py`
- `tests/integration/auth/__init__.py`
- `tests/integration/auth/conftest.py`
- `tests/integration/auth/fake_idp.py`
- `tests/integration/auth/test_configuration.py`
- `tests/integration/auth/test_http_session.py`
- `tests/integration/auth/test_oidc.py`
- `tests/integration/auth/test_persistence.py`
