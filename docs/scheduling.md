# T31 工时容量与依赖排程

2026-10-04实施前冻结；T30 PRIVATE 9d70b9a，586 tracked/索引工作区空。仅本Task纯函数与离线验收，无HTTP/数据库迁移/持久排程/确认/UI/worker/模型，不修改T30草案或旧迁移。验收及PRIVATE保存后才T32，本批T40后停止。

## 数据契约

新app/plans/schedule_schemas.py及scheduler.py复用现Pydantic/受限十进制/严格原始DTO。schedule_plan只接精确PlanDraft与服务端重新读取的≤4个AssessmentData，重验原SHA、当前有效性及完整来源投影、同profile/version/hash/模式；显式generated_at和UTC horizon_start/end，不读取环境/系统时钟/外网/DB。生成时刻必须位于原草案及各源保留期，horizon从生成时刻或之后开始，结束≤最短源TTL且≤84天；fresh来源有效性必须等原引用，变成needs_review/replaced/withdrawn拒绝旧行动排程，先要求新核验草案；新历史草案该来源只允许VERIFY_HISTORY，unavailable只VERIFY_UNKNOWN，混合其他当前来源独立保留。无评估引用的本人自主SELF_DIRECTED_STUDY可独立排，不升级资格。

ScheduleInput要求availability_confirmed=true及rest_excluded=true（本人明确排除休息时段的开发输入，不冒称后端已完成身份确认）；weekly_hours严格0..40小时、至多6位小数或null。null返回CAPACITY_REQUIRED，不补默认；0不安排正工时。明确IANA display_timezone，≤256个唯一ID、不重叠、显式UTC可用时段，单段≤8实际小时、总≤520小时，完整位于horizon内；这些是计算预算，不是健康建议。纯函数时间输入只接受原生datetime和原生timezone的零偏移UTC、fold=0，不开放HTTP字符串；未适配时区/naive/自定义tzinfo与ZoneInfo本地wall输入拒绝，DST含义不猜测；显示指定IANA。

按display_timezone当地周一00:00分周，跨周时段分开计容量；时长一律UTC elapsed整数微秒，6位十进制小时×3600000000精确，不float/截短小工作。每周实际分配≤确认工时且只在明确slots内。不扩时段、不缩估时、不压缩休息、不保证学习或录取效果。

沿T30 task_key和DAG稳定拓扑排程，ready项优先明确内部目标、核验类别及task_key；共享task_key只计一次，目标条件/来源refs不丢。正工时任务可分片跨slot，所有依赖完整完成后第一片才开始。每个任务使用临时容量试排，全工时放不下时该任务不占任何容量并报告完整未分配量，后继DEPENDENCY_BLOCKED，独立任务仍可得到partial。null估时ESTIMATE_REQUIRED并阻断后继；明确0为不占容量的里程碑，取horizon_start或依赖结束的较晚时刻，必须在horizon内及内部目标之前。最多4096 allocations，超预算固定拒绝。非法环/缺依赖经递归重验固定INVALID_SCHEDULE_INPUT，不修改T30 schema使其接受环。

InternalGoal为学生明确task_key及UTC due_at的内部目标，≤100、唯一、位于有效horizon内；finish恰等due_at视为目标冲突，不混入官方期限。所有原PlanDeadlineRef及其精度/local/timezone/候选UTC原样保留；T12当前官方utc_instant恒null，不能由reviewed=true或候选推成硬期限。本Task以DEADLINE_UNRESOLVED报告未确认学校期限，constraints_complete=false；补交取得实得任务只关联supplement用途，其他任务保留自己的application/supplement来源且不自动取最小值。date-only不补23:59。没有官方精确时刻正例可执行，不宣称已通过官方硬期限排程；T32及后续需可信证据接口。

ScheduleDraft绑定原draft_sha256、全部assessment/deadline refs、每任务估时/已排及剩余微秒、依赖/适用期限keys、分片和固定conflicts/options，status=ready/partial/blocked只是容量提案状态；confirmed=false，constraints_complete独立；ready不等于计划确认、当前资格或可申请。算法有界确定性贪心，不声称全局不可行/最优；失败选项仅减少明确目标、本人改估时/时段或周期/核验期限，不自动修改原事实。输出有独立SHA，原PlanDraft的draft/confirmed=false/scheduled=false与SHA保持。

## 修改范围与验收

仅新两纯模块及tests/unit/scheduling/，本契约/验收/ADR044和七治理文档允许改。579其他tracked包括两原文/docs01–05/M0/所有旧源码/迁移/前端/API/DB/依赖保护。

容量恰好/少1微小时/0/null、周界/DST UTC工时、依赖循环/非法构造、依赖完成/分片/共享去重、未知估时阻后继/独立partial、全部排不下与原量保留、日期精度/主补引用/内部目标边界、源投影/模式/TTL/SHA/无IO均用明确金标准测试。运行相关旧纯回归、完整前端Unit/Type Check/demo-auth Build、七契约生成/原文/M0/保护范围和实际暂存PRIVATE保存。无DB变化不跑PG迁移；无Lint/Python静态入口标未执行，真实身份/招生/法律/SQL权限/部署未执行。

2026-10-04实现及合成离线验收完成，实际命令/失败/未执行见[验收](acceptance/T31_scheduling.md)。当前官方UTC未核定，constraints_complete恒false；ready只表示全部任务的容量提案可安排。
