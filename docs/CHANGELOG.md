# 项目变更日志

## PRIVACY-PUBLISH-01 · 源码公开前隐私脱敏候选

- **日期／Task ID**：2026-10-14／PRIVACY-PUBLISH-01，进行中，发布方式待确认。
- **修改目的**：按用户新要求审阅隐私、修复后公开源码，保留原工作及私有历史。
- **修改文件**：4份home脱敏文档（M0_TEST_REPORT、E01、T05、T06）；AGENTS、README、tasks、CHANGELOG、DECISIONS、.gitignore及新增source_publication说明。
- **新增内容**：明确原镜像／全refs检查、误报复核、脱敏注释、私有材料ignore与待选发布方式。
- **修改内容**：8处个人home前缀换为占位符；原记录含义保留。源码受众目标更新，真实业务门槛保持。
- **删除内容**：新候选不复制原私人提交邮箱／旧Git历史；没有删除任何原文件／提交／远程ref。
- **Bug修复**：无应用行为修复，应用／迁移／契约／锁／数据字节未改。
- **检查结果**：原镜像Gitleaks实际exit1／18项，逐项确认均业务常量或合成输入，未发现该候选中的真实凭据；全历史PII与当前脱敏候选审阅已执行，所查真实类别剩余0。新提交元数据／候选扫描待创建后补录。
- **未执行**：应用Unit／Integration／浏览器／Lint／TypeCheck／Build／CI／导入／部署／数据库／凭据探测；用户未恢复这些检查，隐私扫描是本轮明确授权。
- **已知问题**：仓库改名及公开管理方案待选择，两原repo仍PRIVATE，不宣称已完成公开或绝对无未知泄露。

本文件从 P01 起启用统一记录。每次代码修改必须追加条目，即使改动很小；文档治理也记录。记录日期采用项目时区 Asia/Hong_Kong。无新增、删除或 Bug 修复时写“无”，不省略字段。

每条必须含日期、Task ID、修改目的、修改文件、新增内容、修改内容、删除内容、Bug 修复、测试结果、已知问题。测试记录实际命令、结果与未执行原因；状态和验收与 [tasks](tasks.md) 一致。重要决策见 [DECISIONS](DECISIONS.md)，开发规则见 [AGENTS](../AGENTS.md)。

历史补录只依据既有记录，不推断提交、执行命令或未记载的改动。M0 历史实现与检查以 [M0 测试报告](M0_TEST_REPORT.md) 为准；本文件不补造 M0 的逐项修改日志。

## SEARCH-SELECT-01 · 学校/专业身份搜索与级联选择

- **日期**：2026-10-14。
- **Task ID**：SEARCH-SELECT-01。
- **修改目的**：按用户要求替代手填UUID/对象标识，缺失不造，仍不测试，文档后PRIVATE保存。
- **修改文件**：27路径，完整清单见[交付记录](acceptance/SEARCH_SELECT_01.md)。
- **新增内容**：独立reference.directory.1/两GET/正式当前T20身份投影、SQL过滤去重/有界分页/当前证明，默认None；手写TS/client/controller/共享原生级联选择及用途/父资料条件pin，ADR-061和运行边界说明。
- **修改内容**：两reference factory增加默认空的受信reader注入，两培养/毕业页改从完整已选对象取正确id/ref；学院/学科无字典禁用；API/架构/数据策略/工作台及任务文档同步。原数据客户端/查询/Scope/旧T20/生成契约/M0/表/迁移保持，无新依赖。
- **删除内容**：按用户要求移除培养/毕业UI自由UUID及subject_ref输入，不保留手填后门；原后端数据查询协议保持。
- **Bug 修复**：新源码静态审阅对齐base64url/q trim/字段上限/DEMO空格拒绝、父子/country/proof/水位及旧上下文回调清理；关键词Enter增加中文组合输入守卫。本Task小范围保护，没有运行证据或任务外重构。
- **测试结果**：仅源码/文档/Git内容阅读和独立静态审阅。Unit/Integration/浏览器测试、Lint、TypeCheck、Build、compile/import、SQL/HTTP/生成/校验/CI/分页撤回/异步/移动/服务重启均未执行（用户要求）；不借用T20或旧UI通过记录。
- **已知问题**：正式目录未装配，当前无真实选项；培养/毕业仍无数据，英国研究不可发布；学院/学科/官方代码别名及完整覆盖未完成。新后端需重启/受信reader装配，搜索/分页/版本/取消/构建效果未验证；证明只用于身份选择，不是长效授权。本批源码上传后停止。

## UI-OPT-01 · 演示与参考工作台界面优化

- **日期**：2026-10-13。
- **Task ID**：UI-OPT-01。
- **修改目的**：按用户要求优化UI，检查并记录其他优先改进；仍不运行测试。
- **修改文件**：16路径，完整清单见[交付记录](acceptance/UI_OPT_01.md)。
- **新增内容**：共享展示token/可读字号/焦点/主要44px控件、状态派生四步/处理中提示、筛选外已选提示；参考分组查询/分数卡/原生证据展开与短读屏状态；后续名录/模式入口/审核调度页面优先项。
- **修改内容**：8前端Vue/CSS的版式与措辞，演示证据焦点恢复/卸载迟到保护复用现有组件模式，未知期限/生源范围不推断官方状态；原API/client/query/业务控制器/数据/权限/四态/确认及旧迁移保持，无新依赖或重要技术方案改变。
- **删除内容**：无功能删除；省线原表格展示改卡片，技术hash改原生折叠展示，全部原文/来源/复核字段仍可查看。
- **Bug 修复**：本Task相关未知期限误称未公布、筛选隐藏选择无提示、dialog焦点/迟到打开及整证据atomic播报风险在源码层修正，未做运行验证；不重构任务外逻辑。
- **测试结果**：仅源码/文档/Git内容和旧截图基线阅读；Unit/Integration/浏览器测试、Lint、TypeCheck、Build、校验/CI、新截图/对比度/移动/键盘演练全部未执行（用户此前“不用测试”保持）。旧E02/浙江成功不代表新UI通过。
- **已知问题**：视觉/行为/构建未验证，不能宣称WCAG或移动验收通过；旧省线表格/hashes浏览器选择器未来需适配。真实项目名录/培养/毕业事实、英国发布及年度worker仍未接入，未为补界面造数据；本批仅源码保存后停止。

## SCHEDULE-ANNUAL-01 · 年度更新请求调度源码

- **日期**：2026-10-13。
- **Task ID**：SCHEDULE-ANNUAL-01。
- **修改目的**：按用户确认每年11月1日09:00 Asia/Shanghai生成待采集/待审核批次；仍不测试，文档同步后PRIVATE上传。
- **修改文件**：23路径，完整清单见[交付记录](acceptance/SCHEDULE_ANNUAL_01.md)。
- **新增内容**：闭合配置/年度目标与纯planner、维护CLI plan/tick/run、显式独立PG两表/head与不可变请求/完整批次、年度唯一键/配置冲突及有界退避；默认关闭示例与操作文档，ADR-060。
- **修改内容**：tasks记录源码完成/运行未验证；同步README/AGENTS、需求/架构/数据库/数据策略。原API/前端/M0/浙江三条/17业务链及ledger/旧jobs/T66/依赖锁保持，无新包依赖。
- **删除内容**：无；新迁移拒绝自动降级删表。
- **Bug 修复**：仅本Task静态审阅修正新JSON CHECK缺键NULL绕过，用IS TRUE并绑定字段/列；不宣称SQL实测通过，无任务外重构。
- **测试结果**：仅源码/文档/Git内容阅读与审阅。Unit/Integration/浏览器测试、Lint、TypeCheck、Build、import/compile、校验/CI、新DB/角色/迁移/CLI/worker/并发/故障演练全部未执行（用户再次明确“不用测试”）。没有使用任何历史通过结果；未验证清单见交付记录。
- **已知问题**：定时任务尚未启用或运行，新DB尚未建立；实际获取/候选/年度证据/来源许可/独立审核/发布仍未接入。只请求4项维护目标，不是全国全专业覆盖；年度一次不能保证招生期间最新；配置hash变化拒同年覆盖，失败计数仅本进程。源码上传后停止。

## BATCH-UK-2027-INSTITUTIONS-01 · 首批英国两校官方资料研究登记

- **日期**：2026-10-13。
- **Task ID**：BATCH-UK-2027-INSTITUTIONS-01。
- **修改目的**：按用户新增海外资料要求及确认的剑桥/曼彻斯特2027本科范围，完成有限官方来源收集。
- **修改文件**：九路径：data/research/uk_2027_institutions_sources.json、docs/uk_2027_sources.md、docs/acceptance/data_batches/BATCH_UK_2027_INSTITUTIONS_01.md、AGENTS.md、README.md、docs/tasks.md、docs/CHANGELOG.md、docs/data_strategy.md、docs/requirements.md。
- **新增内容**：两校身份/官方入口和八份实际HTML获取元数据、真实hash/短摘录/文本定位、来源年度/日期范围与例外、11类补充资料缺口及本批报告；原文/cache辅助采集工具不提交。
- **修改内容**：本批已完成有限研究候选登记；专业未选、正式审核/发布0，原不测试和真实处理门槛保持。没有数据库/API/前端/迁移/技术栈/重要决策改变。
- **删除内容**：无。
- **Bug 修复**：无；保留浏览工具403与后续本机200的分别记录，不用检索缓存伪造原文hash，未修改任务外代码。
- **测试结果**：`.venv/Scripts/python.exe -X utf8 -B .cache/uk2027_capture.py`、同命令运行`.cache/uk2027_register.py`均exit0，八官方HTML实际200/提取成功；这是本批收集操作。Unit/Integration/浏览器测试、Lint、TypeCheck、Build、验收校验/CI/PG/API/页面查询均未执行（用户原不用测试；本批无应用实现）。Git源/PRIVATE和当前Task内容审阅完成，实际操作详见批次报告。
- **已知问题**：仅八端点研究，非所有专业/英国全覆盖；专业条件、费用/培养/实际就业未采，曼彻斯特相关本科政策年度未知；版权/商业公开复用和正式负责人/领域审核/发布未完成。未接入正式DB/查询/资格，源快照只本机、不随Git分发，本批停止。

## BATCH-ZJ-2026-CUTOFF-01 · 首批真实省线本地闭环

- **日期**：2026-10-13。
- **Task ID**：BATCH-ZJ-2026-CUTOFF-01。
- **修改目的**：按用户指定浙江和3条本地确认完成2026官方来源核验、入库、页面查询。
- **修改文件**：34路径，完整清单见[批次验收](acceptance/data_batches/BATCH_ZJ_2026_CUTOFF_01.md)。
- **新增内容**：source原字节/真实hash、3真实研究事实与确认/适配链，独立4表迁移/维护CLI/SELECT-only local factory、TS分支与来源/缺口renderer、运行说明和ADR-059。
- **修改内容**：reference统计页默认浙江2026省线但显式查询，仅该资源可显示local真实数据；其他资源/旧empty/M0/17链/ledger/十二generated不改，任务完成后停止。
- **删除内容**：无；只清理本次新建随机验证schema，不删原数据。
- **Bug 修复**：本Task源码审阅补batch UTC、完整三记录/固定来源校验及新执行hash对应关系；没有任务外重构或覆盖用户文件。
- **测试结果**：官方取证/PG迁移/导入/用户确认approve/重导exit0；8项独立PG/HTTP+8实际Edge通过/page_errors=[]，原M0ready/网页200；完整回归/Lint/TypeCheck/Build/CI/Docker未执行（原用户要求保留，实际闭环验证限本Task）。真实命令见验收。
- **已知问题**：只浙江2026普通类3条/捕获版本；满分/加分/timezone/全国分母未知。当前公开复用许可unknown，正式身份/运营/公众发布及其他数据未完成，不给真实学校编造录取线，不算概率/自动申请；原HTML/DB/秘密不随Git保存，新机器需实际快照/权限。

## E02 · 实际启动合成演示与核心验证

- **日期**：2026-10-13。
- **Task ID**：E02。
- **修改目的**：按用户明确要求实际启动M0并确认核心流程。
- **修改文件**：AGENTS.md、README.md、docs/tasks.md、docs/CHANGELOG.md、docs/demo_startup_20261013.md；运行缓存/PG/秘密/结果不提交。
- **新增内容**：独立本地PG16.15运行环境、loopback API/Vite进程和新日期核心报告；复用已有M0浏览器检查但另存输出。
- **修改内容**：E02状态已完成；用户有限恢复启动/核心检查，其他不用测试/生产关闭保持。应用/迁移/依赖/夹具未改。
- **删除内容**：无。
- **Bug 修复**：无应用改动；本次辅助启动脚本等待后台子进程树卡住，改仅等待pg_ctl自身，保留PG数据后续成功启动。
- **测试结果**：实际PG迁移head0001_m0/首次seed2机构7证据4项目9规则、重复0；API ready与网页200；Node/Edge既有8项检查exit0/page_errors=[]；数据库只读核对exit0。Docker版本读取失败/Engine管道缺失；完整回归、Lint、TypeCheck、Build、Docker和后续功能未执行（本次授权仅启动/核心验证），详细实际命令见报告。
- **已知问题**：本机服务未安装开机自启；Docker仍不可达。M0合成显示不代表真实招生事实/正式身份/公众发布或后续简化功能已验；源码仓库不含运行数据库/私有配置。

## T67 · 简化源码交付

- **日期**：2026-10-13。
- **Task ID**：T67。
- **修改目的**：单批候选审核清单和缺项阻挡判定；完成本批后停止。
- **修改文件**：services/api/app/statistics/batches.py, data/fixtures/reference/DEMO_batch_2026.json, services/api/app/outcomes/schemas.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T67_20261012.md, docs/acceptance/data_batches/DEMO_2026_cutoff.md, docs/acceptance/SIMPLIFIED_BATCH_20261012.md, docs/reference_workspace.md。
- **新增内容**：单批候选审核清单和缺项阻挡判定；完成本批后停止。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：候选人群观察日期拒时间戳/datetime隐式转日期；当前批次字段审阅补明确日历日期边界。P05原日志22项笔误，本批实际23个剩余Task另记纠正；最终README/AGENTS停止范围文字同步，普通追加文档提交不改写已保存commit。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：真实单批导入/原文/许可/独立审核/发布与撤回均未完成；原规划PG/运营/质量门槛保留，本批未执行任何检查。

## T66 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T66。
- **修改目的**：默认禁用的固定来源连接器请求契约。
- **修改文件**：services/api/app/ingestion/connectors/__init__.py, services/api/app/ingestion/connectors/policy.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T66_20261012.md, docs/connectors_minimal.md。
- **新增内容**：默认禁用的固定来源连接器请求契约。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：未选实际来源/许可，DNS/重定向SSRF防护与实际获取/重试/作业未实现，live恒关闭。

## T65 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T65。
- **修改目的**：可达的毕业届、统计层级和指标缺口页面。
- **修改文件**：apps/web/src/features/outcomes/OutcomesView.vue, apps/web/src/features/reference/client.ts, apps/web/src/features/reference/ReferenceView.vue, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T65_20261012.md, docs/reference_workspace.md。
- **新增内容**：可达的毕业届、统计层级和指标缺口页面。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：仅空结果/局限说明，无真实指标展示或页面测试/类型/Build验证。

## T64 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T64。
- **修改目的**：可达培养入学届查询与当届缺口页面。
- **修改文件**：apps/web/src/features/curricula/CurriculaView.vue, apps/web/src/features/reference/client.ts, apps/web/src/features/reference/ReferenceView.vue, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T64_20261012.md, docs/reference_workspace.md。
- **新增内容**：可达培养入学届查询与当届缺口页面。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：当前只空培养查询，未展示真实版本/课程/证据或执行界面/类型/Build检查。

## T63 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T63。
- **修改目的**：可达的全国统计只读查询页和有界空数据客户端。
- **修改文件**：apps/web/src/features/reference/client.ts, apps/web/src/features/reference/query.ts, apps/web/src/features/reference/ReferenceView.vue, apps/web/src/features/statistics/StatisticsView.vue, apps/web/src/main.ts, apps/web/vite.config.ts, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T63_20261012.md, docs/reference_workspace.md, docs/architecture.md。
- **新增内容**：可达的全国统计只读查询页和有界空数据客户端。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：无真实数据可展示或页面交互/类型/Build验证；目前仅空查询，未接生产部署。

## T62 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T62。
- **修改目的**：按请求层级、毕业届和对象的空结果查询。
- **修改文件**：services/api/app/api/reference_outcomes.py, services/api/app/api/reference.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T62_20261012.md, docs/api.md, docs/reference_api.md。
- **新增内容**：按请求层级、毕业届和对象的空结果查询。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：没有真实结果reader/上级汇总或PG发布查询，items为空，不提供实际就业结论。

