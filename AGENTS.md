# 项目开发约束

2026-10-14 PRIVACY-PUBLISH-01已完成源码公开：用户明确选择保留私有历史、公开同名干净版本。新公开库study-admissions-agent（ID1418914840），默认分支codex/privacy-release，公开工作目录D:/Projects/study-public；原ID1400234431改名study-admissions-agent-private-archive，保持PRIVATE并只读归档。原D:/Projects/study和原镜像origin已指向备份，原文件／历史保留。只从干净副本用GitHub noreply创建公开提交，不合并／推入旧私有历史，不强推；后续正常Task仍按持续授权普通保存。原“源码必须私有”规则为历史，已被本次源码公开授权替代；真实业务／模型／部署门槛及不用应用测试的要求保持。初始公开CI运行0，全部应用／迁移／锁／契约／夹具字节保留。见docs/source_publication.md。

2026-10-14 SEARCH-SELECT-01源码完成：学校/专业显式搜索与级联选择替代手填UUID，身份来自当前正式T20发布证明，默认目录None空缺口；前端仅用所选真实UUID/ref、父子/水位/取消/generation及本地上下文pin，学院学科未适配禁用。无研究/DEMO补项、无新表/迁移/旧generated/M0改变；培养/毕业数据仍空。所有测试/Lint/TypeCheck/Build/import/SQL/HTTP/浏览器/校验/服务重启未执行（用户要求），未装配真实目录。见docs/school_program_search.md；27文件文档同步/PRIVATE保存后停止。

2026-10-13 UI-OPT-01展示源码完成：共享青绿主题/字号/焦点与主要44px控件、M0四步提示/筛选外选择/缺失措辞/证据焦点、参考分组筛选/省线卡片/渐进原文与hash/诚实空缺；只8前端文件及相关文档，原客户端/controllers/API/DB/数据/权限/四态不改。所有测试/Lint/TypeCheck/Build/浏览器/视觉校验均未执行（用户要求），旧截图不算新通过证据。见docs/ui_optimization.md及acceptance/UI_OPT_01.md；文档同步与PRIVATE保存后停止。

2026-10-13 SCHEDULE-ANNUAL-01源码完成：用户确认每年11月1日09:00 Asia/Shanghai仅生成待采集/待审核请求，并再次要求不测试、同步文档后PRIVATE上传。新增默认关闭纯planner/维护CLI、独立PG两表及新head；年度去重/最近周期补偿/配置冲突/有界重试，网络/事实更新/发布恒false。所有测试/Lint/TypeCheck/Build/import/校验/迁移/worker运行未执行，未创建新库或启动定时任务；旧M0/浙江/私有jobs/连接器不改。见docs/annual_source_updates.md；保存核对后本批停止。

2026-10-13 BATCH-UK-2027-INSTITUTIONS-01完成有限研究登记：用户确认剑桥/曼彻斯特、2027本科，具体专业未选；8指定官方页原HTML实际200/bytes/hash，正式审核0/发布0。只data/research候选及来源/日期例外/缺项说明，不接正式DB/API/页面/资格；公开或商业复用许可未建立，原文仅.cache。采集操作不是应用测试，原不用测试保留；九文件PRIVATE保存后本批停止。见docs/uk_2027_sources.md。

2026-10-13新授权BATCH-ZJ-2026-CUTOFF-01完成：用户选浙江并确认普通类494/266/594三条本地参考。官方原HTML取得/真hash、独立PG四表与源/批次/人工链、SELECT-only API8004及页面5174已实际走通；8专项PG/HTTP+8实际Edge检查通过。仅此本地批次，真实学生/公众发布/其他省年关闭；原M0和旧迁移/十二契约保持。其他全回归/Lint/Build仍未恢复。见docs/zhejiang_2026_cutoffs.md。

2026-10-13用户明确实际启动M0并验证核心流程：E02已完成，本机PG16.15专用新合成库/DEMO seed、API8000和Vue5173正在运行；真实Edge8项检查通过、page_errors=[]。只恢复这次有限检查，旧不用测试仍适用其他未授权回归/Build；真实资料/生产关闭，T67停止边界保持。详见docs/demo_startup_20261013.md。

2026-10-13 T67最小源码完成：单批候选审核清单和缺项阻挡判定；完成本批后停止；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：真实单批导入/原文/许可/独立审核/发布与撤回均未完成；原规划PG/运营/质量门槛保留，本批未执行任何检查。PRIVATE保存后本批停止于T67，不自动继续。

2026-10-12 T66最小源码完成：默认禁用的固定来源连接器请求契约；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：未选实际来源/许可，DNS/重定向SSRF防护与实际获取/重试/作业未实现，live恒关闭。PRIVATE保存后继续至T67。

2026-10-12 T65最小源码完成：可达的毕业届、统计层级和指标缺口页面；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：仅空结果/局限说明，无真实指标展示或页面测试/类型/Build验证。PRIVATE保存后继续至T67。

2026-10-12 T64最小源码完成：可达培养入学届查询与当届缺口页面；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：当前只空培养查询，未展示真实版本/课程/证据或执行界面/类型/Build检查。PRIVATE保存后继续至T67。

2026-10-12 T63最小源码完成：可达的全国统计只读查询页和有界空数据客户端；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：无真实数据可展示或页面交互/类型/Build验证；目前仅空查询，未接生产部署。PRIVATE保存后继续至T67。

2026-10-12 T62最小源码完成：按请求层级、毕业届和对象的空结果查询；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：没有真实结果reader/上级汇总或PG发布查询，items为空，不提供实际就业结论。PRIVATE保存后继续至T67。

2026-10-12 T61最小源码完成：明确专业UUID与入学届的空培养方案查询；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：无正式培养reader/真实方案或PG，API仅明确当届缺口，所有HTTP/TS/构建未验证。PRIVATE保存后继续至T67。

2026-10-12 T60最小源码完成：分布、历史录取与指定记录比较的空查询接口；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：无正式统计reader/数据库分页或可读取发布记录；比较接口只返回未启用缺口，不执行虚假比较。PRIVATE保存后继续至T67。

