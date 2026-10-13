> 由原始开发方案对应章节提取；原文件保留。M0 范围以 M0_IMPLEMENTATION_PLAN.md 为准。

# 02 数据与规则规范

## 1. 数据采集优先于自由检索
先由管理员建立来源清单，逐个站点启用。入口包括省级考试机构、阳光高考及高校招生官网；英国包括院校课程页、国际资格页、语言要求页和UCAS流程页。搜索引擎只能帮助发现候选网址，不能把摘要当成已核验招生事实。

权威性按字段判断：省内投档和招生计划使用适用省级主管来源；课程细则使用适用院校/专业官方来源；统一申请平台的流程日期使用平台来源。相互矛盾时保留两份证据并交人工处理，不能规定某一个网站永远覆盖其他全部字段。

来源登记至少包含publisher、domain、入口URL、owner、数据类型、适用范围、抓取方式、条款/robots审核状态、启用状态、复查频率、最近成功与失败状态。官方来源与允许自动抓取是两个独立属性。[S3,S4,S8]

## 2. 采集流水线
登记与权限审查 → 有界抓取 → 保存原始版本与哈希 → 版面/表格解析 → 按schema抽取候选字段 → 程序校验 → 关键字段人工复核 → 发布事实/规则 → 检索索引与受影响方案更新。

优先使用授权API/下载/人工导入，其次公开HTML；只有必要时用浏览器处理动态页面。PDF先读文字层与表格结构，只有图片页且无其他可用来源时才单独OCR并要求人工复核。不得将OCR低置信数字直接写进已核验录取表。

抓取设置超时、每域名并发上限、速率限制、重试退避、缓存与条件请求。禁止绕过验证码、登录与付费访问；抓取失败显示失败，不能拿陈旧内容充当新内容。网站导航或广告变化不一定是招生字段变化，原文hash用于追踪，业务字段diff用于触发审核。

在许可允许范围内保留原始快照；不得默认再分发整份招生册。个人录取公示名单不在采集范围。仅需汇总分数与公开政策。

## 3. 三层保存
原始文档层：原URL、下载/抓取时间、标题、原文、附件、哈希、语言与版面信息。
候选事实层：抽取内容与证据定位，状态draft/review_required/conflicted。
已核验层：经审核发布的事实、适用范围、审核者、版本以及规则引用。向量数据库只存可检索文本与元数据，不能成为数值和资格的唯一真相来源。

## 4. 核心实体
Institution：机构唯一ID、名称别名、国家、官方来源。
Program：学位、课程/专业、校区、授课语言；不同校区/衔接路径分别表示。
AdmissionOffering：Program + entry_year/intake + admission_pathway + applicant_category；国内扩展省份、科类、批次、专业组。代码按年度有效，不能假定跨年不变。
SourceDocument/DocumentVersion/Evidence：来源、不可变版本、原文定位与证据片段。
AdmissionFact：事实键、类型化值、单位、条件、作用范围、有效期、证据和审核状态。
AdmissionRule：受约束的规则表达式、阶段、有效范围、证据、审核者和版本。
HistoricalOutcome：录取年度、统计类型、省份/科类/批次/组/专业、分数、位次区间、计划与录取人数等可用字段。
StudentProfileVersion/Assessment/Achievement：私有画像版本、实得/预测成绩、特长证据。
PlanVersion/PlanItem/Task/Review/ChangeEvent：方案、依赖、执行状态、变更与人工决定。

## 5. 通用字段
业务时间：entry_year、intake、application_cycle、published_at(可空)、valid_from/valid_to(按可知信息)、data_as_of。
系统时间：fetched_at、last_http_check_at、last_verified_at、recorded_at、superseded_at。
证据：source_url、document_version_id、document_sha256、evidence_id、locator、source_language、review_status。

locator对网页可用section/字符位置；对PDF可用页号、区域、表名、行与列；对导入表须保留原文表头、脚注和原始行的映射。翻译文本保留原文链接，条件判断以核验后的原语言事实为依据。

缺失状态分开：not_collected、not_published、not_applicable、conflicted、review_required、source_unavailable。不得用一个null解释全部，也不得以模型自报置信度替代来源审核。

## 6. 国内录取数据
唯一键至少包含：admission_year、province、exam_system、subject_category/combination、batch、institution、group_or_program、pathway、statistic_type。statistic_type枚举至少分省控线、院校/组投档最低分、专业录取最低分、平均分、预估参考值。

