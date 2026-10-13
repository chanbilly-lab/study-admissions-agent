# API 规划：保留 M0 v1，拟建公众 MVP v2

2026-10-14 SEARCH-SELECT-01新增显式reference/local_reference工厂的GET /v2/reference/institutions与/programs：q/country/limit/cursor，专业另需institution_id；独立reference.directory.1回显filters/有界选项/页/当前发布证明/水位及未知总量。默认directory_not_enabled空，无候选/DEMO；当前已发布真实UUID用作培养program_id或毕业对应层级subject_ref，资料届独立。scope改变/水位变化409重查，非法参数422，证明/服务不可用503；重复/extra拒绝、no-store/请求ID、旧Meta不变。旧培养/毕业API及十二generated不改，本批无SQL/HTTP/类型/构建验证或重启。完整字段与状态见[新增契约](school_program_search.md)。

2026-10-04 T36持久作业与站内提醒源码与合成隔离验收完成：36新增pure/16实际PG-HTTP/12契约，684前端/TypeCheck/双Build通过；[验收](acceptance/T36_jobs_notifications.md)。新增五表/第16迁移head及默认关闭、本人确认的站内提醒；持久租约/fencing/去重/有界重试，接受清理仅probe，不做真实删除或外部通知。PRIVATE保存核对后才单独T37，本批T40停止，真实处理关闭。

2026-10-04 T35明确修订与有限历史工作台源码与合成隔离验收完成：57纯专项/19 distinct PG及HTTP/Edge、321契约与350相关Python、635前端/Type Check/双Build通过；[验收](acceptance/T35_plan_revisions.md)。仅复用本人明确选择的新草案，追加接受/拒绝与替代关系，旧确认/完成不改、新计划未最终确认；历史不表示当前资格，真实关闭。PRIVATE保存核对后才单独T36，本批T40停止，真实处理关闭。

2026-10-04 T32确认与进度源码及合成隔离验收完成：56新增pure、28 distinct PG/HTTP、305契约回归、865相关旧Python、474前端与Type Check/demo-auth Build通过；[验收](acceptance/T32_plan_execution.md)。独立state_version与不可变记录、首次确认未来容量及重放当前进度保留，不改变资格/学校事实；PRIVATE保存核对后单独T33，本批T40停止，正式处理关闭。

## T32 计划准备安排 HTTP（源码与合成隔离验收完成）

新增显式 plans profile，继承 assessments，8操作/7路径；POST workspace 追加估时及容量提案，confirm 唯一 T49 header，任务完成为精确原请求自然幂等。state_version 独立于 T30 草案版；未知学校截止须本人明确知悉，不改变四态资格或提交申请。Cookie/Origin/CSRF/当前本人 core 与完整 source 守卫，64KiB JSON 请求，新 real 门槛保持关闭。旧七 profile 不改，源码/HTTP/合成隔离实库已验收；准确 DTO/路径/冲突见[确认契约](plan_execution.md)。

## T28评估HTTP（源码与合成隔离验收完成）

独立assessments profile继承profiles并新增4个显式操作；POST评估不使用T49、不接受客户端结论/AST/owner/clock，replay需confirmed=true且当前Origin/CSRF。历史frozen结果与current_validity分开，正式ruleset仍unknown。完整请求/权限/四态/重放见[契约](assessments.md)，实际命令及失败轮次见[T28验收](acceptance/T28_assessments.md)。

## T23 私有画像HTTP（源码与合成隔离验收完成）

独立profiles profile继承冻结identity，最小本人context/list/create/current/history/append；创建T49，追加strictCAS，同事务确认/当前用途/owner及末端时效。默认零DB/关闭，旧五profile不变。详见[契约](profiles.md)。

2026-10-03最新产品目标（ADR-034）：全部普通高考生源省份逐省配置，英国本科暂定2027、优先剑桥/曼彻斯特；真实省/年/专业适用证据未验收时unknown。下文旧单省描述为先前规划或M0基线，不表示当前产品目标或已实现覆盖。


## T22 审核发布HTTP（已验收；真实处理关闭）

新admin_review profile复用现有来源/导入，补明确证据/事实准备、当前审核/发布预检/发布/撤回，独立/public/v2匿名预览；默认关闭，旧四profile保持。准确操作与权限见[契约](admin_review_workspace.md)。

## T21 管理HTTP（已验收）

新增显式admin profile的context、来源登记/确切读取/修订、UTF8 CSV/JSON隔离上传、幂等导入/回执；旧入口/生成产物保留。服务端当前强管理员/许可/Origin/CSRF执行校验，默认关闭，来源URL不联网。详见[管理契约](admin_workspace.md)。

## T20 公共只读profile（源码与合成隔离实库验收完成）

显式create_public_catalog_app/v2_app新增config、offerings与绑定release的evidence GET，旧foundation/identity/M0保持。默认无reader：config可读且business_available=false，业务503；真实公开默认关闭。必填年份、有界分页/精确scope过滤、当前发布及独立公开许可、no-store/安全错误。详见[public_catalog](public_catalog.md)。

## T19 内部发布接口（源码与合成隔离实库验收完成）

ReleaseService publish/withdraw/get_release；T49同TX发布receipt，source公开许可独立核验，facts-only ruleset_version=null，无新HTTP。详见[releases](releases.md)。

## T18 内部人工审核接口（源码与合成隔离实库验收完成）

ReviewService的decide/get_case/approval_in_transaction记录当前强审核主体和逐字段判断，独立版本锁/冲突台账，无新HTTP。客户端不能改事实/声明角色，批准不直接发布。详见[reviews](reviews.md)。

## T17 内部类型化事实接口（源码与合成隔离实库验收完成）

只内部FactService与严格DTO，不新增HTTP或改既有16 paths/identity v2.t09。候选来自T15原行并绑定T16原文件/范围；所有结果hard_rule=false、publication_eligible=false。详见[facts](facts.md)。

## T16内部证据接口（源码、合成抽查与隔离实库验收完成）

Document/Version/Snippet创建与同TX范围验证，仅内部模块；无新HTTP/schema wire，未来公开读取另需release和公开许可。详见[evidence](evidence.md)。

T15内部ImportService尚无上传或管理HTTP，JSON/CSV同步有界候选、rejected不等于已导入事实；回执只status/counts/固定errors，不返回原始坏行/存储路径。契约见[imports](imports.md)。

T49已验收内部IdempotencyService与pure规范请求工具，尚无HTTP Idempotency-Key中间件或新路径；最少资源引用在重放前后当前鉴权，不发送旧缓存响应。正式TTL待定，默认禁用，合成24h不代表政策。契约见[idempotency](idempotency.md)。

T14已验收的StorageService仅内部接口，尚未新增上传/下载HTTP、signed URL或公开文件；FileData不含path/backend key/filename/owner。T09 metadata grant不能取得bytes，真实处理仍关闭。契约见[storage](storage.md)。

规划日期：2026-10-01，Asia/Hong_Kong；T03契约更新2026-10-02。T02历史验收保留，当前v2.t03模式/入口契约见[T03记录](acceptance/T03_mode_isolation.md)。本文保留M0接口、foundation基础与identity准入协议及公众功能规划，不能把规划端点当可用。数据库设计见 [database.md](database.md)，实施顺序由 [任务规划](tasks.md) 统一。