2026-10-12 T59最小源码完成：独立默认空数据的省线与覆盖只读API及TS契约；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：API只是未启用资料的空响应；无正式published reader/PG/撤回查询或运行契约验证，生产工厂不装配此入口。PRIVATE保存后继续至T67。

2026-10-12 T58最小源码完成：统计和毕业指标的确定性四类可比性检查；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：仅纯定义比较，不证明已审数据/发布；没有排名、预测收入或隐式币种换算。PRIVATE保存后继续至T67。

2026-10-12 T57最小源码完成：逐指标毕业人群、观察窗口、分母与薪资定义候选；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：无真实毕业结果/PG/审核发布；指标样本、分母、周期未知保留，不将落实率当就业率。PRIVATE保存后继续至T67。

2026-10-12 T56最小源码完成：按入学届保存培养版本和有界课程候选；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：无真实培养方案或PG/版本发布，未知当届不复用旧届，候选不代表完成专业映射。PRIVATE保存后继续至T67。

2026-10-12 T55最小源码完成：人数口径和适用身份费用候选；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：无真实人数/费用、PG或发布；周期未知不算总成本，住宿与未来年度不填假值。PRIVATE保存后继续至T67。

2026-10-12 T54最小源码完成：省年组专业粒度的历史投档与录取观测候选；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：无真实录取数据/PG/代码审核与发布，不估录取概率或将单科统计变资格。PRIVATE保存后继续至T67。

2026-10-12 T53最小源码完成：完整降序累计分布验证与合成同分位次区间；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：仅纯候选及一种降序格式，未导入真实分布/PG/个人排序，不生成录取概率。PRIVATE保存后继续至T67。

2026-10-12 T52最小源码完成：精确考试范围和省线类型候选及单条DEMO夹具；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：无实际省分数或PG持久化/审核发布；归一候选hash不是原文字节hash，缺2026真实资料不回填。PRIVATE保存后继续至T67。

2026-10-12 T51最小源码完成：学院层级与省年招生代码映射候选；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：仅严格候选模型，无官方代码名录/PGFK/映射审核及正式连接，原名称与代码不自动标准化。PRIVATE保存后继续至T67。

2026-10-12 T50最小源码完成：34地区×2026覆盖登记与有限本地候选导入基础；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：无新PG表/迁移/正式来源owner或已审核全国事实，候选仅本地模型/bytes；真实覆盖与持久事务/审核发布待实现。PRIVATE保存后继续至T67。

2026-10-12 T48最小源码完成：有限发布门槛报告与缺失证据阻挡判定；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：真实D01–D08、身份/权限/恢复/监控/容量/领域审核与本批运行验证缺失，当前公众发布blocked。PRIVATE保存后继续至T67。

2026-10-12 T47最小源码完成：十项关键合成验收设计与未执行报告契约；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：本批无评测执行或真实领域抽查，十项只是设计样本，不代表100例或严重错误为零。PRIVATE保存后继续至T67。

2026-10-12 T46最小源码完成：显式合成窗口配额、并发预留和幂等计费收据；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：仅单进程内存，不提供生产配额/HTTP装配/多实例/重启持久性或容量测量，D07阈值未知。PRIVATE保存后继续至T67。

2026-10-12 T45最小源码完成：默认关闭的有限指标汇总与纠错候选状态契约；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：持久反馈HTTP/告警、运行采集器、负责人/SLO及故障脱敏演练未实现或未验证。PRIVATE保存后继续至T67。

2026-10-12 T44最小源码完成：合成有界AESGCM备份包、固定维护计划与T40恢复屏障接缝；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：实际PG dump/restore、加密密钥ACL/轮换、独立灾备、RPO/RTO与正式运行责任未验证。PRIVATE保存后继续至T67。

2026-10-12用户确认简化全部剩余任务并逐个执行至T67；T49不重复。本批按docs/simplified_plan.md交付最小源码，原运行/真实资料/发布验收保留未验证；D01/D07等未知不阻挡默认关闭源码顺序推进，但继续阻挡真实启用。此新授权替代先前T50停止及T44源码等待限制。不运行测试/Lint/TypeCheck/Build/校验/演练，每Task文档同步和PRIVATE普通保存后下一项，T67后停止。

2026-10-04 T44：仅完成T44相关代码与依赖核对，备份/恢复尚未实现；D07替代目标及本批仅源码继续的范围澄清待答。测试/Lint/TypeCheck/Build/校验及演练未执行（用户要求），未验证项：D07的恢复/容量目标与责任未定；原T44要求实际恢复证据，本批不用测试；未收到调整原顺序/验收范围的答复，不将等待视为同意，不继续T45–T50。本Task未验收，不暂存/提交/推送；后续顺序等待范围澄清，不部署/处理真实资料。

2026-10-04 T43：完成默认关闭的手动CI源码，推送不触发测试；固定契约、离线Python、独立PG/迁移及Vue四stage。测试/Lint/TypeCheck/Build/校验及演练未执行（用户要求），未验证项：流水线/坏迁移/漂移/网络负例与分支门槛未验证；workflow仅工作分支、默认分支入口和branch protection未配置；旧Windows浏览器/pg_dump路径尚未接入，关键HTTP不能代替浏览器/完整恢复。仅本Task源码/文档保存，不部署/处理真实资料；按授权逐项至T50。

2026-10-04 T42按用户‘先做通用Docker配置’完成本地隔离配置源码；实际城市/供应商/手续仍待定。仅production foundation/空目录、auth静态前端、TLS同源代理、私网业务库与独立卷台账库、显式维护迁移；私有业务/worker/live关闭。按‘不用测试’未执行测试/Lint/TypeCheck/Build/预检或容器演练，源码完成不表示运行通过。本批至T50授权保持；每Task文档同步及PRIVATE保存后再推进。

