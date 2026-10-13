> 由原始开发方案对应章节提取；原文件保留。M0 范围以 M0_IMPLEMENTATION_PLAN.md 为准。

# 03 技术架构与接口

## 架构选择
采用模块化单体：一个仓库，一个后端应用，后台采集worker可独立运行但共用数据模型。不在MVP中自建微服务集群。

建议前端Vue 3 + TypeScript + Vite；后端Python + FastAPI + Pydantic；SQLAlchemy + Alembic做数据库访问和迁移；PostgreSQL保存结构化事实、版本和任务。待检索基线稳定后再增加pgvector向量检索。FastAPI官方文档支持类型化API、数据校验和OpenAPI；pgvector为PostgreSQL增加向量检索功能。[S9,S10]

采集先用HTTP客户端与HTML解析器，文本型PDF用pypdf/pdfplumber等适配器；实现时逐一核验许可证。动态站点必要时才使用Playwright。M0/M1离线导入，M2引入持久任务worker；可采用Celery + Redis，周期任务由明确的调度入口触发。不要把可靠采集和截止提醒寄托于Web进程内的临时任务。

文件存储先采用本地私有目录，提供Storage接口，部署时可替换为经过合规确认的对象存储。访问使用权限校验和短期授权，公共招生原文与私有学生文件不同命名空间。

模型使用LLMProvider接口，包含结构化生成、嵌入（可选）、用量和超时处理。模型名由配置决定。无密钥时启用显式mock模式且界面水印提示；live模式失败不能悄悄回退到演示答案。Codex仅用于开发，不直接成为学生的执行环境。

## 模块边界
web → API认证/限流 → StudentProfile / Catalog / Eligibility / Planner / QA / Tasks。
采集worker → Source Registry → 原始快照 → 候选事实 → 人工复核 → 已核验库 → 检索索引。
变更发布 → 影响分析 → needs_review → 修订草案 → 用户确认 → 新计划版本。

QA不得直接修改招生事实。采集worker不读取学生画像。规则服务不调用LLM。模型不能直接连接管理员数据库或执行SQL/Shell。对模型暴露少量类型化只读工具和草案生成工具，服务端仍独立鉴权和校验。

## 运行时流程
1. profile completeness：只要求对当前路线有必要的缺失字段。
2. scope filter：国家/学段/申请身份/入学年/省份/渠道过滤。
3. evidence retrieval：先结构化查询事实，再检索适用文本证据；中英文实体用审核别名映射。
4. rule evaluation：确定性资格、条件、未知和原因。
5. candidate comparison：偏好、预算、历史竞争背景，不输出录取概率。
6. narrative draft：LLM只解释已核验结果和生成可编辑任务草案。
7. validation：数字/日期等字段引用校验、证据适用范围、任务容量、资格一致性。
8. user confirmation：确认方案或提出修订。

首版可用结构化筛选+关键词检索；加入向量检索时保留同一套元数据过滤。不能先召回其他年度内容再希望模型自行忽略。检索无证据就返回unknown或有限的通用说明。

关键事实优先使用后端模板渲染，不任由LLM重新写数字和日期。自由说明段落进行逐项引用支持检查；模型审查只作辅助，不能替代确定性字段校验和人工金标准评测。Structured Outputs能约束输出格式，但仍可能产生内容错误。[S6]

## 目录建议
apps/web/：学生与管理员前端。
services/api/app/{auth,profiles,catalog,evidence,rules,planning,qa,tasks,admin}/。
services/worker/：采集、解析与变更任务。
packages/contracts/：前后端契约或生成的类型。
config/：来源、支持范围、功能开关、provider配置，不含密钥。
data/fixtures/：合成与可再分发夹具；不可放真实学生资料。
evals/：固定评测集合与结果结构。
tests/{unit,integration,e2e,security}/。
docs/：本包规格、架构决策、数据说明、发布清单。

## API建议
POST /v1/profiles：创建画像；PATCH /v1/profiles/{id}：带版本号的更新并返回新版本。
GET /v1/offerings：支持范围内的项目筛选；GET /v1/offerings/{id}：条件、证据与日期。
GET /v1/evidence/{id}：可访问的原文定位，不暴露私有存储路径。
POST /v1/eligibility/check：profile_version_id + offering_ids，返回四态及规则证据。
POST /v1/plans/drafts：建立计划草案；POST /v1/plans/{id}/confirm：显式确认与乐观锁。
PATCH /v1/tasks/{id}：任务进度与版本校验；POST /v1/qa：范围限定问答。
GET /v1/plans/{id}/changes：证据与方案差异。
POST /v1/admin/sources：来源登记；POST /v1/admin/imports：人工或文件导入任务。
POST /v1/admin/facts/{id}/review：人工核验；POST /v1/admin/releases：发布核验后的数据版本。
DELETE /v1/me/data：启动数据删除流程，覆盖文档、索引、缓存与保留策略。
GET /health/live 与 /health/ready：分别报告进程与依赖状态。

所有输入类型化；列表分页；服务端租户/用户范围校验；写接口具备幂等或版本冲突控制。返回request_id、data_as_of、profile_version、ruleset_version；日志记录工具/版本/耗时而不是隐藏思考链与原始敏感输入。

## 权限与攻击面
爬虫URL仅管理员审批后启用。限制协议、DNS解析到的公网范围、重定向每一跳与浏览器实际出站；禁内网、localhost、link-local和云元数据访问。页面内容清洗和结构化约束不等于安全沙箱，网络层和工具权限必须独立执行。[S7,S11]

原始招生文档在无学生资料、无写权限的隔离解析环境中处理。网页文字不能成为指令，不能修改系统提示词，不能要求上传学生档案。文件大小、类型、页数和解压资源设上限。

账号按student、advisor、data_admin分权。所有学生私有检索、缓存与导出都绑定服务端授权上下文，不能相信模型传入的user_id。初版可用开发账号完成隔离测试，但生产不能暴露公共固定密码。

## 成本与运行
先规则查询，再必要的模型调用；同一文档相同hash不重复抽取。限制模型最大输出、调用次数、超时、并发和每用户预算。统计每份成功计划的调用与成本，不只统计每次调用。私有缓存按用户隔离，避免共享缓存泄露。

离线单测不调用商业API；live smoke test需显式启用。记录P50/P95延迟、失败率、引用不足率和人工复核积压；不预先承诺未知硬件与流量下的性能。依赖异常时提供已核验静态信息或明确失败，不编造实时答案。

部署先Docker Compose本地复现，加入迁移、备份/恢复测试和CI。真实用户上线要单独评审服务部署地区、模型供应商可用性、日志保留和数据跨境问题。
