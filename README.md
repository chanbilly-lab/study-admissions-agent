# 升学咨询智能体

2026-10-14 [PRIVACY-PUBLISH-01源码隐私审阅与公开](docs/source_publication.md)已完成：用户确认保留私有历史、公开同名干净版本。当前PUBLIC库为https://github.com/chanbilly-lab/study-admissions-agent（新ID1418914840），默认codex/privacy-release；新工作目录D:/Projects/study-public，公开提交使用GitHub noreply。原ID1400234431及完整历史在PRIVATE只读study-admissions-agent-private-archive，旧D:/Projects/study与原镜像origin已指向备份。个人home已脱敏、旧私人邮箱元数据不带入公库；应用／迁移／锁／契约／数据字节保留。本轮未运行应用测试／CI／部署，不开放真实业务。

2026-10-14完成[学校/专业搜索选择源码](docs/school_program_search.md)：参考页培养/毕业查询可通过显式学校→专业选择取内部标识，移除手填UUID/对象ref。新增正式发布身份搜索接口和取消/分页/上下文保护；默认真实目录未装配，返回空/禁用查询，不用英国研究或DEMO填充。培养/毕业当届资料仍未接入。按用户要求未测试/Build/SQL/HTTP或重启服务；完整27文件与未验证记录见[交付](docs/acceptance/SEARCH_SELECT_01.md)。

2026-10-13完成[UI工作台优化源码](docs/ui_optimization.md)：演示四步提示、参考导航/筛选、省线卡片及展开证据、可读字号/焦点与移动样式；数据和权限规则保留，真实名录/未审英国候选未接入。按用户要求未运行测试或Build，也未做新UI浏览器/视觉验收；后续优化优先级和完整改动见[记录](docs/acceptance/UI_OPT_01.md)。

2026-10-13已新增[年度资料调度源码](docs/annual_source_updates.md)：每年11月1日09:00（Asia/Shanghai），可配置、默认关闭，创建待采集/待审核请求；数据库按年度去重，国内考试年与英国目标入学年分别保存。源码/独立迁移未运行、定时服务未启动，实际采集/审核/发布未开启；按用户要求本轮不测试。示例[配置](config/annual-source-updates.example.json)及完整操作见说明。

2026-10-13已新增[英国2027本科两校资料](docs/uk_2027_sources.md)：剑桥大学/曼彻斯特大学8个官方页面已实际捕获，来源、真实hash、年度差异和缺项保存在[研究候选文件](data/research/uk_2027_institutions_sources.json)。正式审核/发布均0，尚未接入查询页/资格；具体课程、费用、培养与就业仍需后续采集。原文和运行缓存不提交；M0与已批准浙江页面保留。

2026-10-13新授权BATCH-ZJ-2026-CUTOFF-01完成：用户选浙江并确认普通类494/266/594三条本地参考。官方原HTML取得/真hash、独立PG四表与源/批次/人工链、SELECT-only API8004及页面5174已实际走通；8专项PG/HTTP+8实际Edge检查通过。仅此本地批次，真实学生/公众发布/其他省年关闭；原M0和旧迁移/十二契约保持。其他全回归/Lint/Build仍未恢复。见docs/zhejiang_2026_cutoffs.md。

2026-10-13用户明确实际启动M0并验证核心流程：E02已完成，本机PG16.15专用新合成库/DEMO seed、API8000和Vue5173正在运行；真实Edge8项检查通过、page_errors=[]。只恢复这次有限检查，旧不用测试仍适用其他未授权回归/Build；真实资料/生产关闭，T67停止边界保持。详见docs/demo_startup_20261013.md。

2026-10-13 T67最小源码完成：单批候选审核清单和缺项阻挡判定；完成本批后停止；所有测试/Lint/TypeCheck/Build/校验/演练未执行（用户要求）。真实关闭，未验证：真实单批导入/原文/许可/独立审核/发布与撤回均未完成；原规划PG/运营/质量门槛保留，本批未执行任何检查。PRIVATE保存后继续至T67。

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

T27后补与独立期限源码及合成离线验收完成，实施前冻结[内部契约](docs/deferrals.md)，只给必需事项的许可，不直接输出四态；真实政策仍关闭。

T26范围适配源码及合成离线验收完成，实施前冻结[内部契约](docs/scope_adapters.md)，实际命令见[验收](docs/acceptance/T26_scope_adapters.md)；31省配置不代表已审规则覆盖，英国具体项目/年/阶段独立。

T25类型化规则与三值逻辑源码及离线验收完成，代码前冻结[内部契约](docs/rules.md)，实际命令见[验收记录](docs/acceptance/T25_typed_rules.md)。不把缺失或预测当实得，不把any失败分支当必需条件；尚不产生资格结论或后补许可。

T24画像编辑与确认页面源码及合成隔离验收完成，实施前冻结[工作台契约](docs/profile_workspace.md)，实际检查见[验收记录](docs/acceptance/T24_profile_workspace.md)。当前用途撤回立即清私人草稿，实得/预测与缺失独立，每次修改重新确认，追加CAS冲突不自动覆盖；旧M0和后端契约保持。

T23画像根与纵向确认版本源码及合成隔离验收完成，见实施前冻结的[画像契约](docs/profiles.md)。实得/预测及未知分开，完整新版本需本人确认、当前核心用途与owner，首建幂等、追加CAS；真实处理关闭。

T22审核与发布管理工作台已完成源码及合成隔离验收；[契约](docs/admin_review_workspace.md)/[实际检查](docs/acceptance/T22_admin_review_workspace.md)。显式人工准备、独立审核、发布与匿名当前release预览；真实处理仍关闭，旧T21保持。

T21已完成来源与导入管理工作台：独立admin profile复用现有身份/强管理员/CSRF与来源、隔离存储、候选导入服务。当前契约见[admin_workspace](docs/admin_workspace.md)，默认关闭真实处理。用户新授权逐Task执行T21–T40，每项验收、文档同步和私有上传后才开始下一项，完成T40后停止。

