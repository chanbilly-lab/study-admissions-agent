# T59–T62 最小参考查询入口

2026-10-14 SEARCH-SELECT-01增加GET /reference/institutions、/reference/programs身份目录查询，两factory默认None/空；q0..100 trim/字面包含、country可选2大写、limit1..20默认20、base64url cursor≤512，专业必canonical institution UUID。新reference.directory.1与旧统计/省线/培养/毕业协议分开；选项ID/父级/非合成/正式来源招生年及requirement摘要来自当前T20证明，不读research或M0。目录可跨招生年，资料查询的入学届/毕业届独立；学院/学科没有身份目录。完整wire/默认关闭/409重查见[搜索选择](school_program_search.md)，本批所有HTTP/SQL/测试/校验未执行。

T59先冻结独立手写reference.minimal.1契约，默认只返回空数据/缺口。显式factory `services.api.app.api.reference:create_reference_app`只/v2/reference、verified/disabled，无DB、candidate reader、用户身份或发布接口，不接入现有生产/M0。未来本地启动需明确选择这个factory；本轮没有运行服务。来源未启用不是官方未公布，missing_reason不假造来源状态。字段release/分母/ratio null、business_available=false，items永远空tuple，不能注入客户端自报published的记录。

| GET路径 | 必需筛选 | 当前行为 |
| --- | --- | --- |
| /v2/reference/coverage | year；region_key可选 | 空数据/未启用，无全国覆盖率 |
| /v2/reference/province-cutoffs | year/region_key；subject_category/batch/round可选 | gaokao默认明确；港澳台not_applicable、缺完整考试口径scope_incomplete |
| /v2/reference/score-distributions | year/region_key | 同范围空缺口，无个人精确排序 |
| /v2/reference/admissions | year/region_key；机构/组/专业原码可选 | 空缺口，不折全校一分 |
| /v2/reference/comparisons | year/region_key/left_record_id/right_record_id | 没有可解析发布记录，返回空缺口，不接用户记录payload |
| /v2/reference/programs/{program_id}/curricula | 规范项目UUID/entry_cohort；teaching_year可选 | 空当届缺口，不默认旧届；path ID回显入filters |
| /v2/reference/outcomes | graduation_cohort/requested_level/subject_ref；metric_kind可选 | 仅请求层级的空缺口，专业缺失不回上级汇总 |

year/limit是ASCII十进制整数，limit1–100/默认20；未知/重复参数拒绝，cursor没有发行故拒绝任何值；不回填最新年/DEMO，无过滤值进入日志。响应Envelope/Meta复用基础wire，旧十二generated契约不改，手写TS新增独立文件。完整已发布reader、SQL筛选/撤回/分页、身份与限额装配均未实现；单例纯quota不代表HTTP已限流。

2026-10-12所有HTTP/契约/类型/Build/测试/校验未执行（用户要求），包括本factory未被调用。真实数据仍需T19独立发布生命周期接缝，不以空API表示全国事实可查。

## 当前本地真实省线例外（2026-10-13）

以上空协议是T59–T62历史范围；原create_reference_app仍空。新显式local_reference factory通过独立SELECT-only库只查询浙江2026三个approved_local汇总，province_cutoffs使用新reference.cutoffs.local.1，其他资源仍旧empty。不会将候选JSONpublished标记当证据。来源/新TS/限制/实际16项闭环见[说明](zhejiang_2026_cutoffs.md)。
