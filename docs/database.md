# 数据库规划：M0 现状与公众 MVP

2026-10-14 SEARCH-SELECT-01不新增表/迁移。身份选项通过当前formal/verified已发布release/member/offering/program/institution/dataset及原T20完整证明读取；名称/国家/父学校条件先于DISTINCT身份UUID排序分页，不直接开放T11候选表。实体id来自原PK，outcome_subject_ref为对应层级PK字符串，不用名称/官方代码哈希造标识；它不证明已有毕业统计映射记录，缺资料仍未知。默认reader=None零目录DB读取，浙江独立库不当作目录，可信业务reader需后续显式配置。角色/SQL/分页/撤回与原始数据均未运行核验；旧M0/迁移保持，见[说明](school_program_search.md)。

2026-10-13 SCHEDULE-ANNUAL-01源码新增AnnualUpdatesBase、独立annual_updates_alembic.ini/head0001_annual_updates/version表public.annual_updates_alembic_version，专用annual_source_updates/public。两append-only表annual_source_cycles/annual_source_update_requests保存闭合配置/计划/请求快照及规范化摘要，非原文字节hash；unique(schedule_id,cycle_year)、每cycle唯一target、exam_year/entry_year独立、恒awaiting_collection/false发布标志，FK/JSON IS TRUE/有界大小/提交时完整count与不可变触发器。维护CLI同事务写入、提交后回执、已存全链读取重验，不改已存配置；旧链/数据保持。仅迁移源码，未创建库/角色/表或实测权限/并发；降级拒自动删表。运行约束见[说明](annual_source_updates.md)，不是已通过PG验收。

2026-10-12 ADR-058：本批T50–T57先交付严格类型及有界本地候选bytes接口，不创建原规划统计/培养/就业PG表，也不实现审核发布接缝。既有17业务迁移与独立ledger原样保留，启动不建表。候选JSON并非正式权威数据库，持久化/FK/事务/发布约束属于后续明确待办；不能将本批源码完成记为实库验收。

2026-10-04 T36持久作业与站内提醒源码与合成隔离验收完成：36新增pure/16实际PG-HTTP/12契约，684前端/TypeCheck/双Build通过；[验收](acceptance/T36_jobs_notifications.md)。新增五表/第16迁移head及默认关闭、本人确认的站内提醒；持久租约/fencing/去重/有界重试，接受清理仅probe，不做真实删除或外部通知。PRIVATE保存核对后才单独T37，本批T40停止，真实处理关闭。

2026-10-04 T35明确修订与有限历史工作台源码与合成隔离验收完成：57纯专项/19 distinct PG及HTTP/Edge、321契约与350相关Python、635前端/Type Check/双Build通过；[验收](acceptance/T35_plan_revisions.md)。仅复用本人明确选择的新草案，追加接受/拒绝与替代关系，旧确认/完成不改、新计划未最终确认；历史不表示当前资格，真实关闭。PRIVATE保存核对后才单独T36，本批T40停止，真实处理关闭。

2026-10-04 T34发布变更业务比较与影响追踪源码与合成隔离验收完成：86纯专项/16distinct PG、723相关Python/590前端、Type Check/双Build与八契约核对通过；[验收](acceptance/T34_changes.md)。仅处理已存发布事件的精确关系与不可变影响轨迹，不重算资格或改写计划完成；无新增HTTP/UI/worker，真实关闭。PRIVATE保存核对后才单独T35，本批T40停止，真实处理关闭。

2026-10-04 T32确认与进度源码及合成隔离验收完成：56新增pure、28 distinct PG/HTTP、305契约回归、865相关旧Python、474前端与Type Check/demo-auth Build通过；[验收](acceptance/T32_plan_execution.md)。独立state_version与不可变记录、首次确认未来容量及重放当前进度保留，不改变资格/学校事实；PRIVATE保存核对后单独T33，本批T40停止，正式处理关闭。

2026-10-04 T30草案源码与合成隔离验收完成：81专项pure、23独立PG用例、641相关Python和474前端通过，Type Check/demo-auth Build通过；[验收](acceptance/T30_plan_drafts.md)。五表/内部服务保持draft与来源绑定，512KiB极端组合限额问题已记录；真实处理/HTTP/排程/确认关闭。按持续授权PRIVATE保存核对后再单独T31，本批到T40停止。

## T32 独立确认与进度基线（源码与合成隔离验收完成）

新增独立 ExecutionBase/execution_alembic_version，head/proposal/confirmation/task_completion 四表；head 的 state_version 为独立 CAS，后三张记录不可变，精确 plan/source/proposal/task/owner/模式绑定，不 UPDATE T30 草案或 registry version。显式执行 `EXECUTION_DATABASE_URL` 配置后的独立 `services/api/execution_alembic.ini` 迁移，要求原十二正确 head；启动只检查不迁移。源码及专库新链往返、不可变/复合FK/JSONB约束已验收；命令 `.venv\Scripts\python.exe -m alembic -c services/api/execution_alembic.ini upgrade head`，当前进程自行安全设置EXECUTION_DATABASE_URL且不保存凭据。正式SQL角色/GRANT/RLS未验收。完整数据/限额/留存/历史规则见[确认契约](plan_execution.md)。

## T30 私有草案基线（源码与合成隔离验收完成）

新增独立PlansBase/`plans_alembic_version`，head `0001_plans_t30`，五表为 `plan_draft_roots`、`plan_draft_versions`、`plan_draft_tasks`、`plan_draft_assessments`、`plan_draft_dependencies`。根绑定实际owner registry及确认画像；版本/任务/准确来源关联/同版依赖保留不可变内容，UPDATE拒绝、后续可信DELETE可用。来源评估只有旧单ID唯一约束，因此本Task不ALTER旧表，以原ID FK加同事务owner/profile/hash验证；新表父子范围使用复合FK。JSON有界、required markers严格检查缺键及类型，留存不晚于源画像/评估及UTC 24个月。无新依赖、无启动建表或重导夹具。

仅通过显式命令 `.venv\Scripts\python.exe -m alembic -c services/api/plans_alembic.ini upgrade head` 迁移；调用前自行在当前进程安全设置 `PLANS_DATABASE_URL`，此处不提供或保存凭据。迁移要求已有auth/idempotency/catalog/storage/imports/evidence/facts/reviews/releases/profiles/assessments共十一正确head；随机隔离测试schema先显式执行这些链，再执行本链。应用不代替管理员迁移，正式数据库登录角色/GRANT/RLS未验收。详见[内部草案契约](plan_drafts.md)与[本轮验收](acceptance/T30_plan_drafts.md)。

## T28不可变评估（源码与合成隔离验收完成）

