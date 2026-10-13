# 全国真实资料策略与数据契约

2026-10-14 SEARCH-SELECT-01身份搜索仅从当前正式发布的真实学校/专业投影读取，不能由名称猜/哈希造UUID、把研究两校/省线或DEMO当真实名录。内部实体ID与官方招生/UCAS/学科代码分别定义；选择不证明当届培养/毕业覆盖，入学届/毕业届与身份来源招生年独立，未适配学院/学科不代填。默认无正式目录返回缺口、不推断官方未公布；总量/覆盖未知，后续真实名录来源/审核/许可与数据映射仍需逐批落实。源码交付与未验证限制见[说明](school_program_search.md)。

2026-10-13新增[年度更新请求调度](annual_source_updates.md)：每年11月1日09:00 Asia/Shanghai，仅按已配置目标生成待采集/待审核的维护请求。国内考试年与英国入学年通过显式offset分别设定，source_evidence_year仍未知，不从旧URL替年、不将旧snapshot改为最新、不覆盖批准批次。当前无实际自动采集/候选/审核发布，默认关闭且所有运行验证未执行。年度维护不能代替source复查、公布/勘误/撤回事件；缺目标年度资料保持not_collected/source_unavailable等具体原因，不能推定not_published。单体持久请求设计不授权原文商用复用、真实学生处理或资格更新。

2026-10-13新增海外首批[BATCH-UK-2027-INSTITUTIONS-01](uk_2027_sources.md)：用户确认英国本科剑桥/曼彻斯特2027入学；[研究候选](../data/research/uk_2027_institutions_sources.json)记录八官方页实际获取/真实byte hash与独立来源年度，不改变国内2026资料目标。学校身份/目录、国际资格/中国本科说明、申请渠道日期分别建档；专业/College未选不生成通用要求。正式审核/发布0，使用权未建立、自动采集关闭、资格不使用，原文仅本机.cache；尚无正式入库/页面。本批补充课程代码映射、语言后补、材料/考试、各类日期、fee status/费用、当届培养与真实毕业统计的缺项清单；未知不填补。

日期：2026-10-01；P02研究基线保留，P03同步2026年全国高校范围。本文是规划，另保存P02少量联网核验的[官方研究样本](../data/research/official_samples.json)。P03没有新增采集；样本尚未经过产品发布审核，没有导入应用数据库，不用于 M0、资格判断或公众展示。当前所有功能代码、DEMO 夹具、迁移和离线运行方式保留。

## 1. 覆盖目标与实施边界

用户要求补充真实的全国地区分数线、学校录取分数线、学院/专业培养方案和实际就业情况。全国资料查询是新增数据建设目标；个性化资格检查继续一个配置生源省份普通高考本科＋英国本科。全国参考资料可查不等于全国资格规则已经支持，也不等于全部学校/专业都有就业数据。

大陆普通高考覆盖按 31 个省级地区登记；香港、澳门、台湾分别登记课程/招生路径，不能造出它们的“普通高考省线”。新疆兵团等发布主体作为子范围记录，避免与省级覆盖重复计数。英国课程、资格和毕业结果单列。区域键在研究样本中只是内部标识，正式编码来源及版本由 T50 核验。

D08已部分确定：资料目标年度2026，高校地域范围包括中国大陆、香港、澳门、台湾，招生体系分别建档。仍待明确首版是否必须全量、具体批次/学校/专业/层次、审核与使用权负责人及投入。按2026目标分批建设规划；首版个性化范围不自动扩大。每个导入批次限一个地区×年度×资料类型，或少量学校×专业×入学届；不得把全国所有高校一次性写成可单会话完成的Task。

### 1.1 2026年与全国高校的口径（P03确认）

全国高校是机构地域覆盖维度；名录和办学层次按各地区官方范围分别登记，本科项目是高中升本科分析重点。非本科层次保留机构登记及不适用状态，不扩展专科/成人个性化路径；首批校区/项目/专业/层次清单及审核分母仍待细化。各地区名录分别核验，不能用只覆盖大陆的名单代替港澳台名单，也不能由现有34地区登记声称已收齐高校。