2026-10-04用户追加“不用测试”：本批后续不自动执行Unit/Integration/浏览器测试、Lint、Type Check、Build或验收校验脚本，直到用户明确恢复。此要求优先于下文执行测试的通用规则；保留此前实际执行的结果，新记录明确“未执行（用户要求）”，不宣称已验证。必要的源码/文档阅读、Git状态及提交内容审阅继续；本指令未选择D01部署城市/供应商，也未给出D07替代目标，不解除这些独立依赖。

历史前置记录（同日后续用户选择通用源码，已由ADR-056调整）：2026-10-04 T42部署前置文档核对完成但Task [!] 阻塞：D01部署城市/供应商/适用备案流程未定，不能满足平台地域适配验收。只新增部署范围/待测矩阵与阻塞记录，没有Dockerfile/运行配置/采购或部署；Docker CLI29.8.1但Linux Engine当前不可达。T41已PRIVATE保存4009a36；T43–T50未开始，本批授权至T50保持，解除依赖后才恢复T42；真实处理关闭。见[阻塞记录](docs/acceptance/T42_deployment.md)。

2026-10-04 T41隐私与授权操作页面源码与合成隔离验收完成：62新增前端专项/完整805、228相关Python、1实际PG/HTTP/Edge十一检查点、TypeCheck/双Build通过；[验收](docs/acceptance/T41_privacy_workspace.md)。复用现有隐私/共享，默认折叠本人导出/删除，受理/失败/在线完成分开，原内容只内存并拒迟到；真实关闭。PRIVATE保存核对后才单独T42，本批T50停止，真实处理关闭。

2026-10-04 T40资料权利与独立删除台账源码与合成隔离验收完成：30新pure/11契约、18 distinct实际PG-HTTP含pg_dump/restore、713相关Python加1旧symlink skip、743前端/TypeCheck/双Build通过；[验收](docs/acceptance/T40_data_rights.md)。本人导出/持久删除、备份外最小减权台账与完整性锚点，受理不等于完成，缺最新证明拒流量；真实处理关闭。PRIVATE保存核对后才单独T41，本批T50停止，真实处理关闭。

2026-10-04 T39有限公开证据问答入口源码与合成隔离验收完成：61新pure/9新契约/10 distinct实际PG-HTTP（含1 Edge八检查点）、704相关Python/143模式-M0、742完整前端及末59专项/TypeCheck/双Build通过；[验收](docs/acceptance/T39_qa_entry.md)。默认disabled、固定意图/匿名实例预算与等待后当前证明，纯文本类型化引用；无真实模型/画像工具/DB迁移。PRIVATE保存核对后才单独T40，本批T50停止，真实处理关闭。

2026-10-04 T38范围检索与严格引用验证源码与合成隔离验收完成：106纯及评测校验、10 distinct实际PG、528相关Python/143模式-M0、684前端/TypeCheck/双Build通过；[验收](docs/acceptance/T38_qa_retrieval.md)。仅当前已发布且精确适用的公开证明，等待后重新取证且整答拒伪引用；默认关闭、真实/live/HTTP/UI仍关闭。PRIVATE保存核对后才单独T39，本批T50停止，真实处理关闭。

2026-10-04用户新授权延长至T50：仍按单Task依赖/验收/文档同步/PRIVATE保存后逐个推进，完成T50停止；历史T40停止为旧批次记录，不撤销新授权。真实模型、真实学生、公众部署和事实发布门槛保留。

2026-10-04 T37可替换模型接口与离线预算源码与合成隔离验收完成：90新增离线/async专项、651相关Python/143模式-M0、684前端/TypeCheck/双Build通过；[验收](docs/acceptance/T37_model_gateway.md)。真实live保持关闭，disabled无需密钥；合成mock只读有限接口与进程内预算，不改确定性资格或核心服务。PRIVATE保存核对后才单独T38，本批T50停止，真实处理关闭。

2026-10-04 T36持久作业与站内提醒源码与合成隔离验收完成：36新增pure/16实际PG-HTTP/12契约，684前端/TypeCheck/双Build通过；[验收](docs/acceptance/T36_jobs_notifications.md)。新增五表/第16迁移head及默认关闭、本人确认的站内提醒；持久租约/fencing/去重/有界重试，接受清理仅probe，不做真实删除或外部通知。PRIVATE保存核对后才单独T37，本批T40停止，真实处理关闭。

2026-10-04 T35明确修订与有限历史工作台源码与合成隔离验收完成：57纯专项/19 distinct PG及HTTP/Edge、321契约与350相关Python、635前端/Type Check/双Build通过；[验收](docs/acceptance/T35_plan_revisions.md)。仅复用本人明确选择的新草案，追加接受/拒绝与替代关系，旧确认/完成不改、新计划未最终确认；历史不表示当前资格，真实关闭。PRIVATE保存核对后才单独T36，本批T40停止，真实处理关闭。

2026-10-04 T34发布变更业务比较与影响追踪源码与合成隔离验收完成：86纯专项/16distinct PG、723相关Python/590前端、Type Check/双Build与八契约核对通过；[验收](docs/acceptance/T34_changes.md)。仅处理已存发布事件的精确关系与不可变影响轨迹，不重算资格或改写计划完成；无新增HTTP/UI/worker，真实关闭。PRIVATE保存核对后才单独T35，本批T40停止，真实处理关闭。

2026-10-04 T33计划与进度工作台源码及合成隔离验收完成：116新增前端专项/完整590、56相关Python、Type Check/demo-auth Build及1真实PG/Edge用例通过；[验收](docs/acceptance/T33_plan_workspace.md)。显式目标、UTC微秒/未知估时、独立确认/本人完成、只读历史与迟到清理保留；PRIVATE保存核对后单独T34，本批T40停止，正式处理关闭。

2026-10-04 T32确认与进度源码及合成隔离验收完成：56新增pure、28 distinct PG/HTTP、305契约回归、865相关旧Python、474前端与Type Check/demo-auth Build通过；[验收](docs/acceptance/T32_plan_execution.md)。独立state_version与不可变记录、首次确认未来容量及重放当前进度保留，不改变资格/学校事实；PRIVATE保存核对后单独T33，本批T40停止，正式处理关闭。