T20源码与合成隔离实库验收完成：新增显式公共目录只读profile；旧foundation/identity/M0保留，无默认数据库/身份/模型启动。无reader时config返回业务不可用，目录与证据503；合成正向仅测试，真实公开仍关闭。详见[契约](docs/public_catalog.md)与[验收记录](docs/acceptance/T20_public_catalog.md)。本批完成T20后停止。

项目目标是面向公众的高中升本科咨询工作台：学生确认画像，比较项目，查看确定性资格与证据，再确认准备计划。目标用户在中国大陆、香港、澳门、台湾，计划部署在中国大陆。个性化目标已按用户新指示调整为全部普通高考生源省份＋英国本科，须逐省/年度/专业独立已审规则，尚未实现全省资格覆盖；所在地不能推断招生身份，HKDSE、港澳台联招、台湾学测等另列后续适配范围。

**当前阶段：67已完成、0进行中、0阻塞、0未开始；简化源码完成不表示运行通过。** 本批已逐Task完成T44–T48和T50–T67最小源码并保存；T49不重复，当前停止，原发布验收保留。独立metadata共享见[共享授权](docs/sharing.md)，真实共享关闭。T10内部审计与日志配置见[审计契约](docs/audit.md)，真实运行收集器/备份仍待验收。产品年龄与留存政策见[隐私契约](docs/privacy.md)，未成年私有关闭，正式主体/告知及法律复核仍为上线门槛。 英国本科暂定2027、优先剑桥/曼彻斯特，专业根据学生明确资料/意愿建议并本人确认；模型本批仅接口及离线验证，live关闭（ADR-034）。用户选择自托管Keycloak；新增能力通过显式identity入口提供，默认关闭，只映射预登记启用账户，不自动注册或开放业务权限。T03生产基础仍只有配置/空目录，M0继续合成演示。全国参考资料目标年度2026、高校地域大陆及港澳台、招生体系分别建档；研究不接入应用，不代表全国已采齐或正式发布。正式准入责任/告知/法律适用性、各省/英国2027已审规则与项目负责人、首版全量门槛及审核责任、具体部署区域与其他供应商仍待定；D04真实tenant/MFA/恢复待后续验收。M0浙江/2027仅合成配置。

2026是资料目标年：国内高考省线/计划/投档按2026考试及招生年度；培养方案按适用于2026入学者的官方版本；就业报告保留实际毕业届、调查期和发布日期，不改成2026届。港澳台保留当地学年/路径，只有核验映射后才归入2026目标年。高校所在地与生源省份分开；详见[资料年度与地域口径](docs/data_strategy.md)。

### 规划文档与阅读顺序

| 文档 | 内容 |
| --- | --- |
| [开发约束](AGENTS.md) | 当前授权边界、单 Task 规则、文件保护与演示安全底线 |
| [需求](docs/requirements.md) | 用户、场景、MVP/非 MVP、验收与待决事项 |
| [架构](docs/architecture.md) | 固定技术栈、前后端、认证、模型、存储、部署与安全 |
| [数据库](docs/database.md) | M0七表、六张auth＋两张privacy＋四张grant＋一张audit表、五张catalog候选表、一张候选日期表、两张来源治理表与拟增实体、审核发布、版本、隔离与删除 |
| [API](docs/api.md) | 已实现 /v1 和 /v2基础契约；T49内部幂等已实现，公众业务HTTP仍按Task规划 |
| [任务](docs/tasks.md) | 67主Task：67已完成、0进行中、0阻塞、0未开始；本批最小源码/未验证，原发布门槛保留 |
| [招生机会关系](docs/catalog.md) | T11独立候选模型/范围/版本；真实导入发布关闭 |
| [日期事件](docs/dates.md) | T12精度/IANA/DST候选契约；正式日期审核待后续Task |
| [人工审核](docs/reviews.md) | T18逐字段人类判断、职责隔离及版本锁；已验收，不直接发布 |
| [类型化事实](docs/facts.md) | T17显式分类、原单位与未知状态、精确数字和历史冲突；已验收，不能发布 |
| [证据版本](docs/evidence.md) | T16字节/物理行定位及不可变版本；[合成人工抽查](docs/acceptance/T16_manual_review.md)已确认 |
| [人工导入](docs/imports.md) | T15有界JSON/CSV候选与固定错误回执，未发布 |
| [幂等基础](docs/idempotency.md) | T49同事务最少回执与当前重放鉴权，正式TTL待定 |
| [文件存储](docs/storage.md) | T14隔离UUID/有界格式/逐次权限与事务补偿，真实处理关闭 |
| [来源许可登记](docs/sources.md) | T13发布者/用途/许可/责任与复查，元数据不自动抓取 |
| [对象授权基础](docs/authorization.md) | T07服务端Principal、固定角色/owner矩阵与同事务执行；真实业务继续关闭 |
| [身份供应商配置](docs/identity.md) | D04自托管Keycloak、T04接口/离线边界及真实认证启用前门槛 |
| [真实资料策略](docs/data_strategy.md) | 全国覆盖、分数/培养/毕业结果契约、来源、口径与分批验收 |
| [2026来源候选登记](data/research/source_registry_2026.json) | 34地区、官方入口及238个类型缺口单元；[契约与验收](docs/acceptance/T50A_source_registry.md)，不导入应用 |
| [官方研究样本](data/research/official_samples.json) | 14 条有限观察、14 个来源与地区登记；待审核、未发布，与 M0 隔离 |
| [变更日志](docs/CHANGELOG.md) | 按 Task 记录改动、实际检查结果和已知问题；历史补录有来源 |
| [技术决策](docs/DECISIONS.md) | 决策背景、原因、替代方案和影响；规划、实施与待决状态分开 |

