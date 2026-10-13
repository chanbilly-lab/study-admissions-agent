# T07 对象级授权基础

## T14存储增量（2026-10-03，源码验收完成）

check_owned_in_transaction复用当前owner/active root规则，closed catalog.storage.write/read，POLICY_VERSION=T14_owner_v3。StorageService每次结合T08 core或强data_admin/当前source许可；IO与audit后重验。T09 metadata字段/动作不扩展为bytes下载。详见[storage](storage.md)。

## T13来源能力增量（2026-10-03，源码验收完成）

新增封闭能力catalog.source.register/catalog.source.read和同事务check_capability_in_transaction；即时data_admin及签名MFA/会话/角色重验，POLICY_VERSION=T13_owner_v2。SourceService在调用者业务事务内授权，成功最小审计与登记/读同事务；当前责任人只能为执行者本人，不接受客户端owner或角色。现有require_capability及对象权限保持。真实来源责任名单默认空且real_sources_ready=false；这不是正式D03审查完成。详见[sources](sources.md)。

## T10审计增量（2026-10-03，源码验收完成）

当前认证head为`0006_audit_t10`，增加`auth_audit_events`及其readiness检查，启动仍不建表/seed。identity HTTP/生成契约仍为`v2.t09`；owner/private_business边界不开放真实领域数据，也没有审计HTTP或前端管理入口。

角色维护、本人对象检查/列表/登记/执行与共享授权操作接入封闭事件。同一业务Session追加并flush成功审计；审计失败回滚本地变更并返回安全503，flush后继续以当前锁内的账户、会话、角色/强度和对应对象或证明重验，不能复用flush前许可。未授权对象的失败事件不保存请求中的对象ID；原事务退出后才另事务尽力记录失败，调用者仍持有事务时不抢开连接，不掩盖原固定错误。

内部`AuditService.list_events`/`purge_expired`需要当前operations角色和T06显式签名强度策略，审计I/O后再次重验。`operations.status`原能力不会因此自动获得读取权限，过去角色/Principal/MFA快照不能授权；没有管理员注册/step-up或真实学生内容接口。审计期限最多24个UTC日历月，清理显式、每批最多1000项；专属日志文件维护不代表生产收集器/备份已验证。当前源码验收完成，实际结果见[audit](audit.md)、[T10验收](acceptance/T10_audit_redaction.md)。

## T09独立共享增量（2026-10-03）

T09实现合成fixture的独立对象metadata授权；正式共享关闭。T07 owner-only矩阵和T08核心用途不授第三方权限；recipient须独立会话接受，双方原证明、对象version、field/action及期限逐次重验。撤销/拒绝/退出减少许可，坏告知或陈旧正向proof不能阻挡；旧记录后续重新确认不能复活。字段仅status/version、动作read/list，不开放对话、真实附件/导出payload或worker。详情与实际测试限制见[sharing](sharing.md)、[T09验收](acceptance/T09_explicit_sharing.md)。

更新2026-10-03。下方记录T07 owner-only基础及其历史验收；T09/T10增量以上方章节为准。真实画像、计划、附件、导出和作业业务没有开放，`private_business_available=false`；测试只登记合成权限元数据。原M0演示身份与本模块UUID身份分开，不迁移DEMO用户。

## 服务器契约

`AuthService.get_principal(cookie)`验证opaque会话、账户和当前持久角色，生成冻结的内部`Principal`。`Authorizer`每次重新验证当前状态，传入对象中的roles或身份快照不能授权。角色是可信服务端预登记的`student/data_admin/operations`，受granted_at、expires_at、revoked_at约束；旧账户没有默认角色。没有HTTP角色管理、IdP角色映射或自动赋权。

| 角色/能力 | 允许范围 | 额外条件 |
| --- | --- | --- |
| student 私有 read/list | 本人profile/plan/attachment/export/job | 当前会话、active对象及同owner active根 |
| student write | 本人profile/plan | 版本touch需expected_version；不写学生payload |
| student download | 本人attachment/export | 同owner active profile/plan父 |
| student export | 本人profile/plan | 当前权限；没有真实导出工件 |
| student execute | 本人job | 同owner active根，同事务执行时重验 |
| data_admin 公共事实能力 | catalog.import/review/publish/withdraw | 当前应用角色且T06默认关闭策略中的签名认证强度通过 |
| operations | operations.status | 仅非个人汇总能力，没有真实运维端点 |

