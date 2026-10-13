# T50A · 2026年全国高校来源候选登记

日期：2026-10-01；状态：已完成。T01已完成后独立执行；只建立人工候选登记文件和离线校验，不实现T50后台，不解除T11/T13依赖。

## 数据契约（实施前）

文件`data/research/source_registry_2026.json`使用`study.research.source-registry.v1`。顶层包含task_id=T50A、target_reference_year=2026、registered_as_of、timezone、candidate_only=true、is_synthetic=false、nationwide_collection_complete=false、reviewed_fact_count=published_fact_count=imported_institution_count=0、personalized_scope保持单省高考+英国、sources/regions/coverage_units。期望高校/专业/事实总量与覆盖率为null，不将来源数当数据覆盖。

每个source：稳定内部id、publisher/title、实际url/hostname、source_role（navigation/authority_entry/institution_directory/admissions_entry/curriculum_entry/outcomes_entry）、region_keys、dataset_types、pathways、identity_basis_url/locator；observed_period_label/time_basis/source_year（未知为null）、year_mapping_status（unverified/explicit_gregorian）和year_basis_url；access_status（page_read/partial_page/linked_not_opened/search_result_only/source_unavailable）、checked_on/failure_reason；review_status=review_required、publication_status=not_released、rights_status=not_reviewed、review_owner=null、automated_fetch_enabled=false、affects_eligibility=false、snapshot_status=not_captured、snapshot_sha256=null、is_synthetic=false、notes。

原始URL允许官方HTTP导航候选，但不会猜改HTTPS或启用获取；URL不得含凭据/本地地址。官方归属依据和本轮访问状态分开。source_year仅在正文明确公历年且有定位/依据时填写；其他原始学年/毕业届保持标签，未映射不填2026。就业旧毕业届不因目标年2026变更。页面可读不表示资料适用年/许可/审核已经完成，获取失败不写成尚未公布。只登记链接及短定位，不保存全文快照，不生成哈希。

地区沿用P02的34内部键（大陆31省级地区+香港/澳门/台湾），不是已核验行政区代码；兵团只作子范围，不增加省级分母。每region含key/name/kind/ordinary_gaokao_applicability/pathways/authority_source_ids/institution_directory_source_ids。

coverage_units按34地区×7类型：institution_directory、province_cutoff、score_distribution、admission_statistics、admission_policy、curriculum、outcomes。每单元region_key/dataset_type/pathway/candidate_source_ids/missing_reason/expected_total=null/coverage_ratio=null；用于登记后续工作缺口，不记录事实数值。大陆考试类型按生源地区；机构/培养/就业按机构地域；港澳台普通高考省线及一分一段not_applicable，本地招生路径另登记。学院/专业培养与就业没有学校级来源时not_collected，不用省考院充当其依据。

## 修改范围

新增上述JSON、`scripts/verify_source_registry.py`、`tests/research/test_source_registry.py`和本验收文件；同步README/AGENTS/requirements/architecture/data_strategy/tasks/CHANGELOG/DECISIONS。不改API/数据库字段、应用、迁移、夹具、依赖、P02样本、原始规格和T01验收记录。

新增ADR仅记录文件候选登记与后台分开及向后接入约束，不新增生产架构。来源登记所需有界联网研究与离线校验分别记录。

## 验收与测试用例

1. 34地区唯一，大陆31+港澳台3；七类型缺口清单完整，所有引用存在；中央名录不冒充港澳台目录，机构所在地不冒充生源省份。
2. 可复核的官方身份线索、真实链接及本轮访问状态；失败/未读取准确记录。2026仅目标年，不要求伪造本年文档或整年已采齐。
3. 来源全部候选/待审/未发布，审核发布/导入0，获取/资格关闭，许可待审、hash为空；未知分母不算覆盖率。
4. 离线验证器只读文件、不访问网络、非法输入非零退出，不修改原登记；不存在任意URL获取接口。
5. 负例：重复ID/地区、悬空引用、错误地区或港澳台高考适用性、非法URL/hostname、额外事实/学生字段、bool冒充年/数量、无依据年映射、假hash、启用获取/资格/发布、未知分母填覆盖率、读取失败没有原因。
6. 运行登记校验及相关pytest，原文与文件范围/历史保护、文档链接/Task/日志/ADR同步；未改前后端业务，不重复应用全套/PG/浏览器/Build，以未执行原因记录。