| 数据类型 | 2026目标的含义 | 缺失与历史处理 |
| --- | --- | --- |
| 大陆省线、一分一段、计划、投档/终录取 | exam_year/admission_year=2026，逐生源省份、科类、批次/轮次/组/专业 | 未公布/未取得分别记录；2025记录仍是2025，不补作2026 |
| 高校身份、学院/专业及收费等 | 2026适用的官方名录/版本/条件，保存有效期与校区/层次 | 不造学校数量或把目录来源发现当全量导入；旧版本保留历史 |
| 培养方案 | 优先核验适用于entry_cohort=2026的官方版本，teaching_year单列 | 2026级未公布不自动套2025级，适用沿用须有审核依据 |
| 实际毕业结果 | 优先2026实际采集日可取得的官方报告 | graduation_cohort、调查窗口/观察期、发布日期各自真实；2026发布不等于2026届，缺2026届不推算 |
| 港澳台招生资料 | 地区体系/渠道、原始当地学年/历法标签和已核验的2026映射分别保存 | 未核验年映射明确未知，不套大陆普通高考省线；没有统一跨体系分数换算 |

高校/校区所在地与candidate_province分开：北京高校在浙江招生的记录仍是浙江生源口径，不能只收高校所在地省份的线。机构资料可全国查，不表示全国个性化资格适配已完成。英国本科路线继续单列，具体intake仍待确认；P02研究样本原年/届保留，全部未审核发布，正式覆盖分子为0。旧年招生/培养观察不能填补2026相应类型缺口；旧毕业届就业报告可经正式审核成为背景，但不改成2026届。本次规划日为2026-10-01，后续每个批次记录其实际采集截至日，不伪造全年数据已完成。2026历史资料目标也不延长申请期限，资格仍按实际评估日核验适用周期、已审核政策和有效期，过期/撤回要求不复用。

## 2. 应补充的数据及优先级

| 优先级 | 资料 | 决策价值与限制 |
| --- | --- | --- |
| P0 | 官方学校名录、学院组织、专业目录及历年代码映射 | 分清大学内学院与独立“学院”机构；同名、改名、合并、停招及校区不能自动合并 |
| P0 | 省级控制线/分段线、考试总分与加分口径、一分一段 | 区分本科控制线、特殊类型线和分段线；累计人数只支持明确定义的位次范围 |
| P0 | 省份×年份×批次×轮次×院校/专业组/专业的投档与最终录取统计 | 学校没有跨地区、跨组通用的一个录取分数；投档最低分与最终录取最低分分别存 |
| P0 | 当年招生章程、招生计划、选科/单科/语言/体检条件、调剂与专项限制 | 当年已审核硬条件才可成为资格规则；历史分数只供比较，不能算录取概率 |
| P0 | 培养方案、入学届、专业分流、课程、学分/学时、实习/毕业及转专业规则 | 教学学年与入学届分开；宣传中的培养目标不等于实际培养结果 |
| P0 | 就业质量报告/毕业结果：去向、升学、行业/职业、调查人数与时间 | 必须标明学院/专业/学科/学校层级；没有专业数据就显示缺失或实际聚合范围 |
| P1 | 学费/住宿费、币种/周期、办学校区、学制、学位及证书发放主体 | 年份、项目/校区和本地/国际生条件分开；未经审核不计算总成本 |
| P1 | 计划名额、实际录取/入学人数、退补计划、转专业机会与限制 | 分清计划数、执行计划数、录取数与入学数；制度存在不等于保证能转 |
| P1 | 专业认证/办学资质、有效期、合作办学、毕业要求与实习机会 | 认证范围需精确到项目及年份；学校层级认证不能自动复制到全部专业 |
| P1 | 英国资格路径、国际生费用、英语条件、申请渠道及日期 | 当前课程与过往毕业统计时间不同；不可用旧条件替代当前要求 |
| P2 | 经许可的雇主/岗位需求、行业统计、毕业生匿名调查补充 | 仅作为另列的劳动力市场背景；岗位广告不是该校实际就业，不采集个人履历 |