## T61 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T61。
- **修改目的**：明确专业UUID与入学届的空培养方案查询。
- **修改文件**：services/api/app/api/reference_curricula.py, services/api/app/api/reference.py, services/api/app/api/reference_contract.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T61_20261012.md, docs/api.md, docs/reference_api.md。
- **新增内容**：明确专业UUID与入学届的空培养方案查询。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：同factory的ApiError保留安全details和WWW-Authenticate挑战头；修正文档追加字面换行符。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：无正式培养reader/真实方案或PG，API仅明确当届缺口，所有HTTP/TS/构建未验证。

## T60 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T60。
- **修改目的**：分布、历史录取与指定记录比较的空查询接口。
- **修改文件**：services/api/app/api/reference_admissions.py, services/api/app/api/reference.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T60_20261012.md, docs/api.md, docs/reference_api.md。
- **新增内容**：分布、历史录取与指定记录比较的空查询接口。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：无正式统计reader/数据库分页或可读取发布记录；比较接口只返回未启用缺口，不执行虚假比较。

## T59 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T59。
- **修改目的**：独立默认空数据的省线与覆盖只读API及TS契约。
- **修改文件**：services/api/app/api/reference.py, services/api/app/api/reference_contract.py, services/api/app/api/reference_cutoffs.py, packages/contracts/reference.ts, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T59_20261012.md, docs/api.md, docs/reference_api.md, docs/architecture.md。
- **新增内容**：独立默认空数据的省线与覆盖只读API及TS契约。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：API只是未启用资料的空响应；无正式published reader/PG/撤回查询或运行契约验证，生产工厂不装配此入口。

## T58 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T58。
- **修改目的**：统计和毕业指标的确定性四类可比性检查。
- **修改文件**：services/api/app/statistics/comparability.py, services/api/app/outcomes/comparability.py, services/api/app/statistics/candidates.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T58_20261012.md, docs/comparability_minimal.md。
- **新增内容**：统计和毕业指标的确定性四类可比性检查。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：共享Text拒空白/控制字符，防止空人群定义被当已知；由源码审阅发现，未执行负例。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：仅纯定义比较，不证明已审数据/发布；没有排名、预测收入或隐式币种换算。

## T57 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T57。
- **修改目的**：逐指标毕业人群、观察窗口、分母与薪资定义候选。
- **修改文件**：services/api/app/outcomes/__init__.py, services/api/app/outcomes/schemas.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T57_20261012.md, docs/outcomes_minimal.md。
- **新增内容**：逐指标毕业人群、观察窗口、分母与薪资定义候选。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：无真实毕业结果/PG/审核发布；指标样本、分母、周期未知保留，不将落实率当就业率。

## T56 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T56。
- **修改目的**：按入学届保存培养版本和有界课程候选。
- **修改文件**：services/api/app/curricula/schemas.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T56_20261012.md, docs/curricula_minimal.md。
- **新增内容**：按入学届保存培养版本和有界课程候选。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：无真实培养方案或PG/版本发布，未知当届不复用旧届，候选不代表完成专业映射。

## T55 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T55。
- **修改目的**：人数口径和适用身份费用候选。
- **修改文件**：services/api/app/statistics/quotas.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T55_20261012.md, docs/quotas_minimal.md。
- **新增内容**：人数口径和适用身份费用候选。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：无真实人数/费用、PG或发布；周期未知不算总成本，住宿与未来年度不填假值。

## T54 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T54。
- **修改目的**：省年组专业粒度的历史投档与录取观测候选。
- **修改文件**：services/api/app/statistics/admissions.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T54_20261012.md, docs/admissions_minimal.md。
- **新增内容**：省年组专业粒度的历史投档与录取观测候选。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：无真实录取数据/PG/代码审核与发布，不估录取概率或将单科统计变资格。

## T53 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T53。
- **修改目的**：完整降序累计分布验证与合成同分位次区间。
- **修改文件**：services/api/app/statistics/distributions.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T53_20261012.md, docs/distributions_minimal.md。
- **新增内容**：完整降序累计分布验证与合成同分位次区间。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：仅纯候选及一种降序格式，未导入真实分布/PG/个人排序，不生成录取概率。

## T52 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T52。
- **修改目的**：精确考试范围和省线类型候选及单条DEMO夹具。
- **修改文件**：services/api/app/statistics/cutoffs.py, data/fixtures/reference/DEMO_cutoff_2026.json, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T52_20261012.md, docs/cutoffs_minimal.md。
- **新增内容**：精确考试范围和省线类型候选及单条DEMO夹具。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：无实际省分数或PG持久化/审核发布；归一候选hash不是原文字节hash，缺2026真实资料不回填。

## T51 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T51。
- **修改目的**：学院层级与省年招生代码映射候选。
- **修改文件**：services/api/app/curricula/__init__.py, services/api/app/curricula/identities.py, services/api/app/statistics/candidates.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T51_20261012.md, docs/identities_minimal.md。
- **新增内容**：学院层级与省年招生代码映射候选。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：当前导入所需T50 DecimalException错误映射补齐，源码审阅发现，未运行检查。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：仅严格候选模型，无官方代码名录/PGFK/映射审核及正式连接，原名称与代码不自动标准化。

## T50 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T50。
- **修改目的**：34地区×2026覆盖登记与有限本地候选导入基础。
- **修改文件**：services/api/app/statistics/__init__.py, services/api/app/statistics/regions.py, services/api/app/statistics/coverage.py, services/api/app/statistics/candidates.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T50_20261012.md, docs/coverage_minimal.md, docs/database.md。
- **新增内容**：34地区×2026覆盖登记与有限本地候选导入基础。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：无新PG表/迁移/正式来源owner或已审核全国事实，候选仅本地模型/bytes；真实覆盖与持久事务/审核发布待实现。

## T48 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T48。
- **修改目的**：有限发布门槛报告与缺失证据阻挡判定。
- **修改文件**：services/api/app/release_gate/__init__.py, services/api/app/release_gate/decision.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T48_20261012.md, docs/acceptance/public_release.md。
- **新增内容**：有限发布门槛报告与缺失证据阻挡判定。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：真实D01–D08、身份/权限/恢复/监控/容量/领域审核与本批运行验证缺失，当前公众发布blocked。

## T47 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T47。
- **修改目的**：十项关键合成验收设计与未执行报告契约。
- **修改文件**：data/evals/critical_20261012.json, services/api/app/evaluation/__init__.py, services/api/app/evaluation/report.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T47_20261012.md, docs/evaluation_minimal.md。
- **新增内容**：十项关键合成验收设计与未执行报告契约。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：本批无评测执行或真实领域抽查，十项只是设计样本，不代表100例或严重错误为零。

## T46 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T46。
- **修改目的**：显式合成窗口配额、并发预留和幂等计费收据。
- **修改文件**：services/api/app/limits/__init__.py, services/api/app/limits/quota.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T46_20261012.md, docs/limits_minimal.md。
- **新增内容**：显式合成窗口配额、并发预留和幂等计费收据。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：仅单进程内存，不提供生产配额/HTTP装配/多实例/重启持久性或容量测量，D07阈值未知。

## T45 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T45。
- **修改目的**：默认关闭的有限指标汇总与纠错候选状态契约。
- **修改文件**：services/api/app/observability/__init__.py, services/api/app/observability/metrics.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T45_20261012.md, docs/observability_minimal.md。
- **新增内容**：默认关闭的有限指标汇总与纠错候选状态契约。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：持久反馈HTTP/告警、运行采集器、负责人/SLO及故障脱敏演练未实现或未验证。

## T44 · 简化源码交付

- **日期**：2026-10-12。
- **Task ID**：T44。
- **修改目的**：合成有界AESGCM备份包、固定维护计划与T40恢复屏障接缝。
- **修改文件**：deploy/backup/__init__.py, deploy/backup/archive.py, deploy/backup/maintenance.py, AGENTS.md, README.md, docs/tasks.md, docs/CHANGELOG.md, docs/acceptance/T44_20261012.md, docs/backup_minimal.md。
- **新增内容**：合成有界AESGCM备份包、固定维护计划与T40恢复屏障接缝。
- **修改内容**：任务按最小源码范围完成；原目标/运行验收保留待办。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；仅源码/Git审阅，不宣称运行通过。
- **已知问题**：实际PG dump/restore、加密密钥ACL/轮换、独立灾备、RPO/RTO与正式运行责任未验证。

## P05 · 剩余任务简化规划

- **日期**：2026-10-12。
- **Task ID**：P05。
- **修改目的**：按用户选择简化剩余任务，逐个执行至T67。
- **修改文件**：AGENTS.md、README.md、requirements、architecture、tasks、CHANGELOG、DECISIONS、新simplified_plan；同批保存前轮未提交T44前置记录backup_scope及acceptance/T44_source（明确历史，不作新验收）。
- **新增内容**：22项最小交付映射、ADR-058、源码/运行/真实验收分离约束。
- **修改内容**：至T67授权及逐Task最小源码标准；原Task目标与历史结果保留，不部署，D01/D07未知继续阻挡真实启用。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：未执行（用户要求）；只读文档/代码和必要Git状态/diff，文档编辑脚本不执行校验。
- **已知问题**：所有新源码尚未实现/验证，真实运营目标/审核责任及上线门槛待定；仅规划完成，不能称产品上线可用。

## T44 · 恢复前置与验收范围核对（源码/未验证）

- **日期**：2026-10-04。
- **Task ID**：T44。
- **修改目的**：仅完成T44相关代码与依赖核对，备份/恢复尚未实现；D07替代目标及本批仅源码继续的范围澄清待答。
- **修改文件**：6路径，见[完整清单](acceptance/T44_source.md)。
- **新增内容**：T44可复用能力/后续契约与未执行清单、依赖核对记录。
- **修改内容**：T44先进行中后阻塞，44主Task已完成/1阻塞/22未开始；保留T43源码已保存及未验证状态。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：全部未执行（用户要求）；仅源码/文档读取、Git必要审阅和文档编辑，不是运行通过证据。
- **已知问题**：D07的恢复/容量目标与责任未定；原T44要求实际恢复证据，本批不用测试；未收到调整原顺序/验收范围的答复，不将等待视为同意，不继续T45–T50。

## T43 · 手动CI配置与契约门槛（源码/未验证）

- **日期**：2026-10-04。
- **Task ID**：T43。
- **修改目的**：完成默认关闭的手动CI源码，推送不触发测试；固定契约、离线Python、独立PG/迁移及Vue四stage。
- **修改文件**：12路径，见[完整清单](acceptance/T43_source.md)。
- **新增内容**：workflow_dispatch默认false、三个CI工具文件、有界JUnit拒skip/零用例、18迁移链及随机专用PG容器、T43契约/记录、ADR-057。
- **修改内容**：T43只按本批源码范围完成，原运行验收保留未验证；不改变API/DB/依赖/迁移/业务。
- **删除内容**：无。
- **Bug 修复**：源码人工阅读补direct-script根路径，未修改旧功能。
- **测试结果**：全部未执行（用户要求）；仅源码/文档读取、Git必要审阅和文档编辑，不是运行通过证据。
- **已知问题**：流水线/坏迁移/漂移/网络负例与分支门槛未验证；workflow仅工作分支、默认分支入口和branch protection未配置；旧Windows浏览器/pg_dump路径尚未接入，关键HTTP不能代替浏览器/完整恢复。

## T42 · 通用 Docker 配置源码（运行未验证）

- **日期**：2026-10-04。
- **Task ID**：T42。
- **修改目的**：按用户‘先做通用 Docker 配置’恢复源码开发，实际D01目标延后，按‘不用测试’记录未验证事项。
- **修改文件**：22路径（8旧/14新），完整清单见[T42记录](acceptance/T42_deployment.md)；`.dockerignore`、`.gitattributes`部署LF、deploy十一文件、七治理文档和deployment/acceptance。
- **新增内容**：两Dockerfile、NGINX TLS/同源配置及入口、loopback/私网Compose、外部秘密引用、pending目标记录、有界预检、固定单链显式迁移CLI、运行与有限回滚说明；ADR-056。
- **修改内容**：T42范围调整为通用配置源码并完成，43主Task完成/24未开始；D01实际城市/供应商/手续保留待定，私有业务/worker/live及公众发布关闭。源码完成与运行未验证分别记录，保留原阻塞和追加指令前检查历史。
- **删除内容**：无；当前任务文档改为当前状态，历史前置记录保留。
- **Bug 修复**：无既有业务修复；源码人工审阅补pnpm-workspace构建输入与Linux LF规则，收紧维护源码白名单/外部秘密目标；最终文档审阅修正README进行中统计为43源码任务完成/24未开始，架构原阻塞段明确标历史。首次源码保存后追加普通文档修正提交，不改写已有commit。
- **测试结果**：未执行测试/Lint/TypeCheck/Build/契约或哈希校验、预检、Docker配置/构建/运行、迁移/TLS/回滚（用户要求）。只读取源码/文档、必要Git状态/diff及保存审阅；`.cache/finalize_t42_source.py`仅编辑文档。无运行通过结论，旧结果不作为本次验证。
- **已知问题**：实际镜像/锁安装/网络/秘密ACL/TLS/迁移/恢复/日志TTL未验证，初始化owner非生产运行角色，同主机双卷不证明灾备独立性，Keycloak/worker/锚点没有装配。D01实际平台未定；D07旧目标拒绝、替代与责任待定；D08真实审核负责人未定。根M0 Compose/旧迁移/API/DB/依赖不改，按PRIVATE持续授权仅保存审查过的22路径，不部署。

## T42 · 历史生产部署前置核对（选择通用源码之前）

- **日期**：2026-10-04。
- **Task ID**：T42。
- **修改目的**：核对已授权顺序任务的当前源码/输入，固定部署范围与待测证据，准确记录无法完成的验收。
- **修改文件**：9份文档（7旧/2新），完整清单见[T42核对](acceptance/T42_deployment.md)；AGENTS、README、requirements、architecture、tasks、CHANGELOG、DECISIONS与新deployment/acceptance。
- **新增内容**：部署前置契约、当前事实与输入表、待测矩阵、ADR-055阻塞记录；用户追加“不用测试”的本批执行约束及未执行说明。
- **修改内容**：T42先[~]再依赖核对为[!]；42主Task完成/1阻塞/24未开始，D01待定/D07拒绝/D08有限登记保持；明确T42未验收/未上传。2026-10-04用户追加不用测试后，不再运行自动测试/Lint/Type Check/Build/验收校验脚本，保留此前记录；源码完成与运行验证分别报告，D01独立依赖未解除。
- **删除内容**：无。
- **Bug 修复**：无；不修改应用、Docker、用户磁盘或任务外问题。
- **测试结果**：以下均在用户追加“不用测试”之前执行：`check_task.py T42 --blocked`exit0（当时9文档/803保护文件/66其他卡/441本地链接及旧历史一致）；`verify_originals.py`exit0两原文UNCHANGED；`t42-status-check.py`exit0核67卡计数/决策/HEAD与空索引；Docker版本检查exit1，CLI29.8.1可读但Linux Engine npipe不存在。追加指令后的文档更新未运行测试、Lint、Type Check、Build或校验脚本，原因是用户要求；不沿用先前检查结果宣称本次更新通过。
- **已知问题**：D01城市/供应商/适用流程缺失阻挡原卡验收；构建引擎未连，生产部署配置未实现。D07旧提案不采用/新目标与责任未定，T44–T46相关依赖保持；D08只有限登记/真实审核发布负责人待定。T42无成功Task上传授权适用，不提交未完成任务。

## T41 · 隐私与授权操作页面