固定技术栈为 Vue3/TypeScript/Vite + Python/FastAPI/Pydantic + PostgreSQL/SQLAlchemy/Alembic 模块化单体。公众 MVP 服务目标为中国大陆、香港、澳门、台湾地区用户，计划中国大陆部署，具体城市/供应商待选。必须先完成正式身份、权限、已审核目录、版本/幂等、隐私删除、运维验收；未成年私有功能本版关闭，D02/D06产品政策已定，正式主体/告知及适用性仍为发布门槛，不能宣称已经合法上线。首 MVP 仍只一个配置省份普通高考本科＋英国本科；DSE、联招、澳门/台湾其他资格体系须单独适配，不纳入本次计划的 MVP 功能范围。

T11仅建立独立候选关系与内部数据契约，不新增HTTP路径或改变identity v2.t09/foundation生成产物；公开offerings继续空基础。内部候选store不是鉴权API，客户端不能通过dataset UUID读取或发布候选。真实公开查询待T19/T20装配；范围键和确切版本详见[catalog](catalog.md)。

T12内部日期契约见[dates](dates.md)：候选local日期/时间/IANA/precision、原文pending/conflict、确切机会版本和calculated_utc_instant，与未审核的官方utc_instant=NULL分开。本Task不新增date-events HTTP路径，不改变现有wire/生成产物；下方公开日期端点仍是未来规划。

T13仅内部来源治理契约/SourceService，同事务服务器Principal和catalog.source.register/read能力守卫，客户端字段不能声明owner/role/审核时间。未挂sources HTTP接口，不改变现有16paths/TS；下方管理路径仍为规划。当前权限/复查与正式责任必须在T15导入/T19发布时重验，不能拿一条来源metadata当事实发布依据，见[sources](sources.md)。

## T09共享契约（源码验收完成，真实共享关闭）

T10不新增HTTP路径、请求/响应字段或schema版本，identity仍`v2.t09`/16paths。已实现身份/用途/授权操作加入内部同事务最小审计，服务器request_id关联固定操作日志；请求不能自报主体/关联ID。必需成功审计不可保存时业务回滚并安全503，拒绝审计不改变原错误。审计查询/清理无HTTP管理端点，内部需当前operations及显式签名强认证；审核发布、导出、删除仅固定接入动作，其下方业务端点仍为规划。运行日志必须显式安全配置，边界见[audit](audit.md)。

显式identity当前schema为`v2.t09`、16个path项；基础config/foundation产物不变，session仍原五字段且private_business_available=false。共享仅合成fixture的归属registry metadata：五种对象profile/plan/attachment/export/job，字段status/version、动作read/list，绑定exact resource_version，不提供真实画像、对话、文件下载或worker。独立共享确认不能由T08核心用途或顾问/监护角色代替。

| 当前接口 | 契约及结果 |
| --- | --- |
| GET /v2/sharing/policy | 公开固定合成notice正文/实际hash、范围矩阵和关闭状态 |
| GET /v2/access-grants | direction=issued/received、limit 1–100十进制整数、after_id UUID；本人的授权历史及最少当前证明，不能枚举其他主体 |
| POST /v2/access-grants | 指定预登记recipient、对象/version、field/action、明确offset期限、独立confirmed=true和owner当前revision；创建pending |
| POST /v2/access-grants/{grant_id}/accept | 指定recipient本人会话、成年声明、独立确认、当前policy/hash/grant version；接受后仍须即时重验 |
| DELETE /v2/access-grants/{grant_id} | owner撤销或指定recipient拒绝/退出；无body/query，不受陈旧notice、revision、核心用途或年龄证明阻挡；第三人404 |

五操作成功均200 Envelope，私有GET和unsafe成功/失败no-store，写入继承固定Origin/会话CSRF。grant wire不公开跨主体用途/年龄证明ID；旧授权绑定原证明，不因重新确认复活。列表先SQL范围过滤再count/page；缓存命中和延迟readonly组合即时复核，不能以cache key作许可。事务先按UUID排序锁参与账户后绑定真实actor，不伪造owner Principal。生成器显式限定四个JSON请求路径及隐私/共享UUID参数，未知schema仍拒绝。完整输入/字段/限制见[sharing](sharing.md)、[T09验收](acceptance/T09_explicit_sharing.md)；真实共享、生产数据库权限和公众服务仍关闭。

## T08实施契约（源码验收已完成）

当前仅显式identity profile增加隐私设置，默认foundation保持两条公开基础路径。核心用途`core_consultation`，不赋角色或对象权限；真实处理保持关闭。成年人本人年龄声明只标`declared`，不标核验；unknown/under14/14–17私有关闭。新路径和字段见[privacy](privacy.md)，旧session五字段wire保持。输入使用唯一Cookie/固定Origin/稳定CSRF，额外owner/verified/role拒绝；隐私设置和撤回不依赖事先准入。Task已完成源码/合成验收，不能解释为真实画像已可用。

| T08接口 | 输入与当前结果 |
| --- | --- |
| GET /v2/privacy/notices/current | 公开草案/policy/D06上限；ready=false、notice_id/version=null；合成test夹具才test_fixture_ready |
| GET /v2/me/admission | 当前本人设置/revision、18_plus或null、declared或unknown、consent状态、核心用途原因；业务始终false |
| POST /v2/me/age-declarations | age_band四枚举、confirmed严格true、notice_id、expected_revision；成年正向须当前告知/版本。nonadult拒403但先清旧正许可，无旧记录不新增band，旧revision/notice不阻挡此失效 |
| POST /v2/me/consents | purpose固定core_consultation、confirmed严格true、notice_id、expected_revision；需当前成年声明，旧版本409；其他目的未实现 |
| DELETE /v2/me/consents/{consent_id} | 本人原确认事件UUID、无body/query；返回当前设置，重复撤回旧id不撤掉新确认；旧/坏/未就绪告知不阻挡撤回 |

T08历史identity schema `v2.t08`、12个path项，当时生成器限定两个required application/json请求体和单UUID路径，未知格式/ref拒绝，默认foundation产物原字节保留。unsafe安全校验及私有GET no-store继承T06；错误不回显年龄/声明原文。role_missing仍可做本人设置，准入不分配角色。应用append历史与同TX用途guard不构成数据库RLS、真实处理或持久worker的验收。

## T07内部对象授权契约

T07不增加HTTP路径、公开session字段、OpenAPI或TS；默认/production入口和T06七条路径保持，`private_business_available=false`。内部Principal由服务器Cookie会话与当前数据库角色产生；`Authorizer`固定role/kind/action/owner/parent/state规则，列表先SQL过滤再计数分页；客户owner/role不授权，data_admin/operations不能由角色读取学生私有资料。内部错误复用401/403/404/409/503安全码，foreign/missing/deleted同404。后续私有GET依赖成功/拒绝均no-store/no-cache/no-referrer与server request_id，unsafe保留T06固定Origin/CSRF。测试probe不挂正式factory/schema。

