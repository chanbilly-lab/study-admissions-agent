# T32 计划确认与进度

2026-10-04实施前冻结；T31 PRIVATE b6d9ab3/594tracked/空索引工作区。仅T32 HTTP与本地持久状态、离线/合成PG验收，不UI/修订/发布影响/worker/模型/外部申请；验收及PRIVATE保存后才T33，本批T40后停止。正式处理及未成年私有关闭。

## 数据契约与状态

复用T30 PlansService及T31纯排程，新app/plan_execution/和独立ExecutionBase/execution_alembic_version/0001_execution_t32。四表最小head、不可变proposal、不可变confirmation、不可变task_completion，复合FK绑定同plan/T30精确source version及owner/模式/依赖task身份。head仅投影state_version/current proposal/confirmation可CAS变化；三个历史表UPDATE拒绝，后续可信DELETE保留。T30五表/旧迁移/AuthOwnedResource.version全部保持原值；state_version是本Task独立序号，不能用registry touch破坏T30一致性。

初始state_version=1/state=draft，create使用既有PlanCreateInput、服务端时钟/owner/当前确认画像与≤4源评估，先生成有界preview再同TX原T30草案与新head/proposal。新包装公开创建source JSON预算≤384KiB（旧T30存储上限512KiB不改）；新proposal input/schedule总JSON预算≤1MiB，源/快照超新预算在写入前422，不裁证据或扩大旧cap。既有T30内部极端组合503问题保留。startup不建表/seed，显式迁移先要求原十二head。

预确认workspace编辑是新的proposal，expected_version严格正整数，≤100唯一task_key估时override（0..1000小时6位严格十进制或null）只能改原任务估时；server从不可变T30源克隆/重hash，不接受新标题/动作/来源/成绩/规则/owner。提供nullable完整schedule配置（horizon UTC/start/end、IANA display_timezone、0..40/null weekly_hours、≤256slots、≤100 internal goals、availability_confirmed/rest_excluded真值），或显式null清空排程；不能把availability确认当计划确认。确认后不编辑，此Task不重新确认/替代/重置完成任务，T35才修订。

confirm要求expected_version、expected_draft_sha256、expected_schedule_sha256、confirmed=true及acknowledge_unverified_deadlines=true，服务端按最新proposal/input与fresh完整source重新计算T31，容量ready/weekly_hours已知才确认。T31 constraints_complete始终false，官方日期精度/候选UTC不升级，本人仅确认自己的准备安排及已知未知，不表示学校期限核定/资格达标。fresh source ref必须等原保存projection；旧current来源变withdrawn/replaced/needs_review或画像新版本拒409；新生成的history/unavailable核验草案只允许该来源对应VERIFY_HISTORY/VERIFY_UNKNOWN，并可明确确认核验安排，无源自主学习独立。撤回原用途再同意不能复活旧计划。

唯一confirm接受T49 plan.confirm与opaque Idempotency-Key：receipt只有(plan_id,confirmed_state_version)，原请求hash绑定plan及两SHA。领取receipt在domain锁前；verify当前same confirmation/proposal/source/原用途/owner/时效，重复只原确认一条且查询当下进度，不发送旧缓存私有响应或拿receipt版本改head CAS。不同payload409；过期receipt不再次确认已确认状态。

complete仅confirmed=true+expected_version，服务端本人自报完成当前确认任务，所有依赖已完成才允许。独立自然幂等为(confirmation_id,task_key)唯一及精确规范请求hash（含plan/task/原expected_version/真值）；原相同请求可查当前状态并replayed=true且只一条完成，其他旧CAS/不同请求/未确认/非法任务409或404。完成不更新成绩、资格或学校执行结果；0工时也不自动完成。没有新T49 operation，进度不借plan.confirm。历史GET按state_version重建当时proposal/confirmation/≤该序号完成集合，原不可变行保持；当前源失效时保守拒行动与私有内容读取，后续T34/T35另验历史核验视图，不回退旧许可。

## API与权限

显式create_plans_v2_app/create_plans_app继承assessments，新增8操作/7paths：GET /plans/context；GET/POST /plans；GET /plans/{plan_id}；GET /plans/{plan_id}/versions/{state_version}；POST /plans/{plan_id}/workspace；POST /plans/{plan_id}/confirm；POST /plans/{plan_id}/tasks/{task_key}/complete。workspace用POST追加不可变提案，沿现get/post契约，不新增PUT。只confirm接Idempotency-Key，其它写拒该头；没有客户端owner/source/clock/ScheduleDraft。time wire仅闭合字段显式UTC ISO Z或+00:00转原生UTC；不放宽T31 pure输入。

所有私有路由当前Cookie/本人student/core/原notice与对象owner/active验证；写Origin/CSRF，metadata grant或admin不授私有写。重复query/JSONkey、float估时/坏UUID/坏64hex/额外proof字段拒；JSON UTF8 stream≤64KiB，错误固定且no-store/no-cache/no-referrer，日志无key/payload。context需要当前身份；无identity service默认503，基础config仍无密钥可读；已配置identity但业务关闭可返回明确capability=false，不将匿名context200当承诺。

默认factory无DB/供应商/DDL/文件IO；只显式同Auth/Engine/Clock的合成test服务可启用，real_execution_ready=false不改变公众门槛。新plans OpenAPI/TS profile，旧七生成产物原字节保持，无前端页面/新依赖。

## 事务、修改范围与验收

身份/角色/用途/源及新增全部mapper先校same active Session/Engine再IO；自己事务COMMIT成功后返回，callerTX不能隐藏commit，任何异常使外层整TXabort，不能catch后提交前置用户改动。每次write与required audit后重读所有源/current profile/原purpose/发布/原文件，最后Profile._final权威SQL之后取得single fresh now，以本地值同核head/proposal/确认/完成created_at下界、所有TTL、T49receipt expiry、规则/policy/main/supp日期与会话/角色/告知。T49返回后再最终核，不能将callback bool或先前授权当最终证明。

允许十一旧路径（九治理、generator与新契约LF所需.gitattributes），583其他tracked包括原文/docs01–05/M0/旧迁移/旧七工件/所有既有应用与测试保护；只新增domain/router/factory/增量链/新contracts/Unit与PG/文档。所属newHTTP和domain schema由代理分别写，避免共享写文件；根同步文档/Git。

验收明确create/edit/history/confirm/repeat/progress/依赖与CAS；两owner/admin/已接受metadata grant不越权；源/profile/用途/TTL变化阻旧动作；同key/同task两Session真实竞争、最终SQL/audit锁等待跨file/session/receipt期限、mandatory audit/deferredCOMMIT/caller失败整TXrollback、错mapper零连接、immutable/check/FK/显式migration往返及旧十二heads保持。新的随机execution_t32_UUID合成专库schema，case身份/clock隔离，不触用户schema。离线unit/schema/相关回归、前端Unit/Type Check/demo-auth Build、八生成profile/原文/M0/范围/历史/实际暂存/PRIVATESHA；无配置Lint/Python静态未执行，真实身份/招生/法律/SQL GRANT/RLS/部署/生产恢复未执行。

2026-10-04源码及合成隔离验收完成，实际命令/失败/未执行见[验收](acceptance/T32_plan_execution.md)。真实处理关闭，容量提案不表示官方期限已核定。

2026-10-04范围补充：只读发现新plans工件未有checkout LF规则，实施前将.gitattributes追加两条plans text/eol=lf列入当前必要范围；原所有属性保持，583其他tracked保护。首次确认采用最终fresh now核排程时点，过去容量提案409；已确认读取/重放/完成按原确认时刻校验安排，不因时段已经过而丢历史。