管理角色不能直接访问任何学生私有资料；混合student角色仍仅本人。未知role/kind/action/组合默认拒绝；T07 owner-only服务不使用第三方grant。T09另有独立合成metadata共享服务，真实监护/顾问及业务共享未开放。客户端owner/roles、模型和前端都不赋权。

匿名401，缺功能角色403，foreign/missing/deleted对象一致404，旧expected_version409，存储/配置不可用503；不把外部值写错误消息。SQL查询先限制owner/type/status/有效根再count/page，没有全量加载后Python过滤。列表锁分页窗口及父对象、等待后重读scope；窗口变化最多重试3轮，仍不稳定则503，不返回未锁的新窗口。生产拒绝合成用户与合成归属元数据。

## 调用边界

`list_owned`返回受限items/total/next_cursor；`require_owned`只给读取快照。`touch_owned`仅profile/plan版本递增，通用API不接受修改id/type/owner/parent/is_synthetic。`execute_owned`回调接收同一SQLAlchemy Session、重新读取的Principal和已授权资源；账户→会话→角色→父/对象锁序、锁后时效复核，与`AuthStore.revoke_role`锁账户的维护入口串行化。错误/回调异常回滚本地事务；网络/文件/其他系统副作用不具事务原子保证，可信callback不是任意代码沙箱。

延迟引用仅内部对象，不是HTTP bearer。执行/缓存重读当前会话/角色/对象及父；过去通过不能保证现在执行。`cache_key`包含actor/session、当前角色上下文、固定策略版本、kind/action、resource/version、显式filters；`cached_value`先重新授权再从服务器mapping读取当前key，读取后再次校验时效及范围摘要，次要角色到期导致范围变化也返回未命中。filters是最多32项的有界ASCII字符串tuple，不接任意JSON缓存键。不建设缓存引擎、队列或真实worker。

`current_principal`与`owned_resource(kind, action, resource_param='resource_id')`是后续私有路由的固定服务器依赖；不从query/body/header取owner/role。读取依赖不能代替写入时`execute_owned`重验。身份factory内部装配Authorizer及安全AuthFlowError handler，关闭模式不导数据库。依赖标识私有读取，中央中间件给成功/拒绝no-store/no-cache/no-referrer与server request_id；依赖顺序须先建立私有身份标记再做query/body检查，不声称自动识别任意遗漏私有依赖的GET。写方法继续要求当前会话、固定Origin和CSRF。正式factory/schema不挂测试probe或新增业务路径，T06 wire与TS保持。

## 数据库与运行

认证链增量`0003_auth_t07`创建`auth_user_roles`和`auth_owned_resources`，共六张auth业务表与版本表，保留0001/0002及M0链。registry只存UUID/type/owner/state/version/synthetic/parent元数据；派生对象复合FK保障同owner关系，SQL检查父是active profile/plan根。未来domain须同事务登记并关联唯一归属依据，不保留自由修改的owner副本。数据库未加immutable trigger或RLS；可信维护SQL仍有修改权限，后续读取须重验。

在后续受保护维护环境显式迁移，应用启动不迁移、seed或创建账户：

```powershell
.\.venv\Scripts\python.exe -m alembic -c services/api/auth_alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c services/api/auth_alembic.ini current
```

未升级到当前head只读就绪检查失败503，默认无密钥关闭入口仍可读基础配置/空目录。T07历史验收没有引入新依赖，也不包含真实Keycloak/MFA/恢复配置、公众账号、准入/同意/字段授权/共享grant/审计、领域数据/文件/worker、生产GRANT/RLS及部署；后续T08–T10有限增量不解除真实处理门槛。T07实际命令、测试数量、文件清单与限制见[T07验收](acceptance/T07_object_authorization.md)，技术决定见[ADR-018](DECISIONS.md)，D01–D08权威状态保留在[requirements](requirements.md)。