同时保留score_scale、minimum_score、rank_start/rank_end、rank_definition、plan_count等字段。并列分数可能对应位次区间，应原样保留，不伪造精确名次。分数线本身不是先验录取概率。比较历史位次前检查制度、组内专业构成和计划变化；重大变化标记不可直接比较。官方建议将成绩位次、一分一段表与历年录取信息一起分析，不能只按高于去年多少分推荐。[S5]

无当年官方一分一段表时，不把校内/模拟考分数硬映射成真实省位次。历史成绩只提供条件性的参考情景。制度变更和专业组重组必须建立人工审核的映射记录。

## 7. 国际课程信息
保存accepted_qualifications、各科条件、学术与语言成绩、语言小分、有效期及其参考日期、豁免条件、考试/作品集/面试、推荐信、材料、申请渠道、轮次、费用币种与周期、申请/平等审理/奖学金/补材料/接受offer等不同日期。

UCAS明确各课程和院校设置各自要求，国际资格要向院校核实；因此不能统一假设“某高考分数=某GPA=某英国资格”。[S3]

ApplicationRequirement与EnrollmentRequirement分开。英语成绩未取得时，只有官方允许后补才可生成conditional；没有官方依据就是unknown。最低入学要求、典型offer、录取者统计分布分别建模，不混用。

## 8. 日期结构
每条日期保存event_type、原文、local_date、local_time(可空)、timezone(IANA，可空)、utc_instant(仅可唯一换算时)、precision、入学年、适用课程/轮次、证据、可否晚申请、审核状态。

不要用固定UTC偏移替代Europe/London等地区时区。只提供日期时可以展示日期并安排用户选择的内部提醒，但不能声称官方在23:59截止。平等审理日已过不自动意味着不能申请，应继续检查最终申请阶段与具体课程政策。[S4]

## 9. 资格规则引擎
规则是审核后的声明式数据，不让模型运行任意代码。白名单操作符：all、any、not、exists、eq、in、gte、lte、date_before、valid_at。显式类型、单位和缺失值语义。模糊原文如“原则上”“通常”“视情况”不能未经领域审核变成绝对淘汰条件。

输出必须拆开：eligibility、competition_context、preference_fit、data_quality；不能一个“匹配度89”代替。
- eligible：给定申请阶段、资料与规则范围内，已核验硬条件满足；不表示被录取。
- ineligible：有明确证据的适用硬条件不满足；列出原因、阶段与可能的替代路径。
- conditional：官方允许某项要求后补或后续满足，并列出条件与时限。
- unknown：关键输入/规则缺失、冲突、过期或不可核验；必须补充或人工处理。

采用三值逻辑处理原子谓词。所有条件真才可eligible；明确必须且为假的条件支持ineligible；未知不能当false或true。条件满足期限和申请阶段由适配器处理。

学生特长优先用于兴趣和材料匹配。只有适用官方规则明确规定了特长资格/替代条件时才参与硬判断，且禁止把普通兴趣当竞赛资格。

## 10. 推荐与情景分析
先资格核验，再比较历史竞争区间、预算、学科兴趣、地区与准备时间。不把预算不足定义成学校招生资格不合格，应归入学生约束或情景可行性。

让用户显式选择权重或优先顺序，提供多个取舍方案，说明排除与待核验理由。国内可展示历史位次参考与不确定性；海外优先展示资格、材料差距与课程适配，不强行套用国内冲稳保。

what-if仅表示在其他条件不变且假设输入成立时，规则/预算/工时的变化，不代表未来成绩、offer或因果效果。预算保留学费、生活、申请考试费、币种、单年/全程口径和汇率假设。未经确认的奖学金不得从基础预算中扣除。

第一版不做录取概率。未来若增加预测，需要合法获取有代表性的申请总体及录取/拒绝结果、明确定义预测对象与时点、校准和分组评估；仅有最低录取分、成功案例或录取名单不够。

## 11. 学习任务
仅总分无法定位具体知识薄弱点。基础版以学科成绩变化、学生/教师确认的问题和目标条件规划；更细诊断必须接入对应测评证据，不能虚构错误原因。

Task字段：目标差距、任务类型、estimated_hours、available_slots、dependencies、earliest_start、hard_deadline_id(可空)、user_target_date(可空)、acceptance_criteria、owner、status、plan_version。

每周安排不超过学生确认的可用时数；考虑课程与考试冲突，共用准备任务去重。先做可解释的依赖排序与容量检查，复杂优化后续再加。时间不够时明确冲突，给出减少目标、调整路径或延长周期的选项，而不是压缩休息或保证提分。

形成“目标—差距—行动—测评/完成记录—复盘”闭环。新成绩只触发修订草案，已确认计划不静默替换；已完成任务保留。通知用outbox、幂等键与偏好配置防重。
