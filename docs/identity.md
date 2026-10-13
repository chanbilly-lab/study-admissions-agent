# D04身份供应商与T04–T10认证运行

2026-10-03最新：T08/T09已完成；T10审计与日志源码验收已完成。identity HTTP/生成契约仍为`v2.t09`，当前认证head为`0006_audit_t10`（T09历史head0005）。共享源码及独立验收见[sharing](sharing.md)，产品政策/合成准入见[privacy](privacy.md)，真实处理和未成年私有关闭。用户已授权依次T08–T20，每Task独立验收/保存；以下历史阶段范围不撤销新授权。

更新日期：2026-10-03，Asia/Hong_Kong。阶段背景：用户已明确选择**自托管Keycloak**，T06历史增量已完成；T07于2026-10-03完成离线/隔离实库对象授权验收；T08时新授权准入基础及依次独立验收的后续批次。固定端点授权码/签名验证、一次性登录和服务器会话已离线/隔离实库验收；真实身份服务未安装、未注册client/账号、未部署，不开放公众注册。D04仍部分确定，不能用示例代替真实租户验收。

## T07对象权限基础

T07已完成基础验收，服务器从经验证opaque会话与当前DB角色生成Principal。所有私有对象能力使用固定role/kind/action和SQL owner/parent/state条件；data_admin不因此获得学生资料，公共管理动作还需T06当前签名强度，operations仅固定非个人状态能力。角色不由IdP/客户端/模型赋予，旧账户默认无role。身份factory内部装配Authorizer，默认关闭仍不导DB；不增加HTTP路径、session wire、OpenAPI或前端字段，private_business_available仍false。未来私有GET依赖的成功/拒绝响应均no-store，写入保留中央CSRF；mutation不能仅依赖读取快照，需同事务execute_owned重验。T07历史head0003，当前须显式upgrade到0006；T08实现合成准入与真实处理关闭，注册/真实共享/队列仍未开放；T09仅显式fixture的metadata grant。详情见[authorization](authorization.md)与[T07验收](acceptance/T07_object_authorization.md)。

## T10审计与显式日志配置（2026-10-03，源码验收完成）

当前认证链增加`0006_audit_t10`和`auth_audit_events`，保持旧迁移、M0和身份wire。日志模块、schema/关闭factory不自动安装全局handler，也不因审计导入数据库；只有显式启用身份配置才创建认证存储并检查新增表/字段和head。没有默认审计角色或审计HTTP路径。

已接入的关键登录、退出、角色、owner/shared和准入操作使用固定动作与最少内部责任引用；不保存token、issuer/sub、email、IP/UA、请求内容、学生payload或原始异常。成功审计在业务Session内追加/flush，必需审计失败使本地变更回滚并安全503；有权限要求的操作在审计I/O之后保持既有锁并重验当前身份、时效和对应证明。失败审计等原事务释放后另事务尽力记录，不掩盖原错误；调用者仍持有事务时不另开失败连接。T08已提交的减权后403记录成功失效，不存儿童年龄。

内部`AuditService.list_events`/`purge_expired`要求当前有效operations角色和T06显式签名强度策略，并在审计flush后再次重验；角色、过去Principal或历史MFA通过均不能复用为当前权限。它们不提供真实学生内容或管理员界面，真实Keycloak/MFA/恢复仍需独立配置验收。

D06常规脱敏日志最多30天，审计`expires_at`最多24个UTC日历月（按月末调整，不是720天）。审计清理是显式、每批最多1000项的内部维护；`purge_log_files`只维护可信调用者指定的专属目录，固定`admissions-YYYY-MM-DD.jsonl`按UTC文件名日期而非mtime判断，删除和扫描分别有界，不递归或清理未知文件。stderr收集器、生产备份35天及恢复后的删除传播未验收。详细契约和最终实际结果见[audit](audit.md)、[T10验收](acceptance/T10_audit_redaction.md)；最终回归结果见该记录；不能作为生产运行验收。

## T06写保护、退出与管理员策略

当前identity schema为`v2.t09`（T06/T08时为v2.t06/v2.t08），新增GET `/v2/auth/csrf`及POST `/v2/auth/logout`，其余T05登录wire保持。前端auth模式从同源API获取43字符CSRF到闭包内存，退出时携带`X-CSRF-Token`；浏览器自动产生Origin。所有POST/PUT/PATCH/DELETE在中央检查有效会话、唯一token及唯一固定Origin，遗漏route dependency也不能绕过；未来非Cookie入口必须另Task明确认证边界，当前无豁免。GET身份回调仍用state/nonce/PKCE。

