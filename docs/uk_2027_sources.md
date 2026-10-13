# 英国2027本科首批官方资料

Task：BATCH-UK-2027-INSTITUTIONS-01。2026-10-13用户确认剑桥大学、曼彻斯特大学与2027本科入学；专业尚未指定。

## 本批数据契约与范围

本批只完成两校官方来源的有限人工采集和研究候选登记。保存机构原名、官方域名、申请/课程/国际资格入口；每个来源单独保存访问时间、HTTP结果、实际标题、真实原文大小与SHA256、年度适用证据、用途和缺口。请求目标年度2027与原文明确的入学年度分开；抓取时间不是政策生效时间。无法取得成功原HTML时，原文hash、正文大小和来源适用年为null，记录失败原因。

候选统一为review_required/not_released，不作为资格、计划或正式目录输入。学校级来源不能替代program、College、校区、路径、申请身份、entry_year/intake完整范围；学校/来源内部键不是UCAS官方代码。没有选择课程时，具体成绩、语言小分及后补依据、费用、截止时间、培养版本、专业就业数据均留空并分别说明原因。

范围：data/research/uk_2027_institutions_sources.json、本文件、独立批次报告，以及AGENTS/README/tasks/CHANGELOG/data_strategy/requirements的当前状态同步。不新增框架、数据库表、API或前端功能，不变更旧迁移、固定浙江三条协议、M0及原始研究文件。复用既有研究层，后续按具体课程再进入T11/T13/T18/T19治理链；正式来源管理员、使用权、独立审核仍未落实。

## 本批完成条件

1. 两校与2027目标明确登记，专业/College未选择不生成通用学校录取条件。
2. 只访问列出的有限官方页面，无站内递归、验证码/登录绕过或自动持续抓取。
3. 实际原HTML成功响应才产生原文hash；失败与检索线索分别记录，不能把搜索缓存冒充原文。
4. 来源年度和缺项可追溯；没有原文明确的2027适用性时保留未知。
5. 原文快照只存本机.cache，不随Git再分发；仅小型元数据、必要短摘录及人工释义保存到研究文件。
6. 文档与任务状态同步，当前Task审阅后PRIVATE普通提交推送。本批无程序实现，不执行旧用户已禁用的测试/Lint/TypeCheck/Build或验收脚本；网络取证是此次资料收集操作，不算应用测试。

## 本批结果

采集已完成。结构化文件见[两校来源候选](../data/research/uk_2027_institutions_sources.json)，实际操作见[批次报告](acceptance/data_batches/BATCH_UK_2027_INSTITUTIONS_01.md)。两校、8个来源均取得HTTP200原HTML；正式审核0、发布0，不计算全国或全专业覆盖率。

| 学校 | 采集的官方入口 | 本批年度口径 |
| --- | --- | --- |
| 剑桥大学 | [官方学习入口](https://www.cam.ac.uk/study-at-cambridge)、[网站版本及版权](https://www.undergraduate.study.cam.ac.uk/about-this-site)、[国际资格](https://www.undergraduate.study.cam.ac.uk/international-students/international-entry-requirements)、[课程/College条件](https://www.undergraduate.study.cam.ac.uk/apply/before/entry-requirements)、[UCAS申请](https://www.undergraduate.study.cam.ac.uk/apply/how/ucas-application) | 国际资格和UCAS页明确2027；网站默认2027且允许另行声明。其他页自身没有明确年度时不借用默认说明补成具体课程2027规则。 |
| 曼彻斯特大学 | [2027课程目录](https://www.manchester.ac.uk/study/undergraduate/courses/2027/index.htm)、[国际本科要求](https://www.manchester.ac.uk/study/international/admissions/undergraduate-application-process/undergraduate-entry-requirements/)、[中国大陆说明](https://www.manchester.ac.uk/study/international/country-specific-information/china-mainland/) | 目录明确2027；国际要求及中国本科相关段未明确2027。中国页其他段的排名/研究生信息年份不能替代本科政策年份。 |

两校当前资料均要求按具体课程核验。剑桥China章节的高考政策存在College差异。曼彻斯特现行中国大陆本科说明不接受高考直接进入学位课程，并说明普通高中路线的预科要求；本批不把未标年度的说明当2027专业硬规则，也不据此给任何学生输出ineligible。

剑桥UCAS页列出多数2027申请人的截止背景：2026-10-15、18:00英国时间；Foundation Year和部分成熟学生课程/College另有期限。研究文件保存范围和例外，UTC为空、不参与排程、不表明后补或晚申请许可。

## 原文与使用权

实际快照和获取元数据在本机`.cache/uk2027-source-20261013/`，未提交Git。每源保留原URL/最终URL/取得UTC时间/真实SHA256；证据字符定位指向已明确规范化方法的HTML文本，不是伪造原始字节偏移。获取UTC落在2026-10-12晚间，与本地2026-10-13日期一致。

此前浏览工具对剑桥页返回403；后续本机普通httpx GET全部成功，未进行浏览器伪装、验证码/登录绕过或重试。历史失败与最新原文成功分别登记，不把检索缓存当原HTML。网站页面存在更新可能，hash只证明本次捕获版本。当前未建立自动定期采集或刷新；未来重采需新记录，不能将旧快照时间写成最新。

剑桥网站版权页列出免事先许可用途的限制；公众或商业复用许可尚未建立。两校正式来源负责人、robots/自动采集许可、人工领域复核、公众发布均未完成。只保存必要短摘录和研究释义，不在仓库再分发原HTML、不联系学校或申请任何服务。

## 补充资料优先级

1. 根据学生明确意愿选少量具体本科课程，取得官方课程/UCAS代码、College/校区/入学年映射；预科与本科直入单独建档。
2. 逐课程采集学术资格、单科、英语小分/有效期/豁免、考试/面试/作品集、材料、申请与入学条件；后补政策要独立证据与期限。
3. 分别采集申请、补材料、奖学金、接受offer等日期及适用人群/例外；精度与时区明确后再用于计划。
4. 2027课程费用按fee status、币种、周期采集；住宿/生活费与奖学金分开，资料未知不估总成本。
5. 培养资料按2027入学届保存学制、学位、课程结构、实践及毕业/专业认证；毕业结果保留真实毕业届、观察期、专业/学科粒度、样本/回应率/分母，营销就业方向不能替代实际统计。

每项在研究文件data_gaps中有null及原因。本批没有读取学生资料或确定学生专业，没有录取概率、资格转换、申请提交、真实模型调用。下一批明确专业范围及正式治理责任后再审核入库和接入查询；目前查询页仍仅显示已有浙江批准数据。