- **日期**：2026-10-04。
- **Task ID**：T41。
- **修改目的**：提供可理解且独立于核心用途的本人权利入口及当前撤回/保留说明。
- **修改文件**：21路径（8旧/13新），完整清单见[T41验收](acceptance/T41_privacy_workspace.md)；新SettingsView组合、privacy/rights客户端/状态/面板、前端fixture/三专项、实际PG/Edge harness；旧AuthView最小替换、治理同步。
- **新增内容**：独立导出/删除checkbox、明确状态读取/UUID追踪、有限响应与原UTF8/SHA/expiry核验、临时下载URL撤销、本人/关闭/DEMO说明。
- **修改内容**：SettingsView复用原PrivacyPanel/SharingPanel，核心用途变化重读共享；删除受理清父级准入/画像计划并重读告知，身份/API变更、卸载abort/generation清内容；原后端/生成wire/数据库不改。
- **删除内容**：无。
- **Bug 修复**：新client元数据闭合校验改按实际ProfileMeta九字段；初TypeCheck闭包narrow失败改显式字段检查；提交审查补本地会话/工件静置到期清内存并abort迟到，长时限分段与卸载取消定时器；导出/删除客户端有界wire与api漂移关闭。实际Edge初夹具管理员回调仍旧域，改所有test配置工厂注册真实loopback origin后验证。
- **测试结果**：62新前端专项（38client/17state/7panel）、完整805/49files、VueTypeCheck/demo-authBuild，228相关Python及1实际PG/HTTP/Edge十一检查点通过；12profile/M0/原文保护，初type/harness失败保留，不重复累节点；命令/真实失败/未执行见验收。
- **已知问题**：真实资料/身份供应商/正式权利渠道/法律与部署仍关闭；不自动轮询，刷新页面需本人受理UUID重新追踪，页面不持久保存标识/原内容。10MiB原内容上限与T40有限重试/最小责任记录、备份到期物理清理局限保持。D01用户明确待定；D07旧提案不采用且替代目标未定；D08只确认T50首批34地区×2026登记，真实审核发布负责人未定。auth563.79kB及ignored cache outDir提示、旧Starlette warning保留。T42前read-only docker version：CLI29.8.1但Docker Linux Engine管道不存在，实际镜像/容器检查尚不可执行；不顺带重装或重建数据环境。

## T40 · 资料权利与独立删除台账

- **日期**：2026-10-04。
- **Task ID**：T40。
- **修改目的**：保障本人权利独立于咨询同意，接受删除后继续清理并防止旧备份复活资料和权限。
- **修改文件**：51路径（22旧/29新），完整清单见[T40验收](acceptance/T40_data_rights.md)；新rights模块/API/两独立增量迁移/第十二契约profile及pure、PG、HTTP、文件和真实备份恢复测试；现有认证/隐私/共享/存储/变化七源最小guard接缝，治理同步。
- **新增内容**：五业务表与两独立ledger表、闭合本人确认、精确scope/自然去重/lease fencing/有限重试；有界原内容导出，独立受信锚点和显式恢复重放、匿名影响擦除计数。
- **修改内容**：已装配身份及服务每次核当前台账/恢复水位，退出/角色/core/grant/私有文件减权留最小外部事件；T40启用factory全流量恢复屏障。旧关闭工厂无新DDL依赖、旧M0/十一个profile保持。
- **删除内容**：无。
- **Bug 修复**：删除scope清空推迟到完成状态同flush，避免running不可变约束失败；过期最后一次lease持久failed、显式有限重试；重放最小受理记录使用真实audit收据；重新登录轮换旧会话追加准确减权事件。新测试前提失败与修正详见验收。
- **测试结果**：30新pure/11契约、18 distinct实际PG-HTTP（包含1实际pg_dump/pg_restore及文件恢复），713相关Python/1旧symlink skip、743前端/TypeCheck/demo-auth Build通过；12profile/M0/原文保护。初失败及末新增安全检查保留，不累计重复轮次；命令/真实失败/未执行见验收。
- **已知问题**：仅合成专用PG/本地文件维护装配；生产锚点ACL、独立SQL凭据/GRANT-RLS、加密备份/完整RPO-RTO、到期物理备份及ledger清理未验收。无外部cache/vector，不声称清理此类未配置服务；不声称WAL/磁盘安全擦除或全部备份消失。导出10MiB、scope5000行/256KiB和台账10000条有界，超过明确关闭，不截断。锚点或外台账提交后业务失败须可信重放；锚点自身损坏无自动猜测修复。D01用户答待定；D07提议目标被拒绝，替代目标未定；D08确认T50首批34地区×2026登记/小合成夹具，正式审核和发布负责人未定。既有Starlette warning/auth546.48kB构建提示保留。

## T39 · 有限公开证据问答入口

- **日期**：2026-10-04。
- **Task ID**：T39。
- **修改目的**：提供明确关闭状态、有限公开项目证据问答与引用展开，保留无key核心服务。
- **修改文件**：36路径（13旧/23新），完整清单见[T39验收](acceptance/T39_qa_entry.md)；新QA factory/DTO/service/router与有限生成profile、前端client/验证/状态/面板、新pure/契约/PG/Edge测试；旧生成器及AuthView/CatalogView/Vite最小接缝、治理同步。
- **新增内容**：独立公共QA两个操作、闭合16KiB输入、等待后当前取证、匿名实例预算、仅typed引用/固定建议、明确展开检查提问与迟到200拒绝。
- **修改内容**：明确生成器qa白名单、两生成工件LF；公开所选目标接QA面板，开发loopback8003代理；keywords省略规范为空列表。
- **删除内容**：无。
- **Bug 修复**：新child配置漂移早503补no-store；合法模型unknown不编检索原因；客户端对原optional keywords作严格规范化。测试前提修正与首次失败详见验收。
- **测试结果**：61新pure/9契约、10 distinct实际PG-HTTP（9专项＋1实际Edge/8检查点），704相关Python/143模式-M0；742完整前端及末补丁59专项、TypeCheck/demo-auth Build通过；11profile/M0/原文保持。首次前提与新no-store缺陷修正保留，不累计重复轮次；命令/真实失败/未执行见验收。
- **已知问题**：真实模型/资料/公众部署保持关闭，合成引用不能当真实官方事实；预算为有界进程内保守UTF8计量，持久全局运行配额属T46。现有Starlette warning、auth546.48kB与ignored outDir构建提示保留。D01/D07/D08补充选择待用户回复。

## T38 · 范围检索与严格引用验证

- **日期**：2026-10-04。
- **Task ID**：T38。
- **修改目的**：让有限问答只使用当前适用发布证据，阻止跨年/项目/失效引用及原文指令越权。
- **修改文件**：22路径（8旧/14新），完整清单见[T38验收](acceptance/T38_qa_retrieval.md)；qa四源、新pure与PG专项、固定合成gold/校验脚本、LF规则；七治理文档及检索契约/验收。
- **新增内容**：20字段RequestScope拒客户端dataset；同Session当前公开proof派生dataset；固定公开projection引用/原义JSON atoms/等待后current重验；24固定合成gold及独立预期/完整性校验。
- **修改内容**：仅新QA与治理；.gitattributes增加gold精确LF；旧T20服务/工厂、API/DB/迁移/前端/依赖/M0及十profile保持。
- **删除内容**：无。
- **Bug 修复**：新_native合法重用字典ancestor marker回收修正；actual historical_statistic/typical_offer不误进requirements；整体ProjectionLimit只清空全部引用并保已证pins；私有数据库配置以内部摘要检测SecretStr掩码漂移。新测试漏/写错location_kind与namespace重复request已修；专用PG失联与首次重启端口遗漏已纠正，不改用户DB或Docker。 暂存复核后单atom超2000改专用ProjectionLimit，retrieve只捕该异常；坏字段ValidationError不再伪报限额。
- **测试结果**：106纯/评测校验（19owned/57独立/30gold校验）、10 distinct实际PG（5owned/5独立）、24/24固定合成gold；528相关Python/143模式-M0；684前端/43files、TypeCheck/demo-auth Build；十profile/M0/两原文保持，首环境与夹具失败完整记录；命令/真实失败/未执行见验收。
- **已知问题**：真实事实与live仍关闭；gold只有24合成案例，current_authority_established/manual_domain_review_completed均false，不能代正式领域审阅。日期计算候选与官方精确期限分开，官方UTC仍未知；超有限投影整体返回LIMIT_EXCEEDED。现有auth522.75kB包体提示与Starlette警告保留。D01/D07/D08补充选择尚待用户回复，不在T38中代猜。

## T37 · 可替换模型接口与离线预算

- **日期**：2026-10-04。
- **Task ID**：T37。
- **修改目的**：建立可替换只读模型端口及有限预算，在没有供应商密钥和评审时仍保持核心可用。
- **修改文件**：17路径（7旧/10新），完整清单见[T37验收](acceptance/T37_model_gateway.md)；model_gateway纯模块与async离线专项；七治理文档及模型契约/验收。
- **新增内容**：冻结模式/有限结构化输入输出、可替换async port、bounded worst-case quota/超时并发与使用记录；无商业SDK或网络配置。
- **修改内容**：只治理状态与实施说明；旧providers.py/settings/数据库/HTTP/前端/十生成profile不改。
- **删除内容**：无。
- **Bug 修复**：新成功测试夹具额度32不足容纳最小结构化answer，改合法256并保留大output拒绝；源码独立初始policy/quota快照阻原地合法漂移；async适配器错签名/任务构建失败统一错误、close未启动coro、保留扣量且释放slot。
- **测试结果**：90新增离线async专项（26owned/64独立）、651相关Python和143模式-M0；684前端/43files、TypeCheck/demo-auth Build；十profile/M0契约保持；首次75pass/12fixturefail及实际provider故障修复完整保留；命令/真实失败/未执行见验收。
- **已知问题**：D05实际供应商/处理地域/token费用与数据流评审未完成；真实模型关闭。预算只进程内离线限制，不是正式跨进程计费控制；mock仅明确合成。auth主包522.75kB的Vite体积提示和既有Starlette警告保留。

## T36 · 持久作业与站内提醒

- **日期**：2026-10-04。
- **Task ID**：T36。
- **修改目的**：用持久作业消化已提交发布事件并向明确opt-in本人展示有限变化提醒，恢复与撤权安全。
- **修改文件**：47路径（12旧/35新），完整清单见[T36验收](acceptance/T36_jobs_notifications.md)；jobs/notifications后端、worker有限函数、独立notifications factory、迁移、契约生成、新Vue模块与专项测试/治理文档。
- **新增内容**：五表、第16迁移head、租约generation/token、原用途逐用户证明、默认off偏好CAS、有限站内提醒readCAS、cleanup受理有限probe与真实数据库/离线验收。
- **修改内容**：有限第10生成profile、PlanView折叠入口和治理状态；旧九生成profile、十五迁移head及不可变业务保持。
- **删除内容**：无。
- **Bug 修复**：新偏好首次插入autoflush顺序、cleanup scope JSON规范化、分页OpenAPI边界；运行任务到期但租约未到期的终态筛选修正。新增测试的导入/fixture/类型/断言误用亦已修正，真实首轮失败保留。
- **测试结果**：36新增pure/12新contract；16 distinct实际PG/HTTP（8owned、8独立含新增jobTTL）；712相关Python回归；684前端/43files、49新专项、TypeCheck/demo-auth Build；十profile与原M0契约一致；失败修复与未执行见验收。；命令/真实失败/未执行见验收。
- **已知问题**：真实模型/export/物理删除/外部通知关闭；cleanup_probe仅registry scope完整性，不能代替附件字节和T40删除。尚无正式供应商/法律/SQL GRANT-RLS/部署与生产备份恢复验收。auth主包522.75kB有Vite体积提示，Starlette现有弃用提示。

## T35 · 明确修订与有限历史工作台

- **日期**：2026-10-04。
- **Task ID**：T35。
- **修改目的**：在画像/证据变化后明确审阅新草案和旧执行历史，接受或拒绝而不静默覆盖或转移完成。
- **修改文件**：45路径（12旧/33新），完整清单见[T35验收](acceptance/T35_plan_revisions.md)；限定12旧路径及33新路径；旧14迁移链/8契约/M0/641其他tracked不改，未新增依赖。
- **新增内容**：独立3不可变表/第15head；原pin历史重建、创建时impact和TTL核验；5受保护API/第9有限生成profile；默认折叠修订子工作台和真实合成PG/Edge专项。
- **修改内容**：治理/任务/验收同步；有限generator选项、LF标记及PlanView最小子模块接缝；全新模块输入/时刻/hash/日期/owner与source证明补强。
- **删除内容**：无。
- **Bug 修复**：修复严格false接受0、历史profile字段/API及重复native时间解码、原元数据条件表达式优先级、锁顺序倒置、自洽hash伪历史/差异、后来impact影响旧拒绝、unknown日期耦合；修复UI权限错误文字消失与新测试固定20ms等待不可靠。
- **测试结果**：57新pure、19 distinct PG/HTTP/Edge（5 owned、13独立、1实际Edge）；321契约/350相关Python、635前端/Type Check/demo-auth Build与9生成核对完成，完整实际失败及末版复验见验收；命令/真实失败/未执行见验收。
- **已知问题**：正式学生/规则/供应商/法律/SQL角色及公众部署仍关闭；原官方精确UTC仍未知，历史不能恢复当前资格。关系未全局停用旧T32端口，原证明仍有效时旧完成可继续追加；不承接完成信用。创建时来源轨迹最多100，超限明确409；无真实跨年度项目验收。auth构建主包503.53kB触发Vite体积提示，未为当前Task顺带重构；1条既有Starlette BlockingPortal警告保留。

## T34 · 发布变更业务比较与影响追踪

- **日期**：2026-10-04。
- **Task ID**：T34。
- **修改目的**：完成T34按业务与适用范围识别发布变化、追踪原评估/计划needs_review，保留历史与执行记录。
- **修改文件**：25路径（8旧/17新），完整清单见[T34验收](acceptance/T34_changes.md)；新changes纯契约/比较、3表store/service、独立第14迁移及专项；治理与受影响需求/架构/数据库文档同步，原API/前端/旧迁移不变。
- **新增内容**：精确目标范围的多成员业务multiset diff；已存event自然去重与同TX关系传播；不可变receipt/assessment/plan impacts；原notice/core/owner即时有限轨迹读取；最小关系索引。
- **修改内容**：T34状态、CHANGELOG、ADR-047及运行/数据库/架构说明；无旧业务改写，无新依赖。
- **删除内容**：无。
- **Bug 修复**：实施中修正只看旧rule_refs导致漏新增条件及混合scope误标；关闭入口审计包装的诊断SQL改为前置零IO校验；补目标重复身份一致性；新测试64字符小数夹具计数纠正；新Alembic profile补path_separator=os。
- **测试结果**：最终86纯专项/4.40s与16distinct PG通过（owned7/144.60s、安全9/152.71s；identity补强后added节点1/28.44s再次通过，不累计）；723相关Python/55.59s、590前端/37文件、Type Check、demo/auth Build、八生成profile与原文/M0核对通过；PG首8通过1失败后修复并完整9通过；命令/真实失败/未执行见验收。
- **已知问题**：真实处理、公众发布与供应商/法律/SQL权限门槛仍关闭。轨迹最多100条，超过明确409，分页未实现；规则发布ruleset仍NULL，官方精确UTC仍unknown，未宣称真实规则/精确截止日正例。省份混合范围矩阵为纯专项，真实新增条件为实际发布PG，不伪称混省发布PG。T40须协调删除私有impact与immutable receipt历史计数；本Task尚无删除服务。现有Starlette BlockingPortal警告与Vite缓存outDir提示保留。

## T33 · 计划与进度工作台

- **日期**：2026-10-04。
- **Task ID**：T33。
- **修改目的**：让学生明确选择原评估、核对容量/依赖、确认本人安排和查看进度及只读历史。
- **修改文件**：29路径（9旧/20新），完整清单见[T33验收](acceptance/T33_plan_workspace.md)；仅两旧Vue接缝、新plans工作台/测试、受影响治理文档。
- **新增内容**：八操作安全客户端、计划表单/排程/任务/历史、同profile目标交接、独立private scope与IO代际、防坏200/不确定精确重试、真实合成PG/Edge闭环。
- **修改内容**：AuthView/CatalogView明确交接与折叠入口；当前需求/架构/运行说明、Task状态和ADR046；原后端/API/DB/八契约/迁移/依赖保留。
- **删除内容**：无。
- **Bug 修复**：新实现坏200误归网络、容量/来源/画像/内部目标与进度边界；真实初始mount中context IO取消profile哈希的竞态，分离scope与IO并实际复验。仅新测试前提/等待修正，失败轮次如实保存。
- **测试结果**：116新增前端专项、完整590/37files、56相关Python、Type Check/demo-auth Build、1 distinct真实PG/Edge用例15检查点与可读局部截图人工核通过；重复PG仍计1节点。命令/失败/未执行见验收。Lint/Python静态无入口；真实处理/规则/官方截止/法律/SQL权限/代理HTTPS/部署未执行。
- **已知问题**：ICU与服务tzdata差异保守拒绝；原来源DTO年度缺失明确标注，官方精确期限仍未知，真实服务关闭；既有Starlette弃用warning和Vite隔离outDir提示保留。

## T32 · 计划确认与任务进度

