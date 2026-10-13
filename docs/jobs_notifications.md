# T36 持久作业与站内提醒契约

2026-10-04代码前冻结，现源码与合成隔离验收完成；仅本Task，真实处理关闭。无Redis、新依赖、网络供应商、邮件或SMS。旧T19 pending outbox及十五迁移head保持，后台处理不改变原资格/计划/完成；本批T40停止。

## 数据契约

独立jobs/notifications模块、五新表与第16增量head：durable_jobs、job_attempts、cleanup_permits、notification_preferences、inbox_notifications。Job仅闭集release-impact、notification及未来export/model/cleanup的有限接口，UUID/natural_key/有界引用、queued/running/completed/cancelled/failed、attempt、available_at、expires_at及generation/随机lease_token/lease_until。不能传任意SQL、Shell、URL、handler或学生事实。原event唯一生成release-impact job；只凭持久已提交event调用T34 process_event(session=同事务)，不借历史发布管理员会话、不捏学生Principal。当前事件过期不阻断精确旧影响计算。影响仅fanout明确opt-in owner/profile元数据的独立notification子任务；无偏好不创建私人提醒，默认off。

claim短事务用FOR UPDATE SKIP LOCKED，实际COMMIT后执行另事务。generation/token fencing；执行effect、attempt、ack同事务完成；租约到期可重领，旧token不得写。固定重试上限/有界退避/有限错误码持久，崩溃无ack按lease恢复。去重用事件及精确owner/profile/purpose自然键，不靠Web BackgroundTasks；原outbox不UPDATE。关闭/错误配置先于连接和读写拒绝；worker显式构造/单步或有限循环，不启动自动迁移或seed。

偏好owner唯一CAS，enabled默认为false；开启必须本人明确student_confirmed=true和显式当前profile_id，由服务器保存当前ExecutionReference及原profile版本/hash、notice/consent/declared proof、开启偏好revision。客户端不能提供owner/session/授权判断。GET可独立于旧T32当前来源读取合法有限提醒，不要求选择计划；POST disable在当前有效本人/core下无需selectedProfile。每notification以及未来export/model的用户作业执行都复用AuthStore.locked_principal真实DB行，核active student/session、原purpose/notice/consent/profile current/version/registry notdeleted、偏好开启版本及私有TTL；logout、原用途撤回/再同意、画像更换、对象删除均取消，不能授权时禁止私有effect。最后必需SQL之后同一个fresh now核所有身份/私有/lease/job期限，迟到等待不复用claim时刻。接收owner由数据库得出，不使用发布者身份或caller Principal DTO作为长期权限。

通知保存固定reason及event/assessment/entry_year等有限引用；精确相关计划仍由T34原trace另读，无成绩、quote、自由URL或模型文字。event+owner+assessment+精确profile/purpose去重；固定needs_review只表示原依据变化，不表示eligible或录取。正文不可变；read_at/read_version本人CAS，自然精确重试仍重验权限。通知读取必须核原profile/purpose/TTL；失效清空/拒绝，不因再同意恢复历史私有处理。

cleanup_permits由受信服务在当前本人核验事务受理，owner派生，精确registry resource IDs/type/version/status/mode及整个scope_sha256、acceptance/watermark/expiry/audit，不可变；worker只引用permit ID，固定handler registry，重验持久scope/完整性/当前删除水位，不能扩大ID/owner/epoch/mode。已受理删除/留存能力不依赖原session/core继续存活。T36仅合成受信probe证明logout后仍运行，不删除旧学生数据、不开放删除API；T40接实际删除与独立台账。没有受信受理或处理器必须关闭，self-consistent frozen DTO/hash不代表授权。export/model seam关闭并有限取消/失败，不假装功能已实现。日期型提醒不做猜测或自动填23:59，本Task仅发布影响提醒。