独立AssessmentsBase及assessment迁移链；评估绑定server owner/不可变画像版本/原用途证明、精确目标/release/ruleset/阶段/时刻/engine、受限上下文/表达式/义务及hash，UPDATE禁止、未来可信DELETE保留。TTL不晚于原画像，旧迁移/head不改；实际单表、两索引、复合FK/UTC留存/有界JSON及UPDATE拒绝已在专库随机schema验收，独立head为0001_assessments_t28；audit_event_id保留但不建审计FK以免阻挡独立审计清理；只降级本链再升级、旧十head保持，见[契约](assessments.md)。

## T23 私有画像版本（源码与合成隔离验收完成）

新增独立ProfilesBase两表及profiles迁移profile，复用AuthOwnedResource为归属依据，完整确认快照不可UPDATE/可供未来可信删除，root/version/registry CAS同事务；旧M0及各迁移头冻结。详见[契约](profiles.md)。

2026-10-03最新产品目标（ADR-034）：全部普通高考生源省份逐省配置，英国本科暂定2027、优先剑桥/曼彻斯特；真实省/年/专业适用证据未验收时unknown。下文旧单省描述为先前规划或M0基线，不表示当前产品目标或已实现覆盖。


## T22 工作台（已验收；真实处理关闭）

无新增表/迁移，复用已有证据/候选/审核/release CAS与历史；预检不创建发布或receipt，发布/撤回使用T19事务。SQL GRANT/RLS与真实资料门槛不解除。详见[契约](admin_review_workspace.md)。

## T21 管理工作台（已验收）

无新表/迁移；复用来源、存储、导入、幂等与审计。T15首次HTTP暴露补同事务COMMIT前末端时效验证；无数据库角色/GRANT/RLS启用，真实处理关闭。详见[管理契约](admin_workspace.md)。

## T20 已发布公共查询（源码与合成隔离实库验收完成）

无新表或迁移。复用T19状态/固定成员与不可变ChangeEvent计数绑定游标，以及当前review/source/file证明；按dataset顺序锁读取后重验。应用query_role仍不是配置好的PostgreSQL只读角色/GRANT/RLS。详见[public_catalog](public_catalog.md)。

## T19 发布快照与事件（源码与合成隔离实库验收完成）

独立ReleasesBase五表/profile0001_releases_t19；release/member/event不可变、state CAS、outbox pending无消费者；发布/替代/撤回整笔dataset.revision+1，去重/重放不增加；旧heads冻结。详见[releases](releases.md)。

## T18 审核台账（源码与合成隔离实库验收完成）

独立ReviewsBase/profile 0001_reviews_t18，review_cases唯一logicalkey与revision/currentselection，review_decisions及review_conflict_resolutions不可变；T17历史边/flags与旧heads不改。详见[reviews](reviews.md)。

## T17 类型化候选（源码与合成隔离实库验收完成）

独立FactsBase/profile 0001_facts_t17，两表fact_candidates/fact_conflicts；不可变内容与历史冲突，不覆盖旧Base/heads。规范等价数字不误报冲突，分类/单位/时间/统计口径分别明确；T18另建resolution台账。详见[facts](facts.md)。

## T16文档与定位（源码、合成抽查与隔离实库验收完成）

新增独立EvidenceBase三表及evidence版本表，确切source/file/offering版本FK，不可变version/snippet触发器，原迁移链不变。详见[evidence](evidence.md)。

## T15导入候选（2026-10-03，源码/隔离实库验收完成）

独立ImportsBase/profile三表import_batches/import_candidate_rows/import_row_errors；exact dataset/source/version/file hash与自然内容键、row范围FK、draft/unresolved及只固定错误代码。与T49回执/成功审计同事务，不修改旧目录/发布事实。详见[imports](imports.md)。

## T49幂等事务（2026-10-03，源码验收完成）

IdempotencyBase/profile与idempotency_alembic_version独立，0001仅依赖auth0006；actor/op/key_digest唯一、canonical_request_hash和最少资源引用、processing/completed耦合与deferred完成检查。业务/回执同事务，过期只替换回执；无任意响应payload。显式迁移不在启动执行，旧各域不变。详见[idempotency](idempotency.md)。

## T14文件边界（2026-10-03，源码验收完成）

独立StorageBase/storage_objects及storage profile，显式先具备auth0006/catalog0003；旧链不改。内部attachment/owner或source exact version复合FK、类型/长度/hash/期限与隔离/墓碑状态，不保存客户端路径。上传metadata/registry/audit同事务，FS失败补偿与不可读孤儿边界见[storage](storage.md)；不宣称数据库和文件系统两阶段原子或已实库验收。

## T13来源治理增量（2026-10-03，源码/隔离实库验收完成）

catalog链0003及SourceBase新增catalog_sources根/catalog_source_versions不可变快照，复合FK包含dataset/source/synthetic及确切正版本。publisher/URL/purpose/data_type/scope_note、官方声明/三许可、basis/review参考、服务器责任UUID/UTC声明和复查期限分别存储，不用official标签当许可。服务当前data_admin+签名强认证、同事务版本/审计及最终重验；真实责任配置缺失默认关闭。审计复用administrator.action且无伪source/import引用，不保存URL/原文。CatalogBase/DatesBase及旧链冻结，详见[sources](sources.md)/[T13验收](acceptance/T13_source_register.md)；隔离实库验收完成，正式备份/恢复未执行。

## T12日期候选增量（2026-10-03，源码/隔离实库验收完成）

catalog链新0002只新增catalog_date_events；DatesBase独立，CatalogBase恒五表，M0/auth旧链与0001不改。复合FK绑定确切机会版本及synthetic父范围；entry_year输入只作匹配断言，输出由父派生，表不重复存年。date/minute/second/unknown保持原精度，计算候选与官方UTC分开；draft/unresolved及官方utc_instant NULL落实DB检查，不能伪已审核证据。可信store同事务/当前头检查，不提供HTTP/通用修改。契约、迁移恢复和实测分别见[dates](dates.md)、[T12验收](acceptance/T12_date_events.md)，隔离迁移/恢复已通过，正式备份恢复未执行。

## T11候选关系模型（2026-10-03，源码/隔离实库验收完成）

独立`CatalogBase`/`catalog_alembic_version`及`0001_catalog_t11`新增五张`catalog_`表：datasets、institutions、programs、offerings、offering_versions。不改M0七表/旧迁移或auth0006；默认应用和公开目录尚不装配此存储。内部UUID与DEMO reference/display标记分开；dataset固定private，verified标记不能证明已审核。

Program→Institution、Offering→Program、确切版本→Offering均使用dataset/synthetic复合FK；未知、不适用与已知范围保留不同非空规范键。完整业务键显式包含年、intake、申请周期、渠道、课程、路径、身份、省、考试、科类和批次/组；不同校区在Program级区分。候选登记/版本追加使用调用者同engine活动事务，锁dataset/root并校验expected revision/version，不自动提交或覆盖旧版本。store不提供通用身份/范围更新与旧版本删除；FK不级联历史，未配置生产数据库权限或防恶意维护SQL沙箱。

