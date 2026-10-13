# T63 全国参考查询页面

2026-10-14 SEARCH-SELECT-01替换培养/毕业的自由UUID/对象ref为共享SchoolProgramPicker：关键字明确搜索/原生select/学校→专业、明确下一页、非自动首选；目录未启用/空/失败时禁资料查询。父页用所选program.id或精确层级outcome_subject_ref，不猜标识；改输入/资料届/层级取消并清旧选择/结果，generation及本地purpose/context_key拒旧回调。查询届与身份来源招生年分开，学院/学科暂无字典禁用。默认真实目录仍未装配，不以英国候选或DEMO填项；旧reference client/query不改，原统计页保持。新UI/SQL/HTTP/取消/类型/Build全部未执行（用户要求），见[契约](school_program_search.md)。

2026-10-13 UI-OPT-01展示增量：本地参考/模型关闭模式页头、native分段按钮导航、主范围与可选细分口径、独立主操作及短读屏状态；2026浙江三条由原表格改卡片，原文/技术hash可原生展开，来源/复核范围和关键未知常显。培养/毕业名录未接入的说明常显，原UUID/对象查询在高级details保留。客户端/控制器/默认参数/请求/取消/数据协议不改，不接英国研究候选。所有新UI/浏览器/类型/Build/对比度检查未执行（用户要求），旧截图/记录不作新证据；未来原表格选择器需适配。见[UI优化](ui_optimization.md)。

2026-10-12最小源码范围：新增显式`VITE_APP_MODE=reference`入口，仅挂载全国历史统计查询页。原未配置/`demo`及`auth`入口保持。新入口不自动开启真实查询、私有业务或生产服务；不回退DEMO。

数据契约复用手写`reference.minimal.1`与T59–T60独立空数据API。四类资料为覆盖、省级控制线、分数分布、历史投档与录取观测；年度/34地区内部标识明确选取。统计类普通高考路径固定，科类、批次与轮次原称可选；请求范围不完整、港澳台不适用和来源未启用分别说明。地区名称清单对应后端固定内部名录，不是行政代码，兵团不增加省级分母。

客户端使用同源`/reference/v2/reference`的显式GET、omit credentials、no-store及拒重定向；流式响应上限64KiB、15秒取消。闭合Envelope、verified/disabled Meta、精确filters、空items/发布ID/未知分母和有限missing_reason一起验证；Meta request_id必须与X-Request-ID响应头一致。任何真实记录、字段扩张、发布状态或范围不符均拒绝，错误仅显示固定文案；不展示服务器原错误或写入浏览器存储。筛选变化同步清空，重查/卸载AbortController取消并用generation拒绝迟到结果，读取前后均拒已取消信号。没有自动fetch、排名、概率或虚构证据链接。

源码修改范围：`features/reference/{client.ts,query.ts,ReferenceView.vue}`、`features/statistics/StatisticsView.vue`、`main.ts`、`vite.config.ts`。Vite新本地代理仅`127.0.0.1:8004`，删除`/reference`前缀。未来运行需显式选择`create_reference_app`并选择reference前端模式；本轮没有启动它们，通用Docker foundation也未装配此入口。

将来可测用例：入口可达且不改变demo/auth；显式查询；34地区/年/科类/批次/轮次回显一致；港澳台不适用；缺考试范围未知；未知分母不算0%；超长/非JSON/非空items/Meta污染/重定向拒绝；筛选清空、晚到结果、超时和卸载取消；请求失败不回填DEMO；标签、键盘与窄屏。全部测试、Lint、TypeCheck、Build、HTTP、浏览器、校验与演练均未执行（用户要求），不宣称交互或构建通过。

未验证与后续门槛：尚无正式已发布reader/PG查询、真实来源/原文证据、比较记录或生产装配；这里只提供空缺口。实际资格目标为各普通高考生源省份逐省适配，未覆盖的省/年/专业保持unknown。后续T64/T65按独立Task扩展参考页面，本Task不预先实现培养或毕业结果tab。

T64（2026-10-12）：新增可达培养tab和UUID/entry_cohort/teaching_year表单，路径UUID不重复传query，校验filters包含program_id与默认region=null。切换tab卸载取消，当前只空缺口，不造课程或假证据；所有测试/类型/Build未执行。

T65（2026-10-12）：新增毕业结果tab、明确毕业届/层级/对象/指标，空人群/分母/周期未知说明，不回上级/不排名。复用关闭client、filter清除/卸载/迟到取消，无默认当前毕业届；所有界面/类型/Build/浏览器未执行。

2026-10-13本批停止于T67。统计/培养/毕业结果三页已挂载；原T63文中‘仅统计tab’是当时范围，T64/T65后续扩展见上文。运行方式/全部未执行事项和完整Git文件清单见[批次记录](acceptance/SIMPLIFIED_BATCH_20261012.md)。

## 当前浙江2026真实批次（2026-10-13）

新本地参考5174默认省线/浙江2026但不自动fetch，收到reference.cutoffs.local.1才显示三行、来源/byte hash/公布原时区未知/抓取UTC/人工作用/许可未知与缺字段。scope切换清旧结果，其他年省不回填；旧空factory与其他资源仍empty。原T63–67未执行记录保留，本批另有8实际Edge/page_errors=[]。见[新批次运行说明](zhejiang_2026_cutoffs.md)。