- **日期**：2026-10-04。
- **Task ID**：T32。
- **修改目的**：给本人准备提案提供独立CAS、显式确认和可审计进度，不改写原草案或资格。
- **修改文件**：33路径（11旧/22新），完整清单见[T32验收](acceptance/T32_plan_execution.md)；独立domain/四表迁移、plans HTTP/生成工件/新LF规则、专项测试和受影响文档。
- **新增内容**：不可变提案/确认/完成、state_version历史投影、确认T49幂等及进度自然去重、八操作/有界请求/当前权限与来源单TX末端证明、首次确认未来容量约束。
- **修改内容**：当前API/数据库/需求/架构/运行说明、任务状态与ADR045；旧十二head/T30源/registry版本/七契约工件原貌保留，真实处理关闭。
- **删除内容**：无。
- **Bug 修复**：T32新实现读取返回历史下界与排程重算保护；修复来源有效但时段已过去仍首次确认的边界，确认后保留过往安排与进度。新测试UUID/字段/审计基线前提修正，失败真实保留。
- **测试结果**：56新增pure、28 distinct真实PG/HTTP、305契约及865相关旧Python、474前端和Type Check/demo-auth Build、八生成profile/原文/M0检查通过；补丁后相关复验不重复累计。实际命令/首轮失败/未执行项见验收；无Lint/Python静态入口、UI浏览器/真实处理/法律/权限/部署/生产恢复未执行。
- **已知问题**：官方期限仍未核定，确认不升级资格；真实服务关闭。旧T30极端存储限额问题保留，新包装提前拒422；贪心不保证全局最优，既有Starlette警告保留。

## T31 · 工时容量与依赖排程

- **日期**：2026-10-04。
- **Task ID**：T31。
- **修改目的**：以本人明确时段及周工时生成有界确定性容量提案，明确依赖与不可排原因。
- **修改文件**：15路径（7旧/8新），完整清单见[T31验收](acceptance/T31_scheduling.md)；两纯模块、四专项测试、契约/验收与七治理文档。
- **新增内容**：IANA本地周界/UTC整数微秒、六位十进制精确时长、拓扑与共享任务、全任务试排失败释放容量、零里程碑/未知估时区分、来源完整投影和固定冲突选项。
- **修改内容**：当前需求/架构/运行说明、任务状态与ADR044；当前官方期限保持未知，不改T30草案/hash，不启用确认或持久/HTTP/UI。
- **删除内容**：无。
- **Bug 修复**：本Task输出重新hash后的容量/重叠/依赖/时间自洽校验及冲突数最坏222上界；新测试Expr native夹具与来源冲突错误码前提修正，失败轮真实保留。
- **测试结果**：100新增pure、228相关旧pure、474前端、Type Check/demo-auth Build、七生成profile/原文/M0和579保护tracked通过；完整实际命令见验收。Lint/Python静态类型无入口；PG/HTTP/浏览器因纯Task未执行，当前官方精确期限正例及真实处理/部署未执行。
- **已知问题**：官方精确截止尚未核定，constraints_complete恒false；有界贪心不证明全局最优或绝对不可行。真实处理/计划确认关闭，既有T30极端JSONB限额问题保留未改。

## T30 · 差距到草案任务

- **日期**：2026-10-04。
- **Task ID**：T30。
- **修改目的**：将本人确认目标及确定性资格差距转为可审阅、未确认/未排程的准备与核验草案。
- **修改文件**：26路径（8旧/18新），完整清单见[T30验收](acceptance/T30_plan_drafts.md)；新plans纯DTO/生成器、五表/store/service、独立迁移、Unit/PG金标准与安全测试、契约/验收及八治理文档。
- **新增内容**：四态模板/未知优先、实际必要obligations、兼容语义去重、独立主补日期引用、显式可调估时、当前本人/画像/原用途同事务持久和末端来源/创建时刻重验。
- **修改内容**：ADR043及当前数据库/架构/需求/运行说明与Task状态；沿T11隔离惯例用app/plans，保留旧planning.py字节，无HTTP/API/前端/依赖或旧迁移变化。
- **删除内容**：无。
- **Bug 修复**：本Task JSON缺键与DDL布尔绑定、来源完整投影/当前画像版本、未知排序与新草案创建时刻下界；测试guard、审计表名和状态夹具修正，真实失败轮次保留。
- **测试结果**：81 pure、23 distinct PG、641相关Python/4 deselected、474前端、Type Check/demo-auth Build、七生成profile/原文/M0和diff通过；最后创建下界局部补丁后复验4相关PG节点（含1新增），不累计重复。实际命令/范围/失败及未执行项见验收；Lint/Python静态类型无入口，真实领域/身份/法律/SQL权限/生产备份恢复/部署未执行。
- **已知问题**：合法极端组合纯探针约794881B（JSONB格式估计，未PG），超过524288B版本上限，目前固定503且数据库整笔拒写；保留限额，不为此扩大数据容量。正式处理/HTTP/排程/确认仍关闭，PRIVATE保存核对后才T31。

## T29 · 项目比较与证据工作台

- **日期**：2026-10-04（实施前冻结2026-10-03）。
- **Task ID**：T29。
- **修改目的**：公开目录、准确目标比较、本人确认版四态检查和发布绑定证据组成可审查工作台。
- **修改文件**：32路径（10旧/22新），完整清单见[T29验收](acceptance/T29_catalog_workspace.md)；新catalog/eligibility/evidence模块、CatalogView和前端/实际PG-Edge测试；旧AuthView/ProfileView最小事件、Vite公共开发代理及七治理文档。
- **新增内容**：明确年度/范围分页、跨页四目标比较、完整范围SHA与strict DTO、独立请求取消、四态与历史有效性、原文定位/字节/hash和文本安全展示。
- **修改内容**：当前确认画像最小事件交接、公开/私有独立入口与模式校验、ADR042及实施契约/验收和当前文档状态。没有API/数据库/依赖变化，相应文档及旧生成/迁移/M0保持。
- **删除内容**：无。
- **Bug 修复**：本Task模板作用域/事件参数、旧历史证据不可借新发布、迟到响应、事实文本guard和私有meta模式检查；新夹具/断言/类型错误修正，保留实际失败轮次。
- **测试结果**：474前端、529相关Python、两个实际PG用例（Edge13检查点不单独计pytest）、Type Check和demo/auth Build、七profile/原文/M0/JS语法/保护及文档检查通过；实际命令/失败与未执行项见验收。Lint/Python静态类型无入口；生产代理/HTTPS、真实身份/领域/法律/权限/清理恢复/部署未执行。
- **已知问题**：无新增实现阻断；正式facts-only无ruleset仍unknown，响应没有官方截止时刻不补造日期，真实处理/未成年私有/live关闭；源码保存核对后才T30。

## T28 · /v2 四态评估与重放

- **日期**：2026-10-03。
- **Task ID**：T28。
- **修改目的**：确认画像到确定性四态评估、不可变存储及历史重放，保存当前和历史适用性边界。
- **修改文件**：33路径（11旧/22新），完整清单见[T28验收](acceptance/T28_assessments.md)：assessment/rules新服务与纯引擎、独立迁移/HTTP、生成契约/TS负例、unit/PG/契约、生成器及治理文档。
- **新增内容**：完整AST同变量有界可满足性、必要后补义务、受信合成原文descriptor、同事务证据/用途/最终期限检查、immutable评估及当前有效性、四新HTTP操作和独立Envelope。
- **修改内容**：生成器新增显式assessments白名单/.gitattributes LF；ADR041及README/需求/架构/API/数据库/任务同步。旧六生成产物/迁移/M0/依赖保持。
- **删除内容**：无。
- **Bug 修复**：本Task实施中provider参数、UTC JSON SHA、独立Envelope和精确测试前提问题修正；所有失败轮次保留，不修改旧业务。
- **测试结果**：104纯四态、23新PG（追加1node重跑不累计）、63旧PG、284全部契约、764相关Python、348前端、Type Check/两Build及七profile/原文/M0/范围/治理检查；实际命令/次数/失败及未执行见验收。Lint/Python静态类型无入口；正式领域/法律/SQL权限/生产清理恢复/部署未执行。
- **已知问题**：无新增实现阻断；正式facts-only无ruleset仍unknown，微秒不可精确表达的时间谓词unknown，真实处理/未成年私有/live关闭；PRIVATE保存核对后才T29。

## T27 · 后补与期限资格

- **日期**：2026-10-03。
- **Task ID**：T27。
- **修改目的**：缺实得成绩仅在确切政策/证据/范围/期限均支持时才有事项后补路径，不自动判断可以后补。
- **修改文件**：14路径（7旧/7新），完整清单见[T27验收](acceptance/T27_deferrals.md)：deferral单模块、四unit文件、契约/验收及七治理文档。
- **新增内容**：严格政策/日期绑定与最小query/验证端口、来源日历和独立主补状态、enrollment显式申请不适用、全组/最终快照与自定义时区保护。
- **修改内容**：ADR040及当前README/需求/架构/任务现状；旧层/HTTP/数据库/迁移/生成/依赖/UI/M0保持。
- **删除内容**：无。
- **Bug 修复**：无旧业务修复；新实现保守处理未知政策、截止和构造绕过，实施期间问题如实见验收。
- **测试结果**：最终248新专项/7.27s、1006相关/45.91s、348前端/15.79s、Type Check/两Build及六profile/原文/M0/治理检查，实际命令/分轮结果见验收。Lint/Python静态类型无入口、PG/browser无层变化未重复，真实学生/政策领域审核/法律/SQL权限/清理恢复/部署未执行。
- **已知问题**：无新增实现阻断；allowed仅事项许可不代表conditional，真实政策/全国及英国2027规则实际覆盖仍未知；真实处理和未成年私有关闭，PRIVATE保存后才T28。

## T26 · 国内/英国范围适配器

- **日期**：2026-10-03。
- **Task ID**：T26。
- **修改目的**：逐省/具体英国项目范围匹配与真实规则批准分离，避免跨年、省、课程、身份、阶段和目标规则混用。
- **修改文件**：18路径（7旧/11新），完整清单见[T26验收](acceptance/T26_scope_adapters.md)：adapters四模块、非秘密scope配置、四unit文件、契约/验收及七治理文档。
- **新增内容**：31显式内部省份注册、完整scope哈希目标、最小query/provider/verifier及三态范围选择、全组重验/冲突保护和严格测试模式。
- **修改内容**：ADR039及README/需求/架构/任务当前现状；既有API/数据库/迁移/依赖/前端/M0保持。
- **删除内容**：无。
- **Bug 修复**：新选择器防同ID不同scope、同目标过期/缺规则被正例隐藏、后续回调修改已验条目隐藏冲突；不是旧业务修复。
- **测试结果**：最终208新专项/1.94s、722相关/45.91s、348前端/16.36s、Type Check/双Build、六profile/原文/M0及治理检查，实际命令见验收。Lint/Python静态类型无入口，PG/browser无层变化未重复；真实身份/学生/规则领域审核/法律/SQL权限/清理恢复/部署未执行。两官方页面核查失败单列，不计测试通过。
- **已知问题**：无新增实现阻断；matched不是资格，正式规则编译/审核/全国及英国2027专业覆盖未知，真实处理及未成年私有关闭；PRIVATE保存后才T27。

## T25 · 类型化规则与三值逻辑

- **日期**：2026-10-03。
- **Task ID**：T25。
- **修改目的**：完整有界表达式按三值归约，避免any失败分支误淘汰、缺成绩经not误满足和错误类型/单位/满分自动换算。
- **修改文件**：16路径（7旧/9新），完整清单见[T25验收](acceptance/T25_typed_rules.md)：rules三模块、四专项测试、冻结契约/验收及治理文档。
- **新增内容**：封闭AST/严格typed context与64字符精确数字、Kleene/full trace、按需T23完整投影、显式日期参考与半开valid_at；178规则专项。
- **修改内容**：ADR038及当前README/需求/架构/任务现状；无旧后端/HTTP/数据库/迁移/生成/依赖/前端/M0变化。
- **删除内容**：无。
- **Bug 修复**：新引擎fixed字段kind/单位，杜绝错误同tag合谋；纯入口剥离旧应用顶层导入，pre-JSON共享预算、exact字符串与嵌入tzinfo回调拒绝。两新测试前提修正，不冒充旧业务修复。
- **测试结果**：最终178专项/1.55s、539相关/38.12s、348前端/15.30s、Type Check/双Build及六profile/原文/M0/治理检查；首145pass/3fail与中间复验均保留。命令/结果详见验收；Lint/Python静态类型无入口，PG/browser无层变化未重复，真实身份/学生/领域审核/法律/生产权限/清理恢复/部署未执行。
- **已知问题**：无新增阻断；纯规则不证明已审适用或产生四态，全国及英国2027专业实际覆盖仍未知，真实处理/未成年私有关闭；保存后才单独T26。

## T24 · 画像编辑与确认页面

- **日期**：2026-10-03。
- **Task ID**：T24。
- **修改目的**：本人完整表单/明确确认与不可变版本显示，当前用途或会话变化即时清私有状态，冲突需重新核对。
- **修改文件**：25路径（9旧/16新），全清单见[T24验收](acceptance/T24_profile_workspace.md)：profiles六新应用模块、五测试/夹具、AuthView/PrivacyPanel最小接缝、三新browser模块与治理文档。
- **新增内容**：精确string/null、分课程/身份/路线询问、readonly当前/历史、创建内存幂等key与追加CAS、当前用途clear/abort/generation；69新测试及实际Edge→ASGI→PG流程。
- **修改内容**：两前端组件最小挂载/用途事件、ADR037与当前需求/架构/README/任务说明；旧后端/API/数据库/迁移/生成/依赖/M0保持。
- **删除内容**：无。
- **Bug 修复**：新客户端严格enum/Unicode/hash/提交快照与响应绑定、404私人清理、完整隐藏字段保留；新driver错误路径、未消费errorbody等待和迟到GET前提修正，不冒充既有业务修复。
- **测试结果**：99画像相关、411契约模式、69新专项包含于348完整前端、Type Check/demo-auth Build、六profile/原文/M0检查；最终1PG内12实际Edge检查通过（2root/7version），前六browser失败/超时/主动终止如实保留。实际命令/时间/未执行详见验收；Lint/Python静态类型无入口、全项目PG及真实身份/学生/法律/生产权限/清理恢复/部署未执行。
- **已知问题**：无新增阻断；真实处理关闭，规则/适配尚未实现，不能将地区列表当全国覆盖。正式年龄/隐私/供应商/责任与运维门槛保留；文档同步及PRIVATE保存后才T25。

## T23 · 真实画像与纵向版本

- **日期**：2026-10-03。
- **Task ID**：T23。
- **修改目的**：本人完整确认的新版本保留历史，当前用途/owner约束，缺失、预测与实得独立，不把未知课程套高考规则。
- **修改文件**：35路径（11旧/24新），完整清单见[T23验收](acceptance/T23_profile_versions.md)：新profiles七模块、独立三迁移文件、单元/PG/契约/TS专项与治理。
- **新增内容**：独立两表/六HTTP操作、当前确认绑定/24日历月、创建T49与追加CAS、末端期限及收据同事务回滚、封闭15成绩键与ProfileMeta引用。48pure/51PG/28生成专项。
- **修改内容**：显式profiles生成白名单与LF契约、ADR036及API/数据库/架构/需求/README/任务现状；无旧服务/旧迁移/依赖/UI改变。
- **删除内容**：无。
- **Bug 修复**：新模块收据TTL在最后授权SQL等待后重新核验、创建能力尊重T49开关、未来consent确认时间拒绝。新测试包/安全ErrorEnvelope及生成断言修正，不改旧wire。
- **测试结果**：最终48pure/51实际PG、401相关、411契约模式、279前端/Type Check/demo-auth Build及六profile/原文/M0检查通过；28生成已包含于411。首次collect4errors、第二16fail/32pass、生成初轮及错误路径no-tests均记录；实际命令见验收。Lint/Python静态类型无入口，浏览器无UI改动及全项目PG/真实身份事实法律/SQL权限/物理清理恢复/部署未执行。
- **已知问题**：真实处理关闭；全国/英国2027/专业规则适配尚未实现，未成年私有关闭、正式TTL责任及运维门槛保留。文档同步/私有保存后按批次进入T24。

## T22 · 审核与发布管理页面