T19才建立release与确切版本成员FK，T13来源和T15导入另实施；本Task不保存录取分数/政策期限或发布研究样本。完整契约、规范键界限、迁移恢复及真实检查见[catalog](catalog.md)、[T11验收](acceptance/T11_admissions_catalog.md)。空库/重复升级及隔离schema降级恢复已通过，正式库备份/还原未执行。

## T10最小审计增量（2026-10-03）

当前独立认证head为`0006_audit_t10`，13张auth/privacy/grant/audit业务表加`auth_alembic_version`。增量仅新增`auth_audit_events`，0001–0005和M0链冻结；启动只读检查head和所需表列，不DDL、seed或授予数据库角色。

审计保存UUID、UTC操作时间、固定主体类型及最小user/session引用、固定动作/对象类型、可空对象UUID/正版本、结果/固定原因、服务器32位hex request_id、合成标记、`T10_audit_v1`和有限expires_at。Pydantic拒额外输入，DB落实动作/原因/对象类型白名单与字段耦合CHECK、查询/到期索引。无自由JSON、原文、凭据、成绩、附件、提示词、issuer/sub/email/IP/UA；失败事件不保存请求中的对象ID。引用无FK、没有权限效力，不能冒充防篡改账本；可信维护SQL、生产GRANT/RLS仍须后续验收。

已实现操作的成功审计与业务在同Session/TX追加并flush，失败回滚业务；业务事务释放后失败记录独立尽力写入，不掩盖原固定错误。新增审计等待后再次核对当前账户/会话/角色/用途/共享证明及期限；登录建立会话在提交前再次核对登录事务及绝对会话期限。内部审计读/清理需当前operations与显式签名强认证，同事务最后重验。审核/发布/导出/删除固定动作只预留接入点，相关业务尚未实现。

审计expires_at按UTC日历最多24个月计算；明确有界清理仅删除已到期审计，并记录清理动作，不在启动执行。常规日志30天另由专用目录工具处理；生产收集器、私有删除及备份传播未验收。实现契约见[audit](audit.md)，实际检查另记[T10验收](acceptance/T10_audit_redaction.md)。

## T09共享授权增量（2026-10-03）

T09历史head为`0005_shared_grants_t09`，旧0001–0004及M0链冻结。新增auth_sharing_states（owner单调revision）、auth_access_grants（exact对象/version及双方原证明、policy/hash、期限、pending/accepted/revoked状态）、grant_fields和grant_actions（规范化scope PK/CHECK）。同owner对象及双方原证明采用复合FK；后续新证明不能使旧grant复活。scope不由普通修改接口扩大，换范围须新授权。

T09验收时12张auth/privacy/grant业务表及auth_alembic_version，当前表数以上方T10为准。启动仅检查head/表列，不DDL、seed或赋角色。参与账户先UUID排序锁、再真实actor/角色/对象/证明检查；同事务撤销与授权访问有隔离PG锁测试。SQL过滤scope在分页/count之前，最后fresh clock重验含角色边界。记录最小UUID/状态，不保存学生payload；无数据库immutable trigger或已配置生产GRANT/RLS。数据库迁移仅隔离测试库实际升级/降级验收，正式备份恢复与部署未执行；见[共享契约](sharing.md)。

## T08准入增量（2026-10-03，源码验收已完成）

独立认证链新增`0004_privacy_t08`，旧0001–0003和M0链冻结。新`privacy_notice_versions`保存实际文本/hash、政策/告知版本、责任引用和合成测试复核标记；新`privacy_admission_records`按用户追加revision快照，成年声明仅`18_plus/declared`或清除，当前确认指向原确认事件并用复合FK约束同owner。拒绝的新儿童年龄段不保存；已成年声明改报拒绝年龄则追加最小失效事件。服务不覆盖旧版本；没有数据库防维护SQL篡改的immutable trigger。

账号锁统一序列化确认/撤回；`UNIQUE(user_id,revision)`、同owner确认FK和年龄/同意完整性CHECK落实存储约束。`require_purpose`复用授权操作的同Session事务并重验当前身份/角色/准入，事务actor绑定不是缓存许可。迁移显式执行，启动只验head与所需表，不DDL/seed。默认草案/契约生成无数据库依赖；生产真实处理没有启用开关，只有test环境合成主体与告知夹具可验完整流程。

D06产品保留上限不表示已运行清理、删除或备份恢复传播；正式处理责任和告知、法律适用性未完成。完整字段/验收见[隐私契约](privacy.md)、[T08验收](acceptance/T08_admission_privacy.md)。源码验收通过不代表真实业务或数据库GRANT/RLS已开放。

T05更新2026-10-02：新增独立auth迁移profile、四表与版本表，不改变冻结M0迁移/七表/DEMO夹具。T04纯接口精确键保持；T05在数据库落实issuer/subject唯一、浏览器绑定一次性登录及摘要会话，已离线/隔离实库验收。实际身份配置见[identity](identity.md)。

## T07对象权限迁移增量

T07历史head为`0003_auth_t07`，当时六张auth业务表；T08历史head为`0004_privacy_t08`，再加两张privacy表；当前T09又增加四张grant表及`auth_alembic_version`；应用启动不DDL/seed/赋角色，旧0001–0003与M0原字节保留。新增权限元数据只含UUID与授权关系，不存真实学生资料。

| 新表 | 字段与约束 | 用途 |
| --- | --- | --- |
| auth_user_roles | user_id FK、固定role student/data_admin/operations、granted_at/expires_at/revoked_at；每用户role唯一、期限CHECK | 从当前DB读取有效应用角色，不接受IdP或请求roles；旧账户默认无role |
| auth_owned_resources | UUID id、resource_type、owner_user_id FK、status active/deleted、正version、is_synthetic、nullable parent_id；UNIQUE(id,owner_user_id)、复合父FK(parent_id,owner_user_id) | profile/plan根，attachment/export/job必须同owner根；只有权限元数据，无画像/文件/作业payload |

服务通用修改仅profile/plan版本touch，不能改id/type/owner/parent/synthetic；数据库未加immutable trigger，可信维护SQL仍能改变元数据，后续调用必须重新授权。派生父kind/active状态由SQL授权与可信登记校验，FK落实同owner关系。未来业务必须同事务登记并关联唯一归属依据，不能保留自由修改的owner副本。列表先SQL过滤再count/page；同步操作回调使用同一SQLAlchemy Session，账户→会话→角色→父/对象锁顺序与角色撤销一致，锁后fresh clock。T07当时无共享grant；T09独立metadata grant不放宽此接口。当前无生产RLS、真实领域表/worker或跨系统副作用保证。契约与测试见[T07](acceptance/T07_object_authorization.md)、[授权模块](authorization.md)。

## T06认证迁移增量

