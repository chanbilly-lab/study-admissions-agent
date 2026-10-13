# T27 后补政策与独立期限

2026-10-03实施前冻结。PRIVATE T26 `a58a99306568f91c9aa0f8ac428e7d39a48024be` 已上传SHAclean；517tracked/空索引工作区，当前只T27、`codex/t27-reviewed-deferrals`。治理、两原规格、T12/T16/T25/T26与相关API/数据库已核；旧层与历史记录不改。

## 内部数据契约

新增单模块 `rules/deferral.py`，复用严格CatalogModel、T25 AssessmentKey/explicit_instant与T26 TargetReference/raw scope hash。公开名 `DeferralRequest`、`DeadlineBinding`、`DeferralBundle`、`DeferralPolicy`、`DeferralQuery`、`DeferralResult`、`DeferralInputError`及 `evaluate_deferral`。不是HTTP/四态/权限接口；可信调用方先验证本人确认画像、T26范围/完整规则绑定，并仅提交实际必需的未决实得成绩事项。T28服务重新计算此必要性，不能把not、未选any分支、预测、单位/满分冲突冒充缺成绩。

DeferralRequest含target、entry_year、stage、release_id/release_version、必需非空requirements_version及可空ruleset_version、assessment_key、basis=achieved/predicted、missing_state=known/missing/pending/not_applicable/conflicted、显式assessment_at aware UTC。无成绩、偏好、owner/session或任意字段路径。只有basis=achieved、missing/pending且政策明确允许相应状态才可获得后补许可；known/预测/不适用/冲突未知，不把已失败成绩自动改为缺失。无规则集也未知。

DeferralBundle含bundle_id/reference_key、policy_id/policy_version（64位原始哈希）、release_id/version、requirements_version/ruleset_version、is_synthetic、完整EvidenceScope及scope_sha256、offering_id/version、stage、非空唯一有界assessment_keys与allowed_missing_states、半开有效窗口valid_from/until、policy_evidence_ids、application_deadline_required严格bool、application_deadline与supplement_deadline两项必需nullable。对应目标/hash/版本/年/阶段必须精确相等；unknown scope不是wildcard。政策/证据哈希与审核不是客户端自报reviewed布尔能证明的。

DeadlineBinding含完整T12 DateEventData及唯一有界evidence_ids、必需nullable reference_calendar。T12仍draft/unresolved/utc_instant=null，unique calculated UTC本身不代表审核；独立受信verifier必须证明当前政策、两期限/日历/原文证据与所选release/ruleset的确切绑定。事件dataset/offering/version/year与Bundle精确一致；application期限须application_deadline，补交IELTS事项仅language_supplement、其他已支持成绩仅score_supplement。materials_deadline/equal_consideration/offer等不能替代。

application阶段必须明确application_deadline_required=true，缺申请或补交期限均未知，未来补交不能越过已过/未知申请窗口。enrollment阶段政策可明确申请期限不再适用（required=false且application_deadline=null），结果单列not_applicable；这是该阶段已审政策的显式声明，不能从当前日期推断。若政策仍明确required=true则独立检查。补交期限所有阶段均必要，不能复用申请期限。

`evaluate_deferral(request, *, bundles=None, policy=None, verifier=None)` 接受最多32原生list/tuple，不迭代generator；整组重验后过滤确切目标/年/阶段/事项，同组失效、撤回/不明绑定或不同版本冲突不能first-match。DeferralQuery只给target/year/stage与上述发布版本/事项key/basis，不给missing_state或实际私有值。verifier(query,bundle)必须原生True，并在所有回调后重验原始query/bundle/policy快照；异常仅固定reason，不能暴露输入或内部路径。

DeferralPolicy默认enabled/allow_test_bundles=false、real_deferrals_ready固定false；明确test+demo才可允许DEMO_且is_synthetic=true正例。正式ready/政策编译与审核存储本Task未实现，不把stub当审核。Result为deferral_status=allowed/unknown、固定reason、application_deadline_status及supplement_deadline_status、最小政策/证据/事件引用；allowed只是这一必需事项有有效后补路径，不等于项目conditional/eligible，不代提交申请。

## 日期与安全边界

模型落盘前具体shape补充：DeadlineBinding的T12值字段名为`date_event`。Result固定`deferral_status/reason/application_deadline_status/supplement_deadline_status/bundle_id/policy_id/policy_version/application_deadline_event_id/supplement_deadline_event_id/evidence_ids`；allowed主期限须before或政策明确not_applicable、补期限须before。未知不保留selected refs；evidence_ids合并三组唯一引用、最多96。DeferralQuery不含missing_state或assessment_at；纯函数只用显式request时刻，当前实际发布/许可由可信调用方事务证明。固定reason是受限代码而非原文异常。

reference_calendar须是受信绑定的明确IANA地区键/UTC，复用T12锁定tzdata2026.4；按request.assessment_at转换来源当地日，不读服务器today/now、不接收另一份可冲突的客户端reference_date。仅日期时：来源当地日<截止日为before、等于整天unknown、>截止日expired，但后补结果仍unknown；缺日历、原文conflict/未知精度未知。不得补00:00/23:59或截止UTC瞬时。

minute/second只在独立证明通过、T12转换唯一且时区信息充分时比较显式UTC；reference_calendar与该事件timezone须一致。严格早于为before，晚于expired；精确相等保守unknown，未审核的包含/排除语义不推断。DST gap/fold、未知时区、范围溢出/缺时区或冲突均unknown。政策有效窗口按明确内部契约半开[start,end)，与学校截止语义分开。

在进入旧T12 validator前验证native date/time/datetime及timezone类型，以T25安全instant守卫阻止custom tzinfo回调；copy/model_construct/extra/布尔版本/坏哈希/无界refs全重验。不改旧T12，也不伪造官方UTC。import不读取配置/数据库/网络/模型/系统时钟；明确调用日期换算可读取锁定tzdata包资源，不能访问招生网址或用户文件。

## 修改范围与可测试验收

只新增deferral模块、两实现者及两独立unit文件；root同步七治理文档、ADR040、本契约与验收。无旧app/适配器、HTTP/API生成、DB/迁移/UI/依赖/M0修改；T28四态另做。

1. 必需缺成绩无政策/规则集/证据/期限、未审、错目标/15scope/年/阶段/事项/版本、过期/冲突均unknown；预测/冲突/已达不获通用许可。
2. 申请与补交独立；事件类型不替代，enrollment明确不适用申请与application强制需要分开。
3. 来源日历跨UTC日/服务器日、date-only前/当天/后、未知日历、明确时刻前/等于/后、DST间隙/重叠/精度/换算冲突。
4. 当前组坏成员/不同版本正反序、缺端口/False/非bool/异常、第二项坏DTO、copy/construct/refs预算、回调修改前项、无私有query/异常/自定义tzinfo执行。
5. 新纯专项、T12/T16/T25/T26及模式契约回归、六生成profile/原文/M0/范围保护、前端Test/Type Check/demo-auth Build。Lint/Python静态类型无入口未执行；纯模块无持久/页面变化不重复PG/browser。真实学生/政策领域审核/法律/生产权限/清理恢复/部署未执行。

实际检查见[T27验收](acceptance/T27_deferrals.md)。验收/文档/PRIVATE保存核对后才单独T28，完成T40后停止。