读取依赖仅授权快照；写入/作业执行必须使用同Session事务的`execute_owned`重验，不能把T06跨连接permission_verifier当原子对象权限。`touch_owned`仅profile/plan版本metadata，非真实业务编辑；缓存key不是许可，命中仍读当前状态。真实画像/计划/文件下载/导出/持久worker/角色管理仍未实现；T09仅独立合成metadata grant，未放宽T07 owner-only接口。详情见[授权模块](authorization.md)、[T07验收](acceptance/T07_object_authorization.md)，下方公众业务路径继续为规划。

## 当前v2基础范围（T02建立，T03模式更新）

当前仅`GET /v2/config`、`GET /v2/offerings`及独立`/v2/openapi.json`可用。配置`schema_version=v2.t03`、`contract_stage=foundation`、`business_available=false`、`live_available=false`；supported_scope空、省份/年度null。新增必需app_environment（development/test/production）、query_role（demo_only/published_readonly）；data_mode demo|verified、model_mode disabled|mock来自冻结的服务端启动配置。production必须verified+disabled；v2 live启动拒绝，不能出现在有效wire。独立production factory只挂/v2，无v1/health/M0主应用或私有端点；DEMO Bearer在verified下拒401。未知token访问公开基础不算认证成功。

成功为`{data,meta}`，meta含`api_version=v2`、服务端request_id、data_mode/model_mode，data_as_of/profile_version_id/release_id/ruleset_version/profile_mode均null。没有发布事实就不填日期或DEMO版本。列表data为`{items:[],page:{limit,next_cursor:null,has_more:false}}`，默认limit20、范围1–100；只接limit和cursor，不接受未知/重复标量。此阶段没有合法cursor，任何显式cursor返回422，不提供keyset或数据查询。配置不接查询参数。

错误为`{error:{code,message,request_id,details:[{field_path,code,message}]}}`；v2的401/422/404/405、安全500/503均带同一`X-Request-ID`，不回显输入/凭据/候选事实。独立production根的未挂载路径404，不承诺v2 Envelope；所有M0路径不可用。目录读取候选污染整体503，不能部分返回；当前即使描述合规也不能替代正式发布库。独立OpenAPI servers为`/v2`、paths为`/config`与`/offerings`，不包含v1。代码/schema/TS边界见[T03验收](acceptance/T03_mode_isolation.md)。

生成只依赖现有FastAPI/Pydantic和stdlib，显式固定development/demo/disabled及空可选配置；process环境或M0 .env不能改变生成结果。输出`packages/contracts/v2/openapi.json`与`generated.ts`，`--check`只读拒漂移，未知schema失败。TS保留字段/必需性/null/literal；矩阵跨字段限制、数值/长度/空scope/额外字段与Page关系由服务端验证。子应用只有两个端点及schema，无Swagger/ReDoc。foundation不挂身份；独立identity已实现认证、隐私及合成metadata共享，T49内部组合已实现，真实目录/真实私有业务仍未实施，模式隔离不解除公众发布门槛。

## 保留T05/T06认证路径（当前identity v2.t09）

`api.identity:create_identity_app`是新的显式入口，只挂/v2。默认关闭认证，正确形状认证请求返回503；原production foundation仍只提供下文两条基础路径，原M0/v1保持。身份schema版本`v2.t09`（T06/T08历史为v2.t06/v2.t08），基础config仍`v2.t03`；`packages/contracts/v2/identity/{openapi.json,generated.ts}`由`generate_contracts.py --profile identity`离线生成，保留旧foundation产物原字节。

| 接口 | 输入 | 实际结果 |
| --- | --- | --- |
| GET /v2/auth/login | 不允许查询参数 | 302固定IdP地址，服务器state/nonce/S256；安全browser-binding Cookie；不接任意return URL |
| GET /v2/auth/callback | 唯一state＋code或error，选填iss须精确匹配；拒重复/未知参数 | 匹配Cookie与一次性事务后换码/验签；成功设置新安全session Cookie、清绑定Cookie、303固定/；失败安全401/403/503，供应商描述不回显 |
| GET /v2/auth/session | host-only会话Cookie；不允许查询参数 | 200现有Envelope；无效/到期401并清Cookie；禁用账户不返回会话；不含token/外部身份或角色 |
| GET /v2/auth/csrf | 有效会话Cookie，无query | 200 Envelope data `{csrf_token,expires_at}`，43字符base64url token绑定当前会话；只存前端内存，稳定不滑动到期 |
| POST /v2/auth/logout | 有效Cookie＋唯一X-CSRF-Token＋唯一Origin；无query/body | 200 Envelope data `{logged_out:true}`，服务端原子重验后撤销当前会话/清两Cookie；重复/到期/撤销401并清Cookie，不创建数据 |

session data严格为`authenticated:true`、`user_id:UUID`、`expires_at:UTC date-time`、`is_synthetic:boolean`、`private_business_available:false`。Meta沿用v2基础，不能将登录解释成画像/项目业务开放。Cookie `__Host-admissions-login`/`__Host-admissions-session`均Secure、HttpOnly、SameSite=Lax、Path=/、无Domain；认证响应和重定向均no-store/no-cache与no-referrer。JWT只在服务器临时验证，不持久化，不进入前端storage；精确预登记active账号，不注册/按email合并/映射IdP roles。

错误继续复用现有v2 Envelope与安全码；422验证输入，401无效认证，403未获准账户，503配置/供应商/存储不可用。schema明确Cookie security和302/303 Location/Set-Cookie/X-Request-ID无JSON响应；TS对该两种精确重定向类型为undefined与严格headers，不降级any。只支持GET授权码回调，不接form_post/token body。反向代理需使固定外部回调`/api/v2/auth/callback`准确转到`/v2/auth/callback`，同源前端最终返回/；不从Host自动推导信任地址。

运行、明确配置与真实联调门槛见[identity](identity.md)，迁移见[database](database.md)，真实检查见[T05](acceptance/T05_login_session.md)。T06所有Cookie身份POST/PUT/PATCH/DELETE在中央检查当前有效会话、固定Origin及会话token，新写路由遗漏dependency也受保护。Origin精确匹配注册redirect_uri的序列化origin；Host/Forwarded不扩展信任，缺/错/重复token或Origin返回403，失败不撤销有效会话。所有私有及写拒绝响应no-store，403/503/网络失败不能显示退出已确认。只撤当前应用会话，不退出Keycloak SSO或所有设备；T07资源授权基础见上方；T08隐私准入基础源码验收已完成，真实处理、后台队列与真实业务仍未开放，不解除发布门槛。[T06验收](acceptance/T06_session_csrf.md)。

## 1. 已实现 M0 v1 的准确边界

应用版本 `0.1.0`，业务路径 `/v1`。以下路由已经存在；路径参数真实名称统一为 `{identifier}`。全部是本地合成 DEMO 服务，不是公众生产 API。当前 CORS 仅配置本地 GET/POST 等允许范围；没有正式登录、PATCH、删除、分页、限流、幂等或版本冲突协议。