T06历史head为`0002_auth_t06`（当前须升级0006_audit_t10），新增版本文件，保留`0001_auth_t05`与M0链原字节。auth_sessions增nullable `csrf_digest/csrf_encrypted_token`成对约束、`verified_issuer/verified_client_id`来源对，以及`assurance_acr/assurance_amr/assurance_auth_time`；稳定随机CSRF只存域隔离摘要和Fernet密文，已有会话锁行初始化，绝对expires_at不变。签名验证后提取认证强度，不持久JWT/token/外部roles；旧NULL会话普通读取保留，管理员强度拒绝。

退出在锁定当前会话及账户后再次验证有效期/状态/CSRF并写revoked_at；延迟执行引用重新查询session_id/user_id与当前状态，再调用显式服务器权限verifier，缺省拒绝。内部引用不是HTTP认证凭据，不能由请求owner参数构造授权；尚无队列/对象grant或跨系统副作用保证。启动只读检查新head，未升级503；无自动DDL/seed/账户创建。迁移、并发及旧数据保留以[T06实库验收](acceptance/T06_session_csrf.md)为准。

## T05已实现认证增量

`services/api/auth_alembic.ini`与`auth_migrations/versions/0001_auth_t05.py`使用独立`auth_alembic_version`（T05时head `0001_auth_t05`，当前须升级T10）及AuthBase。显式`migrate_auth(engine)`或Alembic命令才创建表；identity启动只检查ready，不建表或seed。认证可在同一PostgreSQL库独立schema中部署，T05测试随机schema仅包含认证四表+版本表（当前六张auth＋两张privacy＋四张grant＋一张audit表+版本表）；不视作微服务或自动赋予数据库角色/GRANT/RLS。

| 表 | 字段与约束 | 用途 |
| --- | --- | --- |
| auth_users | UUID id、status active/disabled、created_at、is_synthetic；状态CHECK | 预登记账户最少字段；无密码/email/角色，生产拒合成 |
| auth_identities | UUID id、user_id FK、issuer、subject、created_at；UNIQUE(issuer,subject)，PG列COLLATE C | 大小写精确映射；不同issuer或subject不合并，不按email寻找 |
| auth_login_transactions | UUID id、UNIQUE state_digest、browser_digest、固定provider/issuer/client/redirect、encrypted_context、issued_at/expires_at/consumed_at | 两随机值只存域分离SHA256；nonce/verifier上下文Fernet密文，消费后清空；时间和消费约束 |
| auth_sessions | UUID id、user_id FK、UNIQUE session_digest、created_at/expires_at/revoked_at | 不透明随机Cookie只存域分离SHA256；登录轮换撤销旧会话，每次读取验证账户与有效期 |

领取state时在同事务SELECT FOR UPDATE并条件UPDATE，匹配state/browser、未消费且未到期才能提交claim；错误浏览器不消费，已匹配失败不再重试。网络I/O在提交之后；建立会话时锁定精确预登记账户，必须active且符合生产合成限制，撤销旧摘要与插入新会话在同事务。ID/access/refresh token均不持久化。绝对TTL可配置，D06产品上限已选，正式适用性/清理/删除/备份恢复待后续Task，不自动迁移旧M0用户。

后续下方公众模型仍为规划，不能把本四表视作已实现角色、授权、同意、画像或真实目录。验收见[T05](acceptance/T05_login_session.md)，独立迁移理由见[ADR-016](DECISIONS.md)。

规划日期：2026-10-01，Asia/Hong_Kong；T03更新2026-10-02。本文件区分M0七表与公众数据库设计；生产部署、真实私有处理和公众业务仍未开放。固定PostgreSQL + SQLAlchemy + Alembic、FastAPI/Pydantic模块化单体与Vue3/TypeScript/Vite。T03只改应用模式/读取策略，不创建迁移或执行生产数据库操作。

## T03应用读取边界（无数据库设计变更）

`query_role=demo_only/published_readonly`是冻结配置派生的应用策略，不是已配置PostgreSQL登录角色/GRANT/RLS。策略固定内部数据集demo_catalog/verified_catalog，真实候选须非合成、非DEMO、reviewed/published且未撤回；这些描述仅供拒绝检查，不能作为正式审核证据。当前不存在真实发布库，所以任何非空候选均503，正常基础列表为空。v2 factory不导入数据库、不连接、不建表；可选V2_DATABASE_URL只做PostgreSQL格式/已知DEMO身份校验，没有配置也可运行基础。实际SQL角色、最小权限、发布表与查询接入须在后续数据库/目录Task验收，不能用本轮离线策略测试代替。旧M0迁移/模型/夹具与七表保持；生产/verified上下文的M0 seed明确拒绝。见[T03验收](acceptance/T03_mode_isolation.md)。

首个 MVP 面向中国大陆、香港、澳门、台湾地区的用户公开提供服务，计划部署在中国大陆；具体城市/供应商仍待选。正式身份、私有数据隔离、可审核事实、隐私与删除、恢复演练均是上线前要求。未成年人准入及相应告知/同意要求仍是 **Decision TBD / 发布阻塞项**；本规划不构成法律合规结论。单个平台运营，不在首个 MVP 建 SaaS 多租户体系。首 MVP 路径仍仅一个配置省份普通高考本科＋英国本科；DSE、联招、澳门/台湾其他资格体系不在该 MVP 适配范围。

## 1. 已实现的 M0 基线

实际依据为 `services/api/app/models.py`、`schemas.py`、`main.py`、迁移 `services/api/migrations/versions/0001_m0.py` 和 `packages/contracts/index.ts`，不是原方案中所有实体都已落地。现有业务表只有以下七张；`alembic_version` 是迁移工具表。

| 当前表 | 当前列 / 关系 | 当前限制 |
| --- | --- | --- |
| `institutions` | `id` PK，`name`，`country`，`is_synthetic` | 只有 DEMO 机构，没有机构审核或发布表 |
| `offerings` | `id` PK，`institution_id` FK，`country`，`entry_year`，可空 `province`，`is_synthetic`，JSON `payload` | 课程与招生机会信息合在 payload；没有独立 program 或 release |
| `evidence` | `id` PK，`document_version_id`，`document_sha256`，`raw_document`，JSON `payload` | 文档版本 ID 是字符串，不是独立文档版本表的 FK；仅合成原文 |
| `rules` | `id` PK，`offering_id`/`evidence_id` FK，`version`，JSON `payload` | 没有管理员审核流水和规则集发布记录 |
| `profile_versions` | `id` PK，`profile_id`，`owner_id`，`version`，`is_synthetic`，JSON `payload`；唯一 `(profile_id, version)` | 每次确认创建独立 version=1 画像；没有 profile 根表或纵向 PATCH 流程 |
| `eligibility_results` | `id` PK，`owner_id`，`profile_version_id`/`offering_id` FK，`ruleset_version`，JSON `payload` | 确定性结果快照，没有独立规则集 release FK |
| `plan_drafts` | `id` PK，`owner_id`，`profile_version_id` FK，JSON `payload` | 草案内含任务；没有确认、任务进度或周排程表 |