可信Origin由服务器`redirect_uri`解析scheme/host/有效端口，必须精确序列化匹配；不信任请求Host/X-Forwarded。Vite改变后端Host不改变浏览器Origin，回调应登记前端外部origin。生产HTTPS，开发回环例外仍受既有配置校验。CSRF错误403不撤有效会话；无/过期/已撤session401清Cookie；200 `{data:{logged_out:true},meta}`才确认服务端撤销当前会话。退出不清Keycloak SSO、不撤其他设备，不自动跳出全局账号；失败显示退出未确认。

T06新增`0002_auth_t06`，当前认证迁移须显式upgrade head到`0006_audit_t10`，已有会话CSRF NULL通过锁行首次获取后形成摘要/密文pair，TTL不延长；应用启动仅ready检查，未升级503，不运行DDL/seed。迁移流程仍使用下方T05提供的独立profile命令，它现在upgrade到新head；不要把旧revision手工替换或删除历史数据。

`SessionAuthSettings.admin_assurance_policy`默认`{"enabled":false}`。显式启用要求`trusted_issuer`、不同的`admin_client_id`/`student_client_id`、非空`allowed_acr`/`required_amr`以及`max_auth_age_seconds`，须先由责任人验证真实Keycloak签名claim映射；不能默认假设acr=2或amr=otp表示已满足策略。签名验证后的acr/amr/auth_time与服务端固定client/issuer来源保存为最少会话依据；没有auth_time不能用iat补。旧/缺/错误client/策略不匹配/认证过期即403。当前仅内部强度检查，无管理员HTTP登录/step-up、角色管理、注册或恢复端点；T07可信维护函数可登记应用角色，不能由请求调用；强度通过仍要求显式应用权限verifier，不代表管理员业务授权。真实D04 tenant/client/MFA/recovery与发布准入仍待验收。

内部`create_execution_reference`仅由已认证会话生成session_id/user_id引用；`revalidate_execution`/`execute_authenticated`在执行时重新读owner、active、revoked、absolute expiry，并要求服务器提供permission_verifier（缺省拒绝）。这是本地同步扩展接口及离线权限桩验收，不是已建队列或T07同事务对象授权；T07另有Authorizer，T09 grant使用独立同事务服务，不提供跨系统副作用的原子保证。

离线专项和浏览器示例：

```powershell
# 新隔离库，URL只注入过程变量；不能指向生产或旧验收库
.\.venv\Scripts\python.exe -m pytest tests/unit/auth tests/security/auth tests/contracts/test_identity_contract.py -m 'not postgres' -q
# TEST_POSTGRES_URL用于旧认证回归的auth_t05_test；T06_TEST_POSTGRES_URL用于新auth_t06_test
.\.venv\Scripts\python.exe -m pytest tests/security/auth -m postgres -q
.\.venv\Scripts\python.exe scripts/generate_contracts.py --profile identity --check
.\scripts\web.ps1 -Action test
.\scripts\web.ps1 -Action typecheck
.\scripts\web.ps1 -Action build
node scripts/auth_t06_browser_smoke.mjs
```

新浏览器脚本使用隔离本机合成IdP/测试库，不需要API密钥或真实用户；占用8000/5186/9444时失败，不终止用户服务。旧T05脚本/夹具保留历史，旧“没有退出按钮”断言不适用于当前UI，不冒充本轮通过。完整实际命令、fresh PostgreSQL、未执行项与限制见[T06验收](acceptance/T06_session_csrf.md)，决策见[ADR-017](DECISIONS.md)。

## T05登录入口与配置（继续复用）

`services.api.app.api.identity:create_identity_app`只挂/v2。没有`IDENTITY_CONFIG_FILE`时默认关闭：认证路由503，基础配置/空目录可读，无DB/JOSE/供应商实例或连接。原`api.public:create_public_app`及M0入口不变，T04边界工厂仍是纯占位/离线接口，新增真实协议只由T05 KeycloakOidcAdapter提供。