2026-10-04 T31纯容量排程验收完成：100新增专项、228相关旧pure、474前端及Type Check/demo-auth Build通过；[验收](docs/acceptance/T31_scheduling.md)。本地周容量/UTC整数工时、依赖与冲突保留，官方精确期限仍未知，原草案不确认。PRIVATE保存核对后才单独T32，本批T40停止；真实处理关闭。

2026-10-04 T30草案源码与合成隔离验收完成：81专项pure、23独立PG用例、641相关Python和474前端通过，Type Check/demo-auth Build通过；[验收](docs/acceptance/T30_plan_drafts.md)。五表/内部服务保持draft与来源绑定，512KiB极端组合限额问题已记录；真实处理/HTTP/排程/确认关闭。按持续授权PRIVATE保存核对后再单独T31，本批到T40停止。

2026-10-04 T29已完成项目比较与证据工作台：474前端、529相关Python、2独立PG用例（其中实际Edge13检查点）及Type Check/demo-auth Build通过；[验收](docs/acceptance/T29_catalog_workspace.md)。完整范围/权限和原证据文本保持；真实处理仍关闭。按持续授权PRIVATE保存核对后再单独执行T30，本批至T40停止。

2026-10-03 T28源码及合成隔离验收完成：33路径（11旧/22新）、513其他tracked保持；104纯四态、23新PG、63旧PG、284契约、764相关Python、348前端及Type Check/双Build。完整AST/必要后补义务、当前本人/原用途/最终期限、不可变结果与历史current_validity分开；正式规则仍unknown。基线PRIVATE T27 0f61760955f32d4822e637ec22ef41de23f17a97、524tracked/空索引，codex/t28-eligibility-assessments；无新依赖/旧迁移/M0改变，真实处理关闭。文档与PRIVATE保存核对后才T29，详见docs/acceptance/T28_assessments.md。

2026-10-03 T27源码及合成离线验收完成：14路径/510其他tracked保持，248新专项、1006相关、348前端/Type Check/双Build与六profile/原文/M0检查。date-only当天/精确截止相等未知，来源日历/独立主补、enrollment显式申请N/A、受信当前绑定；allowed不是conditional。基线PRIVATE T26 a58a99306568f91c9aa0f8ac428e7d39a48024be、517tracked/空索引，当前codex/t27-reviewed-deferrals；不改旧层/HTTP/DB/UI/依赖/M0，真实关闭。T01–T27/T49共28完成/39未开始；文档/PRIVATE保存核对后才T28，详见docs/acceptance/T27_deferrals.md。

2026-10-03 T26源码及合成离线验收完成：18路径/499其他tracked保持，208新专项、722相关、348前端/Type Check/双Build及六profile/原文/M0检查。31省识别、完整scope pin/阶段/年度与受信端口，matched不是资格，事实ruleset=null仍unknown。基线PRIVATE T25 3abed0cf4f3af77e337a06414247923d44c0940e、506tracked/空索引，当前codex/t26-admissions-scope-adapters。无HTTP/DB/UI/依赖/旧M0变更；真实关闭。T01–T26/T49共27完成/40未开始；文档/PRIVATE保存核对后才单独T27，详见docs/acceptance/T26_scope_adapters.md。

2026-10-03 T25源码及离线验收完成：16路径（7旧/9新）/490其他tracked保持；178新纯规则、539相关、348前端/Type Check/demo-auth Build与六profile/原文/M0检查通过，首145/3及中间复验保留。纯AST/full-tree Kleene、strict数值/单位/满分/日期/缺失预测、预算及构造绕过保护；不证明审核/适用或四态。基线PRIVATE T24 e3c74f956280cd0bc381581ac0da1bcc57be589b、497tracked/空索引，当前codex/t25-typed-rule-expressions。无HTTP/DB/UI/依赖/旧M0改变，真实关闭。T01–T25及T49共26完成/41未开始；文档与PRIVATE保存核对后才单独T26，详见docs/acceptance/T25_typed_rules.md。

2026-10-03 T24源码及合成隔离验收完成：25路径（9旧/16新）、472其他tracked保留；69新专项/348完整前端/Type Check/双Build、99画像相关/411契约模式、六profile/原文/M0检查，1实际PG内12项Edge流程含并发CAS与成功延迟GET后退出。前六browser失败保留，仅新harness采集修正，业务未改。起点PRIVATE T23 f901ab2e406d42e93fec23f28df6a814fb6d6765、481tracked/空索引，当前codex/t24-profile-confirmation-ui。无后端/迁移/API/依赖/旧M0修改，真实处理关闭；T01–T24及T49共25完成、42未开始。文档及PRIVATE保存核对后才单独T25；详见docs/acceptance/T24_profile_workspace.md。

2026-10-03 T23源码与合成隔离验收完成，35路径/11旧24新、446其他tracked保留；48pure/51PG、401相关/411契约模式、279前端/Type Check/两Build。首建收据和最终授权共享同fresh时间，新增等待回滚实际验收；真实处理关闭。基线PRIVATE T22 1054b8129ec9e94700a6f5158ea9f9b3f1f4d9a7、457tracked/索引空，当前codex/t23-profile-versions。文档同步及私有保存核对后按批次进入T24，不同时开发其他Task。详见docs/acceptance/T23_profile_versions.md。

2026-10-03最新产品目标（ADR-034）：全部普通高考生源省份逐省配置，英国本科暂定2027、优先剑桥/曼彻斯特；真实省/年/专业适用证据未验收时unknown。下文旧单省描述为先前规划或M0基线，不表示当前产品目标或已实现覆盖。


## 当前阶段与授权边界

2026-10-03 T22源码与合成隔离验收完成：44路径（12旧/32新），13pure/8PG、100相关、383契约/模式、279前端及Type Check/demo-auth Build；1PG内13项实际Edge检查，首完整前端失败修复并如实记录。旧服务/迁移/依赖/四profile不改，真实处理关闭。起点PRIVATE T21 ed4defaf786b6798acd3a875add8adcdc638e6cf、425tracked/索引空；当前codex/t22-review-release-admin。文档同步及私有提交推送核对后按批次授权进入T23，详见docs/acceptance/T22_admin_review_workspace.md。