每个新任务开始前必读本 README、requirements、architecture、tasks、CHANGELOG、DECISIONS；涉及 API、数据库、真实资料或特定模块时补读对应文档。遵守范围保护及记录规则；验收后同步 CHANGELOG/tasks，再按持续授权提交/推送当前Task改动并报告。旧验收保留；本轮从T08开始逐Task推进已授权批次，验收记录分别保存，不能以批次授权跳过依赖。

先读根目录两份原始输入与 `docs/01–05`，再按上表阅读。原文、M0计划/报告作为历史基线保留；新增记录最新决策。原M2采集延期，首版拟人工导入与审核更新；本轮不推进采集或其他Task。

技术方案沿用Vue3/TypeScript/Vite、Python/FastAPI/Pydantic、PostgreSQL/SQLAlchemy/Alembic模块化单体。公众服务拟采用OIDC＋服务端会话、人工审核事实与确定性模板，模型接口可替换。T03生产入口只挂/v2，拒演示凭据/夹具与mock；无API密钥可读基础配置/空目录，真实资格和计划仍依赖后续Task。

### 私有GitHub仓库与每Task上传

仓库为[chanbilly-lab/study-admissions-agent](https://github.com/chanbilly-lab/study-admissions-agent)，私有、主分支main。P04已上传101份项目文件的首个现状基线`819e5cb`，origin/main核对一致；完成记录也按Task规则提交推送。创建/上传检查见[独立记录](docs/acceptance/P04_git_repository.md)，不把本轮上传说成过去Task的历史提交。

用户持续授权：每个Task验收成功、CHANGELOG/tasks和相关文档同步后，提交并正常push到明确仓库/分支；最终报告commit与远程核对结果。仅stage本Task已审查文件/hunks，保留用户其他改动，拒绝强推或批量stage未知文件。API key/.env、私有学生资料、缓存、数据库与备份不上传；.gitignore不是秘密审核替代。源码上传不代表公众服务部署；只继续用户已明确授权批次内且依赖满足的下一Task。完整执行约束见[AGENTS](AGENTS.md)和[ADR-013](docs/DECISIONS.md)。

### T06会话撤销与CSRF

身份入口新增会话绑定的内存CSRF与固定Origin写请求检查、当前应用会话退出、执行时重新验证，以及默认关闭的管理员签名认证强度策略。增量认证迁移须显式执行；登录不会赋予真实业务权限。运行与配置见[identity](docs/identity.md)、测试矩阵与实际结果见[T06验收](docs/acceptance/T06_session_csrf.md)。本轮不启用真实管理员MFA/注册或部署。

### T05登录与服务端会话（保留基线）

新的`services.api.app.api.identity:create_identity_app`只挂/v2；未设置`IDENTITY_CONFIG_FILE`默认关闭，不导入DB/JOSE、不连接库、不创建表，认证路由返回503。启用必须verified运行模式、固定Keycloak信任/回调、服务端秘密和已显式迁移的认证库。公开注册关闭，精确issuer/subject预登记启用账户才可以登录；浏览器只有安全不透明Cookie，IdP令牌不保存或下发。前端显式`VITE_APP_MODE=auth`提供登录与会话状态，默认仍原M0演示。

运行配置、迁移、Cookie/代理路径与离线测试步骤见[身份运行说明](docs/identity.md)；接口见[API](docs/api.md)，数据库见[database](docs/database.md)，实际检查与未执行项见[T05验收](docs/acceptance/T05_login_session.md)。无需真实IdP/API密钥可以运行关闭入口、旧演示与离线签名测试。T05验收时未实现注销/CSRF；当前T06增量以上方说明为准，真实管理员MFA/注册/部署仍未验收。

### T04身份供应商边界（历史基线）

D04已选自托管Keycloak；T04建立冻结信任配置、`IdentityProvider`协议和固定合成离线实现，默认disabled、不接入原应用。offline仅development/test，production拒绝；T04的oidc_boundary对象仍只提供授权描述，换码/JWT明确Unavailable且不回退。T05使用独立KeycloakOidcAdapter增量实现协议验证，不把旧离线断言当JWT。issuer+subject精确元组不按email合并，也不授予应用角色。

配置与未决真实tenant/MFA/恢复门槛见[identity](docs/identity.md)、无秘密[配置示例](config/identity/README.md)及[实施前契约与实际验收](docs/acceptance/T04_identity_provider.md)。本轮离线专项131 passed、完整离线606 passed/PG4排除、前端18/typecheck/build通过；既有warning/未执行项及首次失败见验收。专项命令为`.\.venv\Scripts\python.exe -m pytest tests/unit/auth -q`，无需IdP服务/API密钥，不能将模板或离线主体当真实注册/登录。

### T03模式隔离与本机入口验证（历史已完成）

[实施前契约与实际验收](docs/acceptance/T03_mode_isolation.md)记录本轮边界；[ADR-014](docs/DECISIONS.md)说明决定。v2 wire当前`schema_version=v2.t03`；`GET /v2/config`显示app_environment、data_mode/model_mode和应用query_role，business_available/live_available=false，省份/年度/发布版本仍null。`GET /v2/offerings`为空；任何注入候选整体503，合规标签也不能替代真实发布库。query_role不是已配置的PostgreSQL用户或GRANT/RLS。

2026-10-02实际验收：475项离线Python测试通过，4项PostgreSQL排除；前端18项、TS类型、Vite构建、契约生成漂移及原文保护通过。无持久化变更，未做实库/部署；Lint/Python静态类型没有配置入口，明确未执行。完整命令、首次失败与限制见验收记录，不用历史结果替代本轮。

| 环境与数据 | disabled | mock | live |
| --- | --- | --- | --- |
| development/test + demo | 可启动基础 | 可启动基础，显式演示 | 启动拒绝 |
| development/test + verified | 可启动基础 | 启动拒绝 | 启动拒绝 |
| production + verified | 可启动基础 | 启动拒绝 | 启动拒绝 |
| production + demo | 启动拒绝 | 启动拒绝 | 启动拒绝 |

v2只读进程V2_变量，不自动加载M0 `.env`、MODEL_MODE或任何API key。旧DEMO_MODE仅检验冲突，不能选模式。可选V2_DATABASE_URL只做PostgreSQL/已知DEMO身份校验，拒连接身份query覆盖；基础不连接库，未配置也可启动。不要把真实秘密写进示例文件或Git。无秘密配置示例见[production foundation](config/production-foundation.env.example)，该文件不自动加载。

本机验证独立入口（不是业务部署；当前M0前端不适用此入口）：

```powershell
$env:V2_APP_ENVIRONMENT='production'
$env:V2_DATA_MODE='verified'
$env:V2_MODEL_MODE='disabled'
$env:DEMO_MODE='false'
.\.venv\Scripts\python.exe -m uvicorn services.api.app.api.public:create_public_app --factory --host 127.0.0.1 --port 8001
# GET http://127.0.0.1:8001/v2/config、/v2/offerings、/v2/openapi.json
# /v1、/health、未实现私有业务均不可用；已知DEMO Bearer在v2拒401。
```

旧M0入口和seed在production/verified/禁演示配置下启动失败，不能绕过；需在独立演示进程使用下文M0配置。v2 live尚无供应商，明确启动失败；M0 live保持请求503，不静默回退。未认证token不获得私有权限，公开基础读取不是账号认证。D02产品路线及准入基础已定、未成年私有关闭；正式处理责任/告知、账号、真实发布目录、资格/计划和生产数据库权限仍待验收，不能据此开放公众服务。

### T02基础契约（历史已完成）

[历史计划与实际验收](docs/acceptance/T02_v2_contract.md)记录v2.t02的两个只读端点、统一错误/request_id、分页及v1兼容；本轮T03升级模式契约，历史结果不改。目录默认limit20、最大100，无有效cursor；独立schema仍/v2/openapi.json。M0前端/v1继续合成演示。

离线生成及漂移检查命令（验收结果以独立记录为准）：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/generate_contracts.py
.\.venv\Scripts\python.exe -X utf8 scripts/generate_contracts.py --check
```

生成文件为`packages/contracts/v2/openapi.json`和`generated.ts`，不改M0手写契约。生成不读取.env/数据库/资料或调用模型，只使用已有依赖；复杂schema不以any兜底。TS保留字段、必需性、null和literal，数值/长度/额外字段及分页跨字段约束仍由OpenAPI/服务端校验；空查询interface不能由TS强制禁止额外参数。可用`.\.venv\Scripts\python.exe -m uvicorn services.api.app.api.v2:create_v2_app --factory --host 127.0.0.1 --port 8001`运行独立基础子应用，其路径为`/config`、`/offerings`及`/openapi.json`，不提供Swagger/ReDoc；默认M0入口则挂载在`/v2`。此命令是运行说明，本次采用离线TestClient验收，未启动该监听服务。

### 目标目录结构

以下为完整目标布局。`[规划]` 表示目录/文件尚未创建或能力尚未实施，只在对应 Task 中增量建立；其余为现有文件。现有扁平业务模块保留并逐步迁移，不能先全仓重构。

```text
study/
├── AGENTS.md                         # 本轮边界与后续单 Task 开发规则
├── README.md                         # 项目入口、现状、目标布局、M0 运行
├── 升学咨询智能体_开发方案与审查.md    # 原始输入，保持不变
├── Codex_升学智能体_首次开发Prompt.txt # 原始输入，保持不变
├── .gitignore
├── .gitattributes                    # 原输入字节保护、v2生成产物LF
├── .env.example                      # 当前本地 M0 配置，不含生产秘密
├── compose.yaml                      # 当前仅 PostgreSQL 演示服务
├── pyproject.toml
├── pytest.ini
├── requirements.in
├── requirements.txt                  # Python 依赖与哈希锁
├── apps/
│   └── web/
│       ├── package.json
│       ├── pnpm-lock.yaml
│       ├── pnpm-workspace.yaml
│       ├── tsconfig.json
│       ├── vite.config.ts
│       ├── index.html
│       ├── src/
│       │   ├── main.ts
│       │   ├── App.vue
│       │   ├── env.d.ts
│       │   ├── styles.css
│       │   ├── api.ts                # M0 请求；未来 v2 放 api/，渐进迁移
│       │   ├── profileForm.ts
│       │   ├── workspace.ts
│       │   ├── components/EvidenceDialog.vue
│       │   ├── router/               # [规划] 路由及会话入口
│       │   ├── views/                # [规划] 页面组装，避免重复业务逻辑
│       │   ├── api/                  # [规划] /v2 客户端、CSRF、统一错误
│       │   ├── shared/               # [规划] 表单、状态、日期、公共组件
│       │   └── features/             # [规划] 按业务组织组件与 composable
│       │       ├── auth/
│       │       ├── profiles/
│       │       ├── catalog/
│       │       ├── statistics/       # [规划] 历史线/位次与范围比较
│       │       ├── curricula/        # [规划] 按入学届的培养方案
│       │       ├── outcomes/         # [规划] 毕业结果及分母/人群
│       │       ├── eligibility/
│       │       ├── evidence/
│       │       ├── plans/
│       │       ├── tasks/            # 任务进度、容量与依赖展示
│       │       ├── admin/            # sources/imports/reviews/releases 子功能
│       │       ├── privacy/
│       │       ├── feedback/         # 故障与事实纠错入口
│       │       └── qa/               # 条件启用；模型关闭时隐藏入口
│       └── tests/                    # 现有交互测试＋对应功能增量测试
├── services/
│   ├── __init__.py
│   └── api/
│       ├── __init__.py
│       ├── alembic.ini
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py               # M0演示入口；生产/verified拒绝
│       │   ├── settings.py
│       │   ├── database.py
│       │   ├── migrations.py
│       │   ├── models.py
│       │   ├── schemas.py
│       │   ├── seed.py
│       │   ├── catalog.py            # 现有 M0 模块，按需迁移同名包
│       │   ├── eligibility.py
│       │   ├── planning.py
│       │   ├── providers.py
│       │   ├── api/public.py         # T03独立production factory，仅mount/v2
│       │   ├── api/catalog_access.py # T03应用读取策略，无真实发布库
│       │   ├── api/v2/               # 基础factory/router/schemas/errors
│       │   ├── api/identity.py       # 显式身份入口；默认关闭，只挂/v2
│       │   ├── auth/                 # T04接口＋T05登录/会话＋T06撤销/CSRF；资源授权[规划]
│       │   │   ├── __init__.py
│       │   │   ├── schemas.py         # 冻结信任配置与纯身份/上下文契约
│       │   │   ├── provider.py        # T04可替换边界/固定离线供应商
│       │   │   ├── config.py          # T05冻结配置与安全错误
│       │   │   ├── oidc.py            # 固定Keycloak换码/成熟JOSE验签
│       │   │   ├── models.py          # 认证四表；不复用DEMO用户
│       │   │   ├── store.py           # 一次性事务/摘要会话/只读ready
│       │   │   ├── service.py         # 服务端登录/会话轮换
│       │   │   └── router.py          # 安全Cookie与3条HTTP认证路径
│       │   ├── profiles/             # T23 私有画像根与不可变确认版本
│       │   ├── admissions_catalog/   # T11候选关系已验收；公开查询待T20
│       │   ├── statistics/           # [规划] 省线/一分一段/历史投档及可比性
│       │   ├── curricula/            # [规划] 学院专业映射与培养版本
│       │   ├── outcomes/             # [规划] 毕业人群及逐指标口径
│       │   ├── evidence/             # [规划] 原文、定位、版本及范围
│       │   ├── rules/                # [规划] 类型化 DSL 与路径适配器
│       │   ├── planning/             # [规划] 草案、容量、确认、修订
│       │   ├── tasks/                # [规划] 任务依赖与进度事件
│       │   ├── admin/                # [规划] 人工来源登记与导入
│       │   ├── ingestion/            # [规划] 有界 JSON/CSV 校验与导入
│       │   ├── reviews/              # [规划] 核验、原子发布与撤回
│       │   ├── qa/                   # [规划] 可选的受限问答
│       │   ├── providers/            # [规划] disabled/mock/live 可替换接口
│       │   ├── storage/              # [规划] 私有本地/对象存储接口
│       │   ├── privacy/              # [规划] 告知、准入、导出与删除
│       │   ├── audit/                # T10同事务最小审计、封闭日志、显式有界清理
│       │   ├── changes/              # [规划] 发布差异与方案影响
│       │   ├── notifications/        # [规划] 私有站内通知与状态
│       │   ├── observability/        # [规划] 运行指标与请求追踪
│       │   ├── limits/               # [规划] 请求限流与原子配额
│       │   └── jobs/                 # [规划] Postgres job/outbox 与 worker
│       ├── migrations/
│       │   ├── env.py
│       │   ├── script.py.mako
│       │   └── versions/0001_m0.py   # 冻结基线；后续任务新增迁移
│       └── worker.py                 # [规划] 共用单体代码，持久作业时建立
├── packages/
│   └── contracts/
│       ├── index.ts                  # 当前 /v1 契约
│       └── v2/                       # T02 Pydantic/OpenAPI生成与漂移检查
│           ├── openapi.json
│           └── generated.ts
├── config/
│   ├── demo.json                     # 当前演示范围说明
│   ├── identity/                     # T04无秘密占位/离线示例，不自动加载
│   ├── scopes/                       # [规划] 经确认的省份/年份/路径配置
│   └── schemas/                      # [规划] 非秘密配置的验证约束
├── data/
│   ├── fixtures/
│   │   ├── build_demo.py
│   │   └── demo_catalog.json
│   ├── research/
│   │   ├── official_samples.json    # P02历史观察，不导入M0/生产
│   │   └── source_registry_2026.json # T50A候选入口与缺口，不是招生事实
│   └── evals/                        # [规划] 已审核回放案例与覆盖清单
├── tests/
│   ├── backend/                      # 当前 M0 规则、API、持久化回归
│   ├── contracts/                    # 当前 OpenAPI/TS/实际响应一致性
│   ├── research/                     # T50A候选契约及只读校验测试
│   ├── unit/auth/                    # T04离线身份边界；其他纯域仍[规划]
│   ├── integration/                  # [规划] PostgreSQL、事务、作业、恢复
│   ├── security/                     # [规划] 会话、越权、隔离、删除、注入
│   └── e2e/                          # [规划] 浏览器端到端流程
├── scripts/
│   ├── web.ps1
│   ├── verify_originals.py
│   ├── verify_source_registry.py     # 离线只读候选契约校验
│   ├── verify_contract.py
│   ├── browser_smoke.mjs
│   └── generate_contracts.py         # T02离线 /v2 类型生成与只读检查
├── deploy/                           # [规划] 配置产物，不是发布授权
│   ├── containers/                   # web/API/worker 镜像与非 root 运行
│   ├── compose/                      # 隔离预发布的服务编排
│   ├── proxy/                        # 同源 HTTPS 与安全响应头
│   ├── backup/                       # 加密备份、恢复与删除重放
│   ├── monitoring/                   # 指标、告警与维护责任
│   └── runbooks/                     # 发布、回滚、恢复、删除与故障手册
├── .github/workflows/                # [规划] CI（选定 Git 托管后建立）
└── docs/
    ├── requirements.md
    ├── architecture.md
    ├── database.md
    ├── api.md
    ├── tasks.md
    ├── CHANGELOG.md                  # 逐 Task 变更与真实验证结果
    ├── DECISIONS.md                  # 重要决策与实施状态
    ├── data_strategy.md              # 全国真实资料契约与来源策略
    ├── identity.md                   # D04配置、T04边界与真实启用门槛
    ├── acceptance/                   # T01/T02/T50A/E01记录；公众发布未实现
    ├── 01_PRD.md                     # 保留原规格提取文档
    ├── 02_DATA_AND_RULES.md
    ├── 03_ARCHITECTURE_API.md
    ├── 04_MILESTONES_ACCEPTANCE.md
    ├── 05_SOURCES_AND_REVIEW.md
    ├── M0_IMPLEMENTATION_PLAN.md
    └── M0_TEST_REPORT.md              # 保留 2026-09-30 历史结果
```

后端业务包按需设置 `router.py / schemas.py / service.py / models.py`；查询复杂时才加 `repository.py`，不预建空层。表模型从现有 `models.py` 增量移入各域，并保证 Alembic 正确导入。`catalog.py` 与 `catalog/` 等同名迁移必须在所选 Task 内一并调整导入并回归，不能并存后依赖隐式解析顺序。

各目录职责：`apps` 提供用户和审核界面，`services` 承担服务端授权与确定性业务，`packages` 维护跨端契约，`config` 保存非秘密范围配置，`data` 分开保存合成夹具、隔离的公开研究样本和评测资料，`tests` 提供分层验收，`deploy` 记录可恢复运行方式，`docs` 是需求和开发依据。学生附件、真实身份资料、生产秘密、数据库文件和导出不放入版本库或前端静态目录。

T01已完成，实库验收见[独立记录](docs/acceptance/T01_postgresql.md)及[M0报告新增日期](docs/M0_TEST_REPORT.md)。按用户已授权顺序，T50A已独立完成48来源/34地区/238类型单元的候选登记，详见[验收](docs/acceptance/T50A_source_registry.md)；不启动T50后台及其未实施的T11/T13，不自动发布真实事实。

## 当前实现与 M0 运行说明

下面保留 M0 的安装与运行方法；“本次验证/本次使用”均指2026-09-30历史环境。2026-10-01的T01另外执行了4项PostgreSQL实库测试及96项离线回归，见报告新增日期；前端未改，未重跑其检查。

M0 是本地开发与展示的离线垂直样例：确认合成画像 → DEMO 项目 → 确定性资格检查 → 合成证据 → 计划草案。默认范围是一个配置生源省份普通高考本科与英国本科；默认省份浙江只是工程配置，未收录任何真实招生政策。

所有机构、项目、画像和证据均为合成演示数据。DEMO 数值与日期不得用于真实申请。`eligible` 只表示演示规则范围内满足硬条件，不表示录取。没有后补政策证据的缺成绩为 `unknown`。本项目不输出录取概率，不自动提交申请。

当前业务实现为M0，另有T03的隔离v2基础配置和空目录；下面是合成演示运行说明，不能用于production。真实数据、审核后台、模型接入、任务排程仍未实现；爬虫未开发。T02历史结果保留于[旧验收](docs/acceptance/T02_v2_contract.md)；本轮T03结果见上文与新记录。

## 目录与阅读入口

- 原始输入：根目录两份中文文档，内容保持不变。
- [实施前契约与测试计划](docs/M0_IMPLEMENTATION_PLAN.md)、[数据与规则规格](docs/02_DATA_AND_RULES.md)、[测试报告](docs/M0_TEST_REPORT.md)。
- `apps/web`：Vue3 + TypeScript + Vite；`services/api`：FastAPI + Pydantic + SQLAlchemy + Alembic 模块化单体。
- `packages/contracts/index.ts`：共享接口；`tests/contracts`：与后端 OpenAPI 及实际响应比较。
- `data/fixtures`：DEMO 招生机会、规则与原文夹具；`config/demo.json`：示例范围说明。

## 安装依赖

建议 Python 3.12、Node 22.12+ 或本次验证的 Node 24、pnpm 11.19.0。运行时不需要模型 API 密钥；第一次安装依赖或拉取 PostgreSQL 镜像需要网络。安装完成后离线测试不访问网络。

在项目根目录执行 PowerShell 命令：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.txt
pnpm --dir apps/web install --frozen-lockfile
```

本次使用了 Codex 随附 Python 3.12.14 与 pnpm；系统 Python 为 3.10.9，未拿它作为本次验证环境。`requirements.in` 锁直接依赖，`requirements.txt` 锁全部依赖与哈希；前端使用 `pnpm-lock.yaml`。

本机普通终端的 Node 为 16；`scripts/web.ps1` 会优先选择可用的 Codex 随附 Node 24，仅修改当前进程的 PATH。当前工作区可用 `.\scripts\web.ps1 install/dev/test/build`（每次传一个操作）替代对应 pnpm 命令。用 uv 建的 `.venv` 默认不含 pip；可用 `uv --cache-dir .cache/uv pip sync --python .venv/Scripts/python.exe --require-hashes requirements.txt` 安装。

## 默认 PostgreSQL 运行

需要可用 Docker 引擎与 Compose，或自行准备空的 PostgreSQL 数据库。保留现有 `.env`；只在不存在时从 `.env.example` 复制。

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d db
.\.venv\Scripts\python.exe -m alembic -c services/api/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m services.api.app.seed
.\.venv\Scripts\python.exe -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000
```

另开一个终端：

```powershell
pnpm --dir apps/web dev --host 127.0.0.1
```

打开 [本地网页](http://127.0.0.1:5173) 与 [API 文档](http://127.0.0.1:8000/docs)。`/health/live` 报告进程，`/health/ready` 检查数据库。应用启动不自动建表、迁移或覆盖夹具。

## 无 PostgreSQL 时的离线演示替身

SQLite 只作为 M0 离线演示/测试替身，需要明确启用；这不等同验证过 PostgreSQL。PowerShell 环境变量优先于 `.env`：

```powershell
$env:DATABASE_URL = 'sqlite:///./.cache/demo.db'
$env:M0_SQLITE_TEST_MODE = 'true'
$env:MODEL_MODE = 'mock'
New-Item -ItemType Directory -Path .cache -Force | Out-Null
.\.venv\Scripts\python.exe -m alembic -c services/api/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m services.api.app.seed
.\.venv\Scripts\python.exe -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000
```

前端使用相同命令。网页明确显示 DEMO/mock，接口返回 `demo_mode=true`。未取得语言成绩的合成画像可同时演示国内满足条件、英国有证据后补和无依据未知。表单留空表示缺失，不把空值变成零。

## 配置与模型接口

`SUPPORTED_PROVINCE`、`ENTRY_YEAR` 控制支持范围；国内夹具只适用浙江/2027。改变配置不会把事实换省或换年；缺对应省份/年度的国内夹具时国内列表为空。英国夹具不限制生源省份，但继续按身份、课程体系与入学年过滤。`config/demo.json` 是说明文件，实际读取环境变量与 `.env`。

`MODEL_MODE=mock` 默认无需密钥，规则引擎始终独立于模型。`live` 保留可替换 provider 接口，M0 尚未接入实际供应商；请求计划时明确失败，不回退为 mock 内容。可用 `M0_ASSESSMENT_DATE` 固定重放日，否则按运行日期核验后补期限。

本地演示凭据 `demo-alice-token` / `demo-bob-token` 对应两个合成用户，服务端解析身份，客户端不能指定 owner。它们不是正式登录系统，仅限本地合成数据演示。切换用户会清空当前画像、资格和计划；私有 API 对其他用户资源返回 404。

## 检查命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q
pnpm --dir apps/web test
pnpm --dir apps/web build
.\.venv\Scripts\python.exe scripts/verify_originals.py
.\.venv\Scripts\python.exe -X utf8 scripts/verify_source_registry.py
.\.venv\Scripts\python.exe -m pytest tests/research/test_source_registry.py -q
```

PostgreSQL集成测试需要专用空测试库和创建schema权限；每例使用随机schema，只清理自身schema。禁止填用户已有或生产库。设置当前进程变量后执行：

```powershell
$env:TEST_POSTGRES_URL = 'postgresql+psycopg://<test-user>:<test-password>@127.0.0.1:<test-port>/<dedicated-test-db>'
.\.venv\Scripts\python.exe -m pytest tests/backend/test_persistence.py -m postgres -q
Remove-Item Env:TEST_POSTGRES_URL
.\.venv\Scripts\python.exe -m pytest -m 'not postgres' -q
```

未配置URL时四项实库检查跳过；配置后即使普通pytest也会执行它们。T01实际使用新建PostgreSQL16.15专用库，通过4项实库测试和96项离线回归；测试库已关闭。Docker/Compose16.6镜像路径本轮未执行成功，不能据此宣称其通过。实际命令、环境准备、结果与限制见[独立验收](docs/acceptance/T01_postgresql.md)和[M0测试报告](docs/M0_TEST_REPORT.md)。

可选真实浏览器检查：启动上述本地服务后执行 `node scripts/browser_smoke.mjs`，需环境已有 Playwright 1.62.1 与 Edge。本机实际模块路径、8 项检查及截图位置见报告。常规离线单测不需要这两个依赖。

## 技术文档核查

实现参考 [FastAPI 数据库文档](https://fastapi.tiangolo.com/tutorial/sql-databases/)、[Pydantic 模型文档](https://docs.pydantic.dev/latest/concepts/models/)、[SQLAlchemy 2 ORM](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)、[Alembic 迁移](https://alembic.sqlalchemy.org/en/latest/tutorial.html) 与 [Vite 运行环境](https://vite.dev/guide/)。锁定依赖的历史验证见 M0 报告；M0 实施未联网采集招生事实。P02 后续规划轮进行了有限官方研究，保存为独立样本，应用仍不读取真实数据。

T19内部发布契约见[releases](docs/releases.md)：源码/合成实库验收完成，真实发布未开放。

### T33 本人计划与进度工作台

认证页面的计划入口默认折叠。读取确认画像、在项目页实际评估并明确加入准备目标，再选择目标创建草案。按原UTC字符串填写估时/可用时段并分别确认时段与休息；服务端容量ready后仍须最终本人确认及未知期限告知。零工时任务也须逐项声明完成，历史版本只读。默认服务处理关闭，无密钥不会回退到M0。无画像选择可读自己的现有计划，写操作须对应当前确认画像。

本Task源码和专库合成闭环通过，不是正式资料覆盖或公众上线。[页面契约](docs/plan_workspace.md)/[T33命令、失败、图片与未执行记录](docs/acceptance/T33_plan_workspace.md)；运行沿用现有auth模式与T32明确装配工厂，没有新依赖或部署步骤。

### T34 当前内部发布影响服务

仅显式合成test配置启用 `ChangesService`，输入为已存T19 event UUID。业务条件/范围/窗口/撤回通过精确原引用形成独立needs_review轨迹；参考ID/hash变化单独保留，不静默修订或清空完成记录。原T28/T32来源当前有效证明仍适用。

新显式迁移使用 `CHANGES_DATABASE_URL` 和 `python -m alembic -c services/api/changes_alembic.ini upgrade head`；需先已有十三迁移head，启动不建表/seed，不在正式数据库执行本轮合成验收。新增第14独立head/三表/两个关系索引，down/up专项已在随机schema验证。无新增HTTP/UI/worker，T35/36分别后续实施，真实入口恒关闭。详见[契约](docs/changes.md)与[验收](docs/acceptance/T34_changes.md)。

### T35 当前明确修订工作台

已有当前确认画像/新评估/本人明确新草案后，展开修订入口、读取旧历史、审阅差异、独立接受或拒绝。接受仅追加替代关系，新草案仍需T32单独排程与最终确认，原完成不复制；原T32来源失效仍409，有限历史不恢复权限。仅合成test显式启用，真实入口关闭。

独立显式迁移 `REVISIONS_DATABASE_URL` / `python -m alembic -c services/api/revisions_alembic.ini upgrade head`，须十四旧head；启动不迁移/seed。五个API与第九有限契约详见[契约](docs/plan_revisions.md)及[验收](docs/acceptance/T35_plan_revisions.md)。

## T36 显式作业与站内提醒

通知入口默认折叠且偏好关闭；用户明确确认后才开启，已读也由服务端CAS确认。独立notifications factory只有显式合成装配可启用，正式能力仍关闭。迁移为 `services/api/jobs_alembic.ini` 的 `upgrade head`，仅受信维护脚本使用专用测试DSN；应用/worker启动不会迁移或seed。`services.api.worker.run_once(service)` 与 `drain(service,max_steps=100)` 是接收已显式构造JobsService的有限函数，不提供自动轮询、部署或环境凭据CLI。

## T37 模型接口运行边界

新增model_gateway只提供显式构造的内部async端口和离线预算，不提供真实网络供应商或API密钥读取。默认verified+disabled明确MODEL_DISABLED；live明确不可用且原v2启动拒live仍保持。只有demo离线合成mock可验接口，问答HTTP/UI由后续单Task提供。无密钥核心照常使用；真实供应商、地域、数据流、token计费和跨进程持久预算仍需另行审查。

## T38 范围检索离线运行

qa是内部只读端口，默认关闭；没有问答HTTP/UI或真实模型。测试只在明确test/demo与已审批发布合成夹具下构造ScopedRetriever；客户端RequestScope不能传dataset_id，服务器派生当前dataset。无依据返回unknown，日期精确计算未知保留原精度，超限清空全部引用。

离线检查：`.venv\Scripts\python.exe -X utf8 -B scripts/verify_qa_golden.py`；纯专项：同Python `-m pytest tests/unit/qa tests/evals/test_t38_golden.py -q --tb=short`。固定24合成案例不证明真实领域审核。PG专项只接受`T23_TEST_POSTGRES_URL`指向专用loopback127.0.0.1:55438/study_t23_20261003，逐case随机schema，不连接生产；命令与真实失败见T38验收。

## T39 有限公开问答

默认无key且关闭问答，独立服务可用`.venv\Scripts\python.exe -X utf8 -B -m uvicorn services.api.app.api.qa:create_qa_app --factory --host 127.0.0.1 --port 8003`运行；`/v2/qa/context`显示MODEL_DISABLED，`POST /v2/qa/answers`503，不自动连接DB/供应商。没有通过配置打开live的路线。开发Vite `/qa`代理此loopback服务；默认折叠，只有明确展开、检查入口、选择问题类型与提问才发QA请求。

合成test/demo/mock读由离线装配和PG测试显式注入，不提供真实处理开关。只发送明确公开项目范围与固定意图，不发送学生画像/成绩；答案只展示当前证明通过的类型化引用与固定一般建议。未知/超时/额度/引用冲突各自显示，不确认资格或申请。运行测试和局限见[T39验收](docs/acceptance/T39_qa_entry.md)。

## T40 本人资料权利与恢复屏障

独立入口可用`.venv\Scripts\python.exe -X utf8 -B -m uvicorn services.api.app.api.rights:create_rights_app --factory --host 127.0.0.1 --port 8003`查看关闭告知；默认无DB/worker，`/v2/privacy/rights/context`显示disabled，写操作503。没有真实处理启用配置。本Task无新UI（T41）。

测试显式装配业务17条迁移链和业务备份之外的独立ledger链、签名锚点/文件backend；应用启动不建表、不bootstrap、不重放。本人退出阻断导出下载；已受理删除由专用持久worker继续。缺最新台账、锚点或恢复水位未追平时服务拒流量。实际专用pg_dump/pg_restore与文件恢复及限制见[T40验收](docs/acceptance/T40_data_rights.md)。

## T41 本人隐私与资料权利页面

auth模式由SettingsView复用已有隐私告知/用途/共享面板。本人权利默认折叠，明确展开后才读T40能力；正式入口保持关闭。合成测试可独立确认导出/删除，读取受理状态与原JSON；失败、在线完成和责任/备份保留分别说明。

不轮询/自动重试/保存浏览器资料；刷新后凭本人受理UUID追踪，服务器校验当前归属。核心用途撤回不会隐藏本人权利入口；删除受理立即关闭私人工作区，退出/收起清内容且不取消后台删除。实际命令与局限见[T41验收](docs/acceptance/T41_privacy_workspace.md)。

## T42 通用 Docker 配置（源码完成，未验证）

用户选择先做通用配置，实际大陆城市/供应商/手续待定。入口与服务范围、秘密文件输入、固定镜像摘要、显式单链迁移和有限回滚见[运行说明](deploy/README.md)；配置为[独立Compose](deploy/compose.generic.yaml)，不修改根M0 compose。

只提供production foundation配置/空目录，API不持有数据库密码；auth静态界面和TLS代理仅本机回环访问，私有业务、worker、真实模型均关闭。所有测试/Lint/TypeCheck/Build/预检、镜像和容器演练未执行（用户要求）；未提供实际运行通过结论。参见[契约](docs/deployment.md)/[T42源码记录](docs/acceptance/T42_deployment.md)。任务按调整后的源码范围已完成，真实地域适配、权限、TLS、恢复、监控及公众发布门槛保持。

## E02 当前正在运行的合成演示

[打开本机演示](http://127.0.0.1:5173/)；[API文档](http://127.0.0.1:8000/docs)。2026-10-13实际PG专用库和8项Edge流程通过，服务保持运行；这是M0合成闭环，真实全国资料/公众服务仍未启用。[本次真实命令、结果与限制](docs/demo_startup_20261013.md)。

## 浙江2026真实省线本地查询

[打开查询页](http://127.0.0.1:5174/)选择浙江2026省线并明确查询，已核普通类第一段494、第二段266、特控594，其他字段缺失保持未知。来源/人工确认/原字节及本次PG和页面真实验收见[运行说明](docs/zhejiang_2026_cutoffs.md)。只供本机参考，不是学校录取线/个人资格，正式公众发布保持关闭。