已有索引是 `offerings.country/entry_year`、`rules.offering_id`、私有表的 `owner_id`，以及结果/草案的 `profile_version_id`。不声称当前已有复合 scope 索引、数据库行级安全、生产用户表、版本锁或删除流程。当前 owner 是服务端 DEMO token 对应字符串，没有用户表 FK。

M0 夹具有 2 个 DEMO 机构、4 个招生机会、7 条合成证据和 9 条规则。证据 payload 包含明确的 `offering_ids` 和年度/国家/省份/身份/路径；引擎校验具体项目范围、原文哈希、片段、版本和审核标签。`demo_reviewed` 只代表演示夹具状态，不能改名冒充真实人工审核。所有事实都是合成数据；数据库默认 PostgreSQL，SQLite 仅显式离线替身。既有 [M0 测试记录](M0_TEST_REPORT.md) 明确 PostgreSQL 实库尚未验证。

## 2. 按小任务演进，不提前建全部表

下列是能力任务的数据库边界，具体顺序和任务编号由 [任务规划](tasks.md) 统一。只有执行相应任务时才创建迁移；本文件的“拟增”表均未实现。公网发布必须等所有标作必需的任务验收，不用“后续再补”替代公众 MVP 的安全底座。

| 能力任务 | 拟增或演进的表 | 首次迁移边界 / 验收 |
| --- | --- | --- |
| 正式身份与隐私底座（上线必需） | `users`、`auth_identities`、`auth_sessions`、`user_roles`、`access_grants`、`privacy_notice_versions`、`consent_records`、`audit_events` | 正式用户与演示凭据隔离；撤销会话/授权立即生效；告知版本与必要确认可追溯；日志不含原始画像或凭据 |
| 可审核目录与人工导入（上线必需） | `datasets`、`programs`；演进 `institutions/offerings`；`sources`、`source_documents`、`document_versions`、`evidence_scopes`、`import_jobs` | 人工导入只形成候选版本；合成/真实事实数据集隔离；文件、哈希和原文定位可复核；默认不自动抓取 URL |
| 事实审核与发布（上线必需） | `admission_facts`、演进 `rules/evidence`、`reviews`、`releases` 及有 FK 的发布成员关系；T19 首建 `change_events/outbox_events` 基础表 | 发布只包含同一 dataset 的已审核版本；公布前 scope/日期/单位检查；发布和待处理事件原子提交；错误版本撤回但不覆盖历史 |
| 画像确认与规则评估（上线必需） | `profiles`、演进 `profile_versions`；`assessments`、`achievements`、演进 `eligibility_results` | 私有根画像与不可变确认版本；预测/实得分离；owner、grant、scope 与四态回放验收 |
| 计划确认与执行记录（上线必需） | `plans`、`plan_versions`、`tasks`、`task_dependencies`、`task_progress_events`、`plan_confirmations` | 确认及修订锁；保留已完成项；依赖无环；用户可用时数约束；无固定期限不补日期 |
| 变化与持久作业（上线必需） | T34 扩展影响关联，T36 扩展已有 outbox 的租约/通知记录；`deletion_jobs`；`idempotency_records` 由基础 T49 先建 | 业务写入和 outbox 同事务；变化待复核；删除、通知/站内事件可重试且去重；后台作业不得读无关学生资料 |
| 上线与运维验收（上线必需） | 按需增加作业步骤/恢复演练记录，不复制业务历史表 | PostgreSQL 实库迁移、回滚/恢复、权限、删除与备份恢复后的删除重放检查；可度量的 RPO/RTO 目标另行决定 |

模型接入只增加必要的 provider 配置、请求用量与审核结果记录，不引入向量库、复杂 Agent 框架或微服务。拟 MVP 模型配置为 `disabled/mock/live`，独立于 `data_mode=demo|verified`：正式 verified 服务无密钥时使用 disabled 的确定性模板；mock 仅在 demo 上下文；live 失败明确失败不自动换模式。M0 当前仅有 mock/live，未实现 disabled。历史竞争数据若进入首个 MVP，只作为独立的有证据资料展示；它不是硬资格门槛，也不生成录取概率。

## 3. 数据集与私有学生资料是不同的边界

`datasets` 描述**公开资料事实**的数据集，包含 `id`、`data_mode=demo|verified`、`visibility=private|public`、负责人、生命周期状态；P02 拟扩展到历史统计、培养与毕业结果。verified 表示正式事实管线，候选行仍需单独审核；真实公开目录只读 verified 且已发布、未撤回的 release。合成机构/项目名称和 ID 继续使用 `DEMO_` 前缀及 `is_synthetic=true`；真实机构要求有可核验身份与来源，不能拿 DEMO 门槛绑定真实学校。

同一 release、规则、证据链和资格评估只能引用一个事实 dataset。使用 `(dataset_id, resource_id)` 复合引用或等效数据库约束，避免某条真实规则引用合成证据。公开目录不接受客户端通过任意 dataset_id 选择私有候选、撤回版本或演示内容。演示服务优先单独部署并使用独立数据库；若共享 PostgreSQL 实例，必须使用独立 schema、数据库访问角色和存储命名空间，不能只靠 UI 水印。

`profiles/profile_versions` 属于**私有用户资料**，有 `owner_user_id` 和服务端确定的 `profile_mode=real|synthetic`，不把学生记录写入公开招生 dataset。评估同时记录 `profile_version_id`、`dataset_id`、`release_id` 和模式，避免把学生是否合成与招生事实是否合成合并成一个真假标志。公众正式环境禁用固定 DEMO 凭据；合成测试画像只在隔离演示/测试上下文创建。真实账号不能通过 body 里的 owner、role、mode 把自己变成管理员或演示用户。

## 4. 目录与适用范围

机构负责身份；`programs` 保存学位、课程、校区、授课语言与路径区别；`offerings` 是 program 在一个具体入学周期和申请路径上的机会。资格用 offerings 默认仅本科、一个配置生源省份普通高考和英国本科；全国参考统计保留自己的生源范围。省份不是机构所在地，英国项目的省份通常 `not_applicable`，仍必须核验申请身份、课程资格、具体项目与年度。

| 关键字段 | 约束 |
| --- | --- |
| `dataset_id`、`program_id`、`offering_id` | 各级 FK；资格用招生事实与规则有明确具体 offering 适用关系，不靠同名或国家推断；公开历史/培养/毕业统计按第10节实际层级关联，不强制伪造 offering |
| `entry_year`、`intake`、`application_cycle` | 与历史录取年度分开；不同年度是不同机会版本，不把去年要求当今年规则 |
| `country`、`study_level`、`course_system`、`pathway`、`applicant_category` | 白名单和独立路径适配器；未支持范围返回 unknown 或“未支持”，不能套用现有规则 |
| 私有画像 `user_location_region` | 仅必要时由用户自述所在地区；与招生申请身份/课程体系分开，不能从香港/澳门/台湾所在地推断 cn_mainland 或某项资格 |
| `province`、`exam_system`、`subject_category/subject_combination`、`batch/group` | 国内粒度；未知与不适用分别记录，选科要求用审核后的结构，不自动推断学生组合 |
| `valid_from/valid_to`、`data_as_of` | 原文未给出的业务期限允许空；记录时钟不能冒充原文业务日期 |
| `version`、`review_state`、`release_id` | 不可变业务版本、独立审核/发布记录；查询固定到某个 release 快照 |