## 结果

候选登记验收完成；T50仍未开始，不声称全国高校事实已采齐或发布。以下记录真实命令/访问结果。


## 本次交付与实际检查（2026-10-01）

已保存48来源候选、34地区及238资料单元。其中166格有入口候选、66格未登记、6格港澳台普通高考省线/一分一段不适用。166不是已采集事实数，不换算覆盖率；期望总量为null，正式审核/发布/高校行导入均0。缺口主要是各校/学院/专业培养与毕业结果，省考院不会填充这些格。

| 实际命令 | 结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe -X utf8 scripts/verify_source_registry.py` | 最终退出0；48 sources、34 regions、238 units、166 units_with_candidates，正式计数0/分母null。只读执行前后文件hash一致；CLI不做网络请求。 |
| `.\.venv\Scripts\python.exe -m pytest tests/research/test_source_registry.py -q` | **101 passed，退出0，无warning**。测试阻止网络；包含非法CLI非零与文件不变、重复JSON键、地区/角色/引用/适用性、旧届与当地学年、危险URL、额外字段和禁止发布/获取/hash等边界。 |
| `.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py` | 退出0，两原始输入未变。 |
| `.\.venv\Scripts\python.exe -m py_compile scripts/verify_source_registry.py tests/research/test_source_registry.py` | 退出0，语法有效；不是Lint/完整静态类型检查。 |
| `.\.venv\Scripts\python.exe -X utf8 .cache/t50a_validate.py` | 退出0：13份UTF-8文档、93个本地链接、11条ADR；34地区×7类型、来源状态/年度/正式计数、Task/日志/ADR与文件范围/历史保护一致。8旧文档改+4新增，73范围外文件不变。P02、T01日志/报告/验收、既有67主Task卡及原始输入保留。 |
| `git -c safe.directory=D:/Projects/study -c core.quotepath=false status --short` | 退出0，仍未跟踪；未重置/提交或改全局Git。 |

未执行：应用全套Unit/Integration/PG、前端Unit/Type Check/Build、浏览器、部署/性能/恢复；没有改相关业务/数据库/配置，T01实库结果单独保留。Lint/静态类型工具未执行，无已配置入口；py_compile不冒充这些检查。没有新增依赖，脚本只用stdlib。

## 有界官方来源研究（与离线测试分开）

31大陆入口分别只打开一次，无链式抓取、重试循环或绕过。结果7正文可读（上海/江苏/福建/山东/陕西/甘肃/新疆），2外壳（浙江旧路径/湖南），16超时，2HTTP错误（安徽502、湖北503），4工具不可访问（河南/重庆/贵州/青海）。这些是当前工具观察，不能据此断言网站永久宕机或政策未公布。HTTP原链接保留，不把工具自动HTTPS显示当迁址证据。山东页脚明确限制未经授权复制/转载/镜像，许可仍待审、获取关闭。

全部48来源本轮状态：16 page_read、3 partial_page、29 source_unavailable。可读只是登记页正文，不代表已核验其链接附件/年度/规则/数据全集。各source记录原URL、发布者身份线索、短定位、检查日、失败原因、原年标签。未捕获全文字节，snapshot_sha256=null。

中央[历史渠道导航](https://www.moe.gov.cn/jyb_xwfb/moe_1946/fj_2020/202012/t20201223_507093.html)原用途为2021研考、发布于2020；官方搜索能找到表，正文复取重定向循环，只作历史主体线索。省级端点本轮单次访问结果补充了当前线索，不把研考渠道变成2026高考依据。[阳光高考历史导航](https://gaokao.chsi.com.cn/gkxx/zc/moe/202106/20210617/2078308929.html)只得到框架/脚本挑战；[2026大陆高校名录](https://www.moe.gov.cn/jyb_xxgk/s5743/s5744/202606/t20260618_1441074.html)浏览超时，普通读取异常，附件/行未取得；[专业目录](https://www.moe.gov.cn/srcsite/A08/moe_1034/s3882/202604/t20260427_1434931.html)重定向循环。官网搜索元数据只用来发现入口，不补招生数字或宣称附件已读。

[香港教育局院校页](https://www.edb.gov.hk/en/edu-system/postsecondary/local-higher-edu/institutions/index.html)和招生导航正文可读，年份未知；[澳门本地院校页](https://portal.dsedj.gov.mo/webdsejspace/site/studyinmacau/tc/campus-information.html)部分正文，院校行未提取。[澳门2026内地保送参与校入口](https://appl2.dsedj.gov.mo/ChinaUEnrollment/UPublic/EnrollmentBrief.jsp)及[内地升学路径指引](https://portal.dsedj.gov.mo/webdsejspace/site/ees/zh-TW/home.jsp?con=union-admissions-office)正文明确2026，只登记相应路线，不计澳门机构目录。[台湾目录](https://udb.moe.edu.tw/ulist/)是114學年度，[数学招生入口](https://srecruit.moe.edu.tw/mathsys/)及其官方链接[分发委员会](https://www.uac.edu.tw/)混115/116等原学年，2026映射未核验。

有限备用入口的失败也保留于本次研究记录：香港institutions短链仅外壳，改读官方完整链接；澳门四校/保送id80092/80073页面仅框架、gov.mo/zh-hant/news/1234635超时；台湾jbcrc主页Internal Error及申请页502、MOE招生资讯导航复取超时、cacportal仅框架。未把这些失败替换成成功或用搜索摘要补数值。

海南2026单专业培养页复取超时；北京石油化工学院2023届报告发布元数据可读、PDF超时，仍没有国内实际就业数字。原毕业届2023与发布日期2024分开，未改为2026届。没有名额/分数/日期要求/学分/就业率事实导入，不接入M0或资格。

## 过程中失败与修正

1. 首次CLI退出1：招生入口不能包含province_cutoff的角色映射过窄；按契约扩充考试资料兼容范围，并将浙江省级公告登记为authority_entry。
2. 第二次CLI退出1：港澳台authority_source_ids被强制单一authority_entry；允许有当地路径匹配的admissions_entry，同时继续拒绝培养/就业越界引用。最终CLI及101测试通过。
3. 文档更新辅助命令两次退出1，分别为换行和目录树缩进匹配；适配后成功，没有覆盖用户文件或修改范围外文件。
4. 只读交叉审查发现中央历史导航备注仍称31端点未打开；已纠正为本轮各打开一次，再次运行CLI通过。结构通过不能代替原文/许可/招生领域审核。

## 变更与剩余门槛

新增JSON、stdlib验证器、101项边界测试和本记录；更新README/AGENTS/requirements/architecture/data_strategy/tasks/CHANGELOG/DECISIONS八文档。API/database规范、应用、旧迁移、DEMO夹具、依赖、P02及T01验收未改，相关当前现状已同步。

全国高校行名录、每校/学院/专业资料、2026完整统计和真实就业结果尚未导入；失败入口、本年映射、主体/代码、许可与正式审核、负责人及完整覆盖门槛仍待解决。香港/澳门目录年份和台湾原学年映射未知；学校培养与就业来源多数缺失。T50后台依赖T11/T13未实施。本轮T50A止于候选登记，CHANGELOG/tasks已同步，不自动开展下一批。