- **日期**：2026-10-03。
- **Task ID**：T22。
- **修改目的**：通过实际人工准备、并排审核及当前公共读取闭环验收发布，不依赖预知fixture ID或管理回执冒充公开事实。
- **修改文件**：44路径（12旧/32新），完整清单见[T22验收](acceptance/T22_admin_review_workspace.md)：新HTTP/facade/工厂、前端、生成契约、专项/浏览器测试及治理文档。
- **新增内容**：14项有界操作、候选发现/独立准备/十项审核/缺口冲突、实际T19预检发布撤回及T20匿名预览；13pure/8PG/57新增前端与实际浏览器检查。无新表/迁移/依赖。
- **修改内容**：显式admin_review生成profile、UUID/body/header约束及LF产物、AuthView最小挂载；ADR035与API/架构/数据库现状/需求/任务同步。
- **删除内容**：无。
- **Bug 修复**：本Task草稿date字段、已定位证据与raw locator、RFC3339归一和前端exact-key在首PG前纠正；完整回归发现匿名AuthView输入兼容问题，改明确展开并新增收起取消旧响应测试，旧测试未改；新mock参数类型失败修复。不顺改旧服务。
- **测试结果**：最终13pure/8PG、100审核发布回归、383契约模式、279前端/Type Check/demo-auth Build、1PG内13Edge检查通过，0外网/页面错误、6匿名请求无Cookie。首277/1与新mock类型失败记录保留；五profile/原文/编译/空白检查通过。真实命令与未执行项见验收；Lint/Python静态类型无入口，全项目PG/正式身份事实法律/SQL权限/清理恢复/部署未执行。
- **已知问题**：真实处理/公众发布默认关闭，日期编辑/PDF/规则编译不在本Task，outbox仍pending；全国/各省/英国目标不代表已覆盖。验收和文档同步后私有保存，再进入T23，不部署。

## T21 · 来源与导入管理页面

- **日期**：2026-10-03。
- **Task ID**：T21。
- **修改目的**：强管理员实际登记/修订来源、隔离上传及查看候选导入状态，错误不冒充成功，普通学生不能操作。
- **修改文件**：37路径（13旧/24新），完整清单见[T21验收](acceptance/T21_admin_workspace.md)：admin HTTP/工厂/前端/契约/专项测试，T15服务一个必要局部修改及治理文档。
- **新增内容**：独立admin profile、能力探针、来源CAS、原UTF8上传、幂等导入/回放、固定安全错误、服务器鉴权UI、实际Edge/ASGI/PG端到端；无新依赖/迁移。
- **修改内容**：T15首次HTTP暴露末端同事务当前期限检查；显式admin生成器/header/UUID格式、AuthView最小挂载；ADR033与用户新范围/模型关闭ADR034、当前文档同步。
- **删除内容**：无。
- **Bug 修复**：T15最后鉴权SQL等待后原file/source和同hash请求file失效时回滚，三实际PG等待证明；新harness deque listener、cookie和NULL owner前提修正，前端mock类型修正，不进行无关重构。
- **测试结果**：最终9pure/7PG、65导入回归、368契约模式（含11新生成）、222前端/Type Check/demo-auth Build通过；1PG pytest内9Edge检查，0外部请求/0页面错误；四profile/原文/编译/空白通过。失败轮次保留，实际命令及未执行原因见验收。Lint/Python静态类型无入口，全项目PG/正式身份、来源、法律、SQL权限、清理备份及部署未执行。
- **已知问题**：真实处理/公众发布默认关闭；PDF与后台导入未实现；全国2026与逐省/英国2027目标不代表已覆盖。验收/文档/私有保存后按新授权进入T22，不部署。

## T20 · /v2公共目录与证据读取

- **日期**：2026-10-03。
- **Task ID**：T20。
- **修改目的**：匿名安全查询当前已发布项目与明确可公开的证据，显式显示资料范围缺口。
- **修改文件**：27路径（11旧/16新），完整清单在[T20验收](acceptance/T20_public_catalog.md)同步；public_catalog五模块、独立工厂/路由、契约生成及纯/PG/TS测试、治理文档与新产物LF属性。
- **新增内容**：独立匿名只读profile、当前许可证明、精确筛选/有界分页/变更失效游标、公开片段release绑定与覆盖未知总量。
- **修改内容**：脚本增加显式public_catalog契约profile与LF checkout；同步当前任务/ADR-032/受影响文档，保留旧入口和迁移。
- **删除内容**：无。
- **Bug 修复**：新Reader缺失release入口409修为404；新增instance model_fields弃用改类访问；空页覆盖/版本distinct、配置漂移及末端证明已验证。首新harness两纯及两PG前提错误修正；不修旧T15任务外问题。
- **测试结果**：最终45pure/23PG合计68 passed/1既有warning，无skip；46相关、357契约模式、170前端/Type Check/demo-auth Build、三profile生成/原文/12module compile通过。首PG20/3、选择7/16deselect及纯两次44/1如实保留。Lint/Python静态类型无入口、后台启动烟测自动审批拒绝以及browser/全项目PG/正式事实/身份/法律/SQL权限/运维部署未执行，原因见验收。
- **已知问题**：真实资料/负责人/法律/SQL权限/运维及全国2026覆盖门槛保留，正式公开默认关闭；T20后停止。

## T19 · 不可变发布与撤回

- **日期**：2026-10-03。
- **Task ID**：T19。
- **修改目的**：固定经过当前审核且获公开许可的成员，失败不部分发布，旧版可追溯并可撤回。
- **修改文件**：23路径（9旧/14新），完整清单见[T19验收](acceptance/T19_atomic_releases.md)；releases六模块/profile/迁移、纯/PG测试和治理文档。
- **新增内容**：五表、三不可变历史trigger、唯一published head、CAS/同TXreceipt/audit/ChangeEvent/pending outbox、当前聚合source/file/MFA期限守卫。
- **修改内容**：当前状态、ADR-031及API/数据库/架构/需求同步；facts-only ruleset_version=null、正式拒DEMO，正向仅test_fixture；原文件和metadata哈希分别绑定。
- **删除内容**：无。
- **Bug 修复**：本新模块末端补同now身份/全部成员期限；替代即时FK顺序明确。首纯harness错误类型/弃用及PG父范围503/三barrier5s前提修正，无旧模块修复。
- **测试结果**：最终24纯/22PG、89相关、333契约模式、170前端/Type Check/demo+auth Build、生成/原文/8module compile通过；首纯23/1、PG18/4、选择4/18deselect如实保留。Lint/Python静态类型无入口、browser/全项目PG/POSIX/正式身份与发布/权利/清理备份/部署未执行，原因见验收。
- **已知问题**：outbox只有pending，无影响/通知consumer；不支持预定发布、规则编译未实现；真实资料责任/正式TTL/SQLGRANT/RLS及运维门槛保留，T15任务外记录未顺改。

## T18 · 人工审核决定

- **日期**：2026-10-03。
- **Task ID**：T18。
- **修改目的**：保留显式逐字段人类判断及唯一当前冲突选择，批准与发布分离。
- **修改文件**：23路径（9旧/14新），完整清单见[T18验收](acceptance/T18_human_review.md)；reviews六模块、独立profile/迁移、纯/PG测试与治理文档。
- **新增内容**：三表、不可变历史触发器、case CAS/显式冲突处理/原literal检查、同TX审计与当前批准验证接口。
- **修改内容**：同步当前状态、ADR-030及API/数据库/架构/需求；旧模块/迁移/HTTP/依赖不改。
- **删除内容**：无。
- **Bug 修复**：本Task初稿纯校验加强Unicode数字/符号与中文单位前缀；新测试修正source409投影、MFA时间fixture及file404拒绝预期，无旧服务修复。
- **测试结果**：最终31纯/23PG、93相关、333契约模式、170前端/Type Check/demo+auth Build、生成/原文/8模块compile通过；首两PG21/2及22/1如实保留。Lint/Python静态类型无入口、browser/全项目PG/POSIX/真实审核/身份/清理备份/部署未执行，原因见验收。
- **已知问题**：合成模拟不代表真实人工审核；账户UUID不证明自然人多账号隔离；真实门槛仍关闭。T15任务外时效跟进记录保留，无顺改。

## T17 · 类型化候选事实

- **日期**：2026-10-03。
- **Task ID**：T17。
- **修改目的**：显式区分最低/典型/历史并精确归一，保留原文、未知与冲突，未经审核不能成为硬规则。
- **修改文件**：23路径（9旧/14新），完整逐文件清单见[T17验收](acceptance/T17_typed_facts.md)；facts六模块、独立profile/迁移、pure/PG测试与当前治理文档。
- **新增内容**：FactsBase两表、不可变触发器、严格Classification/原日期快照、自然去重/历史冲突、当前权限/范围/文件/时效指纹及同事务审计。
- **修改内容**：同步当前状态、ADR-029/API/数据库/架构/需求与运行验收说明；保留M0和旧heads。
- **删除内容**：无。
- **Bug 修复**：本Task初稿无界peer查询改SQL限量；最终期限/caller rollback补守卫；JSONB防护cap容纳合法转义字段。首PG两夹具前提修正，旧服务未顺改。
- **测试结果**：35pure/25PG（最后162.52s）、160相关、333契约模式、170前端/Type Check/demo+auth Build、原文/生成/8module内存编译通过；首PG23pass/2fail已如实保留。Lint/Python静态类型无入口、browser/全PG/POSIX/真实身份与资料/备份清理/部署未执行，原因见验收。
- **已知问题**：真实事实/审核/发布关闭，SQL角色/RLS/物理恢复等未验；T15旧helper最后身份查询后的原file期限窗口仅记录，T17自有最终守卫覆盖当前路径；不宣称旧路径已修。

## T16 · 不可变文档与证据

- **日期**：2026-10-03，Asia/Hong_Kong。
- **Task ID**：T16。
- **状态**：已完成源码、合成原文人工抽查与隔离实库验收。
- **修改目的**：固定可重放的原文字节版本和确切范围片段，防越范围或过期复用。
- **修改文件**：26路径（10旧/16新），完整清单见[T16验收](acceptance/T16_evidence.md)；evidence六模块/profile/三个专项测试、合成原文/人工报告及治理文档；.gitattributes仅新增确切原字节保存规则。
- **新增内容**：独立三表/head与两个不可变trigger、UTF8 byte/physical line/原文片段hash、完整server scope指纹、限定审核衍生读/current proof/同TX审计；ADR-028，无新依赖或HTTP。
- **修改内容**：创建实际read source bytes/hash，getter只验当前metadata及captured hash；当前scope/许可/身份/时效与原始asset均重验，真实默认关闭，旧head/原迁移/wire/UI不改。
- **删除内容**：无用户文件或既有功能删除；降级只本域表/trigger/function。
- **Bug 修复**：本新代码增加读时原size span约束、可达物理行/复制DTO重验、同hash原asset保护、future timestamps及最后查询后时效检查；不顺改既有代码。专项无实际失败，后续补丁分轮复验而不冒称首轮覆盖。
- **测试结果**：最终33pure/19PG、相关143pass+1skip、333契约模式、前端170/Type Check/两Build及原文/生成/范围检查；中间19PG两轮各通过但未加载最后补丁，最后70.44s为最终源码结果。不计程序/AI交叉复核为人工，人工项由2026-10-03用户直接回复确认；Lint/Python静态类型无入口，UI browser/全体PG/PDF/OCR/真实部署未执行。
- **已知问题**：原人工抽查阻塞已由用户确认解除；仅合成定位，不代表真实事实/发布验收。PDF页/节适配、真实事实审核/数据/ACL/物理恢复/清理备份及部署仍未验收。

- **恢复复验**：2026-10-03用户回复“确认，继续执行 T16”；本次pure+PG52 passed68.10s exit0，源码/ini/原json与恢复时hash一致，当前docs状态及CHANGELOG同步。此前前端/相关回归保留实际历史结果，无源码变更不重复，不伪称新运行。

## T15 · 人工结构化导入

- **日期**：2026-10-03，Asia/Hong_Kong。
- **Task ID**：T15。
- **状态**：已完成源码/隔离实库验收，真实路径关闭。
- **修改目的**：把经许可的有界文件转为可审核候选，保留失败与来源版本。
- **修改文件**：24路径（9旧/15新），完整清单见[T15验收](acceptance/T15_manual_import.md)；ingestion/imports/独立profile/专项测试及治理文档。
- **新增内容**：1MiB/200行严格JSON/CSV、显式空值/脚注、固定错误报告、独立三表及自然唯一键、T49同事务当前许可/文件证明/审计、ADR-027；无新依赖。
- **修改内容**：整批错误零候选、候选draft/unresolved；真实与M0/旧发布事实隔离，原迁移/head/HTTP/UI不改，其他66卡保留。
- **删除内容**：无用户文件或既有功能删除；降级只本Task三表。
- **Bug 修复**：本新代码整批DTO位置重验、允许同record多字段、同步尺寸提前拒绝、旧资产双证明及封闭领域错误回滚后恢复；MFA测试边界修正，不修改旧策略或旧T49。
- **测试结果**：46纯/19PG、相关145pass+1skip、333契约模式、前端170/Type Check/两Build及原文/生成检查通过；首PG17pass/2fail后修复重跑。实际命令、范围和未执行项见验收；Lint/静态Python类型无入口、UI browser/全体PG/POSIX/正式部署未执行。
- **已知问题**：真实来源/审核/TTL责任门槛保留；PDF、后台作业、正式事实发布本Task未实施，unknown脚注/定位不能冒充已审证据。

## T49 · 持久幂等基础

- **日期**：2026-10-03，Asia/Hong_Kong。
- **Task ID**：T49。
- **状态**：已完成源码/合成与隔离实库验收，正式TTL/真实业务关闭。
- **修改目的**：为T15/T19依赖建立同事务、并发安全及撤权后仍重验的最小资源回执。
- **修改文件**：24路径（9旧/15新），完整清单见[T49验收](acceptance/T49_persistent_idempotency.md)：idempotency五模块、canonical、独立profile/0001、四专项tests、契约/验收和治理文档。
- **新增内容**：actor/operation/key摘要唯一、bounded canonical JSON SHA256、processing/completed/deferred COMMIT完成约束、有限资源引用与TTL、强制即时身份/角色/用途/领域verifier、same-TX audit；ADR-026，无新依赖或HTTP。
- **修改内容**：后续内部业务可在同Session组合，ownTX返回前提交；callerTX须最终rollback/commit后响应。原auth/catalog/storage heads、旧迁移/HTTP/wire/UI/原规格保持，其他66卡不改。
- **删除内容**：无用户文件/功能删除；过期只替换回执，不删除旧业务资源；降级只本Task新增表/trigger/function。
- **Bug 修复**：无既有应用Bug；新代码审查加入等待/业务/审计后payload重哈希、receipt再验及持久行重建、UTC fold/overflow固定错误，验证后无专项失败；未顺改无关代码。
- **测试结果**：48纯2.69s/19PG23.04s、相关450/契约模式333、前端170/Type Check/demo+auth Build与原文/生成/范围通过；首专项无失败。准备helper quotepath/encoding及尚未落盘目录读取失败单列验收，不能算测试通过；实际命令与未执行见验收。无入口Lint/Python静态类型、无UI browser、全体PG、生产身份/权限/备份/部署未执行。
- **已知问题**：合成24h不是正式TTL；real_idempotency_ready默认false。TTL只控制重放窗口，未请求过期摘要物理清理/删除与备份传播未验收，不称留存合规。trusted callback不是恶意代码或外部副作用沙箱，未来领域Task必须实现current资源guard。

## T14 · 文件存储边界

- **日期**：2026-10-03，Asia/Hong_Kong。
- **Task ID**：T14。
- **状态**：已完成源码、合成与隔离实库验收，真实处理关闭。
- **修改目的**：隔离招生原文与私有附件，有界校验、逐次服务器权限和可追踪事务失败。
- **修改文件**：31路径（14旧/17新），完整清单见[T14验收](acceptance/T14_file_storage.md)：storage八文件/独立profile与迁移/四测试，authorizer最小增量和治理文档。
- **新增内容**：随机UUID命名空间、本地无覆盖及reparse/hardlink拒绝、有限PDF/CSV/JSON校验、独立storage_objects、替换接口、same-TX授权审计、补偿与delete_pending重试；ADR-025，无新依赖。
- **修改内容**：POLICY_VERSION=T14_owner_v3、closed存储能力和同事务owner检查；T09 metadata grant不授予bytes。原HTTP/前端/auth及catalog头/旧迁移/原规格不改，其他66卡保留。
- **删除内容**：无用户文件/功能删除；逻辑与物理删除仅针对隔离合成附件，降级仅本次新表。
- **Bug 修复**：新Windows目录READ_ATTRIBUTES句柄实际未阻止rename，改GENERIC_READ后竞态通过；FileDispositionInfo使用1字节BOOLEAN；新删除完成事务COMMIT失败不再错误返回deleted，实际PG延迟触发器验证pending与重试。
- **测试结果**：最终43 Unit通过/1权限skip、17 PG、531相关/333契约模式、170前端/Type Check/demo+auth Build、原文/生成/范围通过。首次Unit39pass/1fail/1skip保留；首次PG17pass后扩真实completion失败断言并最终17pass29.34s。实际命令、平台限制与未执行详见验收；无入口Lint/Python静态类型、无UI browser、全体PG、POSIX、真实环境/备份/部署未执行。
- **已知问题**：文件quarantined不是安全扫描或事实发布；FS/DB不是两阶段，清理失败孤儿不可用；来源TTL仅合成1天，正式TTL未选；真实负责人/身份/法律/ACL/删除作业/备份恢复门槛保留。