拟唯一业务键为 `(dataset_id, program_id, entry_year, intake, pathway, applicant_category, province_key, subject_scope_key, batch_group_key, version)`；先在路径适配器规范化有意义的键，再建立约束。SQL 中可空字段的唯一语义必须用目标 PostgreSQL 实测，不能以普通 UNIQUE 含 NULL 就断言防重。跨项目共享证据必须显式列出全部 offering，不能自动扩张 scope。

## 5. 原文、事实、审核与发布

| 实体 | 最小必要字段与关系 |
| --- | --- |
| `sources` | publisher、域名/入口、负责人、可用方式、许可/条款审核记录、启用状态；官方身份与抓取许可分开 |
| `source_documents` | source FK、来源 URL、标题、语言、许可/展示限制、稳定文档身份；URL 是数据，不是抓取或执行指令 |
| `document_versions` | document FK、原文/私有对象引用、SHA256、取得时间、published_at 可空、导入人、解析状态；同一文档和 hash 去重 |
| `evidence` + `evidence_scopes` | document_version FK、locator、原文片段、语言、具体 offering 范围、审核结果、数据有效性；hash 必须对应保留原文 |
| `admission_facts` | offering/scope、fact_key、类型化 value、unit/scale/currency、missing_status、业务有效期、证据、版本；最低要求/典型 offer/历史统计不得共用 fact_key |
| `rules` | 审核后的受限 DSL、阶段、scope、关联事实/证据、规则版本、后补政策引用和期限事件引用；无 eval/exec，也不调用模型 |
| `reviews` | 对象及版本、decision、reason_code、审核者、审核时间、必要批注；复核者不能靠角色默认取得学生资料 |
| `releases` | dataset FK、release_version、成员版本清单/hash、发布者/时间、当前可见状态、撤回/替代引用；不可变成员快照 |

候选内容为 `draft → review_required → reviewed`，冲突进入 `conflicted`；发布动作把审核通过的**确切版本**放入 release，不用一个任意字符串标签替代审核流程。撤回和过期作为独立事件/当前有效性状态记录；旧 release 的成员和原始内容保留供审计，当前判断不继续使用撤回或失效规则。修正事实创建新版本并重新审核，新 release 标记受影响计划 `needs_review`；历史已确认计划和旧资格结果保持可回放。

缺失状态至少区分 `not_collected/not_published/not_applicable/conflicted/review_required/source_unavailable`。没有证据的 null 不是自动放行；来源不可用也不能把陈旧内容标作实时已核查。

## 6. 日期独立建模

在事实/发布任务引入 `date_events`（以及需要的 offering 关系），将申请、平等审理、补材料、语言后补、接受 offer、奖学金等事件分开。字段为 `event_type`、原文、`local_date`、可空 `local_time`、可空 IANA `timezone`、`precision=date|minute|second|unknown`、可空 `utc_instant`、entry_year/scope、evidence、review_state。

