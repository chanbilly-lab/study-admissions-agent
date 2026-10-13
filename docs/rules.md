# T25 类型化规则与三值逻辑

2026-10-03代码前冻结。起点PRIVATE T24 `e3c74f956280cd0bc381581ac0da1bcc57be589b`、497 tracked、工作区/索引空；当前仅T25，`codex/t25-typed-rule-expressions`。依赖T17/T23已验收，先读治理、原两规格、API/数据库、类型事实/画像与旧M0资格代码。以下是内部数据契约，不表示规则已审核、发布或真实资格已开放。

## 数据契约

独立 `app/rules/expression.py` 定义封闭有界AST和严格类型，`evaluator.py` 纯解释器；保留旧 `app/eligibility.py`/M0完整行为。表达式只允许 `all/any/not/exists/eq/in/gte/lte/date_before/valid_at`。all/any使用非空children（1..32），not一个child；原子只允许固定FieldRef和显式类型literal，拒extra/op/自由路径/函数/SQL/模板。最大depth16、nodes256、in集合32、文本256字符/1024 UTF-8字节、DSL64KiB；解析前检查整棵树与限额，短路不能隐藏非法分支。JSON入口拒重复key及非法数字，构造copy/model_construct也重新验证。错误只固定RuleInputError/422，不输出原值、SQL或内部路径。

字段仅本科study_level、entry_year、五个独立scope、subjects、T23封闭15assessment的achieved/predicted，以及显式评估参考日/瞬时；不包含姓名、预算、兴趣、owner、任意对象属性。成绩必须带unit/scale，整数和decimal不同类型；decimal严格非负词法字符串最长64，拒float/指数/NaN/Infinity/bool/负数/前导零，比较Decimal不作算术四舍五入。单位points/band/percent/fraction必须原样相等、明确正scale且value<=scale；无自动百分比、GPA或满分换算。entry_year为严格整数，不把true当1。文本与唯一字符串集合独立；in对文本为显式候选成员，对subjects为任一交集（全包含须显式all组合），不是自由Python成员运算；eq不跨类型或将集合当标量。

EvaluationContext只容纳上述固定字段的TypedDatum及显式可空assessment_date/assessment_at，不读取数据库、环境变量、服务器当前时间或模型。Datum区分known、missing、pending、not_applicable、conflicted，非known值保持null；scope unknown不推断所在地/省份/身份。`context_from_profile`先重新验证T23完整ProfileSnapshot，然后按固定表投影。只用provided achieved判断硬条件；predicted FieldRef可解释为PREDICTED_NOT_ACHIEVED/unknown，不能代替缺失实得。缺少整项、missing/pending/not_applicable/conflicted都是unknown；known零是有效值。Profile的subjects=[]没有独立“明确空集合”确认语义，投影为missing；内部context只有显式known集合才进行成员判断，其空集合in为false。存在性exists表示已明确提供可用值，known零或显式known空集合都是true；未知仍unknown（not exists缺成绩也unknown），不从null得到明确不存在。

eq/in/gte/lte使用严格类型匹配；合法但字段值类型、单位或满分不匹配返回unknown，不能误放行或淘汰。date_before严格比较同精度date或有明确时区的instant，参考时刻须由调用方显式提供；不将date-only补成00:00/23:59，不把T12候选UTC当已审UTC。valid_at窗口必须显式from/to且start<end，按 `[start,end)` 的UTC瞬时窗口，开始包含、结束排除；缺参考时刻、日期精度或时区不匹配unknown。官方截止/来源日历与后补判断留T27，不默用服务器日期。

Result只含truth=`true/false/unknown`和固定reason及有界节点trace（op/field/outcome/reason/children，不含学生数值/自由异常）。不能用Python bool强制归约unknown；解释器先验证完整树，再计算每个合法子分支并按Kleene归约：all有false即false、否则有unknown即unknown；any有true即true、否则有unknown即unknown；not unknown仍unknown。false未选any分支不会成为必需条件失败。此纯模块不返回eligible/ineligible/conditional，不编译T19候选为发布ruleset，不证明证据/权限/适用范围。

## 内部接口形状

公开函数为 `parse_expression(raw|Expr)`、`evaluate_expression(expression,EvaluationContext)`、`context_from_profile(ProfileSnapshot,...)`，固定 `RuleInputError(422,INVALID_RULE_INPUT)`。Expr按op只接受相关字段：all/any的children、not的child、exists的field、eq/gte/lte/date_before的field+value、in的field+values、valid_at的start/end；不能携带其他op的字段。FieldRef=`{name,key?,basis?}`，只有assessment允许封闭15项key与显式achieved/predicted basis，不开放自由dotpath。

TypedValue分text/integer/decimal/string_set/date/instant，均有kind与对应value；decimal另带unit/scale，date另带明确calendar域，instant另带明确precision。integer是严格原生int，绝对值上限2^53−1（未来HTTP安全表示界限，非自动数据换算）；Profile入学年仍由原1..9999契约约束。EvaluationContext=`{fields:最多40个唯一ContextField(field,TypedDatum)序列,assessment_date:DateValue|null,assessment_at:InstantValue|null}`；重复field拒绝。TypedDatum只known可非空typed value，其余状态保持null。EvaluationResult=`{truth,reason,trace}`，trace为完整有界preorder节点理由，不包含实际画像值。

这些内部Pydantic值不是新增HTTP wire、数据库规则表或生成契约。实现可保留直接原生date/aware datetime的显式严格构造；JSON入口必须按ISO词法、类型和预算重新验证，不能通过构造对象绕过。

## 修改范围与可测试验收

只新增rules包/expression/evaluator、对应离线unit与独立真值表/安全测试；root同步README/当前需求与架构、ADR038、tasks/CHANGELOG及验收。无HTTP/API生成、数据库/迁移、前端、依赖、旧M0改动，不开始T26。

1. 完整3×3 all/any及3值not真值表，all(false,unknown)、any(true,false/unknown)、任意排列/嵌套/完整branch trace。
2. 非空逻辑树、depth/node/children/in/bytes限制、未知op/字段/extra/重复JSON key/构造绕过，即使any另一分支true仍拒坏AST；无eval/exec/getattr/SQL/模型/网络。
3. 严格int/decimal/text/set，零/尾零等价/64位相邻精度、最大值、坏float/bool/NaN/类型/单位/满分，明确missing/pending/unknown/预测不能成为false或true。
4. 真实T23快照投影独立所在地/身份、省份和subjects，保持不收偏好/预算；日期同精度、缺时区/参考时间、窗口首尾/跨日不造时间。
5. 新unit、相关T17/T23/M0与契约模式回归、原文/生成/治理、现有Type Check和Build。Lint/Python静态类型无入口明确未执行；DB/实际browser无变更无需扩大，真实用户/供应商/事实审核/部署未执行。

完整实际结果写入 [T25验收](acceptance/T25_typed_rules.md)；成功验收、文档同步和PRIVATE保存/SHA核对后才单独T26，完成T40后停止。