2026-10-03批次澄清：用户明确全部普通高考生源省份目标、英国本科入学年暂定2027、优先剑桥大学与曼彻斯特大学，专业根据学生明确情况/意愿建议并本人确认；模型本批仅接口/离线验证、live关闭。此新目标替代历史单省产品目标，不变更既有M0单省合成基线；逐省/年/专业的真实规则与审核责任未覆盖时保持未知，2026参考不自动变成2027资格。见ADR-034。

2026-10-03用户新授权按顺序逐个执行T21–T40、加速；每Task先读取/冻结范围、实际验收、文档同步及私有源码提交推送后再进入下一Task，完成T40后停止。此新授权替代历史T20停止的当前行动限制；历史记录保留，不部署/真实资料处理/自动采集/自动申请。T21来源与导入管理页面已验收，T01–T21及T49已完成；验收37路径、9pure/7PG、65导入回归、368契约/模式、222前端/类型/两Build及1PG内9项Edge浏览器检查。见docs/acceptance/T21_admin_workspace.md。私有保存核对后进入T22；任何必要决策未明确仍保留对应真实启用关闭。

2026-10-03 T20源码与合成隔离实库验收完成，T19已保存557ca402；385tracked/开始干净、冻结public_catalog/ADR-032。45pure/23PG最终68 passed、46相关、357契约模式、170前端/类型/两Build、生成/原文/12module compile通过；首PG20/3与新harness44/1保留。27路径、旧heads/入口/依赖不改，私有候选库通过当前release有限投影，真实公开默认关闭。T01–T20及T49共21主Task完成、46未开始；文档同步和普通保存后本批停止，不启动T21或部署。后台uvicorn烟测被自动审批拒绝未执行；正式事实/法律/SQL权限/清理备份门槛保留。详见docs/acceptance/T20_public_catalog.md。


2026-10-03 T18已保存b3cab25，当前T19源码与合成实库验收完成；371 tracked/开始干净、冻结docs/releases.md，正式拒绝DEMO、test_fixture仅离线，ruleset_version=null不伪造T25。24pure/22PG、89相关、333契约模式、170前端/类型/两Build通过；首PG18/4为新harness前提，最终22通过。20主Task完成、47未开始。同步保存后只T20，然后停止，不部署。

2026-10-03 T18人工审核模块源码与合成隔离实库验收完成，T17已验收并PRIVATE上传94daf36，357 tracked/开始干净。先读必读/原规格/相关代码并冻结docs/reviews.md；只合成模拟审核，当前唯一case/逐字段检查/追加历史，不改T17或发布。31pure/23PG、93相关、333契约模式、170前端/Type Check/双Build通过；19主Task完成、48未开始。首两PG失败为本新测试前提，最后23通过。同步保存后逐个T19/T20，T20后停止，真实门槛保留。

2026-10-03 T17显式类型化事实已验收：35pure/25PG、160相关、333契约模式、170前端/Type Check/双Build通过；首PG两测试前提失败已修、最后25通过。独立2表/profile、精确数字、保留原类型/单位/脚注与历史冲突，所有候选不可发布/硬规则；旧heads/HTTP/依赖不变。T01–T17及T49共18完成、49主Task未开始；真实处理关闭，T15任务外时效问题仅记录。同步/源码保存后按既有批次单独T18–T20，T20后停止。详见docs/acceptance/T17_typed_facts.md。

2026-10-03用户已直接确认T16合成A/B/C原文抽查并继续执行T16。恢复核对无源码变化，本轮33pure/19PG合计52 passed68.10s；此前143相关加1 symlink skip、333契约模式、170前端/类型/双Build为已记录历史结果。T16源码/合成抽查与隔离实库验收完成，T01–T16及T49共17主Task完成，其他50未开始。文档同步/普通提交推送核对后，按既有批次授权依次单独T17–T20，T20后停止、不启动T21；不开放真实资料或部署。详见docs/acceptance/T16_evidence.md。


历史暂停记录（现已由用户确认解除）：2026-10-03 T16源码与自动检查完成但Task阻塞：最终33pure/19PG、143相关加1 symlink权限skip、333契约模式、170前端/类型/双Build通过；独立证据三表/profile、不可变版本/片段、原byte/line/hash与current范围指纹、限定衍生审核读，无旧head/HTTP/依赖改变。本Task卡要求人工原文抽查，材料docs/acceptance/T16_manual_review.md已生成并向用户问询，未收到确认，不标完成、不提交推送、不启动T17–T20；确认/修正后恢复既有顺序授权。T01–T15及T49共16主Task完成，T16一项阻塞、其他50未开始；真实资料/公开发布/部署仍关闭。详见docs/acceptance/T16_evidence.md。


2026-10-03 T15人工结构化导入已验收：有界JSON/CSV、固定错误持久回执、整批拒绝零候选、自然内容键及T49同事务审计/回执，候选draft/unresolved。46纯/19PG、145相关加1 Windows symlink权限skip、333契约模式、170前端/类型/双Build通过；首PG17/2修后19通过。T01–T15及T49完成、51主Task未开始；真实来源/审核发布与正式TTL仍关闭。CHANGELOG/tasks同步保存后按授权进入T16，不启动T21或部署。详见docs/acceptance/T15_manual_import.md。


2026-10-03必要依赖T49已验收：独立幂等0001、最少资源回执/同TX与deferred完成约束，每次重放当前身份/角色/用途/领域检查；48纯/19PG、450相关/333契约模式、170前端/类型/双Build通过。T01–T14及T49完成、52主Task未开始。正式receipt TTL待定且真实路径默认关闭，无物理摘要清理/部署验收；文档与保存后按已授权批次进入T15，不启动其他未授权任务。详见docs/acceptance/T49_persistent_idempotency.md。