不新增学生家庭资产、健康明细或就业个人身份等画像字段来填充资料库。学校公开统计与学生私有数据继续隔离；地区、家庭偏好、预算由学生按必要性确认，不能从来源访问或地理位置推断招生身份。

## 3. 公共契约

正式数据继承既有 source/document_version/evidence/review/release 流程。各记录至少含：

- 身份与范围：稳定实体 ID、原始名称/代码、适用地区、招生路径、考试体系/科类、批次/轮次、项目/专业组、校区，以及粒度。
- 独立时间轴：发布/更新日期及精度、采集时间、考试/招生年度、入学届、教学学年、毕业届、调查窗口/统计截至日、复查时间。未知留空，不由 URL 文件名猜日期。
- 事实与口径：原始字段名、规范指标类型、数值/单位/统计方法/分母、原文定位与短摘录、缺失原因、版本及冲突关系。
- 来源与治理：官方原始 URL/发布主体、许可与再发布状态、原文快照及真实字节哈希、审核人/时间/结论、不可变 release、撤回/替代关系、is_synthetic。

研究 JSON 使用 study.research.official-samples.v1，是可读研究记录而非生产导入契约；只记录已知日期，精确抓取时刻未留存则 retrieved_at=null。未保存原文时 snapshot_hash=null、snapshot_status=not_captured，不制造哈希。所有记录 is_synthetic=false，但 review_status=review_required、publication_status=not_released；“来源属于官方”与“事实已经人工审核可发布”是不同字段。

### 3.1 分数线与一分一段

ProvinceCutoff：province、exam_year、exam_system、subject_track、batch/stage、round、pathway、cutoff_kind、raw_label、score、score_scale、bonus_policy、evidence_id。分段名称按原文保留，不强行转换为本科线。数值未给出总分则 score_scale=null；不能按别省惯例填 750。

ScoreDistribution：上列考试范围＋score_band、count、cumulative_count、cumulative_direction、tie_policy、candidate_population、source_definition。同分人数构成区间；没有个人同分排序和加分口径时不返回一个伪精确位次。不跨改革/科类套用位次。

AdmissionObservation：province、exam_year、institution_id、local_institution_code、group/program_code、mapping_version、scope_level、batch、round、plan/pathway、subject_requirements、bonus_policy、metric_kind、value/unit、evidence。metric_kind 至少分 filing_min_score、final_admission_min_score、final_admission_mean_score、filing_min_rank、final_admission_min_rank。同分处理列需另存 raw_definition，不自动变成单科门槛。PlanQuota 单独标 initial/executed/remaining/final_admitted/enrolled；来源表题“录取人数”若须知定义为执行计划数，必须按须知规范化并保留原标题。

### 3.2 学院、专业与培养

Institution 与 AcademicUnit 分开；官方全国学校代码、校内学院 ID、国家本科专业代码、省年招生专业/组代码及英国 provider/course/UCAS code 不能互作主键。ProgramCodeCrosswalk 带来源、年份、有效区间、校区及匹配状态；模糊同名只能产生待审核候选。专业组可包含多个专业，不能自动展开到所有年份。

CurriculumVersion：institution/program/academic_unit、entry_cohort、teaching_year、version、degree_awarder/type、duration、campus、total_credits、graduation_requirements、effective_status、evidence。CurriculumModule：code、name、required/elective、credits、hours、year/term、prerequisites、practice/internship、evidence。官方未分配专业/学院映射时保持 unmapped；学分不把网页排版错误猜成数值。未来模块标 provisional，不自动视为下一入学届已确认。

### 3.3 实际毕业结果

OutcomeReport 元数据与每条 OutcomeMetric 分开。每条指标都有独立 population_id：graduation_cohort、degree_population、aggregation_level、institution/college/program/subject_group、study_mode、residency/international_filter、survey_period/cutoff、months_after_graduation、method、eligible_population_count、published_sample_count、response_rate及其分母定义、rounding/suppression、source_scope。

