# T10 审计与日志脱敏契约

## T14文件调用（2026-10-03，源码验收完成）

私有附件复用固定owned附件动作/引用，来源复用administrator.action且object字段NULL；无filename/path/hash/content日志。业务metadata/registry与required成功审计同TX，IO及flush后最终权限重验；FS补偿与孤儿不能冒称两阶段原子，详见[storage](storage.md)。

## T13来源调用增量（2026-10-03，源码验收完成）

来源登记、追加版本和读取复用administrator.action；object_type/id/version均NULL，来源责任引用保留在来源版本，审计不记录入口URL、publisher、scope_note或许可正文。业务与required成功审计使用同Session/TX，失败回滚，flush后重验身份/角色/MFA与新版本复查期限。caller-owned失败由外层先释放事务再处理失败审计。T10白名单不新增伪import类型，详见[sources](sources.md)。

日期：2026-10-03。数据契约、修改范围和验收条件在代码修改前冻结；下列“当前源码行为”是在本Task专项验收后补充的实现说明。T10源码/合成与隔离实库验收已完成；首轮完整回归19失败已修复复验，历史过程保留于独立记录；仅T10，依次执行批次不解除真实资料处理或部署门槛。

## 数据契约

现有独立认证链增加`0006_audit_t10`和`auth_audit_events`一表，旧0001–0005及M0链保留。最少字段为event UUID、UTC occurred_at、actor_kind（anonymous/user/system）、可空actor/session UUID、固定action、可空object_type/UUID/version、succeeded/denied/failed、固定reason_code、服务器32位hex request_id、is_synthetic、policy_version及expires_at。引用仅作责任线索，无FK、无权限效力；避免账户删除和失败审计另连接自锁。不保存issuer/sub/email/IP/UA、自由文本、JSON payload、原始异常、成绩、附件、提示词或凭据。未授权对象不记录请求中的对象ID。

动作采用封闭白名单：登录/退出、角色维护、本人/共享授权检查、成年声明/失效、核心确认/撤回、grant创建/接受/撤销与权限元数据读取/变更。审核发布、导出及删除仅预留固定接入动作和测试probe，不代表相应业务已实现。其他动作和多余输入拒绝，不接受请求自报actor。

成功写操作与现有业务Session追加/flush审计、同事务提交；必需审计失败回滚并安全503。失败事件等业务事务退出释放锁后另事务尽力保存，不掩盖原固定错误。T08已有成人失效后返回403属于已提交减权，记录invalidate成功，不记录新儿童年龄。现有账户/会话/角色/对象/共享锁序保持。

只提供内部最小审计读取：当前operations角色加T06显式配置的签名强度策略，同事务即时重验；无默认角色通道、无HTTP审计管理端点、无学生payload。读取自身也留下最小事件；审计写不绕过业务权限。

## 日志与留存

配置的常规日志处理器仅输出固定operation_id、request_id、状态、固定错误码与必要耗时；丢弃query/headers/body、原始msg/参数/异常信息和traceback，不用token正则假装全面脱敏。安全格式覆盖uvicorn access/error及第三方库的配置输出；不宣称控制其他进程、任意恶意本地代码或上游代理自定义handler。

D06为产品上限：常规脱敏日志30天、审计最多24个日历月；expires_at按真实日历生成，不以固定720天冒充24个月。提供明确、有界、显式调用的过期清理并验证边界；不在启动清理，不宣称已控制stdout收集器、生产备份或法定例外。正式最短必要期限/处理责任仍须上线前核实。

## 当前源码行为与使用边界