## T13 · 来源登记与权限记录

- **日期**：2026-10-03，Asia/Hong_Kong。
- **Task ID**：T13。
- **状态**：已完成源码/合成与隔离实库验收，真实来源启用关闭。
- **修改目的**：让来源有明确许可记录、服务器责任与复查期限，避免把官方标签当使用权或自动抓取授权。
- **修改文件**：28路径（16旧/12新），详见[T13验收](acceptance/T13_source_register.md)：sources六文件含namespace、0003、纯/PG三测试、catalog head/env/DateStore与旧T12 target、authorizer及相关文档。
- **新增内容**：独立来源根/只追加版本、三许可与basis/review参考、明确复查周期/责任UUID、closed SourcePolicy、同事务即时管理员能力及审计后时效重验；ADR-024，无新依赖或网络。
- **修改内容**：catalog当前头0003，POLICY_VERSION=T13_owner_v2使旧缓存重验；旧require_capability/HTTP/v2.t09/auth0006/M0/前端保持，其他66卡保留。
- **删除内容**：无（没有删除用户文件或旧功能）；降级仅隔离测试的新增来源表。
- **Bug 修复**：新SourceBase跨metadata字符串FK解析失败，改实际Column引用并复验；URL scheme数据库大小写与schema一致；新测试helper捕获既有AuthFlowError父型。无顺带修复无关问题。
- **测试结果**：31纯/18PG、相关542/契约模式333、前端170/Type Check/两Build及原文/wire/生成/范围通过；首PG7pass/11fail25.78s保留，修后18pass21.67s。命令与未执行检查详见验收；Lint/Python静态类型无入口、browser无UI变化、全体PG/真实Keycloak/法律/生产权限/备份/部署未执行。
- **已知问题**：D03正式负责人待答，real_sources_ready默认false；许可由管理员声明不冒充法律判断或事实审核。历史启用字段是快照，T15/T19须重新验当前许可/期限；无DB不可变trigger/RLS；T49 TTL待定。

## T12 · 日期事件契约

- **日期**：2026-10-03，Asia/Hong_Kong。
- **Task ID**：T12。
- **状态**：已完成源码/合成与隔离实库验收，正式期限/部署关闭。
- **修改目的**：保留日期类型/精度/IANA，避免虚构23:59、DST猜选和未审核UTC冒充官方期限。
- **修改文件**：23路径（13旧/10新），详见[T12验收](acceptance/T12_date_events.md)：四日期模块、0002、unit/PG专项、catalog当前头/env及两T11历史target、受影响文档。
- **新增内容**：严格事件/日期精度、包内锁定tzdata换算、candidate/official UTC分开、确切机会版本/合成约束、原文pending/conflict、同事务候选维护与ADR-023；无新依赖。
- **修改内容**：catalog当前头0002，CatalogBase五表/0001/M0/auth0006/wire/UI保持；T11历史检查固定001；只T12卡完成，其他66卡保留。
- **删除内容**：无（未删除用户文件或功能）；隔离测试降级仅清理本次日期schema数据。
- **Bug 修复**：无既有应用Bug；新fixture SQLSTATE/约束优先级假设及本地辅助脚本escape已纠正并复验，不冒称业务修复。
- **测试结果**：新纯43/PG11、相关274/契约模式333通过，前端170/Type Check/demo+auth Build、原文/生成/范围文档通过；配置5通过。首PG9pass/2fail、首次不存在目录命令未执行测试均保留，命令详见验收。Lint/Python静态类型无入口、browser无UI变化、全体PG/正式环境/人工审核/备份/部署未执行。
- **已知问题**：机械UTC仅计算候选；官方UTC仍NULL、真实证据/审核发布未建立；原文矛盾须人工标conflict，不自动NLP解析。生产权限/恢复及正式责任门槛、T49 TTL待定。

## T11 · 招生机会关系模型

- **日期**：2026-10-03，Asia/Hong_Kong。
- **Task ID**：T11。
- **状态**：已完成源码/合成与隔离实库验收；真实导入/发布关闭。
- **修改目的**：用明确dataset/program/年度范围和确切版本防止候选碰撞、DEMO混接，并保留M0/auth历史。
- **修改文件**：22路径（9旧文档/13新），完整清单见[T11验收](acceptance/T11_admissions_catalog.md)：admissions_catalog四文件、独立catalog配置/env/0001、四专项测试文件、契约/验收与治理文档。
- **新增内容**：五表/非空规范范围键、复合FK/完整唯一键、caller事务维护/锁与版本冲突、显式迁移和恢复说明；ADR-022，无新依赖。
- **修改内容**：仅T11卡完成，其他66卡保留；M0七表/旧迁移、auth0006、identity v2.t09、HTTP生成产物/前端/依赖/研究资料不变。
- **删除内容**：无（未删除用户文件或既有功能）。
- **Bug 修复**：新store逐五mapper验证Session.binds，拒绝default engine合法但catalog mapper错库；仅修当前Task。新PG测试helper超长拒绝类型假设已修，旧T09未标记PG问题只记录。
- **测试结果**：新schema80/配置5/最终PG30通过；1377回归选择通过（含14旧未标记PG）、395deselected/1既有warning；前端170/Type Check/demo+auth Build、生成/原文/范围/文档检查通过。首PG29pass/1fail及首次选择1363pass/14缺URL setup错误保留，实际命令详见验收。不声称本轮全部1777Python通过；Lint/Python静态类型无入口、浏览器无UI变化、正式环境/法律/备份/导入/发布未执行。
- **已知问题**：正式事实审核/发布/权限和运营门槛仍未就绪，store是可信内部维护而非授权API，DB无不可变trigger/RLS；生产恢复未执行；T49 TTL待定。旧T09 marker只记录，不顺带修改。

T11保存补充：源码已普通push并核对SHA。暂存URL正则误报配置单测中的合成占位表达式，shell未传递该辅助Python失败，不能宣称其首轮通过；已逐行核对并精确豁免该测试占位后重新扫描。只补日志/验收记录，不改源码或既有commit；实际命令与保存边界见T11验收。

## T10 · 审计与日志脱敏

- **日期**：2026-10-03，Asia/Hong_Kong。
- **Task ID**：T10。
- **状态**：已完成源码/合成与隔离实库验收，真实处理和部署关闭。
- **修改目的**：已实现关键操作责任可追踪，敏感输入不进入配置的常规日志，落实D06有限审计/日志维护。
- **修改文件**：39路径（24旧改/15新），完整清单见[T10验收](acceptance/T10_audit_redaction.md)：audit模块、0006、日志配置/测试、必要auth/privacy/grant事务接点与旧current-head断言、受影响文档。
- **新增内容**：封闭最小事件/DB白名单、同TX成功审计、事务退出后失败记录、内部operations+签名强度读/清理、服务器请求关联、显式日志配置/有界日历留存维护与ADR-021；无新依赖。
- **修改内容**：当前head0006，新增审计flush后权限/证明/期限重验；identity v2.t09/16paths、M0/foundation/前端/依赖保持；只T10卡标完成，其他66卡保留。
- **删除内容**：无（未删除用户文件或既有功能）。
- **Bug 修复**：合法foreign/私有extra不能覆盖server ID，危险msg/异常先丢弃；触碰mtime不延长日志期限；补位置参数外部事务边界、审计等待后的登录/授权期限重验。首整套发现旧迁移禁用logger后配置静默，显式重启固定logger并回归；默认factory全局副作用移除。新测试harness失败按真实过程记录，不冒充旧业务Bug。
- **测试结果**：最终Python1662 passed（365PG/1297其他）、1既有warning、398.14s；基础21/独立153/配置纯日志133；前端170/Type Check/demo+auth Build通过；原文/契约/范围/历史/链接/语法/暂存检查单列。首整套19failed/1641passed及其他首次失败保留，真实命令见验收。Lint/Python静态类型无入口、browser无UI/wire变化、真实IdP/法律/生产权限/收集器/备份/部署未执行。
- **已知问题**：真实处理、未来审核/发布/导出/删除业务仍关闭；生产collector/backup/D04/MFA/恢复与责任门槛未验收，DB无immutable trigger/RLS，外部副作用不保证。T49收据TTL仍待答复，不阻当前Task。

## T09 · 顾问/监护访问授权

- **日期**：2026-10-03，Asia/Hong_Kong。
- **Task ID**：T09。
- **状态**：已完成源码/合成与隔离实库验收，真实共享关闭。
- **修改目的**：精确独立确认、受权人接受、可到期撤销共享；角色/核心同意不能自动放行。
- **修改文件**：51路径（28旧改/23新），完整清单见[T09验收](acceptance/T09_explicit_sharing.md)：auth/grants、privacy/proofs、0005、identity/schema/TS、前端sharing/离线专项、必要旧head断言及受影响文档。
- **新增内容**：四张grant表、五HTTP操作、同TX双方账户锁/原证明绑定/SQL过滤、缓存/延迟readonly重验、独立确认UI；ADR-020及冻结契约，无新依赖。
- **修改内容**：当前head0005、identity v2.t09/16paths，原session wire/foundation保留；生成器限定JSON/UUID，tasks仅T09完成，其他66主卡保留。
- **删除内容**：无（未删除用户文件或功能）。
- **Bug 修复**：新到期输入拒数字伪UTC、limit拒float/exponent；subject/事务标记/慢锁后fresh proof与角色边界、缓存严格projection；notice失败UI仍提供负向退出/撤销。新测试fixture/harness错误和旧T08 milestone断言修复已复验，不冒称旧应用Bug。
- **测试结果**：Python1483 passed（321PG/1162其他）/1既有warning；独立160/基础14/契约110；前端170、Type Check、demo/auth Build、浏览器10通过。首轮整套1482/1failed与其他初期失败、真实命令及未执行项见验收；原文/范围/旧记录/生成/语法/暂存检查通过。Lint/Python静态类型无入口未执行，真实IdP/生产TLS/法律/部署/GRANT/RLS/清理未执行。
- **已知问题**：仅合成registry status/version字段和read/list，真实学生资料/文件/worker/共享未开放；正式责任/告知、Keycloak/MFA/恢复与上线门槛保留；可信维护SQL无immutable trigger/RLS、外部副作用不保证。T49收据期限待用户答复，不阻当前Task。

## T08 · 年龄、告知与准入流程

- **日期**：2026-10-03，Asia/Hong_Kong。
- **Task ID**：T08。
- **状态**：已完成源码/合成与隔离实库验收，真实处理未开放。
- **修改目的**：落实用户确认的D02年龄/未成年关闭及D06产品上限，身份与用途准入分开，确保撤回和旧许可失效。
- **修改文件**：51路径（25旧改/26新），完整逐路径清单见[T08验收](acceptance/T08_admission_privacy.md)；privacy模块、0004增量迁移、identity装配/契约、前端隐私设置、专项/浏览器测试及必要旧head/path断言；相关文档同步。
- **新增内容**：两张追加notice/admission版本表、五条本人/公开隐私接口、同Session用途guard/actor绑定、合成告知与默认真处理关闭、前端独立确认/撤回/账号失效处理；ADR-019与产品草案人工用户确认记录。无新依赖。
- **修改内容**：认证head0004、identity v2.t08（session五字段/foundation原产物保持）；SQL readiness验隐私列、限定JSON/UUID契约生成；年龄非成人减许可不受陈旧证明阻挡，声明与确认版本控制。tasks仅T08完成，其他66主Task卡保留。
- **删除内容**：无（未删除功能/用户文件）。
- **Bug 修复**：新增确认输入拒绝数字1/1.0；新告知/政策重新声明可再次确认，旧声明拒绝；坏/缺告知仍可撤回，旧撤回不影响新确认；年龄CHECK显式非空；CSS radio尺寸、过期确认展示与禁用。新测试导入/错误契约假设及浏览器harness等待修复，不冒称生产Bug。
- **测试结果**：最终全回归1274 passed/1既有warning（277PG/997其他），T08独立安全102、契约75；前端116、Type Check、M0/auth两Build、最终浏览器9通过；生成两profile/M0/原文/35冻结路径/其他66Task卡/语法/空白检查通过。初轮失败、浏览器未完成/视觉失败及实际命令分别保留于验收；Lint无入口、Python静态类型工具未配置未执行；真实Keycloak/MFA/恢复/TLS/法律复核/部署/清理未执行，不能称全部检查通过。
- **已知问题**：正式主体/权利渠道/生产告知及法律适用性仍待验收；未成年私有与真实处理关闭，年龄本人声明非独立核验；删除/保留清理与数据库immutable trigger/GRANT/RLS未实现。T49收据期限待确认，不影响当前T08验收。不部署真实资料。

## T07 · 对象级授权基础

- **日期**：2026-10-03。
- **Task ID**：T07。
- **状态**：已完成。
- **修改目的**：落实服务端Principal、当前持久角色与owner授权，覆盖列表/对象/附件/导出/作业/缓存边界。
- **修改文件**：33路径（17旧改/16新），完整逐文件清单见[验收](acceptance/T07_object_authorization.md)；auth六模块、identity assembly、新0003、两旧迁移head/table断言与11新授权测试模块，AGENTS/README及本日志、tasks/DECISIONS/API/数据库/架构/需求/身份/新授权文档同步。无前端/依赖/旧迁移改动。
- **新增内容**：auth_user_roles/auth_owned_resources、冻结Principal、固定kind/action/角色矩阵、SQL owner/active parent过滤、版本touch、同Session执行/缓存重验、纯HTTP依赖；ADR-018和T07专项131/63。
- **修改内容**：身份factory懒装配Authorizer、统一安全服务错误与私有GET no-store；T06/T07统一账户优先锁序；认证head0003且旧账户无role。wire/schema/TS仍v2.t06，private_business_available=false；tasks仅T07完成。
- **删除内容**：无（未删除功能或文件）。
- **Bug 修复**：慢cache次要角色到期仍返回旧scope值、列表锁等待/重填窗口未充分锁新候选、旧JOIN会话锁与T07反序风险、直接授权异常被通用500截获；新fixture错误接口调用已纠正，不更改旧实现满足错误假设。
- **测试结果**：最终独立PG helper全回归实际1123 passed/1既有warning/exit0，marker收集200PG及923非PG；新集成131、PG63、旧认证450通过。web test62、typecheck、默认M0与显式auth build、当前T06浏览器12均exit0；21模块语法/原文/两生成profile/M0契约/35依赖兼容及范围/历史/文档/暂存检查通过，三新库残留检查及自有cluster停止见验收。首轮新fixture+缺统一handler118失败、慢cache新2失败修后复验；第一full1115通过但未含最后补测，最终以1123为准。Lint/Python静态Type Check无配置/工具未执行；真实Keycloak/MFA/recovery/生产TLS/SSO/部署未执行。实际命令、环境和失败详情见验收，不引用历史为本轮通过。
- **已知问题**：保留既有Starlette/AnyIO警告；角色维护/Principal/回调是服务器可信接口，无HTTP角色管理/RLS/DB immutable trigger/跨系统事务。真实业务、T08准入/T09grant/T10审计/worker及D04/D02/D06与公众发布门槛未完成；不自动开始后续Task。

## T06 · 会话撤销与 CSRF