| 当前方法与路径 | 权限 | 成功状态 / data |
| --- | --- | --- |
| `GET /v1/config` | 公开 | 200，`RuntimeConfig` |
| `GET /v1/profiles` | DEMO Bearer | 200，当前 owner 的 `Profile[]`，未分页 |
| `POST /v1/profiles` | DEMO Bearer | 201，`Profile`，每次独立 version=1 |
| `GET /v1/profiles/{identifier}` | 当前 owner | 200，`Profile`；不可访问返回 404 |
| `GET /v1/offerings` | 公开 | 200，`Offering[]`；仅 `country/entry_year/province` 三个筛选，未分页 |
| `GET /v1/offerings/{identifier}` | 公开 | 200，`Offering`；直接按 ID 读取，不暗示可用于当前画像 |
| `GET /v1/evidence/{identifier}` | 公开 | 200，`Evidence`，仅合成证据 |
| `POST /v1/eligibility/check` | 当前 owner | 200，`Eligibility[]`，结果落库 |
| `POST /v1/plans/drafts` | 当前 owner | 201，`PlanDraft`；服务端重新计算资格并与草案同事务保存 |
| `GET /v1/plans/{identifier}` | 当前 owner | 200，`PlanDraft`；不可访问返回 404 |
| `GET /health/live` | 公开 | 200，`{"status":"ok","demo_mode":true}`，非 Envelope |
| `GET /health/ready` | 公开 | 200，同上；数据库连接/迁移不可用返回 503 |

`/health/ready` 当前执行 SELECT 1 和 offerings 查询；不核验最新 migration head、已 seed、正式身份或 live provider 可用性。FastAPI 默认还提供 `/openapi.json`、`/docs`、`/redoc`，这些不算业务功能。

身份仅是服务端映射 `demo-alice-token → demo_alice`、`demo-bob-token → demo_bob`。401 表示缺/错误演示凭据；私有画像/资格/计划由服务端 owner 过滤，跨用户资源按 404 处理。输入对象 `extra=forbid`，body 的 owner 等多余字段被拒绝；没有正式账号/顾问共享。

### 当前输入与响应

`POST /v1/profiles` 接收 `ProfileInput` 本身，不包 `data`。必填：display_name、`is_synthetic=true`、`confirmed=true`、`study_level=bachelor`、`course_system=gaokao`、entry_year、province、`applicant_category=cn_mainland`、subjects、assessments、weekly_hours。省份必须等于配置；每周工时 `0 < hours <= 40`。M0 成绩键只有 `gaokao_total/math/english_language`，每项是 `{value, scale, unit:points|band, kind:achieved|predicted}`；缺成绩省略键，不传 0 冒充缺失。

资格与草案的共同请求是下面的小对象，offering_ids 1–10 个且不能重复：

```json
{"profile_version_id":"DEMO_PROFILE_example","offering_ids":["DEMO_CN_MATH"]}
```

业务成功响应为 `Envelope<T>`：`data` 加 `meta`，meta 包含 request_id、data_as_of、profile_version 可空、ruleset_version、`demo_mode=true`、`model_mode=mock|live`。当前 data_as_of 固定 DEMO 快照 `2026-09-30`，ruleset_version 为 `DEMO_M0_v1`，不是实时资料时钟；`X-Request-ID` 与成功 meta 相同。当前错误仍用 FastAPI 的 `detail` 或 validation `detail[]/loc`，**没有统一错误 body 内的 request_id**。

M0 的四态是 eligible/ineligible/conditional/unknown；原因原子为 true/false/unknown/deferred。缺成绩只有已审核适用入学阶段后补政策、具体项目/年度证据和未过期带证据期限都成立才 conditional；缺期限、缺证据、冲突、预测冒充实得或单位不匹配均 unknown。明确适用硬失败优先。无真实历史竞争/偏好分析，不输出录取概率。

当前 config 显式给出 `live_available=false`。mock 无密钥可运行；live 模型只预留接口，创建计划返回 503 并回滚，不静默回退。画像修改、计划确认、任务进度、管理员导入审核、QA、变化与删除接口均**尚未实现**。

## 2. 拟 v2 的版本策略与公共边界

公众 MVP 使用 `/v2`，因为分页响应、正式画像类型、统一错误、身份和日期/发布结构会改变 v1 wire contract。保留M0契约和本地v1测试；T03已提供独立生产基础入口，仅挂v2并拒DEMO凭据，M0主入口限本地演示。基础schema/TS与HTTP已验收，其余正式身份、目录、画像和计划仍为规划。

v2 仅单平台运营。`actor_user_id/owner_user_id/roles/access_grants` 来自服务端经验证会话；私有 body 和查询不能指定 owner/role 或冒用他人身份。公开目录固定可见的真实已审核 dataset/release，演示实例有单独数据库/访问上下文；`dataset_id` 不是用户资料所属公共库，真实学生资料始终私有。用户可以选择公开 release 做明确的历史重放，但不能从参数读取私有候选或撤回内容。`data_mode=demo|verified` 与 `model_mode=disabled|mock|live` 独立：verified 无密钥使用 disabled 确定性服务，mock 仅允许 demo；当前 M0 v1 不包含 disabled。

### 成功、错误、分页与并发约定（T02基础协议，其余拟实现）

有JSON正文的业务成功响应为 `{data, meta}`；204、OIDC重定向、文件流和健康探针是明确例外，仍在header给 `X-Request-ID`。meta 保留 request_id/data_as_of/model_mode，并扩展 `api_version="v2"`、`profile_version_id` 可空、`release_id` 可空、`ruleset_version` 可空、`profile_mode=real|synthetic` 可空和 `data_mode=demo|verified`；不把隐私 owner、内部对象存储路径或供应商密钥放进 meta。`data_as_of` 来自使用的 release，不等于本次请求时间；不使用招生release的账号/隐私响应data_as_of可空，不能填DEMO快照。公开目录可缓存，私有响应 `Cache-Control: no-store`，私有缓存必须按用户/授权版本隔离。

列表 data 为 `{items: T[], page:{limit, next_cursor, has_more}}`，默认 limit=20，最大100；稳定 keyset 顺序为业务排序字段＋ID，cursor 与过滤/snapshot 绑定，不能修改 cursor 来跨授权范围。没有支持的筛选字段返回 422，不能静默忽略；列表无数据为200空 items，单个不可见/不存在资源为404。