2026-10-03当前批次：T08–T14均已独立验收与保存；T14新增可替换本地隔离存储，43纯测试通过/1文件symlink权限跳过、17 PG与531相关回归、333契约模式、170前端及类型/双构建通过。真实处理、POSIX、正式TTL/ACL/清理/备份及部署未验收。T01–T14完成、53主Task未开始；按用户授权下一单列必要T49依赖，再逐个T15–T20，不启动T21。历史逐Task停止记录不撤销本次批次授权。详见docs/acceptance/T14_file_storage.md。


2026-10-03 T13来源登记已验收：catalog0003/SourceBase独立两表、同事务即时管理员/签名MFA及最小审计，官方声明与三许可分开、无fetch。新纯31/PG18、相关542/契约模式333、前端170/Type Check/双Build通过；首PG7pass/11fail修复后复验。D03正式责任人待答，real_sources_ready默认false，不登记真实来源或发布。T01–T13完成、54主Task未开始；CHANGELOG/tasks同步保存核对远程后进入已授权T14。详见docs/sources.md和docs/acceptance/T13_source_register.md。

2026-10-03 T12候选日期已验收：catalog0002/DatesBase独立表，日期纯43/PG11、相关274/契约模式333通过，前端170/Type Check/双Build通过；原始精度/IANA与计算UTC候选保持，官方UTC固定NULL/draft、证据unresolved，真实原文审核未完成。T01–T12完成、55主Task未开始；保存并核对远程后进入已授权T13，真实责任/发布/部署门槛不解除。详见docs/dates.md和docs/acceptance/T12_date_events.md。

2026-10-03 T11候选关系模型已验收：独立admissions_catalog/catalog profile及五表，80schema/30PG与1377回归选择通过，默认入口/HTTP契约/M0/auth数据保留；生产事实和真实资料仍关闭。每个已授权Task独立保存后继续T12，不部署、不启动未授权里程碑；最新逐Task命令与配置专项见docs/acceptance/T11_admissions_catalog.md。T01–T11完成，56个主Task未开始。

2026-10-03用户新授权先确定D02，再逐个执行T08–T20并加速。D02产品路线已选：18+本人确认，14–17须独立监护但首版不提供核验，因此未成年私有关闭；unknown/under14公开only。D06产品上限及开发验收告知草案已由用户确认，真实运营主体/告知/法律适用性仍是上线门槛。本轮每次只实施一个Task，分别验收/文档同步/提交推送后才进入下一已授权Task；历史单Task停止限制不阻挡本次明确批次授权。T15/T19必须先完成T49，依赖单独验收，不藏入其他Task；不授权部署、真实学生处理或招生事实发布。T08–T10已完成；T10最终1662 Python（365PG/1297其他）、170前端、Type Check/两Build，identity契约不变；当前head0006/v2.t09，审计仅最少责任引用、共享仅合成fixture，真实处理关闭。验收同步后保存并进入已授权T11，其他状态以tasks为准。

2026-10-03用户新授权执行T07，现已完成对象级授权基础：最小持久角色与归属元数据、服务器Principal、SQL对象/列表、同事务执行与缓存重验，认证head0003，既有wire与业务关闭状态保持。最终1123项Python（200PG/923非PG）、专项131/63、前端62、浏览器12和Type Check/两模式构建通过；Lint/Python静态类型无入口未执行，真实Keycloak/MFA/recovery/TLS未执行。T01–T07已完成、其他60主Task未开始。CHANGELOG/tasks及受影响文档同步后按持续授权提交推送并停止，不开始T08、共享grant、正式业务/注册/角色管理HTTP接口或部署。此授权替代历史T06“不启动T07”的当前限制，历史记录保留；实际验收见docs/acceptance/T07_object_authorization.md，真实D04/D02/D06及公众发布门槛保留。

2026-10-02用户新授权执行T06，2026-10-03完成：当前会话原子退出、固定Origin/稳定CSRF中央写保护、执行时会话与显式权限重验，默认关闭的管理员签名acr/amr/auth_time强度策略，增量0002认证迁移保留旧session/M0。全项目929项（含137PG）/前端62/浏览器12及两模式构建通过；Lint/Python静态类型无入口未执行，真实Keycloak/MFA/recovery/生产TLS未执行。T01–T06已完成、其他61主Task未开始。CHANGELOG/tasks同步后按持续授权保存源码并停止，不启动T07或部署；真实D04、D02/D06与公众发布门槛保留，grant/队列仍未实现。详见docs/identity.md与docs/acceptance/T06_session_csrf.md。此授权替代历史T05“不继续T06”的当前限制，历史记录保留。

2026-10-02用户明确授权执行T05，现已完成：新增显式identity入口、固定Keycloak换码/RS256验证、预登记active账户与服务器摘要会话，独立认证迁移链保留M0旧链/七表。默认认证关闭、无DB连接；不自动注册、不开放画像/资源权限、不部署。最终758项Python（含45 PG）/42项前端/8项浏览器及两模式构建通过；T01–T05已完成、其他62主Task未开始。验收/文档同步后按持续授权提交推送本Task并停止，不继续T06。真实tenant/版本/地域、管理员MFA/恢复、D02准入与其他发布门槛不解除；详见docs/identity.md与docs/acceptance/T05_login_session.md。此授权替代历史“不实施T05”的当前行动限制，旧Task记录保留。

2026-10-02用户授权先明确D04再执行T04，并选择自托管Keycloak。T04可替换身份接口、冻结信任配置与固定合成离线供应商已完成：131专项/606离线回归通过；不实现T05登录/会话、不注册真实账号、不部署。D04供应商路线及接口配置层部分确定，真实tenant/版本/地域、管理员MFA和恢复流程仍需后续配置验收；其他待决与公众发布门槛不解除。T01–T04已完成、其他63个主Task未开始，详见docs/identity.md及docs/acceptance/T04_identity_provider.md。验收和文档同步后按持续授权提交推送源码并停止，仅此Task；历史阶段限制不撤销本次明确授权。