- **日期**：2026-10-02开始，2026-10-03完成（Asia/Hong_Kong）。
- **Task ID**：T06。
- **状态**：已完成；验收/文档同步后保存源码并停止，不启动T07或部署。
- **修改目的**：保护Cookie身份下全部写操作、当前会话撤销及执行时重验；管理员强度策略默认关闭。
- **修改文件**：45路径（29旧改＋16新增），精确清单见[独立验收](acceptance/T06_session_csrf.md)：认证config/models/store/service/oidc/router及新assurance/http_security；identity factory、0002_auth_t06、生成器/identity JSON与TS、auth前端3模块及测试、新T06浏览器夹具/脚本、security包与7专项文件、新单测、受影响的3个旧契约/实库HTTP测试；README/AGENTS/config说明与本日志/tasks/DECISIONS/API/数据库/架构/需求/身份/验收文档。
- **新增内容**：会话随机CSRF摘要/密文pair、固定Origin中央unsafe保护、200当前退出与401重复/到期清Cookie、可信执行引用/当前权限重验；固定签名可选acr/amr/auth_time与来源、默认关闭独立adminclient强度策略及无角色授予；增量迁移兼容旧session。无新依赖。
- **修改内容**：identity v2.t06增7路径schema/TS、auth内存token退出及异步竞态保护，旧head/logout断言最小更新；Task状态、D04部分配置说明和受影响运行文档同步。默认foundation/M0、T04接口、原输入及旧迁移/验收保留。
- **删除内容**：无。
- **Bug 修复**：锁等待到期fresh校验、回调后旧assurance/provenance、最终权限重验与父层DEMO写拒绝缓存头；收集auth.conftest同名冲突用独立security包隔离。首轮旧head1失败与前端测试TS2339已修复验；辅助路径/标题/中文Git读取失败及暂存末尾空行检查失败均修正，无无关重构。
- **测试结果**：全新隔离PG16.15端口55436/两个测试库，helper注入两URL后`.\.venv\Scripts\python.exe -m pytest -q --tb=short`929 passed（792非PG/137PG），1既有warning，87.88s，exit0；专项security/auth132 passed（92PG/40非PG），最终追加真实factory无DDL断言同用例1 passed；unit/auth165 passed。`.\scripts\web.ps1 -Action test`62 passed，typecheck及默认M0/显式auth build均exit0；新Node浏览器12 checks通过，无外网/页面错误。24模块py_compile、两profile --check、verify_contract、verify_originals、uv pip check均exit0；范围/历史/文档/暂存核对见验收。首full收集1error、旧认证148pass/1fail及前端首次类型错误真实记录并已复验。新PG/schema/browser服务按自有范围清理，旧库未动。Lint/Python静态类型无入口且ruff/mypy未安装，未执行；真实Keycloak/MFA/恢复/TLS/注册/部署未执行，不称全部检查通过。
- **已知问题**：无T06阻断项；既有依赖warning、实际D04/D02/D06与公众发布门槛保留；T07资源权限/真实队列/全局SSO退出未实现。Git保存结果以最终commit/远程SHA核对报告为准。

## T05 · 登录与服务端会话

- **日期**：2026-10-02。
- **Task ID**：T05。
- **状态**：已完成；保存本Task源码后停止，不启动T06。
- **修改目的**：按用户明确授权实现固定Keycloak授权码登录与安全服务端会话；只实施T05。
- **修改文件**：46路径（16旧修改/30新增），精确清单见[验收](acceptance/T05_login_session.md)。新增auth六模块、api/identity、auth_alembic/auth_migrations、identity配置/生成契约、前端auth三模块/三测试、浏览器脚本/合成夹具、integration/auth七文件与契约测试；修改.gitattributes、AGENTS、README、main、config/identity/README、requirements.in/txt、生成器及本日志/tasks/DECISIONS/api/architecture/database/identity/requirements。
- **新增内容**：固定RS256/claims/JWKS/PKCE与有界换码、精确预登记active账户、加密/一次消费登录、摘要Cookie会话及登录轮换；独立四表迁移保留M0链，显式默认关闭入口与auth前端。新增joserfc1.7.5/cryptography50.0.2及cffi/pycparser哈希锁，既有版本不变；ADR-016与实施前契约/148新专项。
- **修改内容**：main显式auth模式仍保留M0默认；生成器精确identity profile与302/303无body类型，新增契约LF规则；任务状态/当前范围与影响文档同步。默认foundation/M0/schema/旧迁移/夹具/原始规格与其他Task保留。
- **删除内容**：无。
- **Bug 修复**：本Task审查补强换码/JWKS/验签耗时后fresh时效、完成时session TTL、mounted缓存头、production SQLite拒绝及注入service启动复核。首轮generator默认loader位置参数导致旧3项失败，恢复zero-argument兼容；测试超长Windows参数ID setup错误改短ID、PG输入长度先触发DataError改为准确CHECK负例、浏览器fixture CSP增加固定回调origin，均复验。无无关重构。
- **测试结果**：最终读取ignored专用环境JSON设置TEST_POSTGRES_URL后`.\.venv\Scripts\python.exe -m pytest -q --tb=short`758 passed/1既有Starlette-AnyIO warning/退出0（54.73s，含45真实PG；713非PG），独立`tests/integration/auth -q`128 passed、契约20 passed，修复生成器后两契约59 passed。此前full offline3 failed/709 passed/45排除，修复后712 passed/45排除，新增生产SQLite负例纳入最终758。`.\scripts\web.ps1 -Action test`42 passed、`-Action typecheck`/`-Action build`退出0；显式auth vue-tsc/Vite --outDir .cache构建退出0。Node最终8浏览器项通过，无页面错误/外网请求；19新改Python模块py_compile、两profile --check、verify_contract、verify_originals、uv pip check均退出0；范围/历史/文档/暂存审核另见验收。PG与浏览器helper按自有路径停止，旧T01库未动。Lint/Python静态类型无入口且ruff/mypy未安装，未执行；真实Keycloak/生产TLS/部署/MFA/恢复未执行，不宣称全部检查通过。
- **已知问题**：真实tenant/版本/地域、管理员MFA/恢复、D02准入、D06正式留存/清理及其他发布门槛未解除；注销/CSRF/资源授权等留后续Task，默认关闭且不部署。1条既有依赖弃用警告未顺带升级；最终Git上传以核对结果报告。

## T04 · 正式身份供应商边界

- **日期**：2026-10-02。
- **Task ID**：T04。
- **状态**：已完成；验收/文档同步后保存源码并停止，不启动T05。
- **修改目的**：按用户要求先明确D04身份供应商配置，再建立可替换、可离线测试的身份边界；用户明确选择自托管Keycloak。
- **修改文件**：新增`services/api/app/auth/{__init__,schemas,provider}.py`、`config/identity/{README.md,offline.example.json,keycloak-boundary.example.json}`、`tests/unit/auth/{conftest,test_configuration,test_login_context,test_provider_boundary}.py`、`docs/identity.md`及`docs/acceptance/T04_identity_provider.md`；修改`AGENTS.md`、`README.md`、`docs/requirements.md`、`docs/architecture.md`、`docs/api.md`、`docs/database.md`、`docs/tasks.md`、`docs/DECISIONS.md`、本日志。9旧改+12新增，共21路径，精确清单见验收。
- **新增内容**：D04自托管Keycloak配置基线、ADR-015、实施前契约、131项新专项与实际验收；冻结配置/可替换Protocol、固定合成Provider、精确主体元组和PKCE/nonce/state/时效纯绑定。
- **修改内容**：当前Task状态/授权边界与D04部分确定状态；无真实身份、应用wire/路由或数据库变化。
- **删除内容**：无。
- **Bug 修复**：本Task首版固定URL接受无效主机/空或0端口/编码控制与点段，已收紧并补负例；lone surrogate proof逸出原UnicodeEncodeError，已固定安全转换。首轮两个测试假设错误（RFC预期漏末尾M、helper提前拒未知assertion）和独立审查脚本入口笔误已修；没有顺带修改既有应用。
- **测试结果**：`.\.venv\Scripts\python.exe -m pytest tests/unit/auth -q`最终131 passed、1既有warning、退出0；首次97 passed/2 failed已保留原因。`... -m pytest -m 'not postgres' -q`606 passed、4 deselected、1上述warning、退出0（15.83s）。`.\scripts\web.ps1 -Action test`18 passed、`-Action typecheck`/`-Action build`均退出0；7新模块py_compile、generate_contracts.py --check、verify_contract.py、verify_originals.py均退出0。独立URL/proof/生产/错绑及fresh-process无auth/M0/DB/网络审查通过；范围辅助保护98范围外文件及M0 schema/旧Task/日志/ADR，并做文档/链接/状态与实际暂存核对，21文件无越界。Lint/Python静态类型无入口且ruff/mypy未安装，未执行；PG4项排除，无持久化变化。真实Keycloak/换码/JWT/持久state与会话/MFA/恢复、浏览器/部署未执行，尚未实现或范围外，不宣称全部检查通过。完整命令/首次失败/限制见[T04验收](acceptance/T04_identity_provider.md)，最终commit/远程SHA在Git与最终报告核对。
- **已知问题**：无T04阻断项。既有Starlette/AnyIO弃用warning；原始Pydantic.errors可能含input，不直接日志，当前边界提供固定错误且无HTTP/log接入。真实tenant/版本/地域、管理员MFA与恢复配置尚未具备；真实身份与会话、D01/D02/D06及公众发布门槛保留。

## T03 · 演示/生产模式隔离

- **日期**：2026-10-01开始，2026-10-02完成实施及验收。
- **Task ID**：T03。
- **状态**：已完成；按持续授权提交推送源码后停止，不部署。
- **修改目的**：按用户授权隔离演示与生产入口、启动配置及目录读取策略。
- **修改文件**：29路径（23旧改+6新），精确清单见[计划与验收](acceptance/T03_mode_isolation.md)。后端settings/main/seed、api/v2三文件与新public/catalog_access；.env.example及新config生产基础示例；generator/JSON/TS产物/TS验收/三个既有v2测试及新security两文件；AGENTS/README、requirements/architecture/database/api/tasks、本日志/DECISIONS及新T03验收。旧输入/迁移/夹具/研究/锁文件/历史验收不改。
- **新增内容**：冻结V2RuntimeSettings、生产独立factory只挂/v2、模式矩阵/DSN/旧开关冲突校验、服务端派生应用查询策略及污染整体503、production配置示例、141项离线安全专项、运行模式与环境独立生成验收、ADR-014。
- **修改内容**：M0入口与直接seed加生产/verified拒绝守卫；v2 schema升级v2.t03、data/model运行枚举及app_environment/query_role必需字段；generator固定所有配置；本Task和受影响文档同步。M0 wire、mock/live/规则真值及持久化不改，其他Task未开始。
- **删除内容**：无。
- **Bug 修复**：本Task验收发现显式legacy_demo_mode=None不能覆盖旧DEMO_MODE别名，规范化初始化键后修复；工厂重验copy/construct、DSN身份query覆盖拒绝、DEMO拦截移至完整v2 middleware，防止 schema/重定向路径漏拦与候选类型污染返回500。未顺带重构无关业务。
- **测试结果**：`.\.venv\Scripts\python.exe -m pytest -m 'not postgres' -q`最终475 passed/4 deselected/1既有Starlette AnyIO warning、退出0；security+v2专项187 passed，contracts最终91 passed；前端web.ps1 -Action test18 passed、typecheck/vue-tsc和build/Vite均退出0。generator --check、verify_contract、verify_originals、compileall退出0，范围/旧历史/其他Task/M0规范化OpenAPI检查通过。初契约专项3 failed/88 passed，修复上述alias后通过；初M0误引用不存在test_eligibility.py退出4、无测试运行，纠正为test_rules.py后66 passed/4排除；首次stage辅助统计遗漏已入索引新增文件退出1，修正辅助后重新验证，实际29路径索引未越界。Lint/Python静态类型没有配置入口且ruff/mypy未安装，未执行；PG4项排除/未执行（无持久化变化），监听/浏览器/生产部署/真实数据/live均未执行且范围外，不声称全部检查通过。完整实际命令及保护结果见验收，提交推送及SHA以本Task的Git和最终报告核对。
- **已知问题**：既有Starlette/AnyIO弃用warning；公众身份、真实目录/资格/计划与PostgreSQL登录角色/GRANT/RLS仍未实现，query_role仅应用策略。基础verified无密钥只读配置/空目录、业务不可用；M0前端仍演示。无T03阻断项，不以本Task解除D01–D08或发布门槛。

## P04 · GitHub仓库与验收后提交推送规则

- **日期**：2026-10-01。
- **Task ID**：P04。
- **状态**：已完成；仓库及基线上传已验收，本轮停止。
- **修改目的**：按用户新授权创建私有仓库、上传已验收项目，并将后续Task成功后提交推送设为持续规则。
- **修改文件**：`AGENTS.md`、`README.md`、`.gitignore`、`docs/tasks.md`、本文件、`docs/DECISIONS.md`；新增`.gitattributes`、`docs/acceptance/P04_git_repository.md`。应用、依赖、原规格及历史记录不改；Git仅本仓库必要分支/remote变化。
- **新增内容**：私有chanbilly-lab/study-admissions-agent仓库、101文件现状首个commit及上传；验收后限定提交推送持续规则、ADR-013；.gitattributes原输入字节/生成LF保护与私有运行文件忽略规则；独立验收。
- **修改内容**：P04仓库治理已完成，验收成功后限定提交推送规则已生效；其他业务Task仍未开始，不以源码上传授权推断部署授权。
- **删除内容**：无。
- **Bug 修复**：无。
- **测试结果**：gh auth/create --private/repo view、branch -m main/remote add、显式路径add/commit/push均退出0。首个commit819e5cb3e1640249b6d0ddb8155f5f825ee567b8，ls-remote一致，远程101 blobs/truncated=false，私有/main准确。P04辅助--prepare/--stage/--stage --final退出0：6旧改+2新、93范围外哈希保护、101候选无高置信token/私钥形态、22私有路径忽略、6文档86本地链接、旧Task/日志/ADR保留；原规格与生成产物暂存blob字节未变。verify_originals.py、verify_contract.py和generate_contracts.py --check退出0。完成记录随P04独立提交推送，最终HEAD/工作区检查结果见Git及最终报告。初git log/repo view退出1为无commit/仓库不存在；原core.autocrlf暂存warning已记，无创建/上传失败或全局设置变化。应用Unit/Integration/Lint/Type Check/Build、PG/浏览器/部署本轮未执行，纯治理变更，不用T02历史作本次通过。完整命令见[独立验收](acceptance/P04_git_repository.md)。
- **已知问题**：无P04阻断问题。代码保存不等于公众部署；未来Task仍需审查实际hunks和用户既有暂存，不能依赖.gitignore自动排除已跟踪秘密。

## T02 · /v2 基础契约

- **日期**：2026-10-01。
- **Task ID**：T02。
- **状态**：已完成；本轮停止。
- **修改目的**：按用户授权建立独立v2契约与生成流程，保留M0行为。
- **修改文件**：新增`services/api/app/api/__init__.py`及`api/v2/{__init__,router,schemas,errors}.py`、`packages/contracts/v2/{openapi.json,generated.ts}`、`scripts/generate_contracts.py`、`tests/backend/test_v2_api.py`、`tests/contracts/test_v2_http_contract.py`、`tests/contracts/test_v2_generation.py`、`apps/web/tests/v2-contract-types.ts`、`docs/acceptance/T02_v2_contract.md`；修改`services/api/app/main.py`、`README.md`、`AGENTS.md`、`docs/requirements.md`、`docs/architecture.md`、`docs/api.md`、`docs/tasks.md`、`docs/CHANGELOG.md`、`docs/DECISIONS.md`。9旧文件修改+13新增，精确清单见验收。
- **新增内容**：独立v2 factory和OpenAPI；foundation配置/空目录、统一成功/安全错误/服务端请求编号、分页边界；稳定离线TS/schema生成及只读漂移拒绝；109项新专项、前端类型编译验收、实施前契约和最终记录；ADR-012。
- **修改内容**：M0 main只增加v2导入和挂载，v1协议保持；文档区分当前基础与未来公众业务，T02状态/日志/ADR同步，其他Task未启动。
- **删除内容**：无。
- **Bug 修复**：无既有业务Bug改动；本任务验收辅助的Settings字段、schema文本换行比较及engine属性写错已修正，实际失败保留在验收，不顺带重构M0。
- **测试结果**：`.\.venv\Scripts\python.exe -m pytest -m 'not postgres' -q`最终306 passed、4 deselected、1条既有warning、退出0；HTTP46/生成35/实际契约28含于其中。`... -X utf8 scripts/verify_contract.py`与`... -X utf8 scripts/generate_contracts.py --check`退出0。`.\scripts\web.ps1 -Action test`18 passed、`-Action typecheck`vue-tsc、`-Action build`vue-tsc/Vite均退出0。Python py_compile、`scripts/verify_originals.py`、`.cache/t02_validate_20261001.py --final`及只读Git检查退出0；77保护文件、原文/docs01–05/旧验收/迁移/夹具/研究/锁文件不变，M0 OpenAPI规范化对照不变。辅助初次两次退出1后修正通过，应用测试无失败。PostgreSQL4项排除/未执行（无持久化变化），Lint/Python静态类型无配置入口，浏览器/监听服务/公众部署和真实数据检查未执行且范围外；不引用旧测试为本次通过。完整实际命令和限制见[独立验收](acceptance/T02_v2_contract.md)。
- **已知问题**：既有Starlette/AnyIO弃用warning；TS不强制数值/长度/封闭对象/Page跨字段规则，已由OpenAPI/服务端约束并注明。公众认证、真实目录、私有写入、生产隔离及keyset仍未实现，本轮不发布、不继续其他Task；无T02阻断项。