只有日期时保留 `date`：不补 `23:59`、时区或 UTC 时刻。只有时区和时间足以唯一换算且经过审核时才保存 `utc_instant`；出现夏令时歧义先 unknown。系统记录时钟用 timezone-aware timestamptz，原文地域时区仍单独保存；PostgreSQL 的 timestamptz 不保留最初输入的时区身份。[PostgreSQL 日期类型文档](https://www.postgresql.org/docs/current/datatype-datetime.html)

期限核验使用来源政策已审核的参考日历，不默认使用服务器所在地区日期。只有日期、缺参考时区、期限当天或夏令时边界无法确定是否过期时，保持待核验/unknown；能确定未过期才允许后补条件。不得为得到布尔结果补造截止瞬时。

计划的 `user_target_date` 是用户目标；`hard_deadline_event_id` 才是有证据的固定期限。计划生成时检查事件范围、审核、有效性及引用完整性。未公布日期仍可形成“人工核验期限”的任务，但不伪造学校截止日期。

## 7. 正式身份、确认画像与四态结果

`users` 仅保存业务必需身份和账号状态；正式认证按架构建议采用OIDC授权码＋PKCE，供应商与恢复策略为D04 Decision TBD，通过 `auth_identities` 映射经服务端验证的issuer＋subject。`auth_sessions` 保存高熵会话标识的 hash、到期/撤销时间及最少风控元数据，不保存明文凭据。管理员强认证、会话撤销、过期、CSRF 与暴力尝试控制均需在公开前验收。

`user_roles` 给平台职责，`access_grants` 给具体学生资源、字段集合、动作、期限和撤回状态；`advisor/data_admin` 不自动拥有学生资料。每条私有查询、缓存、对象存储签名和导出都从服务端身份上下文验证 `owner_user_id` 或有效 grant。数据库业务连接不能使用迁移超级用户。若采用 RLS 增强隔离，必须测试表 owner/BYPASSRLS 绕过及备份完整性，不能仅“打开 RLS”就宣称隔离已完成。[PostgreSQL 行安全文档](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

`profiles` 是稳定根 ID、owner、当前已确认版本和 `row_version`；`profile_versions` 保存不可变确认内容、confirmed_by/at、输入 schema 版本及 consent/告知版本引用。更改画像插入新版本，不 UPDATE 旧画像 JSON。学生所在地、招生身份、课程体系必须分别由必要自述/核验字段取得；不收护照号码，也不依据居住地区或姓名猜测资格。未支持的 DSE/联招等画像不能直接按 gaokao 判断。`assessments` 属于某个画像版本，保存 kind、value、scale、unit、考试/测评日期、有效性和来源状态；缺成绩不创建 value=0 行，预测成绩不能冒充实得。`achievements` 区分自述和已核验经历，普通兴趣不作为硬资格。

普通顾问grant允许辅助建议，不默认代替学生确认画像/计划或用途同意。确认记录必须绑定实际owner主体；监护人能否及如何代确认由D02准入政策独立确定并验收，不能把通用write权限解释成用户已确认。

`eligibility_results` 演进为不可变评估快照，保存 profile_version、offering/version、release/ruleset、engine_version、assessment_at、原子结果、缺失项、条件、证据链及结果维度。实际判断与假设情景单独标记，情景不写回学生画像。

| 资格状态 | 判断规则 |
| --- | --- |
| `eligible` | 范围正确，适用、已审核、有效完整必需表达式为真，且无必要后补义务；不表示录取 |
| `ineligible` | 有适用证据的完整必需表达式明确失败，且无政策允许该失败后补；不是 any 某一分支失败 |
| `conditional` | 完整需求无不可后补硬失败，其余必要未决项仅为可后补义务；必须有适用、已审核且未过期的后补政策和带证据期限 |
| `unknown` | 缺实得成绩且无上述后补依据，或规则/证据/范围/单位/期限不能核验；未知不当 true/false |

`competition_context`、`preference_fit`、`data_quality` 分开保存，不混为一个匹配总分。历史统计只用适用且可比资料；不给出录取概率，不把历史最低分当今年招生资格。

表达式按三值语义归约：any(true,false/unknown) 为真，all(false,unknown) 为假，not(unknown) 为未知。只有表达式实际需要的缺失义务参与 unknown/conditional，不能将未选替代分支的原子失败直接升级为整体 ineligible。

## 8. 计划、版本锁、事务与幂等

`plans` 是私有根和当前版本/row_version；`plan_versions` 内容固定到已确认画像与 release，保存 `draft/confirmed/needs_review/superseded` 的生命周期记录。`plan_confirmations` 明确确认人、时间、确认版本和目标；资料变化只生成修订建议，不静默覆盖确认计划。

`tasks` 保存 plan_version、目标差距、类型、估时、可用时段、验收条件、证据、固定期限、用户目标日期和 row_version。依赖必须同一 owner 和允许的计划范围，事务内验证无环；进度事件追加到 `task_progress_events`，保留原完成记录。修订任务用明确 supersedes/carry-forward 关系，不能把旧的 done 改回 todo。实际分周安排不超确认工时；排不下报告冲突，不承诺提分。

版本修改使用 `expected_version` 条件比较并递增，失败返回 409；业务版本号与数据库 row_version 分开。SQLAlchemy `version_id_col` 只覆盖相应 ORM flush，批量 UPDATE/DELETE 不能自动获得同样保护，须显式 WHERE 版本并检查影响行数。[SQLAlchemy 版本计数文档](https://docs.sqlalchemy.org/en/20/orm/versioning.html)

`idempotency_records` 的唯一键为 `(actor_user_id, operation, idempotency_key)`，保存规范化请求 hash、状态、响应/资源引用与 expires_at。相同 key+同请求重放相同业务结果，不重复写 profile/plan/import；同 key 不同请求返回 409。不能用 owner 外共享 key 缓存响应。幂等保留时长在运维配置确定，并说明到期后不再保证重放。

重放前仍校验当前身份、角色/grant、用途准入和删除状态；曾被授权不代表缓存响应永久可读。优先保存资源引用或最小回执；确需保存私有响应时纳入权限、留存及删除传播。

画像版本＋根指针；计划＋任务＋确认；审核发布＋成员＋change/outbox；删除标记＋作业＋会话撤销，分别在单个本地事务内一致提交。模型或对象存储等外部调用在受限接口执行，不长期持有数据库锁；成功后再次校验版本才入库，外部失败显式记录，不回退为假成功。

## 9. 索引、删除留存与 PostgreSQL 验收

拟索引从实际查询产生：公开目录 `(dataset_id, release_id, country, entry_year, pathway, applicant_category, province, id)`；scope/证据关联的 FK；画像 `(owner_user_id, updated_at, id)` 和 `(profile_id, version)`；结果 `(owner_user_id, profile_version_id, created_at, id)`；任务 `(owner_user_id, status, target_date, id)`；grant 受权人/资源/失效；作业 `(state, available_at, id)`；日期事件 `(offering_id, event_type, entry_year)`。JSONB 用于快照和有限 DSL，主查询 scope/owner 必须有类型化列；是否加 GIN 以 EXPLAIN 和样本查询验证，不预建所有可能索引。

`privacy_notice_versions` 保存不可变告知文本/hash及适用范围；`consent_records` 记录用户、用途、版本、确认或撤回时间，不能把一个勾选框当作所有处理的合法依据。大陆部署面向大陆/港澳台用户时的告知、服务适用性与跨境 provider/存储须经相应专业审查，不能默认连接国外模型。多用途consent_records为未来规划；T08当前privacy_admission_records固定core_consultation且未成年私有关闭，正式主体/告知及法律适用性复核仍须落实，不能从姓名推断年龄，也不默认收身份证/护照。

`deletion_jobs` 记录请求者、数据范围、步骤状态、可重试错误和完成证明。受理时阻止新的相关写入，撤销会话/共享授权；有序清理画像、评估、计划/任务、附件、私有检索索引、缓存、幂等私有响应、导出工件、provider 留存和 outbox 敏感 payload。删除/留存清理凭受理时验证的专用系统授权继续执行，不依赖已撤销的用户会话；一般导出/通知/模型作业则取消或重新核验当前准入。公共招生事实不因一个学生删除账号而删除。最少审计保留使用不含画像的记录或去关联标识；必要保留的依据、范围、期限和访问者须在地区/隐私决策后确定，不能无期限保留全部原文。

备份是受控、加密、有限保留的恢复副本，删除不能只从在线库移除后宣称全链路完成。最新最小化删除/撤权台账及完整性水位独立于待恢复业务备份保存，按政策保护和保留；不能把旧备份中的墓碑当最新状态。恢复在隔离环境执行，先取得并核验最新台账、重放删除/撤权，再验证旧账号会话与私有资料不会重新暴露，才允许切换流量。必须测试“备份A之后发生删除B，再恢复A”的顺序；缺台账或水位落后则拒绝开放服务。告知需说明备份与台账处理期限及限制；具体期限和 RPO/RTO 属发布前待定运营要求。

对应每个能力任务执行：空 PostgreSQL 库迁移；现有 M0 库升级/数据映射且原文件与用户资料不覆盖；约束/索引检查；并发版本冲突与幂等重放；真实/合成、两用户/顾问/管理员权限矩阵；删除重试及恢复后的删除重放。Alembic 迁移冻结当时 schema，不能调用当前 ORM `create_all()`；破坏性迁移先备份和还原演练。SQLite 单测仅快速替身，不能替代上述 PostgreSQL 验收。

P00/P02规划轮只审阅源码、编写设计与隔离研究样本；上述公众拟增表、迁移、数据库权限、删除与恢复仍未实现/验收。T03只完成应用入口及模式隔离，不改变这些数据库待办。

## 10. 全国统计、培养与毕业结果拟增实体（P02）

详细字段以 [data_strategy](data_strategy.md) 为准；以下不是已创建表，按 T50–T58 增量迁移。仍复用 dataset/source/document/evidence/review/release 生命周期，不用一个任意 JSON 字段代替查询/约束。

| 拟增实体 | 核心范围 / 类型化列与关系 |
| --- | --- |
| regions / source_authorities / coverage_units | 地区、发布主体及子范围、路径；年度/届×类型×粒度；发现/读取/审核/发布数与失败，期望总量及其来源/版本可空 |
| academic_units / major_catalog_versions / program_code_crosswalks | 机构内学院层级、国家专业代码版本；省/年/组/招生专业代码→正式实体；有效范围、校区、匹配/审核状态及证据 |
| province_cutoffs | 地区、考试年、体系/科类、批次/段/轮次、路径、线种/原始标签、数值/单位/总分/加分定义 |
| score_distribution_rows | 同一考试范围、分数段、人数、累计方向/人数、同分规则与考生总体定义；不能推断未公布个人排序 |
| admission_observations / plan_quotas | 地区/年/批次/轮次/组/专业粒度；投档/终录取/均分/位次独立指标；计划/执行/录取/入学人数定义分开 |
| curriculum_versions / curriculum_modules | program/academic_unit FK、入学届、教学年、版本/学位/学制/校区；课程码、必选修、学分、学时、年/学期、先修/实践及证据 |
| outcome_reports / outcome_populations / outcome_metrics | 报告元数据；逐指标人群的毕业届、学位/学习方式、实际学校/学院/专业/学科粒度、调查窗口/时点/方法/样本/分母；去向/就业/升学/薪资、币种/周期/税前后 |

指标使用有精度限制的 NUMERIC 与 CHECK（如百分数0–100、人数非负、学分/学时非负），缺失为 NULL＋missing_reason，不能填0。原始标签、原始值和定义保留；解析歧义/小样本抑制不建立伪精确数值。薪资未核验周期、人群不匹配或专业统计缺失时禁止对应比较。

真实研究记录不直接导入：正式导入需原文快照真实 hash、完整范围、代码审核、使用权及人工审核记录。发布成员分别引用类型化实体版本并同一 dataset；每行具有粒度 CHECK/相应 FK，例如学科汇总不能填虚假的 program_id，专业组不能自动拆成全部专业。研究中的 local_institution_code/UCAS/provider/course code 未经 crosswalk 不作为 institutions PK。

新增业务唯一键覆盖 dataset、类型、全部规范化考试/人群范围、指标、来源版本与记录版本；NULL 语义、重导幂等和并发由 PostgreSQL 验证。冲突来源保留两个候选及冲突关系，不按平均或取最大覆盖。coverage_units 的分母无已核验名录/定义时为 NULL，禁止计算全量覆盖；研究数量与正式 published 数分开。

拟索引按地区/考试年/类型/科类/批次/组/项目、program/entry_cohort、population/metric_kind 与 release 可见性查询建立；学科到专业不做隐式 join。资格数据与统计只通过已审核显式关系连接，历史分数/就业不得回写规则。旧 0001_m0 与 DEMO 夹具冻结，现有七表与默认迁移头本轮不变。

## T34 发布影响独立迁移

新增 `ChangesBase` / `changes_alembic_version=0001_changes_t34`，保留十三旧head。三表 `change_event_receipts`、`assessment_change_impacts`、`plan_change_impacts`：分别event PK、event/assessment PK、event/plan_version/assessment PK，原release/dataset/year/mode与计划来源/owner关系FK；不允许UPDATE，未来专用受理删除可依FK顺序DELETE。

receipt仅存固定参考/字段/hash/事件审核引用与历史计数，JSON上限256KiB；每impact上限64KiB。receipt FK延迟到COMMIT以原子写fanout后receipt。新增 `ix_assessment_release_target` 与 `ix_plan_source_assessment` 原表索引只在新迁移创建，旧迁移字节不变。扫描传播无LIMIT，owner trace超过100条明确409。

显式 `CHANGES_DATABASE_URL` / `services/api/changes_alembic.ini`，应用启动不迁移。独立schema已验证down/up/immutable/FK/真实COMMIT回滚。T40须以最小删除台账协调私有impact清理与不可变历史计数，不可为了计数永久保留已受理删除对象。见[契约](changes.md)。

## T35 明确修订独立迁移

新增 `RevisionsBase` / `revisions_alembic_version=0001_revisions_t35`，保留十四旧head。`revision_proposals` 固定old/new owner/mode/source/proposal/state/request SHA与2MiB有界历史快照；`revision_decisions` 一revision一决定、version2及自然请求重放；`plan_replacement_links` 一old successor/一new predecessor，action='accept'参与复合FK，不允许拒绝产生关系。

三表拒UPDATE/允许未来受理DELETE，关系期限不超过原任一私有TTL与24个月；无新TTL续期。`REVISIONS_DATABASE_URL`显式迁移，启动不建表/seed。实际随机schema down/up只新head并保留旧十四，constraints/rollback已验；T40须先关系、决定、提案再执行/完成/计划，不能为FK永久保留私有对象。见[契约](plan_revisions.md)。

## T36 第16独立迁移head

`jobs_alembic_version=0001_jobs_t36`，五新表cleanup_permits/durable_jobs/job_attempts/notification_preferences/inbox_notifications；前十五head不改。permit和attempt为UPDATE-only不可变保护，inbox正文不可变，只允许明确read_version/read_at/read_request_sha256转换；实际删除治理仍待T40。durable job唯一natural_key与generation/token/lease/expiry，原T19pending outbox从不UPDATE。两用户并发领取、真实deferred COMMIT失败回滚与新进程租约恢复均有专用PG验收。

## T40 权利业务与独立最小台账

业务第17独立迁移链`rights_alembic_version=0001_rights_t40`新增rights_restore_watermark、privacy_rights_requests、privacy_rights_attempts、rights_erased_impact_counts、rights_backup_registrations五表；旧16头不改。outside-business-backup独立`rights_ledger_alembic_version=0001_ledger_t40`新增privacy_ledger_head、privacy_ledger_events两表。显式迁移配置分别rights_alembic.ini/rights_ledger_alembic.ini；不在startup创建/导入。

权利scope≤256KiB/5000行、lease与有限attempt SQL检查、受理授权不可变；完成删除只在completed同flush擦scope。台账事件UPDATE/DELETE拒绝，有限10000链+SHA及业务备份外HMAC锚点，不能用单纯不同连接当独立位置；实际namespace同库同schema拒绝。匿名擦除计数没有owner，live+erased维持T34原不可变回执。业务备份只明确business schema allowlist，恢复必须外台账最新证明+显式重放；物理35天备份清理/生产独立ACL与凭据仍待运维验收。

## BATCH-ZJ-2026-CUTOFF-01 新独立reference链

2026-10-13新增ReferenceCutoffsBase、reference_cutoffs_alembic.ini/head0001_ref_cutoffs及四表reference_cutoff_sources/batches/records/reviews（外加version表）。原17业务/独立ledger链与M0不改，新库reference_zj_2026独立于演示库。source真实BYTEA/hash/size+元数据；records typed line_kind/int value及闭合快照；batch完整3行/candidate→approved_local→withdrawn；reviews只追加并绑定人工作用/源/执行摘要。不可变触发器/unique/FK/deferred完整性、实际SELECT-only角色和只读事务均已本批验证。未新增全国统计PG全模型或T19公开发布，未知字段/null与权限范围见[说明](zhejiang_2026_cutoffs.md)。