2026-10-01用户新授权执行T03，2026-10-02完成演示/生产模式隔离与离线验收：冻结配置、独立production factory只挂/v2、DEMO凭据/夹具拒绝、目录污染整体503、无密钥基础读取。当前真实目录/资格/计划与PostgreSQL登录角色/GRANT/RLS未实现；query_role仅应用策略，业务不可用。T03已完成、其他64个主Task未开始；本轮按持续授权提交推送后停止。详见docs/acceptance/T03_mode_isolation.md。此授权替代历史“不开始T03”的当前行动限制；不继续后续Task、不部署，历史记录保留。

2026-10-01：P00–P03、T01实库验收、T50A来源候选文件登记和E01本地Docker修复已完成。用户授权的T02 /v2基础契约已完成：独立基础子应用、统一响应/错误、空目录分页和离线OpenAPI/TS生成已验收，保留M0 v1；本轮停止。其他65个主开发Task未开始，不自动继续T03/T49、正式账号/真实目录/采集器，不部署或提交。来源后台T50仍受原依赖约束；旧迁移、DEMO夹具、研究文件及旧验收未改。详见docs/acceptance/T02_v2_contract.md。

2026-10-01后续新授权：P04 GitHub仓库与验收后提交推送规则已完成。用户确认的chanbilly-lab/study-admissions-agent私有仓库已建立，main已上传并核对远程；持续授权每个Task成功验收、文档同步后提交及推送当前Task改动。此授权替代此前当前任务“不提交”的限制，仅覆盖源码版本保存；不授权业务部署、真实用户数据或招生事实发布，不开始T03。历史M0/T01/T02等记录原意保留。

目标是正式面向中国大陆、香港、澳门、台湾高中升本科学生的公众服务，计划在中国大陆部署。全国参考资料目标年度2026、机构地域覆盖大陆及港澳台已确认，实际覆盖尚未完成；各地区原始学年、培养入学届和就业毕业届保留。首 MVP 个性化继续一个配置生源省份普通高考本科＋英国本科；所在地与招生身份/课程体系分开，HKDSE、港澳台联招、台湾学测等未适配路线不套用高考规则。正式准入责任/告知/法律适用性、个性化真实生源省份、首版全量资料门槛、具体部署区域及供应商仍待决定，相关门槛未完成不得开放对应真实数据处理或公众发布。

## 后续 Task 通用规则

1. 每个新任务开始前必须阅读 `README.md`、`docs/requirements.md`、`docs/architecture.md`、`docs/tasks.md`、`docs/CHANGELOG.md`、`docs/DECISIONS.md`，并核对原始两份规格、相关代码及 Git 状态。涉及 API、数据库或特定模块时，还必须阅读 `docs/api.md`、`docs/database.md` 或对应模块文档。未理解现状、任务范围及依赖前不修改代码；实施只选一个 Task。
2. 保留用户文件和改动，不覆盖、重置、清理不认识的文件；提交推送遵守下文的用户持续授权，不纳入无关改动。原始两份输入、`docs/01–05` 和旧验收记录不改写；新检查用新日期记录。Git 所有者错误只允许为当前命令指定 safe.directory，不修改全局安全配置。
3. 只修改当前 Task 所需文件，优先复用现有逻辑；不擅自改变架构或技术栈、不随意删除已有功能、不顺带重构。新增依赖必须说明用途、必要性和影响，并同步依赖文件与锁文件。发现无关问题只记录到任务文档。任务太大先细分，缺少必要决策标明依赖，不能猜测验收。
4. 采用 Vue3/TypeScript/Vite、Python/FastAPI/Pydantic、PostgreSQL/SQLAlchemy/Alembic 模块化单体。模型和文件存储保留可替换接口；不提前引入微服务、向量库或复杂 Agent 框架。
5. 新功能先列数据契约、修改范围和可测试验收；更新对应文档。迁移增量创建，冻结旧迁移；应用启动不建表、不重导夹具。破坏性迁移须有备份、恢复验证及明确授权。
6. 资格引擎只用受限声明式规则，禁止 `eval/exec`，不调用模型。保留 eligible/ineligible/conditional/unknown；缺成绩没有适用、已审核、带期限的后补政策依据时必须 unknown。真实要求、数字和日期必须来自适用已发布证据，不能以 DEMO 或其他年份资料填补。
7. 画像及计划必须由有权限的用户明确确认；模型不能代确认、改事实、改权限、提交申请、付款或接受 offer。服务端验证身份、owner 和 grant；前端角色或 owner 参数不作为权限依据。
8. 演示与真实事实隔离。T03已实现独立production入口只挂`/v2`与冻结启动模式；正式认证/真实业务仍逐Task实现。`data_mode=demo/verified`与`model_mode=disabled/mock/live`分开；mock仅demo，verified+disabled无密钥可读基础配置/空目录，v2 live未实现并拒绝启动，不回退。M0入口/seed在production/verified/禁演示上下文拒绝，v1合成wire与live请求503保留；query_role只是应用读取策略，不等于已配置PostgreSQL权限。
9. 离线测试不调用外部网络或商业 API；用隔离的测试库、假身份/模型供应商，不使用生产学生数据。根据项目实际情况运行相关 Unit Tests、Integration Tests、Lint、Type Check、Build 和专项检查，记录真实命令、数量和结果。无法运行、跳过或不适用须分别说明原因；禁止虚构测试或将历史结果写成新通过。纯文档任务可用文档/链接/状态/哈希检查验收，应用检查明确未执行及原因。
10. 完成前必须同步 `docs/CHANGELOG.md`、`docs/tasks.md` 和受影响文档，按下文固定格式报告后停止；推荐不代表自动继续。提交、真实用户数据收集、对外发布均不由任务建议自动授权。
11. 全国参考资料与个性化范围分开；详见 [数据策略](docs/data_strategy.md)。真实研究样本仅存 `data/research`，不接入 M0/资格/生产发布；`is_synthetic=false` 不能代替正式审核。省段线、投档/最终录取、计划/录取人数、毕业去向/纯就业率和专业/学科汇总不得混用。时间、分母、单位、代码映射与缺失原因逐项记录；没有原文字节不得编哈希。历史数据不自动变成当前资格，缺失不能由模型补造。

## Git仓库与持续提交推送授权