## E01 · Docker Desktop 启动修复

- **日期**：2026-10-01。
- **Task ID**：E01。
- **状态**：已完成；Linux引擎与实际容器烟测通过，与tasks同步。
- **修改目的**：响应用户修复本机Docker的新请求，先确认缺失数据盘与恢复条件，避免误清理旧数据。
- **修改文件**：`docs/tasks.md`、`docs/CHANGELOG.md`；新增`docs/acceptance/E01_docker_repair.md`。诊断/保护缓存`.cache/e01-docker-20261001-105443/`不纳入版本库。
- **新增内容**：环境维护Task与独立验收、项目85文件基线、配置/注册/现存引擎盘/日志备份及官方校验安装包；本机新Docker数据盘与烟测镜像。
- **修改内容**：本机Docker Desktop由4.22.0升级为4.93.0，原all-users模式保留；经明确同意重建空Docker环境、关闭默认Ubuntu集成。项目仅记录变更；应用、迁移、夹具、依赖和T01/T50A历史验收未改。
- **删除内容**：经再次路径/空目录核对，只注销旧docker-desktop-data登记；烟测容器由--rm自动移除。无项目文件删除，没有注销Ubuntu或手工清理其他发行版。
- **Bug 修复**：解决Docker数据盘缺失导致的引擎启动失败；新建空环境不能算旧数据恢复。
- **测试结果**：初始Docker version退出1，Ubuntu/data两次/bin/true退出4294967295，有限扫描与保全已记录；官方包哈希/Authenticode通过，安装退出0。修复后`docker version --format '{{json .}}'`/`docker info --format '{{json .}}'`退出0（Client/Server29.8.1、Linux）；隔离hello-world实际运行退出0并清理容器，`docker ps -a`/`docker volume ls`为空、Compose5.5.1检查退出0，WSL状态/Ubuntu原注册与关闭集成校验退出0。原文与范围/历史/字段/状态/链接校验退出0：2旧文档改+1新增，83保护文件不变、18本地链接，未提交。首次下载停止后退出1，换系统curl成功；辅助后验收先语法错误、后大小写误判导致失败，修正最终退出0，详见[独立记录](acceptance/E01_docker_repair.md)。应用Unit/Integration/Lint/Type Check/Build、项目Compose数据库/PG/主机重启后启动/公众部署未执行：无应用变更，超出本地Docker烟测范围；联网下载/Hub拉取不冒充离线测试。
- **已知问题**：旧Docker镜像/容器/卷未恢复，Ubuntu数据盘仍缺失且未修。Docker当前保持运行；不自动继续业务开发。详见[独立记录](acceptance/E01_docker_repair.md)。

## T50A · 2026年全国高校来源候选文件登记

- **日期**：2026-10-01。
- **Task ID**：T50A。
- **状态**：已完成；与tasks及独立验收同步，T50后台未开始。
- **修改目的**：按用户授权在T01之后独立推进可核验的2026全国高校官方来源候选登记。
- **修改文件**：新增`data/research/source_registry_2026.json`、`scripts/verify_source_registry.py`、`tests/research/test_source_registry.py`、`docs/acceptance/T50A_source_registry.md`；更新`README.md`、`AGENTS.md`、`docs/requirements.md`、`docs/architecture.md`、`docs/data_strategy.md`、`docs/tasks.md`、`docs/CHANGELOG.md`、`docs/DECISIONS.md`。
- **新增内容**：48来源候选、34地区×7类型238缺口单元、只读无网络stdlib校验器、101边界测试、独立验收与ADR-011。
- **修改内容**：当前阶段/授权/目录与T01已验收现状同步，来源的访问/原年度/许可/审核区分；T50/T11/T13依赖保留。P02/原始输入/M0/旧迁移/夹具/依赖及T01记录未改。
- **删除内容**：无。
- **Bug 修复**：无应用修复；修正新验证器对招生资料与港澳台来源角色的过窄约束，以及父导航访问备注矛盾。
- **测试结果**：`.\.venv\Scripts\python.exe -X utf8 scripts/verify_source_registry.py`最终退出0：48来源/34地区/238单元（166候选、66未登记、6不适用），正式审核/发布/导入0、分母/覆盖率null，文件只读；`... -m pytest tests/research/test_source_registry.py -q`退出0：101 passed、无warning。原文保护脚本、py_compile、`.cache/t50a_validate.py`文档/本地链接/字段/引用/范围/历史保护及项目限定Git读取均退出0（13文档、93本地链接、11条ADR）；8旧文档改+4新增，73范围外文件不变，未提交。联网研究单列：31省级端点各打开一次，7正文/2外壳/16超时/2HTTP错误/4工具不可访问；全部来源16正文/3部分/29不可取得，均在JSON记录。首两次CLI退出1为角色兼容过窄，修正后通过；文档辅助命令遇换行/树缩进匹配退出1后适配完成；交叉审查备注冲突已修并重验。未执行应用全套/PG/前端Unit/Type Check/Build/浏览器/部署/性能/恢复及Lint/静态类型工具：无相关业务变更及工具配置，语法校验不冒充它们。详细实际访问、命令、失败和限制见[独立验收](acceptance/T50A_source_registry.md)。
- **已知问题**：全国高校/专业事实未导入，多数培养/就业来源未登记，本年适用映射/原文/许可/审核及责任/完整覆盖门槛待完成；来源登记不算全国采齐或发布，不启动T50后台/T11/T13/爬虫。本轮停止。

## T01 · PostgreSQL基线验证

- **日期**：2026-10-01。
- **Task ID**：T01。
- **状态**：已完成；四项实库和CLI验收完成，与tasks同步。
- **修改目的**：补齐M0历史未执行的PostgreSQL基线，验证幂等、保留、回滚与可丢弃schema迁移往返。
- **修改文件**：`tests/backend/test_persistence.py`、`README.md`、`AGENTS.md`、`docs/tasks.md`、`docs/CHANGELOG.md`、`docs/M0_TEST_REPORT.md`（只追加）；新增`docs/acceptance/T01_postgresql.md`。
- **新增内容**：隔离PGfixture与四项实库测试、独立验收和新日期实际记录。
- **修改内容**：持久化验收覆盖、当前任务/运行检查说明；旧离线测试保留，0001_m0/DEMO夹具/业务/依赖/配置未改。
- **删除内容**：无；临时PG服务已关闭，缓存保留。
- **Bug 修复**：无应用修复；不处理已有弃用警告或Docker环境故障。
- **测试结果**：专用PostgreSQL16.15空库（loopback55432）上`.\.venv\Scripts\python.exe -m pytest tests/backend/test_persistence.py -m postgres -q`退出0：4 passed、4 deselected、1已有警告；`... -m pytest -m 'not postgres' -q`退出0：96 passed、4 deselected、1已有警告。CLI upgrade/current到0001_m0、seed2/7/4/9、重seed0均退出0；psql八表/计数/残留schema0检查退出0；pg_ctl stop退出0、status预期3、监听0。原文脚本、py_compile、`.cache/t01_validate.py`范围/历史/任务日志检查及项目限定Git状态均退出0；6旧文件改+1新增，74范围外文件不变，无提交。代理另执行无URL的PG检查4 skipped/4 deselected及4项离线持久化通过，仅作为缺环境语义，不算实库通过。Docker version退出1，Desktop WSL引擎失败后改用.cache官方ZIP临时库；ZIP下载/准备退出0，与离线应用检查分开。未执行Compose16.6-alpine容器路线、前端Unit/Type Check/Build/浏览器、Lint、公众部署/性能/备份恢复，原因见[独立验收](acceptance/T01_postgresql.md)及[M0报告新增日期](M0_TEST_REPORT.md)。只读交叉审查无阻断缺陷。文档检查首轮退出1，因独立验收用中文数量而校验要求passed关键字；同步明确统计后复跑退出0（12文档/77本地链接/74保护文件），未发生应用测试失败。
- **已知问题**：Docker/WSL仍不可用；1条Starlette/AnyIO弃用警告；验证限PG16.15本地M0，公众功能仍未实施。下一项来源候选登记独立进行，T50后台依赖T11/T13未解除。

## P03 · 2026年全国高校资料范围确认

- **日期**：2026-10-01。
- **Task ID**：P03。
- **状态**：已完成；仅规划范围同步，与tasks的P03记录一致。
- **修改目的**：落实用户确认的2026年、全国高校含大陆及港澳台且招生体系分别建档，避免时间和地域口径混用。
- **修改文件**：`AGENTS.md`、`README.md`、`docs/requirements.md`、`docs/data_strategy.md`、`docs/tasks.md`、`docs/CHANGELOG.md`、`docs/DECISIONS.md`。
- **新增内容**：2026资料时间/地域口径、P03任务与ADR-010。
- **修改内容**：当前范围、D03/D08部分确认与剩余待决；保留单省个性化与M0历史基线。
- **删除内容**：无。
- **Bug 修复**：无应用修复。
- **测试结果**：2026-10-01：`.\.venv\Scripts\python.exe -X utf8 .cache/p03_validate_20261001.py` 最终退出0：10份UTF-8文档、68个本地链接、67个未开始任务/402项原业务字段、249条无环依赖边、四条日志40项字段、10条ADR70项字段、2026大陆及港澳台范围和时间语义检查通过；P00–P02任务/日志及ADR-001–009历史内容保留，研究JSON哈希不变。仅7份旧文档改变，无新增纳入检查清单文件，范围外73文件哈希不变。首次校验退出1因文字关键词过窄（要求“真实毕业届”，文档用graduation_cohort字段），改为对应字段检查后通过。`.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py` 退出0，两份原始输入未变；`git -c safe.directory=D:/Projects/study -c core.quotepath=false status --short` 退出0，文件仍未跟踪，未提交。只读交叉审查无阻断问题。Unit Tests、Integration Tests、Lint、Type Check、Build、PostgreSQL实库、浏览器/部署和联网核验未执行：本轮只同步既有规划和用户确认，不改运行代码/配置/依赖/数据，不引用历史应用结果作为本次通过。
- **已知问题**：全国2026资料尚未实际采齐，首版完整覆盖门槛、审核/使用权责任与投入未定；不启动开发或采集。

## P02 · 全国真实资料策略与官方研究样本

- **日期**：2026-10-01。
- **Task ID**：P02。
- **状态**：已完成；仅规划及研究样本，与tasks P02同步，不代表全国采集或功能实现完成。
- **修改目的**：补充用户要求的全国分数线、院校历史录取、学院/专业培养与实际毕业结果，避免口径混用并拆成可验收小任务。
- **修改文件**：`AGENTS.md`、`README.md`、`docs/requirements.md`、`docs/architecture.md`、`docs/database.md`、`docs/api.md`、`docs/tasks.md`、`docs/CHANGELOG.md`、`docs/DECISIONS.md`；新增 `docs/data_strategy.md`、`data/research/official_samples.json`。
- **新增内容**：资料策略、隔离的官方研究样本、T50–T67 与 ADR-009、D08 待决。
- **修改内容**：相关需求/目录/架构/数据库/API 规划与数据质量、覆盖和开发约束同步。
- **删除内容**：无。
- **Bug 修复**：无应用 Bug 修复；修正新任务依赖说明循环及研究/API口径不一致，属于规划与研究记录修正。
- **测试结果**：2026-10-01：`.\.venv\Scripts\python.exe -X utf8 .cache/p02_validate_20261001.py` 最终退出0：10份UTF-8文档、64个本地链接、67个Task/402项业务字段/67个未开始状态、249条无环依赖边；原49项Task的294项业务字段和P00/P01历史记录内容保留；三条日志30项字段、9条ADR63项字段；研究14来源/14观察/34地区登记，正式审核/发布数均0；仅9份旧文档改变、2份新增，范围外纳入检查的69文件哈希不变。初次校验退出1：尾部空白被误判历史内容改变，调整为内容对照；随后退出1：新任务依赖栏把后续批次验收写成前置形成循环，已移出依赖；修正及终审调整后重跑通过。`.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py` 退出0，两份原始输入未变；`git -c safe.directory=D:/Projects/study -c core.quotepath=false status --short` 退出0，文件仍未跟踪，无提交。只读交叉审查后的课程原名、来源页面代码/统计人群、通胀依据、四态比较与公开访客契约均已同步。官方联网研究单列，部分正文/复取失败已记录，不是离线应用测试。Unit Tests、Integration Tests、Lint、Type Check、Build、PostgreSQL实库、浏览器和部署检查未执行：仅修改规划/研究记录，未改变运行代码/迁移/依赖；不使用历史测试作为本次通过。
- **已知问题**：全国完整采集、国内就业数值、正式原文快照/使用权审批/人工审核与发布尚未完成；网页超时/重定向和PDF正文失败已记录，未拿搜索摘要补值。D01–D08剩余决策保留，T01–T67均未开始；个性化仍单省高考＋英国本科，无新API/页面/采集器。本Task到此停止。

## P01 · 开发规则与记录同步

- **日期**：2026-10-01。
- **Task ID**：P01。
- **状态**：已完成（仅文档治理），已与 tasks 的 P01 表格/任务卡同步。
- **修改目的**：落实用户提供的 AI Development Rules，统一开始前阅读、范围保护、变更/决策记录、任务状态、文档同步和完成报告。
- **修改文件**：`AGENTS.md`、`README.md`、`docs/tasks.md`；新增 `docs/CHANGELOG.md`、`docs/DECISIONS.md`。
- **新增内容**：CHANGELOG 记录规范；既有规划决策索引及本次治理决策；P01 任务卡；T01–T49 显式状态。
- **修改内容**：AGENTS 必读六文档、依赖说明、检查规则、ADR/同步要求及固定七标题；README 导航和目录；tasks 状态、记录同步及完成定义。
- **删除内容**：无；保留原始规格、P00/M0 历史记录与现有功能。
- **Bug 修复**：无应用 Bug 修复；补齐缺失的治理文档和任务状态标记。
- **测试结果**：PowerShell 内联 Python（`.\.venv\Scripts\python.exe -X utf8 -`）退出0：9份 UTF-8 非空文档、51个本地链接、49个开发 Task 的294项业务字段和49个未开始状态、143条无环依赖边；两条日志的20项必填字段、8条 ADR 的56项必填字段、六份必读文档和固定七标题通过。前后逐字段对照确认开发任务业务字段及P00历史验收记录未变；哈希仅3份旧文档修改、2份新增，范围外73文件未变。`.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py` 退出0，两份原始输入未变；`git -c safe.directory=D:/Projects/study -c core.quotepath=false status --short` 退出0，文件仍未跟踪，未提交。文档交叉审查无阻断问题。Unit Tests、Integration Tests、Lint、Type Check、Build、PostgreSQL 实库、浏览器和部署检查本轮未执行：本任务只改文档，不涉及运行代码或部署；不引用历史应用测试作为本次通过。
- **已知问题**：T01–T49 尚未开始；M0 实库检查缺口、D01–D07 剩余决策和公众功能未实现仍保留。规则已写入文档后仍需每次任务执行，未建立自动化强制机制。

## P00 · 项目需求与技术规划（历史补录）

- **日期**：2026-10-01；依据原 P00 验收记录，本次仅补录。
- **Task ID**：P00。
- **状态**：已完成（仅规划）。
- **修改目的**：在保留 M0 的基础上完成公众 MVP 需求、技术架构、目录、数据/API 与小任务拆分。
- **修改文件**：`README.md`、`AGENTS.md`；新增 `docs/requirements.md`、`docs/architecture.md`、`docs/database.md`、`docs/api.md`、`docs/tasks.md`。
- **新增内容**：五份规划文档、49 个未开始的开发 Task、未来公众服务的验收和待决事项。
- **修改内容**：README 项目入口/目标目录；AGENTS 规划边界和后续单 Task 规则。
- **删除内容**：无。
- **Bug 修复**：无应用修复；澄清规划中的完整表达式四态、持久事件创建顺序、删除恢复台账与权限边界。
- **测试结果**：历史证据见 [tasks 的 P00 验收记录](tasks.md)。当时原始文件命令 `.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py` 退出0，两份原始输入未变；内联 Python 文档检查退出0：7份文档、20个本地链接、49个 Task、294项必填字段、143条依赖边、无循环。这些不是 P01 重新执行的结果；当时应用测试/构建/PG/浏览器/部署未执行，因仅规划。
- **已知问题**：实际可运行实现仍是 M0 合成演示；PostgreSQL 实库尚待 T01，未成年准入等决策与公众功能未完成。补录不代表已有生产能力或发布授权。
