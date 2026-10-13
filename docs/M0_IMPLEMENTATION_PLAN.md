# M0 实施前契约与验收计划

原始输入仅两份文件，无 AGENTS.md / README.md / docs / 代码或 Git 仓库。原文件保留不修改。
从开发方案内嵌章节提取 docs/01–05。省份默认浙江，由配置读取，纯演示选择，不推断用户所在地。

## 修改范围

新增 apps/web（Vue3 + TS + Vite）、services/api/app（profiles/catalog/evidence/rules/planning/providers）、SQLAlchemy 模型与 Alembic 最小迁移、packages/contracts、config、data/fixtures、tests、README、环境模板和 Compose。
M0 不包含真实信息接入、爬虫、历史竞争算法、概率、正式认证、自动提交、任务执行/确认/排程或 M1–M6。

## 数据契约

TypeScript 契约见 packages/contracts/index.ts，后端 Pydantic 生成 OpenAPI；离线测试核验关键枚举与字段。

- ProfileInput → 不可变 ProfileVersion：本科、普通高考、配置省份、申请年、身份、选科、成绩（M0 键为 gaokao_total / math / english_language；数值/满分/单位/实得或预测）、每周时数（0 < hours <= 40）、合成标签、用户确认。
- Institution / Offering：DEMO_ ID 与名称；入学年/国家/省份/课程体系/申请路径/身份；缺截止日期单独标为 not_published。
- Evidence：合成原文、非官方 demo:// URL、不可变版本 ID、SHA256、定位、审核状态、时间与适用范围（含明确适用项目 ID）。
- Rule：M0 原子白名单 gte/eq/in/exists，阶段、单位与满分、版本、证据；后补政策单独引用证据与带证据期限。
- Eligibility：eligible/ineligible/conditional/unknown，原子三值+deferred、原因、缺失项、条件、证据 ID、规则版本。历史竞争、偏好、数据质量分别返回，不输出概率。
- PlanDraft：引用重新计算的规则结果；只生成未确认草案任务及验收条件、估时、依赖、证据与可空期限；没有期限不生成截止时刻。
- API：GET /v1/config；GET/POST /v1/profiles；GET /v1/profiles/{id}；GET /v1/offerings；GET /v1/offerings/{id}；GET /v1/evidence/{id}；POST /v1/eligibility/check；POST /v1/plans/drafts；GET /v1/plans/{id}；health/live、health/ready。
- 私有接口：Bearer 演示凭据由服务端映射用户，忽略/拒绝客户端指定 owner；越权资源按 404 返回。只供本地合成数据演示。
- 统一响应：data + meta（request_id/data_as_of/profile_version/ruleset_version/demo_mode/model_mode）。

## 先列验收用例

1. 空库执行 Alembic，再导入夹具；重复导入不覆盖用户画像。
2. 全部硬条件满足 eligible；单科实得分不足 ineligible。
3. 缺成绩无后补依据 unknown；已审核适用后补政策及期限支持 conditional。
4. 后补证据缺失、冲突、过期、跨年、缺期限均不得 conditional。
5. 已确认预测成绩不冒充实得资格；满分/单位不匹配 unknown。
6. 跨入学年/省份/身份/体系/路径隔离；未审核规则不得放行。
7. DEMO 机构/项目/画像/证据全程标注合成；无真实学校假分数与日期。
8. 两用户列表/画像/资格/计划隔离；客户端不可指定 owner。
9. 缺期限项目不伪造日期、23:59 或 UTC 瞬时。
10. 无 API key 的 mock 完整闭环；live 模式明确不可用且不回退。
11. 前端类型检查、构建、关键交互测试；API OpenAPI 与 TS 契约校验。
12. PostgreSQL 实际迁移/夹具检查视本机依赖执行；SQLite 仅离线测试替身，不能据此宣称 PostgreSQL 已通过。
