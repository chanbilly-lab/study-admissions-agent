# T28 /v2 四态评估契约

2026-10-03实施前冻结，现源码及合成隔离验收完成；实际命令、失败及限制见[验收](acceptance/T28_assessments.md)。文档同步、PRIVATE保存核对后才T29。

## 数据契约

请求只包含本人profile_id、不可变profile_version_id、精确TargetReference、release_id、application/enrollment阶段、六个显式required-nullable附加ScopeKey及confirmed=true。不接受owner、资格结论、成绩、表达式、规则哈希或客户端时钟作为权威。服务端读取T23确认快照、T26范围及当前发布/审批/证据链并取明确UTC评估时刻；结果保存不可变绑定和SHA，过期不晚于原画像。

四态使用原完整T25表达式：true为eligible、false为ineligible；unknown不能通过任意叶替换变真。仅实际achieved missing/pending且T27精确政策/期限允许的变量进入有界可满足性检查：同成绩变量共享值，使用严格单位/满分一致的Decimal边界、阈值及区间代表值；保留all/any/not原结构，未来值限制为T23可确认的非负/不超满分、最多7位整数及6位小数域，最多4096组合，超限保守unknown。没有完整true路径仍unknown，不把可能的候选值保存成学生成绩；conditional保留必须完成的原表达式义务。仅exists时可保留未来提供合法实得记录的存在性义务，不声称官方满分或写入内部代表值；not exists缺成绩及相反阈值不能造conditional；未选any分支失败不淘汰。预测、单位/满分/日期/范围冲突不后补。

资格、竞争背景、偏好和数据质量分开；未实现数据维度明确unknown，不制造概率、排名或适配分数。输出有界规则原因/证据ID，默认不返回学生完整画像、原文HTML、内部供应商配置或任意JSON对象。

## 当前规则证明边界

T19发布仍是facts-only、ruleset_version=null；T26/T27真实规则和政策开关仍关闭。T28不伪造正式规则审核账本，不自动把minimum事实变DSL。可替换内部RuleBindingReader只接最小BundleQuery，不接学生成绩；只有test+synthetic显式开关允许服务器合成DSL绑定。新服务在同Session核实际当前test_fixture release/member、T18当前批准、T16证据链、来源/文件/公开许可、完整scope及精确literal/单位/满分和hash；布尔reviewed标签不作证明。合成正例还要求已批准/发布的原文逐字匹配有界DEMO_T28_RULE表达式/typed literal/unit/scale/hash描述符；后补独立DEMO_T28_DEFERRAL描述符绑定事项/阶段/缺失状态/主补需求及精确日期/日历，任意同范围minimum或两个date不能替代后补政策。正式路径仍RULESET_UNAVAILABLE/unknown，合成四态不表示真实专业覆盖或领域审核完成。

## 权限、历史与接口

独立create_assessments_v2_app/create_assessments_app继承profiles profile，新context、POST /eligibility/evaluations、GET /eligibility/evaluations/{assessment_id}、POST /eligibility/evaluations/{assessment_id}/replay。旧六工厂/协议及M0不改；默认无DB/provider并安全关闭。写入使用当前session/Origin/CSRF；读取和重放每次检查current本人/student/core、原画像consent/declaration/notice绑定和期限，重新同意不复活旧版本。共享和管理员不获得私有评估。T49没有assessment operation，本轮不冒用profile.create/plan.confirm；POST评估不宣称命令幂等。

重放使用原画像上下文、表达式/政策快照、engine/tzdata版本和原评估时刻，不取latest/today。画像根已确认新版本时旧评估标needs_review；新check只针对当前确认版本，旧版仅有权历史重放。旧发布替代/撤回可有权读取最小历史结果；current_validity独立标记current/replaced/withdrawn/needs_review/unavailable。新评估必须当前发布证明；历史重放不把旧结果当当前资格，失效来源不返回当前原quote/URL。所有SQL及审计flush后核最终fresh身份/角色/用途/画像/发布/来源/文件/规则政策期限，失败事务回滚。

## 修改范围

新增rules/assessment_engine.py、schemas/service/router；assessments/models/store及独立assessment Alembic链/profile；api/assessments.py；新生成assessment OpenAPI/TS；单元、隔离PG/HTTP、契约负例。根生成器只增加独立显式profile白名单，旧生成字节不改；同步AGENTS/README/tasks/CHANGELOG/DECISIONS/requirements/architecture/api/database及本文件/独立验收。无新依赖、旧迁移修改、T29页面、模型调用或真实资料启用。

## 验收用例

- 四态/all-any-not完整真值、同成绩相反阈值、重复条件、未选分支、没有政策/期限/错范围/预测/冲突、组合预算。
- 同Session实际PG合成发布/审批/证据绑定与正式facts-only未知；两owner、管理员/共享拒绝、confirm/CSRF/重复JSON/额外字段、model disabled无密钥。
- 不可变评估/历史重放、旧发布替代/撤回与current_validity、原consent撤回再同意、24月期限、最终SQL等待越过身份/角色/用途/来源/文件/政策期限并回滚。
- 独立迁移空库upgrade/current/downgrade/upgrade、UPDATE拒绝与可信DELETE可行；七profile生成及旧字节保护、实际HTTP与TS一致。
- 相关Python/PG、前端Unit/Type Check/demo-auth Build、原文/M0/范围/文档检查；Lint及Python静态类型无入口标未执行，正式身份/领域审核/法律/SQL权限/备份清理/部署未执行。

合成规则与真实facts-only未知、历史替代/撤回、新画像版本、实际SQL等待跨期限及回滚已验收；真实处理与领域审核保持关闭。

## 时间精度接缝

assessment_at保留真实服务器UTC微秒，不截断或补未来秒。T25只支持minute/second参考，真实时刻不能精确表达时仅该context.assessment_at留空，valid_at/瞬时date_before为unknown，其它完整表达式正常归约；不把时间精度未知作为可后补成绩。未引入日期参考日历猜测，微秒规则精度扩展须后续明确契约验收。

## 独立入口与数据库运行

新工厂`services.api.app.api.assessments:create_assessments_app`可供uvicorn `--factory`使用，默认lazy关闭且无数据库/网络/商业密钥；本轮实际ASGI和PG测试，不宣称另跑uvicorn烟测。四个新操作是GET `/eligibility/context`、POST `/eligibility/evaluations`、GET `/eligibility/evaluations/{assessment_id}`、POST同路径`/replay`；两POST必需JSON确认、无客户端结论或时钟、无幂等承诺。独立AssessmentEnvelope严格绑定真实profile metadata，三个非资格维度必需unknown，历史响应不泄露保存上下文。

`services/api/assessments_alembic.ini`读取显式`ASSESSMENTS_DATABASE_URL`并拒绝缺失配置；auth/idempotency/catalog/storage/imports/evidence/facts/reviews/releases/profiles十头先满足后仅升级本链。专库通过Alembic Python API在随机schema实际upgrade/current/downgrade/upgrade，应用启动不建表。生产SQL角色/GRANT/RLS和正式数据库部署未执行；不能以测试DB管理员权限当正式权限配置。