metric_kind 分 employment_rate、destination_implementation_rate、work_or_study_rate、further_study_rate、industry_share、occupation_share、earnings_median/mean 等；“毕业去向落实”“工作或升学”不改名为纯就业率。薪资带币种、周期、税前后、名义/实际值、区间定义与方法；未核验周期不显示为月薪/年薪。回应率不能反算精确受邀人数。未公布专业统计不能用学校或学科统计填入专业字段，实际聚合层级必须随结果返回。不同指标可能用不同毕业届、样本及分母，不能复用。

就业统计描述已报告人群，不代表对个人就业或收入的保证；学校报告、抽样调查、行政税务数据、行业背景分别标方法和来源局限。跨币种、观察期、学位或国家的人群不做直接排行榜，未取得有日期的汇率也不自动换算。

## 4. 来源策略与本次实际研究

以下是P02的有限研究历史，P03只同步范围，不新增观察或把旧年/届重标2026。

优先发布原文：省级考试院/招生主管部门；院校招生网站与教务/学院培养方案；院校就业质量报告；教育部学校/专业目录；英国院校课程页与 Discover Uni/HESA 方法资料。阳光高考作为官方汇总/导航补充，保留实际原发布者。商业排名、自媒体、论坛及招生宣传不能替代硬要求或实际就业依据。

