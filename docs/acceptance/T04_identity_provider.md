# T04 · 正式身份供应商边界

日期：2026-10-02，Asia/Hong_Kong。用户授权“先明确D04身份供应商配置，再执行T04”，随后明确选择自托管Keycloak。T02/T03已完成；本轮只T04，不启动T05或部署。

## 修改前基线

必读AGENTS、README、requirements、architecture、tasks、CHANGELOG、DECISIONS及API/数据库/身份规划已核对；两份原规格哈希未变。Git起点codex/t03-mode-isolation / `3a939044aefc0c883a9ae601ef29c2e75af014bd`，工作区/索引为空；新分支codex/t04-identity-boundary。`.cache/t04-baseline-20261002/`保存107文件哈希、历史与规范化M0 OpenAPI，不上传缓存。

## D04先行决定

- 用户选择：自托管Keycloak，沿用独立IdP＋FastAPI BFF的OIDC接口方案，不改变Vue/Python/PostgreSQL应用技术栈。本轮不安装Keycloak、不注册/创建真实账号或client、不采购或部署。
- 接口基线：授权码、PKCE S256、固定server信任issuer/client_id/授权及token/JWKS地址、精确回调allowlist、最少openid scope；不直接向SPA发token，不自建密码/找回接口，不按email自动合并账号。
- 沿用既有管理员MFA要求：未来管理员独立受限client/流程，必须强制因子，不能把供应商role或前端字段当应用管理员授权；真实MFA与恢复仍需后续配置/验收。公开自助注册保持关闭，D02未成年准入未定不收集真实画像。
- 账号恢复由Keycloak托管流程负责，管理员不得套用默认邮箱重置绕过MFA。具体恢复责任人/证明/邮件通道、部署地域/版本、真实realm/domain/client/secret及登记回调尚未具备，继续作为上线/认证启用门槛。D04只在供应商路线与T04接口配置层部分确定，不宣称全部生产参数已验证。
- 官方依据：[OIDC端点](https://www.keycloak.org/securing-apps/oidc-layers)、[管理指南](https://www.keycloak.org/docs/latest/server_admin/index.html)、[生产配置](https://www.keycloak.org/server/configuration-production)、[PKCE标准](https://www.rfc-editor.org/rfc/rfc7636)。Keycloak默认条件式2FA与找回OTP行为不能代替管理员强制策略。

## 实施前数据契约

1. 新增独立auth模块。冻结、extra forbid、错误脱敏配置；provider_mode=disabled/offline/oidc_boundary，默认disabled。固定provider_id、issuer、client_id、authorization_endpoint/token_endpoint/jwks_uri、登记callback_allowlist、最少openid与S256、机密客户端认证方式及允许的签名算法。Keycloak配置从server固定realm issuer推导官方端点，再精确核对外部metadata；不接受客户端任意issuer/JWKS/discovery或jku/x5u指示，不发网络请求。
2. `IdentityKey`保留原样case-sensitive `(issuer, subject)`元组；不拼接成模糊分隔字符串，不按email/显示名合并，不赋owner/role/grant。固定离线主体明确合成；同一issuer+subject重复夹具拒绝，同subject不同issuer不碰撞。数据库唯一约束/用户持久化留T05。
3. `IdentityProvider`可替换协议，声明纯授权请求与回调/身份验证边界。Fixed离线实现只识别固定服务端夹具及绑定上下文；configured OIDC只形成受信配置/授权描述，真实换码和JWT签名尚未实现时明确Unavailable，不自动回退离线。离线只能development/test且显式启用，production拒绝；应用接入仍关闭。
4. 登录上下文由server创建，绑定provider/issuer/client/登记redirect、state/nonce/PKCE verifier与S256 challenge、timezone-aware有效时间；Secrets使用SecretStr/repr隐藏。纯函数/离线回调检查绑定及过期，不把内存对象说成持久一次性事务。真实JWT signature/audience/expiry、state消费/重放、用户与会话、Cookie/CSRF由T05/T06实现。
5. 本轮不新增HTTP端点/对外wire、迁移、账号存储或重要依赖；M0/v2 OpenAPI、生成产物、public factory及业务不可用状态不改。所有示例均无秘密、明确占位/合成，不能声称真实tenant已注册或真实登录已验收。

## 修改范围与验收用例

- 代码：新services/api/app/auth/{__init__,schemas,provider}.py；非秘密config/identity示例及说明；新tests/unit/auth独立离线验收。复用Pydantic及stdlib，不引入JWT/IdP SDK或部署框架。
- 文档：AGENTS/README、requirements/architecture/api/database/tasks/CHANGELOG/DECISIONS、新docs/identity.md与本验收；其他Task/原输入/docs01–05/旧验收/迁移/夹具/研究/依赖与锁文件冻结。
- 验收：配置模式/错误/冻结及copy/construct重验；固定Keycloak端点/metadata及回调exact allowlist，拒userinfo/fragment/query、wildcard、scheme/外部URL替换；主体tuple唯一与大小写/分隔符碰撞；替换provider不增权限；S256标准向量、verifier长度/字符、state/nonce/时间/上下文错绑；秘密脱敏；production禁离线、真实适配Unavailable不回退；断网/无M0与DB导入、foundation仍不开放auth路由。
- 执行相关pytest、现有前端test/typecheck/build、契约/原文/语法/范围/历史/文档检查；无入口的Lint/Python静态类型及未做的实库/浏览器/Keycloak/部署分别注明。开始前没有新Task测试结果，不用T03历史通过代替。

## 实际结果

已完成T04，2026-10-02。本轮不开始T05，也不进行真实身份注册、业务/IdP部署或招生资料采集。D04按用户选择为自托管Keycloak，具体配置见[identity](../identity.md)；真实tenant/MFA/恢复仍是后续配置与启用门槛。

### 已实现行为

- `AuthProviderSettings`默认disabled；冻结/extra forbid，不自动读env或dotenv。工厂/直接供应商构造及操作入口重验配置和`V2RuntimeSettings`，拒生产offline与HTTP回调，也拒copy/construct伪造配置。
- Keycloak端点从固定HTTPS realm issuer推导；四字段`ProviderMetadata`只是显式受限投影，精确核对、不发现/获取外部URL。回调精确allowlist；无效hostname/端口、userinfo/query/fragment/wildcard、dot segment与百分编码路径拒绝。大小写等原值不归一化。
- `IdentityProvider`为可替换协议；固定离线fixture仅合成，主体tuple保留issuer+subject原样，不按email合并，无role/owner/grant。可替换协议不表示内置任意供应商适配器；当前配置profile/factory只支持所选Keycloak边界和离线替身。
- 服务端创建随机state/nonce/verifier、S256 challenge与aware时间；默认300秒离线参数（1–3600秒，不代表D06）。绑定/时效/PKCE与固定assertion识别可离线验收，无持久一次性消费/真实JWT保证。oidc_boundary只产生授权描述，验证操作明确Unavailable且不回退。
- 配置/比较边界输出固定安全错误，SecretStr隐藏repr/JSON；原始Pydantic `.errors()`可能含input，不直接输出。无日志/HTTP接入；未来T05/T10仍需成熟库与统一脱敏。
- 新包不接入任何应用、HTTP或数据库；无新增依赖。原public入口/config/空目录、M0、v2.t03/OpenAPI/TS、旧迁移/DEMO夹具/研究保持原状。

### 精确变更文件

9个既有相关文档更新，12个新增，共21路径：

```text
AGENTS.md
README.md
docs/requirements.md
docs/architecture.md
docs/api.md
docs/database.md
docs/tasks.md
docs/CHANGELOG.md
docs/DECISIONS.md
docs/identity.md
docs/acceptance/T04_identity_provider.md
services/api/app/auth/__init__.py
services/api/app/auth/schemas.py
services/api/app/auth/provider.py
config/identity/README.md
config/identity/offline.example.json
config/identity/keycloak-boundary.example.json
tests/unit/auth/conftest.py
tests/unit/auth/test_configuration.py
tests/unit/auth/test_login_context.py
tests/unit/auth/test_provider_boundary.py
```

### 实际命令与结果

以下均为本轮实际执行，不使用T03历史通过替代。PowerShell cwd为`D:\Projects\study`。

| 命令/检查 | 实际结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest tests/unit/auth -q` | 最终退出0：131 passed，1条既有Starlette/AnyIO弃用warning；独立身份专项，无外部网络/真实身份服务 |
| `.\.venv\Scripts\python.exe -m pytest -m 'not postgres' -q` | 退出0：606 passed，4 deselected，1条上述warning，15.83s；含M0/契约/模式/研究/新身份的离线回归，PG未执行 |
| `.\scripts\web.ps1 -Action test` | 退出0：4文件、18 tests passed |
| `.\scripts\web.ps1 -Action typecheck` | 退出0：vue-tsc --noEmit |
| `.\scripts\web.ps1 -Action build` | 退出0：vue-tsc --noEmit与Vite生产构建；构建产物不上传，也非业务部署 |
| `.\.venv\Scripts\python.exe -X utf8 scripts/generate_contracts.py --check` | 退出0：v2 artifacts match，只读；原v2.t03产物未变 |
| `.\.venv\Scripts\python.exe -X utf8 scripts/verify_contract.py` | 退出0：M0 TypeScript/OpenAPI契约一致 |
| `.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py` | 退出0：两份原输入UNCHANGED |
| `.\.venv\Scripts\python.exe -m py_compile services/api/app/auth/__init__.py services/api/app/auth/schemas.py services/api/app/auth/provider.py tests/unit/auth/conftest.py tests/unit/auth/test_configuration.py tests/unit/auth/test_login_context.py tests/unit/auth/test_provider_boundary.py` | 退出0：新7模块语法编译；不是Lint/静态类型检查 |
| `.\.venv\Scripts\python.exe -X utf8 .cache/t04_validate_20261002.py`，完成后`--final`及暂存后`--stage --final` | 均退出0；21当前Task文件、98范围外文件保护、138本地链接；M0规范化OpenAPI/旧Task/日志/ADR不改，文档状态与暂存一致，无高置信秘密形态/越界，原输入暂存blob与生成LF保持。缓存辅助不上传 |
| 私有仓库与只读Git检查 | origin为既定HTTPS仓库，isPrivate=true，明确codex/t04-identity-boundary，起始与提交前不存在用户暂存；按显式路径暂存审查与普通commit/push，最终SHA以Git及最终报告核对 |

收尾新增独立FakeProvider Protocol消费用例后，专项由130增至131，完整离线回归由605增至606，均重新实际执行通过；两种不同实现由同一消费函数调用，不依赖离线make_callback。

额外只读独立审查实际执行`PowerShell here-string → .\.venv\Scripts\python.exe -B -` stdlib/JSON stdin probes，最终退出0：固定URL/Unicode异常（最终9负例）、安全错误出口、factory/direct constructor生产与伪造runtime拒绝；fresh process对public factory禁止auth/M0/DB导入与所有外网连接/DNS，只有基础paths，未导入SQLAlchemy/psycopg。auth专项会禁止外部连接/DNS；Windows异步TestClient需要精确回环socketpair，不能写成所有socket均禁止。主验收命令以上表可复现测试为准。Git既有core.autocrlf仅产生已知LF/CRLF暂存提示，不改全局设置；`git diff --cached --check`退出0。

### 首次失败及修复

1. 首轮`pytest tests/unit/auth -q`退出1：97 passed、2 failed。测试的RFC预期常量漏尾部`M`，已按[原RFC Appendix B](https://datatracker.ietf.org/doc/html/rfc7636#appendix-B)核实，完整challenge43字符；另一用例在make_callback就拒未知assertion，改为合法Artifact后替换proof，才覆盖verify_callback拒绝。算法未因错误样例更改。
2. 独立probe发现首版URL校验接受`.`主机、空端口/0端口与百分编码控制/点段；本Task收紧主机/端口和固定路径校验，补负例并最终通过。
3. 独立probe发现lone surrogate proof在UTF-8比较中逸出原始UnicodeEncodeError；加入固定安全转换与fixture检查，state/nonce/verifier/assertion负例通过。正常UTF-8材料仍按原样比较。
4. 独立只读综合probe第一次误写不存在的`api.production`入口退出1；纠正为既有`api.public.create_public_app`后通过。这是验收脚本错误，不是新增应用故障。

### 未执行或不适用

- Lint：未执行。项目无Python/前端lint入口，ruff不可用；未为此Task引入工具依赖。
- Python静态Type Check：未执行。无配置入口且mypy不可用；TS Type Check已实跑通过，语法编译不冒充类型检查。
- PostgreSQL4项：排除/未执行。本Task无持久化、迁移或SQL权限变化，旧T01不能冒充本轮数据库通过。
- 真实Keycloak租户/client/MFA/恢复、网络换码/JWT cryptography、持久state消费与会话：未执行，尚未实现/无真实配置，属T05/T06及部署验收，不宣称通过。
- 浏览器E2E、监听服务、真实资料/账号/生产发布：未执行，本Task没有UI/HTTP应用接入或此项授权。不进行部署/采购。

### 收尾与剩余问题

tasks/CHANGELOG、ADR-015及受影响文档同步为T04已完成；D04只供应商/接口层部分确定，D01/D02/D06等仍待决。无T04阻断问题，既有Starlette/AnyIO warning未顺带修改；生产认证尚不可用。验收后仅保存本Task21文件，普通推送codex/t04-identity-boundary并核对远程SHA/private；源码上传不代表部署，不自动启动T05。