显式配置见[session.example.json](../config/identity/session.example.json)。示例保留.invalid域名/占位client，不会自动加载，不能当真实账号或服务。文件仅含非秘密配置；loader拒重复字段、超64KiB、额外字段与inline秘密。`IDENTITY_CLIENT_SECRET`和`IDENTITY_CONTEXT_KEY`只从当前进程注入，后者为独立、受保护、稳定Fernet key（32随机bytes的标准URL-safe base64，不能使用示例测试零key）。不读取M0 .env，不将秘密放URL/Git/前端。供应商openid/S256/client_secret_basic/RS256及端点从固定issuer推导，不做任意discovery。enabled必须verified；生产回调HTTPS且拒测试传输/合成账户。

启用还必须显式配置`V2_DATABASE_URL`为受限认证PostgreSQL连接，并先执行认证迁移。当前readiness检查`0006_audit_t10`、六张auth、两张privacy、四张grant业务表及新增`auth_audit_events`的必要字段，不创建或导入任何用户。预登记账户由后续准入/运营流程负责，没有公开/管理注册API，也不迁移DEMO用户；没有匹配active issuer/subject一律403。生产用户的is_synthetic必须false，测试仅合成。

### 无密钥关闭入口

在未设置IDENTITY_CONFIG_FILE的独立shell中，运行以下示例；不是部署步骤：

```powershell
$env:V2_APP_ENVIRONMENT='production'
$env:V2_DATA_MODE='verified'
$env:V2_MODEL_MODE='disabled'
.\.venv\Scripts\python.exe -m uvicorn services.api.app.api.identity:create_identity_app --factory --host 127.0.0.1 --port 8000 --log-config config/logging/identity.json --no-access-log
```

`GET /v2/auth/session`明确503；`/v2/config`仍为foundation v2.t03且business_available=false。`--log-config`显式安装[封闭日志配置](../config/logging/identity.json)，覆盖root及配置的app/uvicorn/httpx/httpcore/SQLAlchemy/FastAPI/Starlette处理器，只输出固定operation_id、服务端request_id、状态、固定原因和必要耗时；原消息、参数、异常及附加请求内容丢弃。继续关闭访问日志以避免不必要的回调URL处理；上游代理、其他进程、后挂自定义handler和托管收集器不在此配置控制范围，须另行验收。默认factory不修改进程日志配置，不能省略该运行选项后宣称所有输出已脱敏。

### 认证库显式迁移（真实配置验收前不启用公众服务）

在已配置受保护V2_DATABASE_URL的独立维护进程中执行：

```powershell
.\.venv\Scripts\python.exe -m alembic -c services/api/auth_alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c services/api/auth_alembic.ini current
```

当前head为`0006_audit_t10`，使用独立auth_alembic_version（保留0001–0005）；旧M0 profile完全不变。不要对未知现有库自动降级/删表；隔离测试库新schema验证后再按正式备份/权限/恢复流程部署。当前迁移无用户seed、无启动自动清理/隐私删除/GRANT/RLS；T10显式维护不代表生产清理调度或删除传播已实现。

### 前端与离线验收

`VITE_APP_MODE=auth`显式选择独立登录页，默认仍M0；同源`/api/v2`经Vite代理剥/api后到API `/v2`。供应商注册的外部redirect必须和实际浏览器origin/path完全相同，例如本机测试`http://127.0.0.1:5185/api/v2/auth/callback`（仅非生产）；正式配置必须HTTPS。服务端成功303固定/，无可控return URL。会话状态/刷新、顶层登录与当前隐私设置，不展示角色、不存token、不开放画像/注册；当前T06新增退出按钮与CSRF，见上方T06段。

```powershell
$env:VITE_APP_MODE='auth'
.\scripts\web.ps1 -Action dev
```