| 已读取的有限样本 | 已核验内容 | 重要限制 |
| --- | --- | --- |
| [浙江 2026 普通类分数线](https://www.zjzs.net/art/2026/6/25/art_155_12467.html) | 一段 494、二段 266、特殊类型 594 | 一段不是通用本科控制线；历史 2026 不能当 2027 项目要求 |
| [北京 2025 本科普通批投档 PDF](https://www.bjeea.cn/uploads/soft/250720/178-250H0201058.pdf) | 北京大学 01/02/03 组投档最低分 686/697/687 | 只适用北京该年/批次/组；不是全校全国终录取线；最近复取超时 |
| [海南大学 2025 级计算机培养方案](https://cs.hainanu.edu.cn/info/1066/12900.htm) | 专业 080901、4 年、工学学士 | 网页学分原文“16 5.5”解析有歧义，规范学分留空 |
| [海南大学 2026 级计算机培养方案](https://cs.hainanu.edu.cn/info/1066/13080.htm) | 158.5 学分、4 年、工学学士 | 只适用 2026 级；首次读取成功，后续复取超时 |
| [海南大学 2026 招生章程](https://bkzs.hainanu.edu.cn/info/1003/5647.htm) | 收费表中的计算机科学与技术 4600 元/生/学年 | 只记录该年标准，不猜下一年和住宿/总费用 |
| [北京石油化工学院 2024 级培养方案](https://www.bipt.edu.cn/pub/xinxi/bkjy/pyfa/733e57a8149d4117b7dc5eb8b71d180a.htm) | 080901、4 年、工学学士及两门课程学分/学时 | 只对应 2024 级，不复制到别校/别届 |
| [Sussex 计算机课程](https://www.sussex.ac.uk/study/undergraduate/courses/computer-science-bsc-hons) | G400、3 年、2027-09 开始 | 所列模块对应 2026/27 教学年，2027 入学培养模块尚不能据此确认 |
| [Discover Uni 该课程统计](https://www.discoveruni.gov.uk/course-details/10007806/53726/FullTime/) | 工作或升学 90%；另有薪资中位数 GBP 30000 | 前者该课程、2022–23 届、20 人；后者全校全日制计算机学科课程、2021–23 届、15 人；均观察毕业后 15 个月，周期/税前后未核验 |
| [北京石油化工学院 2023 届就业报告发布页](https://www.bipt.edu.cn/xxgkai/de2442e6881f45c18a8a660a36f4fce9.htm) | 标题及 2024-01-05 发布日期 | [正文 PDF](https://www.bipt.edu.cn/docs/2024-01/601794b8b6ec4bf89b610c4177dd70d3.pdf)访问失败，全部就业数值未采集，不引用搜索摘要 |

本次取得 14 条研究观察（包括只有元数据的就业报告），尚无国内可核验的实际就业数值。上述 PDF/网页初读与复取状态分别记录；缺原文快照及正式复核，不能发布。完整字段、来源和 34 地区研究覆盖登记见 JSON，未采集地区显示未采集，HK/MO/TW 普通高考类型显示不适用。

[教育部 2026 全国学校名单](https://www.moe.gov.cn/jyb_xxgk/s5743/s5744/202606/t20260618_1441074.html)的统计范围不含港澳台；不能以此证明这些地区学校覆盖。[2026 专业目录](https://www.moe.gov.cn/srcsite/A08/moe_1034/s3882/202604/t20260427_1434931.html)仅完成来源发现，未核验附件全文，不能声称已导入目录。[Discover Uni 方法](https://www.discoveruni.gov.uk/about-our-data/)说明调查时点与小样本处理；[2023/24 届 GO 最新结果](https://www.graduateoutcomes.ac.uk/results/)的发布不改变课程页仍显示较早毕业届的事实。

## 5. 获取、审核、发布与更新

先人工有界导入，延用 T13–T19 的来源登记、文件隔离、证据定位、双状态审核/发布与撤回。不为研究改造现有 M0；真实记录只能进入未来 verified 公共资料域。来源登记同时核验官方域名/发布权限、使用/再发布范围、自动获取约束；可公开访问或允许机器人并不自动构成全文再发布许可。优先保存获准的结构化事实、定位、链接和必要短摘录，不镜像整站或转载整份培养方案。

T66 仅规划可选有限白名单连接器：管理员触发、预登记 URL、HTTPS、安全 DNS/重定向与 SSRF 检查、文件/MIME/页数/大小上限、速率/超时/有限重试、持久作业、幂等与可暂停。遇登录、验证码、付费或禁止获取时记录 source_unavailable，转人工或停止，不绕过；不做全网爬虫或学生/毕业生个人履历采集。自动提取只生成候选，绝不自动发布或生成资格规则。

人工审核至少复核：来源及许可、原文数值/定义、地区/年度/科类/批次/轮次、实体代码映射、毕业届/人群/分母、适用期、缺失与冲突。首次发布固化 release/version/hash；改版建立新版本，保留历史，不用“最新值”覆盖不同届数据。两来源冲突并列待审核，不取更有利值。

更新由事件和日历双驱动：年度名录/计划/省线/投档阶段、各入学届培养方案、各毕业届报告；复查周期由数据负责人按来源发布节奏确定。新年份未公布显示 awaiting_publication，旧年份仍可作为标年历史查询；当前硬要求过期/撤回后不得继续用于资格。连接器失败需对管理员告警并显示最近成功读取/审核时间，不能静默沿用旧事实声称当前有效。

## 6. 覆盖、缺失与可比性

覆盖单元是 region×year/cohort×dataset_type×pathway×scope_level。分别记录 discovered/read/parsed/reviewed/published 数量、失败原因和已知总量/总量来源版本。总量未知时 denominator=null，不计算“100%覆盖”；名录覆盖不等于该校所有专业培养/就业覆盖。研究样本 reviewed=0、published=0，不能出现在正式覆盖率分子。

缺失采用 value=null＋missing_reason，至少区分 not_published、not_collected、source_unavailable、parsing_ambiguous、suppressed、review_required、conflicted、not_applicable、not_recorded、unmapped。零是来源明确的零，未知不能填零，也不能由模型估算补齐。百分数用 percent，人数用 persons，分数用 points；所有数值保留原始标签与精度。

可比性返回 comparable/limited/not_comparable/unknown 及 reasons。comparison_assessed 标记是否实际比较；未请求时为 false，comparison_status=null、reasons=[]，不增加第五种比较结果。跨年须核对考试改革/满分/加分、批次/路径、科类、专业组成员、招生名额、分数/位次定义；跨就业指标须核对聚合层级、学位/学习方式/人群、毕业届、调查观察期、方法、分母和薪资定义。缺关键字段为 unknown；方法或对象不同为 not_comparable；不能把无法比较的数据拼成单一排名。比较服务不输出录取概率、模型预测收入或录取/就业承诺。

## 7. 分批交付、测试与未解决事项

新增 T50–T67 全部未开始，详见 [tasks](tasks.md)。数据域迁移、导入、只读 API、页面和可选连接器逐 Task 实施；生产安全与发布仍依赖原任务。每个地区/年度或学校/届批次用 T67 的模板单独建子 Task，并给定源清单、范围、已知分母及审核责任人。

离线验收用小型获准摘录/手写边界夹具，不在单测中访问真实网站：分段线不转本科线；投档/终录取/计划定义不混；同分位次区间；跨年代码/专业组变化；2025/2026 培养不混；排版歧义/null；就业与升学不同；学校/学科数据不冒充专业；响应率不反算分母；薪资周期未知；冲突/撤回/小样本；名单覆盖与资料覆盖分开；真实资料不能进入 M0；历史分数不改变资格四态。真实批次另有人工原文抽查与权限/许可记录，不能仅以测试通过代替领域审核。

尚未完成：全国2026目标范围完整采集、国内就业数值、正式学校/专业代码全集、来源使用权审批、人工发布及所有新功能；更早年份仅保留历史研究，不作为首批全量目标。P03也没有进行应用回归、迁移或部署，不购买数据、不联系机构、不发布或继续功能Task。


## 8. T50A：2026全国高校来源候选文件登记（2026-10-01）

本节是P02/P03之后的实施，保留原14源/14观察原文件及上文研究历史。用户授权T01之后独立建立[source_registry_2026.json](../data/research/source_registry_2026.json)；不是T50后台或事实批次导入。目标2026、大陆31省级地区+港澳台3地区、七类型238单元；每格记录来源候选或not_collected/not_applicable，期望事实总量/覆盖率均null，正式审核/发布及高校导入均0。

来源的官方身份线索、实际访问状态、原始年份/学年、许可/审核分别记录。31省级入口先由[教育部历史渠道表](https://www.moe.gov.cn/jyb_xwfb/moe_1946/fj_2020/202012/t20201223_507093.html)发现：原用途为2021研考渠道，发布2020，不能成为2026高考规则或域名当前性证明。本轮有限端点核验保留结果；未打开/失败/主体变更待核验均明确记录，不擅自改HTTPS、不将查不到写成未公布。

[2026教育部名单入口](https://www.moe.gov.cn/jyb_xxgk/s5743/s5744/202606/t20260618_1441074.html)只登记大陆候选，附件/行未取得。[香港教育局院校页](https://www.edb.gov.hk/en/edu-system/postsecondary/local-higher-edu/institutions/index.html)可读但未明确2026版本；[澳门院校资讯](https://portal.dsedj.gov.mo/webdsejspace/site/studyinmacau/tc/campus-information.html)只取得部分正文；[台湾114学年度目录](https://udb.moe.edu.tw/ulist/)保留原学年，2026适用映射未知。澳门保送内地名单是招生路径来源，不是澳门机构名录。

只有正文明确公历年并具定位才记录source_year；其他未核验年份为null，不从URL或页脚猜。台湾115学年度/混合116消息不整体映射2026。海南单专业2026培养入口复取失败，其他地区培养/就业来源多未登记；省考院不替代教务/就业发布主体。[北京石油化工学院2023届报告发布页](https://www.bipt.edu.cn/xxgkai/de2442e6881f45c18a8a660a36f4fce9.htm)只提供元数据，PDF读取失败，不采就业数值、不改毕业届。

全部source待审/未发布、许可待审、review_owner未知、自动获取及资格影响false。未保存原文快照，hash=null；目录行/学校数/分数/名额/学分/就业率没有导入。checked_on是登记或访问/线索检查日期；linked_not_opened表示端点未访问，不解释为健康检查成功。sources数、地区数、缺口格数可精确报告，但不计算事实覆盖率。

离线执行`python -X utf8 scripts/verify_source_registry.py`和相关pytest；验证器拒绝额外字段、重复/悬空引用、错误地区、bool年份/计数、危险URL、假hash、误启获取/资格/发布和未知总量覆盖率。校验通过只证明候选文件契约，无网络可达/使用权/本年事实审核保证。完整命令、访问失败和剩余门槛见[验收](acceptance/T50A_source_registry.md)。