- `app/audit`提供封闭事件模型、服务器请求上下文、同事务Writer、内部AuditService与明确调用的留存工具。事件模型和数据库约束拒绝自由action/reason/type；actor引用仅由已有身份/当前授权接点取得，不是新的身份凭据。输入与展示模型重验复制/构造对象；展示模型拒绝超过24个日历月的到期值。
- identity HTTP中间件复用服务端已有request_id，关联固定operation/action及最少状态；不从header/query/body接收关联ID或actor。不含业务payload的服务错误和路由前拒绝可以在原操作事务退出后记录。已有服务装饰器识别位置参数与关键字参数中的外部Session：外部事务尚未结束时不另开失败审计连接，由该事务的外层边界负责记录。失败写入仍为尽力处理，不掩盖原401/403/404等固定错误。
- 当前登录开始/消费/完成/取消/退出、角色维护、owner/共享权限元数据及隐私声明/确认/撤回接点已追加最少事件。成功必须与对应业务同Session提交；成功审计flush失败使业务回滚。T08已提交的成人准入失效仍可返回403，保存invalidate成功事件和固定拒绝，不保存新的儿童年龄区间。
- 审计flush属于新增I/O。owner/shared和内部审计读取/清理在flush后再次检查当前会话、角色和适用证明；登录在已消费state后、换码前复核context，并在建立会话事务的auditflush后检查登录context截止和会话绝对截止，过期不提交新会话。角色撤销保持既有账户锁序；不能用过去的审计事件或请求自报角色取得权限。
- `AuditService.list_events`/`purge_expired`是服务器内部接口，要求当前operations角色、当前可信issuer/client与显式启用的管理员强度策略。缺失、撤销、到期或政策失效均拒绝；默认关闭。没有审计HTTP管理路由，不授予学生数据读取能力。PG专项中的管理员来源是明确的合成可信数据库夹具，不能称真实IdP/人工管理员验收。
- 日志配置文件是`config/logging/identity.json`，使用封闭Filter/Formatter。配置覆盖root、现有application/server/library输出；原msg/args/异常先丢弃后解析可选extra。合法格式的foreign request_id与看似内部的LogRecord字段均不可信：上下文内只用服务器ID，外部生成新ID。必须由运行入口显式加载配置，identity factory不自动更改进程logger配置；独立factory回归及logger被旧迁移禁用后的恢复专项/完整复验已执行。可信本地代码后来挂载的其他handler、上游代理和其他进程不在保证范围。
- `purge_log_files`只处理显式传入的应用专用目录内`admissions-YYYY-MM-DD.jsonl`，以UTC文件日期判断30天边界，触碰mtime不能延长；跳过符号链接/其他文件，不递归。删除limit为1–1000，实际迭代scan_limit为1–10000（包括不匹配项），不在应用启动运行。内部审计清理只删除已到期行，limit为1–1000；完整生产收集器、备份和删除传播未实现或验收。
- 原M0、旧迁移/验收、招生研究、前端实现和依赖保留。公开HTTP wire/生成契约仍为原identity `v2.t09`，没有新的T10业务接口或真实审核/导出/删除/worker功能。正式controller、法律、真实IdP/MFA/恢复和部署门槛保持。

## 修改范围

新增app/audit纯schema/context/logging、模型/服务、0006迁移及专项测试；现有auth/store/readiness/env、认证/隐私/owner/shared事务的最小审计接点，identity装配及运行日志配置。必要旧current-head断言和相关docs同步。保持M0、原始输入、旧迁移/验收、现有HTTP wire/生成契约、前端及依赖；无新增框架或依赖。

## 可测试验收

1. 敏感哨兵覆盖header/query/body、token/code/state、成绩、附件、提示词、异常/自定义extra；配置输出不出现原文，仍有固定错误和request_id。
2. 合成身份的关键已实现操作可追踪；不存在未实现业务的伪造成功；拒绝操作不回显/记录foreign对象或原始输入。
3. 同事务写与审计共同提交/回滚，审计失败不能保留成功业务；失败审计不持原锁另开连接、不掩盖原错误；并发用隔离PG实测。
4. 当前会话/operations角色/强认证缺失、撤销、到期/锁等待之后拒绝审计读取；角色不访问学生payload；read/replay不能复用过去权限。
5. 增量迁移保留旧数据及M0；启动无DDL/seed；calendar retention边界和显式有界清理实际验收。
6. 相关Unit/Integration、前端回归、Type Check/两Build、契约漂移与原文/范围/文档检查；无Lint/Python静态类型工具则明确未执行。真实IdP、法律审查、生产部署/日志收集器及备份传播不作为本轮通过。

实际命令、失败和完成状态另记[T10验收](acceptance/T10_audit_redaction.md)。上述说明为源码验收边界，不能当作公众发布验收；文档同步后按持续授权保存源码。