测试不用真实Keycloak、API密钥、真实学生或外部网络。Python专项用真实RSA签名的固定MockTransport；浏览器用隔离本机TLS授权页、合成SQLite测试库与fake backchannel。PostgreSQL另用新隔离库/随机schema验证锁与唯一约束，不以SQLite代替实库验证。Secure/HttpOnly Cookie始终保留；浏览器仅本机夹具忽略临时证书，不能推广到生产TLS。脚本需要本机Node/Playwright/Edge和空闲8000/5185/9443，端口占用时不杀用户服务；密钥/证书/数据库只在忽略.cache。

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/auth tests/contracts/test_identity_contract.py -m 'not postgres' -q
.\.venv\Scripts\python.exe -m pytest -m postgres -q
.\.venv\Scripts\python.exe scripts/generate_contracts.py --profile identity --check
.\scripts\web.ps1 -Action test
.\scripts\web.ps1 -Action typecheck
.\scripts\web.ps1 -Action build
node scripts/auth_browser_smoke.mjs
```

上述T05历史PG命令须有专用TEST_POSTGRES_URL，测试限定本机独立auth_t05_test，未配置不代表通过。node需先使用web.ps1配置的bundled运行时加入进程PATH（脚本支持明确T05_PLAYWRIGHT_MODULE文件路径与T05_PYTHON）；具体实际命令/结果见[T05](acceptance/T05_login_session.md)。运行时登录TTL默认300秒、会话3600秒可调，不是正式D06留存；登录失败事务一次消费，T05时退出/CSRF待T06；当前增量以上方章节为准。T07对象授权基础已完成独立验收；全局SSO退出未实现，真实管理员MFA与真实业务仍未验收。

## T04基线说明（保持历史接口边界）

下方描述T04完成时的行为；该纯离线/占位工厂在T05后仍保留。不将其断言、示例或历史测试结果冒充新增真实签名/持久会话验收。T05依赖/迁移/HTTP增量以本页上方与ADR-016为准。

## 已确定配置

| 项目 | T04基线 | 状态与后续要求 |
| --- | --- | --- |
| 身份供应商 | 自托管Keycloak；应用依赖标准Provider协议 | 用户已选，保留可替换接口 |
| 应用方式 | 模块化单体内FastAPI BFF，授权码、PKCE S256 | 不新增微服务；HTTP登录/回调与换码留T05 |
| 信任配置 | 服务端固定provider_id、issuer、client_id及回调allowlist | 不能从请求参数选issuer/JWKS/metadata地址 |
| issuer | 固定HTTPS realm地址，按原样精确比较 | 真实域名/realm待登记，不按大小写或尾斜线自动合并 |
| Keycloak端点 | 固定issuer下的`/protocol/openid-connect/auth`、`/token`、`/certs` | 配置推导；metadata只能核对，不能替换信任配置或触发发现请求 |
| client类型/认证 | 机密BFF client、`client_secret_basic` | 不接收public/none客户端；秘密未来由受限运行配置注入，不进Git |
| OIDC scope/算法 | 最少`openid`、授权码、S256、允许RS256 | 只是接口配置，不代表本轮已验证真实JWT签名 |
| 回调 | 精确、无通配的服务端登记allowlist | HTTPS；开发回环地址的例外依代码校验，不自动允许外部地址 |
| 主体键 | case-sensitive `(issuer, subject)`元组 | 不按email合并、不拼接歧义分隔串；数据库唯一约束留T05 |
| 管理员 | 独立受限client/认证流程，强制MFA | 延续既有架构要求；IdP角色不能自动赋应用管理员权限 |
| 注册/恢复 | 公开注册关闭；恢复由供应商托管 | 实际找回政策、邮件、责任人与强认证恢复验证待确认 |

端点与配置依据为[Keycloak OIDC文档](https://www.keycloak.org/securing-apps/oidc-layers)；S256与verifier按[PKCE RFC 7636](https://www.rfc-editor.org/rfc/rfc7636)。[Keycloak管理指南](https://www.keycloak.org/docs/latest/server_admin/index.html)中的默认条件式2FA可能在未配置因子时跳过；默认邮箱找回也涉及OTP重新配置。这两项默认行为不能作为管理员MFA/恢复验收，未来需独立强制流程和恢复证明。

## T04模式与应用边界

| provider_mode | 用途 | production | 当前行为 |
| --- | --- | --- | --- |
| disabled | 默认关闭 | 可构造边界 | 身份操作明确Unavailable |
| offline | 显式合成固定供应商，仅development/test | 拒绝配置 | 只按服务端固定夹具返回合成主体 |
| oidc_boundary | Keycloak信任配置和授权请求描述 | 可构造边界 | 换码/JWT适配未实现，明确Unavailable；不回退offline |

模式不读取M0 `.env`、DEMO token或模型密钥，不自动加载配置示例。auth模块不挂入public/M0应用；当前`/v2`仍只有基础配置/空目录/schema，schema版本与生成TS不变。包级离线身份检查不能用于真实登录，不能赋予角色、owner或grant，也不能进入生产私有业务。

配置和运行时均在供应商创建边界重验，避免用Pydantic `model_copy`/`model_construct`绕过校验。LoginContext由服务端建立，绑定provider/issuer/client/登记redirect与state/nonce/PKCE、带timezone-aware有效期；秘密用SecretStr并隐藏repr。纯函数检查与固定离线断言只验证上下文绑定，不提供持久一次性消费/重放保证，不将离线断言冒充JWT。供应商入口将校验异常转换为固定`AuthProviderError`；`hide_input_in_errors`只隐藏Pydantic文本错误，原始`.errors()`默认可能含input，不能直接作为日志或HTTP错误。本轮无日志/HTTP接入；未来T05/T10仍须统一脱敏，也不能输出显式解封后的秘密。

## 真实认证启用前待补配置

1. D01确认实际大陆部署区域/主机/网络/运维责任；选定维护的Keycloak版本与补丁流程。T04不虚构版本或部署可达性。
2. 登记真实realm issuer、学生/管理员client_id、精确回调、HTTPS hostname及可信端点；确认实际客户端S256强制、代码流程、scope/算法与秘密存储轮换。
3. 核实跨大陆/港澳台用户的真实身份服务可达性和实际数据处理位置；本地离线通过不能代替验证。
4. 明确账号恢复责任人、身份恢复证明/审核、邮件渠道及防止邮箱重置绕过管理员MFA的执行流程；实际强制MFA、管理员再次认证与恢复检查留T05/T06及发布验收。
5. D02未成年准入/告知与D06留存期限等仍为门槛；认证成功不自动许可真实画像采集。
6. T05需选择成熟OIDC/JWT库，验证签名、issuer/audience/nonce/有效期/PKCE并持久消费state，建立账号与会话、轮换Cookie；T06完成撤销/CSRF。本轮不提前添加库、迁移、路由或会话存储。

## 离线使用与验收

内部接口为`AuthProviderSettings`、四字段受限`ProviderMetadata`、`IdentityKey.as_tuple()`、`OfflineIdentityFixture`、`LoginContext`、离线`CallbackArtifact`、`AuthorizationRequest`及标识来源的`VerifiedIdentity`。`create_identity_provider(settings, runtime_settings, fixtures=None, metadata=None)`同时重验配置和既有`V2RuntimeSettings`；`IdentityProvider`只要求`settings`、`prepare_authorization`与`verify_callback`，没有供应商SDK耦合。当前内置配置profile/factory仅所选Keycloak边界和离线替身，替换其他供应商需独立同协议适配与对应固定信任配置，不意味着请求可指定任意IdP。`create_login_context`、`pkce_s256`、`validate_callback_binding`为纯绑定工具；`make_callback`只属于固定离线实现，不是未来HTTP入口。

默认离线主体`offline-alice`/`offline-bob`仅为合成夹具，assertion标记见配置说明。登录上下文默认离线测试有效期参数300秒，可显式1–3600秒；这不是会话或用户资料的生产留存决定，也不解除D06。

配置示例与使用方式见[config/identity](../config/identity/README.md)。示例使用保留域名和合成身份，无真实秘密，不能视为已注册tenant。本轮没有外部身份服务或API密钥也能运行原基础应用并执行auth离线测试；它不提供真实登录界面。

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/auth -q
.\.venv\Scripts\python.exe -m pytest -m 'not postgres' -q
```

实际接口名称、文件清单、命令结果与未执行项以[T04独立验收](acceptance/T04_identity_provider.md)为准；[ADR-015](DECISIONS.md)记录供应商选择及范围。应用前端、依赖、迁移、生成契约与真实资料均保留原状。

## T40 当前减权台账屏障

显式安装RightsGuard后，AuthStore/服务固定engine/clock/guard引用重验当前外台账与业务水位；不得移除guard或改连同schema冒充独立。当前退出/重新登录轮换旧会话、角色撤销精确grant epoch留外部最小事件，原Cookie/CSRF及权限规则不放宽。启用生产身份缺guard拒服务；默认关闭入口无新DB初始化。

业务恢复旧会话时，最新证明或重放不足即503；完成replay后旧revoked会话仍401，其他owner有效当前身份保持。terminal删除不通过再登录/声明/同意复活。真实Keycloak/MFA/生产ACL未验收。