HTTP独立notifications factory继承revisions，默认关闭零IO、real_notifications_ready恒false，test仅显式合成。5operations：GET /notifications/context；GET/POST /notifications/preferences；GET /notifications (limit<=20/cursor有界)；POST /notifications/{notification_id}/read。Preference输入expected_version>=0、enabled严格bool、profile_id UUID|null、student_confirmed严格true；read输入expected_version>=1/student_confirmed=true。固定Cookie/CSRF/Origin、no-store/严格有界JSON及query/有限错误、最小审计。无新增T49action或私有idempotency response副本。第10有限生成profile，旧9profile字节保持。

## 修改范围

新app/jobs、app/notifications、services/api/worker.py、新api/notifications factory、jobs_migrations/env/version与ini、新pure/实际PG/HTTP专项。旧仅八治理/数据库/API等九文档、.gitattributes、scripts/generate_contracts.py、PlanView.vue最小子组件接缝；新features/plans/notifications client/validator/controller/panel及Vitest。默认折叠零fetch、显式刷新/开启/关闭/已读，无轮询/push。actor/core/profileEpoch立即abort及清空，无selectedProfile也可读合法有限提醒；旧T32 source409不放宽。服务端确认后才更新偏好/已读，409要求明确重读，无自动重写。私人迟到200/写200/坏200不能跨actor/core/epoch复活。

## 可测试验收

1. pure严格schema/模式/budget/固定引用与fencing/不捏Principal/closed零IO；有限cleanup能力抗伪造/扩scope，UTC精度未知保留。
2. 实际PG正常发布→持久处理→opt-in本人提醒→重复去重/readCAS；旧outbox/确认/完成保持；新迁移重复/downup保留15旧head。
3. 两真实consumer、崩溃重启、租约过期/旧generation、audit与真实deferred COMMIT失败原子回滚，重试/backoff/failure；currentsession/purpose/profile/删除撤权与最后SQL等待后到期取消。
4. 已受理合成cleanup probe退出仍完成；错owner/ID扩张/水位回退/mode/无受理源关闭。真实export/model/deletion未实现明确关闭。
5. 真实HTTP owner/admin/metadata grant/CSRF/Origin/no-store/body/query；新meaningfulUI与全前端Tests/TypeCheck/demo-authBuild；相关Python/contract/10profile/原文保护与文档同步。无Lint/Python静态入口注明未执行；正式处理/模型/法律/SQL权限/部署/生产恢复未执行。

结果见[验收](acceptance/T36_jobs_notifications.md)。

## 冻结wire明细

NotificationContextData：schema_version=v2.t36、can_read/can_manage_preferences/can_mark_read严格bool、is_synthetic严格bool、delivery_channel=in_app、external_delivery_enabled严格false。PreferenceData：version>=0/enabled、profile_id/profile_version_id/profile_sha256可null、is_synthetic、updated_at可null；缺省v0/off/null。NotificationData：UUID id/event_id/assessment_id/profile_id/profile_version_id/dataset_id/offering_id，profile_sha256，version>=1/offering_version>=1/entry_year1..9999，is_synthetic、固定T34 reason/needs_review、before_release_id/after_release_id可null、created_at/expires_at UTC/read_at可null。Page：最多20items/有界next_cursor或null；无planID数组/quote/成绩。

偏好 DTO 的 enabled 表示当前有效开启。原会话、画像或用途绑定失效时，在当前本人/core仍合法的前提下仅返回关闭态及持久 CAS version/updated_at，三个 profile 引用为空；不自动 UPDATE 偏好、不将旧同意换成新授权。重新开启或关闭仍须本人明确确认当前 CAS。损坏的 hash/归属/持久证明不能吞成关闭态。站内列表只分页当前可读原用途的有限记录；旧用途撤回后不展示旧通知或其数量/游标，重新同意不复活旧通知，也不阻挡新授权下合法提醒。明确读取旧 notification ID 仍重验原用途并拒绝。

T36 CleanupResource 仅登记资源 ID/type/registry version/status/mode；scope_sha256绑定整个有限registry清单，不声称逐附件原文字节SHA核验或真实文件删除。T40实际处理器须另核对象/附件定位和当前水位，不以本probe验收替代删除覆盖。