2026-10-14用户已明确授权经过本轮审阅的干净源码公开。当前源码仓库`https://github.com/chanbilly-lab/study-admissions-agent`（新ID1418914840）为PUBLIC，默认分支codex/privacy-release，正常公开工作目录D:/Projects/study-public。只推送到已核实的当前origin／明确分支，并使用GitHub noreply；新分支保持codex/前缀。原仓库ID1400234431仅作PRIVATE只读备份，旧工作目录／镜像origin指向study-admissions-agent-private-archive，不得推入公库。早期main／必须私有的源码规则是历史；仓库公开不代表服务部署或真实事实发布，不授权强推、重写历史、其他remote／可见性调整或共享真实资料。

每轮一个Task全部验收、CHANGELOG/tasks及受影响文档同步后，执行提交和普通push，无须再次请求已经给出的授权。开始时记录Git基线和已有暂存内容；只暂存当前Task审查过的必要文件或hunks，不用`git add -A`/`git add .`纳入无关用户改动。若同一文件混有用户改动，只提交明确属于本Task的hunks；不能可靠区分时保留用户内容并报告上传边界，不替用户提交。初始P04只上传人工核对的项目清单，不编造旧Task单独commit。

提交前核对实际暂存diff。用户开始前已有的暂存内容同样不属于Task上传授权；不得reset/撤销用户索引来清理它。必要时用隔离索引或明确路径/hunks提交本Task并保留既有索引，不能可靠隔离时报告阻挡条件，不把用户暂存顺带commit。

提交信息包含Task ID和具体结果。不得提交.env、API密钥/登录token、私钥、真实学生附件/导出、数据库/备份/WSL磁盘、node_modules、构建产物或.cache；.gitignore不能代替暂存审查，已跟踪文件同样检查。两个原始输入用.gitattributes保留原字节，生成v2 schema/TS保持LF。认证复用本机已有凭据或当前命令的gh credential helper，不把token写进remote、文档或脚本，不修改全局Git安全配置。

推送后核对远程分支SHA与本地HEAD、报告commit/分支/上传结果。推送失败保留本地提交和用户改动，记录错误/解除条件，不reset/强推，不宣称成功，也不自动继续后续Task；必要时区分“实现验收已完成”和“上传失败”。

## 修改记录与 Task 状态

每次代码修改完成后必须更新 `docs/CHANGELOG.md`，即使只是很小的修改；本项目的文档治理任务也记录。每条含日期、Task ID、修改目的、修改文件、新增内容、修改内容、删除内容、Bug 修复、测试结果、已知问题；无对应内容明确写“无”，不能略过字段。保留旧记录，历史补录标明来源和未核验部分，不伪造提交或测试。

开始所选任务时将 `docs/tasks.md` 状态改为 `[~] 进行中`；尚未开始为 `未开始`，依赖或环境阻挡当前任务为 `[!] 阻塞`，完成所有验收条件后才标为 `已完成`。阻塞记录原因和解除条件；恢复时重新核对状态。不能以部分实现、被跳过的必需检查或时间不足代替验收。每项必须有明确状态，不自动启动其他任务。

## 技术决策与文档同步

修改系统架构、数据库设计、API 规范、技术/部署方案，引入框架或重要依赖，或作出会影响后续开发的重要决定时，必须更新 `docs/DECISIONS.md`。每条含 Decision ID、日期、背景、决策、原因、考虑过的替代方案、影响；另标状态、来源及实施范围。普通代码修改无需 ADR。已有决策保留，后续改变用新 ID 说明替代关系；没有历史证据的日期、原因或替代讨论明确标注，不补造讨论。

同步规则：API → `docs/api.md`；数据库 → `docs/database.md`；架构 → `docs/architecture.md`；需求 → `docs/requirements.md`；任务状态 → `docs/tasks.md`。只更新当前变更影响的文档，不为同步而改无关文件。文档必须准确区分当前已实现行为、历史结果、未来规划和待决事项；ADR 中采纳的规划不能写成代码已实现或公众发布已获授权。D01–D08 的待决状态以 requirements 为准。

## 完成任务的固定输出

最终报告必须按顺序使用以下七个标题；每部分可简短，但不可省略。Tests 必须列实际命令、结果及未执行检查和原因。Documentation 明确 CHANGELOG 与 tasks 的同步状态；Known Issues 没有问题时写“无”。

```markdown
### Task
Task ID 和名称

### Summary
完成内容

### Files Changed
变更文件

### Documentation
更新文档；确认 CHANGELOG.md 和 tasks.md 已同步

### Tests
实际命令及结果；未执行检查及原因

### Known Issues
已知问题

### Next Step
推荐下一 Task；不自动开始
```

确认 `docs/CHANGELOG.md` 与 `docs/tasks.md` 的 Task ID、状态、文件及测试记录一致后，本次任务才结束。

## 保留的 M0 演示基线约束

以下为原 M0 约束，继续适用于既有演示实现及其回归；其中“本轮”指 M0 实施轮，不能解释为本规划轮的功能开发授权。

先阅读原始两份规格与 docs。保留用户文件和改动，不覆盖、重置或自动提交。

本轮只做 M0：合成画像、DEMO 项目、确定性资格、合成证据、计划草案。
国内一个配置省份普通高考本科 + 英国本科。不做爬虫、真实招生数据库、录取概率、自动申请或后续里程碑。

所有演示机构/项目使用 DEMO_ 前缀和 is_synthetic=true；学生是合成画像。
演示证据不能标作真实官方依据。缺少成绩且没有适用、已审核、带期限的后补政策时必须 unknown。
规则禁止 eval/exec，不调用模型。画像创建必须由用户确认；身份由服务端演示凭据解析。
mock/live 显式配置；live 失败不得静默回退。M0 live 仅预留接口，明确不可用。

使用 Vue3/TypeScript/Vite、Python/FastAPI/Pydantic、PostgreSQL/SQLAlchemy/Alembic 模块化单体。
离线测试不调用外部网络或商业 API；报告实际命令与结果，未执行的检查明确标记。
