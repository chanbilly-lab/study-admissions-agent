# SEARCH-SELECT-01 学校与专业搜索选择

2026-10-14事前契约。用户要求学校/专业搜索选择替代手填UUID，缺失不编造，仍不测试，文档同步后PRIVATE保存。只交付源码；目录/数据与运行验证不凭默认值宣称完成。

2026-10-14源码与文档交付完成，当前尚未启用/导入正式目录。完整27文件、静态审阅与未验证项见[交付记录](acceptance/SEARCH_SELECT_01.md)。原运行实例没有自动加载Python新路由，本批未重启服务。

## 目录与选择契约

新增独立GET `/v2/reference/institutions`、`/v2/reference/programs`（专业必须institution_id）。参数q为0–100字的精确文本，country可选两位大写，limit默认20/1–20，cursor有界；重复/多余参数拒绝。响应reference.directory.1回显resource/filters(q,country,institution_id)/page、directory_available、missing_reason(directory_not_enabled/no_published_matches/null)、catalog_watermark可空、expected_total=null。选项含正式UUID、名称、国家、outcome_subject_ref（对应所选身份UUID字符串）及发布证明，专业还含父学校UUID；is_synthetic=false。证明含release_id、offering_id、offering_version、identity_evidence_entry_year、requirements_version。它证明名称/身份来源，不证明培养/毕业资料或资格。

q在HTTP边界trim，百分号/下划线作为字面字符；cursor为无padding的base64url。no_published_matches仅指本次请求页未返回匹配，不证明全国名录为空或对象不存在；expected_total未知，不统计全量。每身份附一份当前可读正式发布证明，不代表所有历史/入学年完整覆盖。同名记录标识尾部及来源年用于核对，未提供的校区别名不编造。

目录是当前正式发布的身份投影，可以含不同招生年；培养入学届、毕业届在资料查询中独立填写，不能把毕业届当招生entry_year。选择前显示身份来源的招生年，缺目标届资料仍保留缺口。学校名/同名专业不自行合并，同名不同UUID分别呈现，不将学校ID当专业或学科ID。

真实目录尚未装配，两个reference factory默认directory_reader=None，返回空及directory_not_enabled，零目录DB读取。学校/专业不取research两校、M0或T11未发布候选补充；不创建/导入真实名录。新增具体PublishedDirectoryReader由服务器显式注入可信T20 CatalogReader，必须verified/disabled、正式发布、真实准备与非合成，不接受请求自报已发布数组。SQL先名称字面搜索/分组去重/稳定UUID排序再limit，分页绑定筛选和ChangeEvent水位；每个身份经原发布/源/证据当前证明并末次重验，变化报409重查，失败不回退。原T20生成契约/reader源码不扩改。

## 前端行为

共享选择器采用关键字输入＋明确搜索＋结果原生select，学校→专业级联；UUID仅内部取响应，不再提供自由UUID/subject_ref输入。改学校/关键字/国家/用途或父页面资料届/层级立即取消请求、清下级/旧选择/旧资料，generation拒迟到；没有自动搜索、自动选择首条、localStorage或模糊造标识。查询已有选项分页必须明确下一页。

父组件另核对本地事件purpose/context_key（培养入学届/教学年或毕业届/层级/指标），避免父条件已变而子props尚未刷新时的旧回调恢复选择。此pin不是HTTP筛选、服务端授权或来源年度证明。

关键词输入的Enter有显式输入法组合状态守卫，组合输入时不搜索，普通Enter仅搜索对应目录而不隐式提交父资料表单；中文IME实际行为仍未运行验证。

培养必须学校+专业后查询所选program_id。毕业学校级用所选学校outcome_subject_ref，专业级必须学校+专业并用该专业ref；学院/学科暂无可信目录，保留不可用说明并禁查询，不拿学校/专业代填。选择目录只提供对象标识，原培养/毕业空数据行为不变。

## 修改范围与源码完成条件

新增手写TS契约与directory客户端/controller/选择组件；改CurriculaView/OutcomesView移除手填标识；新增后端目录DTO/可信发布reader/router并在原reference/local factory添加默认关闭的注入。API/架构说明、DECISIONS、tasks/CHANGELOG和相关工作台文档同步。无新依赖、迁移、事实/用户数据、旧迁移/生成契约或M0改变。

源码审阅须满足：默认空且明确原因；真实身份/父子/证明pin与分页；字面SQL搜索不把一页过滤当全量；同名不猜映射；数据用途与三类年份分开；改输入立即清选择/旧数据及异步取消；学院/学科禁用；原数据请求只取已选可信ID；缺目录无法提交查询；真实准备关闭不读研究/DEMO；不自动发布/确认。

## 未运行用例

本轮均未执行：端点参数/默认空、正式已发布学校/专业SQL搜索与分页、名字含%/_/中文/同名、撤回/过期/水位变化/权限及合成拒绝；选择/改学校/字词/父届/层级取消与真正迟到返回、无结果/错误/下一页与重启、ID映射/学院学科禁用；键盘/手机/视觉/Unit/Integration/Lint/TypeCheck/Build。原测试成功不作本轮证据，不创建新DB/执行SQL/启动服务验证。

## 启用与数据缺口

默认`create_reference_app()`与`create_local_reference_app()`的目录均None；新客户端只在用户按搜索时GET，没有可选项时查询按钮禁用。现有浙江库及批准三条不属于学校/专业目录，不能拿它当字典。

后续由可信服务器在完成来源/审核/正式发布等门槛后构造T20 CatalogReader，再用PublishedDirectoryReader(catalog_reader)显式传入对应factory的directory_reader关键字；不从客户端或.env装载任意数组。local factory保留原SELECT-only浙江连接，目录使用该受信T20的独立业务engine，不借用省线库。新GET注册需重启所选Python服务；本轮未装配/启动/重启或运行上述配置。无需新增数据库表/迁移/第三方依赖，也不自动开启原production/M0入口。

HTTP错误/目录关闭/空页分别展示；404或异常不能被转换为官方未公布。真实名录未装配时保留空；后续先落实小批次学校/专业的合法来源、完整身份与年度、负责审核人，再正式发布并装配，不能仅为让UI出现选项使用研究候选或合成夹具。
