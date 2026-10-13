# T26 国内与英国本科范围适配

2026-10-03代码前冻结。基线PRIVATE T25 `3abed0cf4f3af77e337a06414247923d44c0940e`、506 tracked、工作区/索引空；当前仅T26，`codex/t26-admissions-scope-adapters`。T11/T19/T25已验收，治理、两份原始规格及相关目录、发布、画像、规则代码已读。ADR-034全国高考目标替代旧单省产品目标，旧M0不改。

## 数据契约

新 `rules/adapters` 是内部纯范围选择器，不输出四态，不验证学生身份/用途或代确认。可信调用方提供本人确认后的画像范围、具体项目引用及明确申请阶段；未来T28在当前事务重新验证owner、确认、发布和规则绑定。输入DTO或字段`reviewed=true`不能证明真实审核。

`ScopeRequest` 保留明确入学年、学段bachelor、所在地/课程/身份/生源省/路径五个独立ScopeKey；具体目标引用包含dataset/institution/program/offering UUID及机会版本、country，stage为application/enrollment。申请intake/application_cycle/channel/exam_system/subject_scope/batch_group须显式ScopeKey，画像没有这些字段，不能从省份、年份、所在地、成绩、选科或偏好猜值。可选原T23完整画像投影仅按需导入/重验；只投影范围，不向provider发送成绩、偏好、预算、owner或会话。

规则Bundle是受信服务器供应商交付的内部值，必须绑定具体dataset/release/requirements_version/ruleset_version、目标身份/机会版本、完整EvidenceScope、阶段及有界T25表达式和明确fact/evidence引用。完整scope/hash和规则版本不能用学校名字或事实快照hash代替。BindingVerifier端口独立重新验证实际发布、当前批准、证据/期限及表达式绑定；默认缺provider/verifier/规则集均unknown。默认端口无数据库、网络、时钟或模型I/O；本Task只测试明确合成供应商，不实现真实规则编译/人工审核存储。

现T19 ReleaseData和T20 PublicOfferingData的ruleset_version固定null、T17候选hard_rule=false；这些值必须返回RULESET_UNAVAILABLE，不能自动把历史分数、最低数字、典型offer或学校名字编成DSL。合成正例仅test环境且明确允许fixture、DEMO_引用及is_synthetic=true；formal/production不得接受它。真实规则准备开关本Task保持关闭，不把stub或provider自述当正式审核。Bundle冲突/撤回/替代/不一致或provider异常保守unknown，不能first-match任取。

范围选择输出selection_status=matched/unknown/unsupported及固定reason、有限版本引用；matched仅表示范围与当前受信绑定检查通过，绝不等于eligible或conditional。不暴露实际学生范围值、成绩或自由异常。课程/身份/路径明确不支持为unsupported，缺失或跨年/省/阶段/项目为unknown；unknown ScopeKey不是wildcard。

## 国内和英国语义

实现前复核修订：`TargetReference.scope_sha256` 必需，由受信调用方从确切读取的目标完整15维Scope计算；选择器在绑定验证之前要求与Bundle原始scope哈希完全相等。同program/offering引用但course/campus等scope不同必须拒绝，不能只依赖返回True的测试验证器。此哈希不是授权或审核凭据，也不能经省份别名归一化改写原证据。country仅接受CN/GB，其他值在DTO入口以422拒绝。

公开内部名称冻结为 `TargetReference`、`ScopeRequest`、最小 `BundleQuery`、`RuleBundle`、`AdapterPolicy`、`AdapterSelection`；函数 `scope_request_from_profile`、`canonical_province`、`select_rules`。ScopeRequest的六项额外ScopeKey是必需nullable，null保持未知；assessment_at明确aware UTC参考时刻，不能读取系统now。RuleBundle含bundle_id/reference_key、release_id/version、requirements_version/ruleset_version可空、scope及offering/version、stage、valid_from/until半开窗口、expression和唯一有界fact/evidence UUID序列。全部AST重新验证；provider只接受BundleQuery(target/entry_year/stage)，输出必须是至多32的原生list/tuple，拒无界generator。

AdapterPolicy默认enabled=false/allow_test_bundles=false，real_adapters_ready固定false，并明确运行环境/数据模式；真实路径本Task不可开启。verifier为服务器可信注入，只验证Bundle或最小query/Bundle，必须返回原生True才通过，缺失/错误/异常均未知；这不是执行恶意Python的沙箱，也不是客户端reviewed布尔。测试stub仅证明合成接口，未来真实provider/verifier须另有实际当前发布/规则审核证明。模块四文件schemas/scope/selector/__init__，非秘密scope配置显式加载不在import或启动读文件。

沿现T24界面31个Pascal省份代码作为内部canonical；配置逐项明确lowercase别名，InnerMongolia可单列inner_mongolia，不使用全局lower/trim、模糊缩写或同名转换。仅适配比较，不回写画像、哈希、证据或旧M0。Shanxi与Shaanxi分开，HK/MO/TW及兵团不静默映射为高考省份。31配置只表示输入识别与逐省框架，不表示某省/年度已有真实规则；2026参考与英国暂定2027分开。

唯一明确学段映射bachelor→undergraduate。国内country=CN/pathway=gaokao、普通高考课程及cn_mainland声明独立核对，生源省须已知且在配置登记，并与规则确切省份相等。英国country=GB/pathway=uk_undergraduate仍逐课程/身份/项目/年/阶段匹配，不凭剑桥/曼彻斯特名称生成通用要求；专业候选依据明确学生意愿，但目标必须由学生确认，不能由适配器自动选。

英国规则省份明确not_applicable时，学生省份可为已知、未知或明确不适用，不机械冲突；若规则明确限定生源省，必须按配置精确匹配，规则省份unknown仍unknown。此范围选择不证明高考分数口径或满分已核验。其他维度not_applicable只与明确声明同维度不适用匹配，不是通用wildcard。科类/组合由显式声明与受信绑定约束；subjects空或自由标识不能自动生成科类。Program.course不等于学生course_system，progression_pathway不等于申请pathway。

## 修改范围与测试

只新增rules/adapters纯schema/config/选择与可替换端口、非秘密config/scopes文件及unit矩阵；root同步七份治理文档、ADR-039、冻结契约和独立验收。无HTTP/API生成、DB/迁移、UI、依赖、旧M0或历史规则变更；T27后补/T28四态不提前实现。

1. 31登记唯一及全部旧UI代码/明确别名、山西陕西、未知大小写/兵团/港澳台及碰撞拒绝。
2. 国内省/年、英国省NA或限定、所在地与身份独立、课程/学段/路径/渠道/周期/科类/阶段矩阵；缺失不推断。
3. 同名不同program/course/campus/offering版本及dataset/release/hash拒绝混用；本人目标引用由可信调用方提供，不由偏好推断。
4. 缺规则集/缺验证器、未审/过期/撤回/替代/冲突、全量有界输入重验、构造绕过、坏表达式/跨模式、provider异常；matched不含四态。
5. 新pure unit、T25/T11/T23和契约模式回归、六生成profile/原文/M0/范围历史保护，现有前端测试、Type Check和demo/auth Build。Lint/Python静态类型无入口明确未执行；无持久或页面变化不重复PG/browser，真实事实领域审核/身份/学生/法律/部署未执行。

实际结果见[T26验收](acceptance/T26_scope_adapters.md)。成功、文档同步及PRIVATE保存核对后才单独T27；批次到T40停止。
