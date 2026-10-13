# T04–T10 身份配置示例与日志运行

T05新增`session.example.json`，只在显式IDENTITY_CONFIG_FILE指定时加载；.invalid/client为占位，不能运行真实登录。默认无文件则关闭且无数据库连接。loader拒inline client_secret/context_encryption_key，秘密只由IDENTITY_CLIENT_SECRET/IDENTITY_CONTEXT_KEY注入；启用必须verified、显式认证迁移和精确预登记active账户，不自动注册。配置、迁移和代理路径见[运行说明](../../docs/identity.md)，真实tenant/MFA/恢复与公众发布门槛仍未验收。

## T06配置增量

显式SessionAuthSettings新增默认关闭的`admin_assurance_policy`（缺省`enabled:false`）；启用必须冻结trusted_issuer、不同admin/student client、allowed_acr、required_amr、max_auth_age_seconds，并通过真实供应商配置验收。当前未登记真实管理员client/claim映射，不自动开启，不用示例值冒充真实MFA。公开恢复/注册与管理业务仍关闭。

CSRF可信Origin来自已注册redirect_uri，而非请求Host或代理header；无需另加宽泛CORS/Origin allowlist。已有会话保留但T06历史增量为0002_auth_t06，当前认证schema需显式upgrade到0006_audit_t10（保留旧迁移），缺迁移启动503。细节与新离线命令见[身份运行说明](../../docs/identity.md)及[T06](../../docs/acceptance/T06_session_csrf.md)。

## T10日志与审计增量（2026-10-03，源码验收完成）

身份HTTP契约仍为`v2.t09`。当前源码增加`auth_audit_events`及其readiness检查；启用认证前需在维护进程显式迁移到`0006_audit_t10`，启动不执行DDL/seed。成功审计和权限/准入变更在同一事务追加并flush，之后重验当前会话、角色或对应证明；内部审计读取/清理还要求当前operations角色及T06显式配置的签名认证强度，不新增管理员HTTP入口。

运行日志配置与`IDENTITY_CONFIG_FILE`身份配置分开。以下命令从项目根目录显式加载[安全日志配置](../logging/identity.json)，不自动启用身份服务或注册账户：

```powershell
.\.venv\Scripts\python.exe -m uvicorn services.api.app.api.identity:create_identity_app --factory --host 127.0.0.1 --port 8000 --log-config config/logging/identity.json --no-access-log
```

配置处理器只输出封闭operation/request ID、状态、固定原因及耗时，丢弃原消息/参数/异常和请求内容；factory不安装全局日志handler。其他进程、上游代理和后来另挂的自定义handler不在控制范围。D06日志30天、审计最多24个日历月只对应显式有界维护接口：stderr收集器留存、生产备份与删除传播尚未验收，不启动自动清理。实际结果以[T10验收](../../docs/acceptance/T10_audit_redaction.md)为准，源码回归不代表生产服务已验收。

以下T04示例与工厂继续保持纯边界/固定离线行为；T05换码验签由独立KeycloakOidcAdapter实现，不将旧assertion当JWT。

这些文件不自动加载，不属于真实 Keycloak realm/client 注册，也不能启用登录。域名 `.invalid`、client 名称和离线主体均为占位或合成测试资料，文件没有真实秘密。

- `offline.example.json`：仅供 development/test 明确选择的离线供应商；production 构造和工厂均拒绝。
- `keycloak-boundary.example.json`：Keycloak OIDC 信任边界占位示例。配置验证通过只能生成纯授权描述；真实换码和 JWT 验证始终明确不可用，不回退离线。

由可信服务端使用 `json.loads` 和 `AuthProviderSettings.model_validate` 显式读取。配置默认 disabled，不读环境变量或 `.env`。issuer 是精确 HTTPS Keycloak realm URL；三个端点由 issuer 推导，显式端点及四字段 `ProviderMetadata` 必须完全匹配。metadata 不是未经筛选的完整 discovery 文档，不获取 URL。

回调只接受完整精确 allowlist，禁止通配、userinfo、query、fragment；仅 development/test 可登记明确的 localhost、127.0.0.1 或 ::1 HTTP 回调，production 仅 HTTPS。Issuer、授权/token/JWKS 端点始终 HTTPS，不归一化不同 issuer。不要在 URL 中放秘密。

本轮固定路径不支持百分编码，拒绝编码控制/点段和无效 hostname、空端口或非1–65535端口。错误的安全文本不回显输入；Pydantic 的原始 `errors()`/输入对象仍可能含秘密，不能直接打印或写日志，应使用边界提供的固定错误码/消息。

T04 的 `client_secret_basic`、`RS256` 是后续真实 BFF 适配器的基线，本轮没有 secret、网络换码或签名校验。未来 secret 从受保护配置注入，不能写入这些示例或 Git。`AuthorizationRequest` 中的 state/nonce 使用隐藏的 SecretStr；不打印授权 URL、登录上下文或 token。

`create_login_context` 使用服务端随机 state/nonce/verifier，默认离线有效期参数300秒（允许显式1–3600秒，不代表生产留存策略）。`CallbackArtifact`、`make_callback` 是内部离线测试协议，不是 HTTP 回调 body。校验绑定和有效时间不能代替 T05 的持久 state 消费、防重放、真实 JWT 验证、账号映射及会话。

固定默认离线 assertion 为 `OFFLINE_ASSERTION_ALICE` 和 `OFFLINE_ASSERTION_BOB`，主体为 `offline-alice` 和 `offline-bob`，均明确 `is_synthetic=true`。它们不能作为生产凭据；不产生应用 owner、role 或 grant。原foundation public/v2及T04边界工厂不接认证HTTP；显式identity profile当前提供auth、T08privacy与T09合成metadata共享设置，默认关闭认证/真实处理。