统一错误由服务端异常处理器转换；FastAPI 支持覆盖验证及 HTTP 异常处理器，现 M0 尚未采用此协议。[FastAPI 错误处理文档](https://fastapi.tiangolo.com/tutorial/handling-errors/)

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "成绩满分必须为正数",
    "request_id": "0123456789abcdef0123456789abcdef",
    "details": [{"field_path":"body.assessments.math.scale","code":"OUT_OF_RANGE","message":"必须大于 0"}]
  }
}
```

不回显 token、原始学生字段值、SQL 或 provider 原始错误。schema 类型错误用422；无认证401；已认证但无某项平台动作权限403；私有资源不存在/不可见404；版本、发布冲突或幂等 key 内容不同409；容量/依赖等业务验证422；限流429并给 Retry-After；受控 provider/依赖不可用503。unknown 是200中的正常资格业务结果，不以500替代。

修改/确认 body 必须含 `expected_version`。服务端在同一事务验证并更新，过期版本409 `VERSION_CONFLICT`，允许当前资源所有者读取 current_version 后重新审阅；不能自动重试并覆盖新内容。`expected_version` 是根/任务并发锁，profile_version_id、plan_version_id 是不可变内容 ID。

创建、确认、导入、发布、删除和进度写入使用 `Idempotency-Key`；服务端按 actor+operation+key 和规范化请求 hash 处理。相同请求重放同一业务资源，不同内容409 `IDEMPOTENCY_CONFLICT`；明确响应是 replay，仍生成本次 request_id。幂等保持期限由配置公布；跨账号不共享响应。数据库约束与事务必须覆盖并发，不仅靠应用内 dict 缓存。

幂等重放前重验当前身份、角色/grant、用途准入和删除状态，不用曾经授权的缓存响应绕过撤权。私有响应缓存与导出工件进入删除/留存范围，优先保存最小回执和资源引用。

## 3. 正式认证、授权和隐私接口（拟实现，上线必需）

D04已选自托管Keycloak，正式认证采用 OIDC Authorization Code + PKCE S256，由 FastAPI 完成回调并建立服务端会话；真实tenant、管理员强认证与恢复实际配置仍待验收。T04只提供未挂入应用的Provider/冻结配置/合成离线边界，默认关闭；本节中登录/回调/session已由T05实现、CSRF及当前logout由T06增量实现；其余端点仍为后续规划，实际行为以上方current profile为准。详见[身份配置](identity.md)与[T04验收](acceptance/T04_identity_provider.md)。内部拟依赖AuthContext，正式身份必须经过服务端验证；拟会话使用 Secure/HttpOnly/合适 SameSite cookie，浏览器不把长期 token 存 localStorage，写操作带会话绑定 CSRF 防护。T05使用成熟库校验登录事务 state/nonce、受信任 issuer、签名、audience、有效期及PKCE，不接受客户端选任意身份供应商。[OIDC 授权码流程](https://openid.net/specs/openid-connect-core-1_0.html#CodeFlowAuth)、[OAuth 安全实践](https://www.rfc-editor.org/rfc/rfc9700.html#section-2.1.1)

| 方法 / 拟路径 | 输入或返回 | 权限与验收 |
| --- | --- | --- |
| `GET /v2/auth/login` | 启动受信任OIDC登录事务，302到固定供应商；return_to仅允许同站路径 | 限流；PKCE/state/nonce；不是任意redirect/issuer代理 |
| `GET /v2/auth/callback` | 供应商code/state/error；验证后建立/轮换会话并303到允许的站内地址 | 身份事务专用回调，不以业务CSRF方式阻断回调；错误不泄露token |
| `GET /v2/auth/session` | actor 的必要显示信息、有效角色、会话状态、所需告知确认；不返回 session secret | 未认证401；不披露别人的账号存在性 |
| `POST /v2/auth/logout` | 当前会话撤销，200 Envelope；已失效401 | 已实现T06：原子撤销并清cookie；CSRF/固定Origin；不开放所有设备/SSO退出 |
| `GET /v2/privacy/notices/current` | 适用的告知版本、用途、数据范围、保留/删除说明 | 可公开读取，按必要的用户自述地区/服务适用范围选择，不根据姓名推断所在地或年龄 |
| `POST /v2/me/consents` | notice_version、purpose、明确 decision；server记录 actor/time | 必要确认和可选用途分开，错误旧版本409；不能认为同意免除其他上线要求 |
| `DELETE /v2/me/consents/{consent_id}` | 撤回指定用途确认，返回操作状态 | owner；停止相应用途，并按适用规则触发删除或限制处理 |
| `POST /v2/access-grants` | resource_type/id、受权人、允许字段/动作、expires_at、用户显式确认 | 资源 owner；受权人验证，不允许任意 user_id 指定即授权，拒绝超范围 grant |
| `GET /v2/access-grants` | 当前用户拥有或获授的 grant 分页 | 返回最少字段；管理员职责不默认拥有该列表 |
| `DELETE /v2/access-grants/{grant_id}` | T09当前返回200 Envelope，取代旧204规划 | owner撤销或指定recipient拒绝/退出；metadata授权即时重验，真实导出/下载仍未实施 |

OIDC登录回调不自动许可私有画像处理：供应商认证后还需账号启用、所需年龄/授权流程与告知确认。注册/恢复由D04选定方案补全同一个身份任务，是发布阻塞项；不额外自建密码接口。data_admin 发布权限需要强认证，学生/顾问/数据管理员按动作与资源验证。公众服务是否允许未成年注册、是否需监护关系/确认和如何验证，等待准入决策与专业审查后定义；TBD 期间不能开放相关注册或处理。敏感文件采用经API实时授权的下载；若以后允许直连短时签名URL，必须说明已签发链接的剩余撤销窗口，不能声称单纯撤grant就立即吊销存储签名。

## 4. 项目、证据和日期（拟实现）

| 拟路径 | 主要过滤/结果 | 可见性 |
| --- | --- | --- |
| `GET /v2/config` | supported_scope、supported_province、entry_year、model_mode、data_mode、live_available、schema版本 | 只公布可用能力，不泄露内部部署/密钥 |
| `GET /v2/catalog/releases` | country/entry_year/pathway、分页已发布版本、data_as_of | 公开可见 release；不显示内部草稿 |
| `GET /v2/offerings` | country/study_level/entry_year/intake/course_system/pathway/applicant_category/province/subject_scope/release_id、分页 | server 限定支持范围和公开 release；不以学校品牌代替机会粒度 |
| `GET /v2/offerings/{offering_id}` | 机会版本、program/机构、要求、原文链接、日期事件、缺失状态 | 无适用已发布版404；详情不能暗示所有申请身份均适用 |
| `GET /v2/evidence/{evidence_id}` | version/hash/locator/excerpt、审核发布、适用项目/year/scope | 仅允许的已发布片段，受许可限制；不暴露私有快照存储路径 |
| `GET /v2/offerings/{offering_id}/date-events` | 申请/后补等事件、original_text/local_date/local_time/timezone/precision/utc_instant、evidence_id | 返回独立事件，不将平等审理日自动当最终申请日 |

所有 scope 在结构化查询前过滤，再检索证据；英国本科校验资格体系/中国内地身份/具体课程/入学年，国内按配置省份、普通高考、科类/选科及路径匹配。无该年度资料明确显示缺口，不用去年规则填充。only date 的事件 local_time/timezone/utc_instant 可空，不合成23:59；日期 unknown 的 task 也不能悄悄生成截止时刻。

后补期限按已审核政策的参考日历核验，不能使用服务器本地日期代替机构日期。期限当天、只有日期且缺参考时区等无法确认是否过期的边界保持 unknown/待核验，不擅自补时刻后放行或淘汰。

## 5. 画像与资格（拟实现）

| 方法 / 拟路径 | 请求摘要 | 返回 / 行为 |
| --- | --- | --- |
| `POST /v2/profiles` | `confirmed=true`、结构化本科画像、必要告知版本；无 owner/mode/role | 201，profile 根 ID、confirmed_version_id、version=1；server 判定真实/合成上下文 |
| `GET /v2/profiles` | 分页 | owner 或明示获授资源；默认不列他人画像 |
| `GET /v2/profiles/{profile_id}` | 指定根 ID | 根/当前确认版本、row_version；field级 grant 收窄响应 |
| `GET /v2/profiles/{profile_id}/versions/{version_id}` | 精确旧版 | 不可变确认快照；跨画像/跨用户404 |
| `PATCH /v2/profiles/{profile_id}` | expected_version、confirmed=true、changes、有效告知/用途确认 | 201，新不可变版本及更新根指针；旧版保留；模型建议不能自己调用确认 |
| `POST /v2/eligibility/check` | profile_version_id、offering_ids、明确 release_id、stage=application|enrollment | 200，批次/逐项目结果，固定 engine/release/assessment_at；服务端身份和scope校验 |
| `GET /v2/eligibility/results/{evaluation_id}` | 保存结果 ID | owner/grant 允许时读取回放快照，注明历史评估与当前是否需复核 |

画像和计划的显式确认默认由owner本人执行。顾问可以在grant内协助提议，但普通read/write grant不能代替学生确认或用途同意；监护人的代确认范围只在D02政策确定后专门设计、记录并验收。模型不能成为confirmed_by主体。

画像 schema 分开 `user_location_region`（仅必要时用户自述 `cn_mainland/hk/mo/tw/other/unknown`）、`applicant_category`、`course_system`、`pathway`，所在地不能决定招生身份；无需身份证/护照号。当前 MVP 不支持的 DSE/联招/澳门台湾其他资格路径，输入请求返回422 `SCOPE_NOT_SUPPORTED`；已保存历史评估遇适配范围不成立时为unknown，不能按普通高考套用。成绩 schema 为 subject/exam/source、value/scale/unit、achieved|predicted、测评与有效期；本阶段已支持哪些 exam/subject 是 schema 白名单，不支持键拒422。缺成绩字段保留缺失状态，不把 null 强制为零或自动换满分。预测、模拟和假设输入独立标记，不修改真实成绩。

结果继续分四态，新增 stage/scope/release/engine_version/assessment_at/review_needed；每条 reason 有 rule_version、原子结果、field_path、证据、missing_status 或明确失败原因。四个维度为 eligibility、competition_context、preference_fit、data_quality，缺历史或偏好信息返回可解释 missing 状态，不用通用匹配分填充。

范围错误/缺年度规则/证据失效属于 unknown；输入 schema 错误、无资源权限属于 HTTP 错误。必要成绩缺失且没有适用、已审核、带证据期限的后补政策必须 unknown；后补过期/跨项目/跨年/冲突也 unknown。已确认预测分仍不能当实得资格。all/any/not 按完整表达式三值归约；any(true,false/unknown) 不因未选分支失败而 ineligible。只有完整必需表达式的适用硬失败且无法按政策后补时才 ineligible；eligible 要完整表达式为真且无必要后补义务；其余必要未知不被模型或未经批准政策消除。

## 6. 计划确认、进度与变化（拟实现）

| 方法 / 拟路径 | 请求/返回 | 关键限制 |
| --- | --- | --- |
| `POST /v2/plans/drafts` | profile_version_id、offering_ids、release_id、确认过的准备偏好；201 plan/version/tasks | 服务端重算资格；模型只解释可用结果，不接受 client eligibility、数字或日期作为事实 |
| `GET /v2/plans/{plan_id}` | 当前版本、状态、row_version、任务摘要 | owner/grant；读旧版本不被新资料替换 |
| `GET /v2/plans/{plan_id}/versions/{version_id}` | 历史内容与确认记录 | 精确回放；不静默重新生成 |
| `POST /v2/plans/{plan_id}/confirm` | expected_version、plan_version_id、confirmed=true、selected_task_ids/目标 | 确认当前草案而非执行学校动作；有待复核变化409，依赖/容量不成立422 |
| `POST /v2/plans/{plan_id}/revisions` | expected_version、新 profile_version/release、修订选择 | 创建新草案，保留已完成记录与旧确认；重新确认后才切换活动版本 |
| `PATCH /v2/tasks/{task_id}` | expected_version、允许状态转换、实际投入/完成记录或用户目标日期 | 仅owner或有对应grant；完成依赖、估时/可用时段检查；不能修改招生固定日期 |
| `GET /v2/plans/{plan_id}/changes` | 分页 change_events 与影响、旧/新证据引用 | 新发布后 needs_review；不自动更改已确认任务 |

任务字段包括目标差距、estimated_hours、acceptance_criteria、dependencies、earliest_start、hard_deadline_event_id 可空、user_target_date 可空、状态/版本/确认。依赖无环且不得跨用户；自主目标和学校硬期限区分。工时排不下给422容量冲突与可调整参数，不压缩休息或承诺提分。ineligible/unknown 项目形成差距/人工核验任务，不生成“已可申请”指令。

拟 `GET /v2/me/notifications` 分页读取自己的站内变化通知，`PATCH /v2/me/notifications/{notification_id}` 用 expected_version 标记已读；写入需 CSRF/幂等，不能改通知证据或读取他人的通知。站内提醒由 T36 实施，不发送邮件/SMS。T45 拟 `POST /v2/feedback` 接收最小事实纠错/故障说明与公开证据引用，返回回执；受限流和内容上限约束，不自动公开用户报告或改招生事实。

## 7. 人工导入、审核与发布（拟实现，上线必需）

| 方法 / 拟路径 | 最小输入 / 输出 | 权限和事务 |
| --- | --- | --- |
| `POST /v2/admin/sources` | 来源身份、入口、方式、许可审核、scope；201 source | data_admin 的 source_write；登记不触发抓取 |
| `POST /v2/admin/imports` | 人工文件/文本、source_id、dataset_id、scope；201 有界同步导入回执；需要持久异步且 worker 已验收时才202 import_job | 明确人工导入；校验大小/格式/hash与恶意内容；内容不是指令；超同步边界不启临时后台任务 |
| `GET /v2/admin/imports/{import_id}` | 阶段、错误 field_path、候选引用、需复核项 | 对应admin；不掩盖失败，不删除上一版本 |
| `GET /v2/admin/review-queue` | 类型/year/scope/status 分页 | 仅候选公共事实，不读取学生资料 |
| `POST /v2/admin/facts/{fact_id}/review` | expected_version、version_id、decision、reason | review权限；数值/日期/定位对照原文；reviewed真实事实与demo_reviewed不同 |
| `POST /v2/admin/rules/{rule_id}/review` | 同上；受限DSL和证据关联 | type/scope/阶段/单位/后补期限验证；规则不 eval/exec/调用模型 |
| `POST /v2/admin/releases` | dataset_id、明确成员版本列表、expected_dataset_version、确认 | 201，不可变 release；全部成员同dataset、已审核且有效；release＋change/outbox同事务 |
| `POST /v2/admin/releases/{release_id}/withdraw` | expected_version、reason、确认 | 发布权限；撤回事件，旧成员不覆写；当前公开读取停止使用，受影响方案待复核 |

人工导入是公众 MVP 的数据入口。URL 字段只记录来源，不存在“任意URL自动抓取”或全网爬虫接口。公开展示真实学校的数字、要求和日期必须属于可核验、审核、已发布的真实事实；拿不到依据就显示 unknown/缺口。角色审核记录、证据片段、来源许可和版本审计必须可展示并验收，不能以“人工reviewed”标签绕过流程。

## 8. QA 与可替换 provider（拟实现，条件启用）

自由问答/模型解释是条件启用能力，不是确定性核心上线的前提；上线MVP允许disabled模板。开启live QA前必须完成供应商、传输、成本、引用与授权验收。

`POST /v2/qa` 输入 question、profile_version_id 可空、offering_ids、release_id；必要时带 owner 的读取grant。问题最大长度、候选项目数量、响应token/成本、超时、频率由部署配置确定并公开必要限制。schema中的来源文本不作为指令。

返回 `answer_status=answered|limited|unknown`、有来源的 statements（evidence_id、fact/rule_version、scope）、通用建议单独标签、unknown_fields 与引用完整性检查结果。规则判断固定由确定性引擎产生；模型不能改画像、事实、资格、任务确认或授权，也不能执行SQL/Shell、任意网络请求或学校申请。无证据不猜数值/日期；所有生成引用必须属于这次请求的可见已发布材料。

拟 provider 模式明确 disabled/mock/live，独立于数据模式。verified 正式服务在无密钥的 disabled 模式仍提供结构化目录、确定性资格和模板计划/受限事实解释；mock 只供 demo 且显式标注，不能用于真实服务。公开服务是否启用live及大陆可部署的供应商/城市为发布前决策；跨境供应商和学生字段传输需单独审查，不默认接国外模型。已经配置live后的超时/供应商失败返回503 `PROVIDER_UNAVAILABLE`，不静默换为 disabled/mock；目录和确定性资格不依赖模型仍可运行。后台模型调用的学生字段最小化、授权与保留要求须跟随隐私决策完成后方可启用。

## 9. 删除、运行状态与验收（拟实现，上线必需）

资料查询/更正已由画像版本接口提供。`POST /v2/me/exports` 输入明确的数据范围并重新认证，返回202 export_job_id；`GET /v2/me/export-jobs/{job_id}` 查询自己的作业状态；`GET /v2/me/export-jobs/{job_id}/download` 在逐次owner校验后流式返回导出文件（文件成功响应不包JSON Envelope，错误仍用统一错误协议）。导出只含用户可取得的私有记录、必要版本和引用，不包含其他学生、内部审核批注、凭据或受限公共原文。文件私有、有限期保留，删除/撤权时停止下载，不能作为公开分享链接；异步执行同样校验用户状态。

`DELETE /v2/me/data` 经当前用户强度适当的重新认证、CSRF 与 Idempotency-Key，返回202 deletion_job_id、accepted_at和可公开的阶段；进入删除状态后拒绝新的相关私有写入并撤销会话/共享授权。请求不允许body指定另一owner。`GET /v2/me/deletion-jobs/{job_id}` 读取自己的最少作业状态；认证账号已删除时用专用短期查询能力且只显示作业状态，不能继续访问业务资料，具体协议在身份/删除任务中定稿。

删除覆盖在线记录、对象、私有索引/缓存、幂等私有响应、导出工件、provider保留、敏感outbox，并明确必要审计及备份处理的范围/期限。异常返回可重试步骤，不把“队列受理”标作“全部删除”。一般导出/通知/模型作业重验当前准入；删除/留存作业凭受理时核验的专用系统授权继续，不因会话已撤销而停住。恢复备份后从独立于该业务备份的最新最小删除/撤权台账验证水位并重放、验证隔离，再开放访问；台账缺失不得放流量。地区相关留存依据和用户通知为Decision TBD门槛，不在接口里捏造法定期限。

拟 `/health/live` 只报告进程存活；`/health/ready` 检查目标迁移版本、数据库、必要发布配置、正式身份与后台作业的可运行条件，失败503且不泄露内部地址。可选模型失效若仍提供规则服务，应在能力状态上明确 degraded；需要模型的独立路由仍503。公开健康返回最少字段，详细运维状态只供受授权运维人员。

每个接口任务都需验证 Pydantic/OpenAPI/TS实际序列化、权限矩阵、字段错误、分页稳定性、版本409、幂等并发、交易回滚、真实/合成隔离和四态边界。公众发布前另需正式认证/CSRF/撤销、PostgreSQL真实迁移、数据审核抽查、删除重试与备份恢复演练、基本滥用控制、大陆部署及面向港澳台用户的适用审查、未成年准入决策完成。已有M0测试通过不等于这些检查已通过。

本规划没有录取概率、全网采集、自动提交申请/付款/接受offer端点。T02只实施本文顶部两个基础端点及协议检查；本节公众运行/删除/恢复等功能与检查仍**未实现/未执行**。

## 10. 全国资料只读接口（P02 拟建，T59–T62）

契约与口径见 [data_strategy](data_strategy.md)。沿用 v2 Envelope、游标分页和公开 release 可见性：真实、已审核已发布、未撤回且使用权允许；公众请求不能选任意私有 dataset。查询不存在的年度返回空数据及相应 coverage/missing_reason，不回填最近年度或 DEMO。

| 方法 / 路径 | 范围和返回内容 |
| --- | --- |
| GET /v2/data/coverage | region/year/cohort/dataset_type/pathway/scope_level；各发布覆盖单元、最近核验、缺失原因及已知总量，分母未知为 null |
| GET /v2/statistics/province-cutoffs | province/exam_year/exam_system/subject_track/batch/stage/round/pathway/cutoff_kind；原名、类型、值/单位/总分/加分定义 |
| GET /v2/statistics/score-distributions | 明确考试范围；分数段、人数/累计方向与同分位次区间；没有个人排序不返回伪精确 rank |
| GET /v2/statistics/admissions | province/exam_year/batch/round/institution/group/program/scope_level/metric_kind；投档/终录取/位次/计划各自定义与版本 |
| GET /v2/programs/{program_id}/curricula | entry_cohort/teaching_year/version；当前适用届、学位/学制/校区、课程/学分/学时、毕业要求、缺口及 evidence |
| GET /v2/outcomes | institution/college/program/subject_group、graduation_cohort/metric_kind/method；实际人群/粒度、观察期、逐指标样本/分母、回应率和薪资定义 |
| GET /v2/statistics/comparisons | 有界的已发布 observation_ids；comparable/limited/not_comparable/unknown 及原因；无个人画像、录取概率或总排名 |

统计响应共同携带 requested_scope、actual_scope、aggregation_level、source_definition、独立时间字段、evidence、release_id、data_as_of、missing_reason、comparison_assessed 和 comparison_status/reasons。未请求比较时 comparison_assessed=false、comparison_status=null、reasons=[]；执行比较时 comparison_assessed=true，comparison_status 只取 comparable/limited/not_comparable/unknown 四态。outcomes 按 metric 返回各自 population，绝不能将工作/升学与薪资的样本/届共用；请求专业而只有学校/学科数据时默认专业值缺失，仅明确标注另列汇总数据，不在 program 数值字段返回上级统计。

关键筛选缺失或相互冲突返回422，无法映射代码保留 unmapped，不隐式同名匹配；未公开/撤回对象返回404，限流按既有429协议。省份与机构所在地分开；香港/澳门/台湾普通高考类型返回 not_applicable，其他路线未适配。已发布公开资料允许未登录访客查询，与私有画像接口分开；分页固定范围/release 保持稳定，查询限额和来源展示限制按 T59/T46 确认。

来源登记/人工导入/审核/发布复用既有 admin 端点并新增类型化数据校验；T66 若选择实施，再单独设计管理员白名单获取作业接口与鉴权/SSRF/限额契约，本轮不提供任意 URL 抓取端点。研究 JSON 不作为这些接口的可用返回，也不是生产 seed。

## T35 当前有限修订协议

独立 `create_revisions_v2_app` 继承plans有限profile，只新增五路：GET `/plan-revisions/context`、GET `/plan-revisions/history/{plan_id}`、POST `/plan-revisions`、GET `/plan-revisions/{revision_id}`、POST `/plan-revisions/{revision_id}/decision`；父应用挂`/v2`。默认closed/real_revisions_ready=false，不自动扩展production入口。

提案输入仅old_plan_id/new_plan_id/expected_old_state_version/expected_new_state_version/student_confirmed=true；决定仅expected_revision_version/action accept|reject/student_confirmed=true。JSON<=64KiB、固定UUID/无额外query/无Idempotency-Key；每写要求真实当前session、CSRF+Origin，服务端owner/原purpose/notice/TTL与accept新current来源重验。统一no-store/错误/request_id；409须显式重读不自动重试。历史current_actions=false，不含画像/成绩/replay/quote，保留目标年/范围、原期限精度/安排与完成UUID，unknown日期/时间/时区为null且官方UTC恒null。接受new_plan_confirmed=false/completion_credit_transferred=false。

生成工件为 `packages/contracts/v2/revisions/{openapi.json,generated.ts}`，有限第九profile，不放宽八旧profile。详见[契约](plan_revisions.md)。

## T36 notifications 独立装配

默认关闭的 `create_notifications_v2_app` / `create_notifications_app` 继承revisions，5 operations：GET /notifications/context、GET/POST /notifications/preferences、GET /notifications、POST /notifications/{notification_id}/read。limit整数1..20/cursor1..1024，严格body64KiB/CSRF/Origin/no-store；owner来自DB。enabled需要当前本人明确true和当前profile_id；失效原证明只返回当前合法本人下的off/CAS版本，不自动恢复授权。列表不泄露失效通知数量/游标，旧ID明读仍拒绝。完整wire与错误闭集见[jobs_notifications](jobs_notifications.md)，第10独立生成工件，旧9profile保持。

## T39 独立有限公开QA profile

`create_qa_v2_app/create_qa_app`保留T20三个只读操作，新增GET `/qa/context`与POST `/qa/answers`，parent mount `/v2`，五操作/五path；新工件`packages/contracts/v2/qa/`，旧十profile保持。无key默认verified/disabled，context200/can_ask=false/MODEL_DISABLED，answers503且无DB/provider/quota初始化。

输入复用T38完整RetrievalRequest、可省略keywords默认[]，16KiB UTF8 stream闭合JSON，无自由prompt/owner/学生/幂等key/query。服务固定意图模板与可信实例预算；模型await前/后current取证，仅已验证typed CitationData和有限AdviceCode出口。未知可保留合法发布pins但不编检索原因；内部atom/Claim自由value不传前端。旧标准错误Envelope不扩枚举，固定details qa代码、503/429/409，配置漂移早拒也no-store/requestID。完整字段及界面时序见[冻结契约](qa_entry.md)。

## T40 独立本人资料权利profile

新增`create_rights_v2_app/create_rights_app`继承T36通知profile，六操作：GET `/privacy/rights/context`，POST `/privacy/exports`，GET `/privacy/exports/{request_id}`，GET `/privacy/exports/{request_id}/content`，POST `/privacy/deletions`，GET `/privacy/deletions/{request_id}`。parent只挂/v2；十二profile生成工件`packages/contracts/v2/rights/`，十一旧profile保持。

输入只16KiB闭合JSON `owner_confirmed:true`；当前Cookie、Origin/CSRF、server owner/范围，无query/幂等header/客户端路径或handler。context关闭时匿名200且零DB，其他默认503；启用只synthetic test。所有权利响应no-store；启用T40factory全部traffic核当前外台账及业务水位。状态queued/running/failed/cancelled/completed分开，删除只有completed标online_cleanup_complete=true；可查固定失败原因/责任记录期限。UTF8 JSON原内容导出≤10MiB+SHA/bytes/短期expiry，无会话秘密/他人内容/公共原文件；每次下载当前身份重验。字段与范围见[data_rights](data_rights.md)。

## T59 独立参考空查询（2026-10-12）

新增显式reference factory的GET /v2/reference/coverage与province-cutoffs；year/region及分页参数契约见[reference_api](reference_api.md)。当前只空items、release/分母null与source_not_enabled/not_applicable/scope_incomplete；无DB或published reader，不开放真实数据。新手写packages/contracts/reference.ts与原十二generated契约独立；测试/运行全部未执行。

T60（2026-10-12）：新增同一独立factory GET reference/score-distributions、admissions、comparisons；必需year/region，比较还需两个固定record ID。只空缺口，原码筛选有界，无记录payload/概率/发布reader，全部未运行验证。

T61（2026-10-12）：新增GET reference/programs/{program_id}/curricula，UUID与entry_cohort必需、teaching_year独立；空缺口不复用旧届。固定factory错误保留挑战头和安全details；全部未运行。

T62（2026-10-12）：新增GET reference/outcomes，毕业届/请求层级/对象必需、metric_kind可选。只返回明确空缺口，不回填学校/学科数据为专业值，不换算工资周期。所有HTTP/类型/构建验证未执行。

## BATCH-ZJ-2026-CUTOFF-01 本地真实查询

新create_local_reference_app只localhost，显式REFERENCE_CUTOFFS_READ_DATABASE_URL、实际SELECT权限，默认空factory/M0不变。GET /v2/reference/province-cutoffs返回独立reference.cutoffs.local.1：3本地approved真实行、source/批次/人工引用/UTC抓取及原公布标签、缺满分/加分定义null，release_id/expected_total/ratio仍null，business_available=false/local_reference_only=true。其他年省not_collected、港澳台not_applicable、科类批次round未支持scope_not_supported、未审review_pending、撤回withdrawn；只有批准行可读。limit3..100/无cursor/重复或多余query422；数据无原HTML/密码/私有路径，Meta旧九字段保持。原其余reference资源仍空，十二generated协议不改，手写TS分支升级。完整字段及实际查询见[说明](zhejiang_2026_cutoffs.md)。
