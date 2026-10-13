# BATCH-ZJ-2026-CUTOFF-01 实施契约

2026-10-13用户授权首个真实数据闭环，选浙江，并明确确认官方原文的普通类第一段494、第二段266、特殊类型控制线594，仅供本地参考查询。本Task取代T67停止对本批的限制，不扩展其他省/年/类型或真实学生/公众发布。基线PRIVATE fd4d94b6ba2bef0a8d79f819dff14bf28ad6f890，空索引和干净工作区；已读必读治理/原规格、统计候选/来源/审核/发布/参考API/前端。

## 数据及审核契约（修改前冻结）

- 仅2026浙江普通类的三条省级汇总，region=cn_region_11；一段/二段是segment_first/segment_second，不能标本科控制线；special_category单列。艺术/体育/单独考试不在首批范围，无法取得的其他省年/录取数据不回填。
- 源：浙江省教育考试院，https://www.zjzs.net/art/2026/6/25/art_155_12467.html；正文title=2026年浙江省普通高校招生各类别分数线，公布原标签2026-06-25 13:22，时区未明确=null。真实原HTML已200取得68359bytes，SHA256=b9fd87a8a202b37d6ff9e4f1efb8fdef394213448ffe983b9f5e7361e4dfb38a；缓存只内部保存，不公开全文。
- 每记录保留原称、value=494/266/594、unit=points、subject_category=普通类、段/特殊用途、原文定位与短摘录；max_score和bonus_definition=null且说明not_stated_in_source，不推满分750或加分范围，不生成资格/概率。
- 来源官方性、实际取得、人工复核、本地查询授权与对外再分发许可分开。用户此次明确确认是人工复核依据，记录USER_ZJ2026_ORDINARY_3及完整source/manifest hash；公开再分发许可unknown，不开启公众部署。
- 独立ReferenceCutoffsBase/新Alembic profile四表，source_versions、cutoff_batches、cutoff_records、review_events。源字节/行/复核事件不可变，candidate→approved_local→withdrawn；幂等源/manifest、撤回不被重导复活。迁移/导入/批准/撤回均显式维护CLI，启动不DDL/seed。
- 维护账户与API SELECT-only账户分开，在新本地reference_zj_2026数据库，不重用M0演示表/角色。真实记录is_synthetic=false、无DEMO字段；原17业务迁移/ledger/十二generated契约/M0保留。

## HTTP契约

新显式create_local_reference_app只本机loopback，原create_reference_app继续空；/v2/reference/province-cutoffs使用reference.cutoffs.local.1，其余资源保持空协议。query年省/普通高考路径与可选subject_category/batch/round完整回显；limit3–100/无cursor，读完整有限3条batch。非ZJ2026不回其他年省，其他类别/批次范围不推。

data保留resource/filters/page/release_id=null/expected_total=null/coverage_ratio=null/business_available=false；增加local_reference_only=true/reference_available及source/batch/items。只有approved_local读，撤回/candidate立即不出行；Meta仍旧基础release_id=null/data_as_of=null，源日期单列，不伪装T19正式release。source包含URL/title/publisher、原始公布字符串/timezone=null、captured UTC/original sha/bytes及复核状态；batch包含UUID/manifest hash/approved_local/本地复核ref。items固定3种类型、整数point、缺字段原因/原句定位、is_synthetic=false。不提供原HTML/密码/路径/数据库账户。

## 修改范围与验收

新reference_cutoffs模块/独立迁移/维护CLI与local_reference工厂，真实研究manifest+人工作用收据，独立TS协议/renderer及现有reference客户端/统计页最小接缝；相关API/DB/架构/需求/Task/日志/ADR同步。不新增框架或依赖、不改M0/旧迁移/旧generated、不给真实学校编数。

实际闭环：原文字节hash、三记录口径/manifest、空PG迁移/导入/幂等、用户确认批准、SELECT-only读、API筛选/缺年省/未审/撤回与重导不复活、页面来源/数字/缺字段、真实与演示隔离。用户原‘不用测试’的其他全回归/Lint/Build保持；本Task会实际执行必要迁移、导入、查询与页面闭环验证，不能用旧M0结果代替。专项检查如无法执行逐项记录，不虚构。

当前状态：已完成（仅本地参考真实批次）；本批完成后停止。


## 实际命令及结果（2026-10-13）

- `.venv/Scripts/python.exe -X utf8 -B .cache/zj2026_acquire.py`：exit0，明确一个官方URL、HTTP200、68359真实字节/b9fd87...dfb38a，非爬虫；完整原文只.cache/internal DB。
- `.cache/zj2026_prepare_manifest.py`及`zj2026_import_adapter.py`：exit0；表格494/266及特控594实际提取，PubDate13:22原时区未知，源/root研究稿和执行协议衍生关系有记录。
- `.cache/zj2026_provision.py`：实际创建新reference_zj_2026与owner/SELECT角色，M0不改。秘密仅private runtime，未提交。
- `python -m alembic -c services/api/reference_cutoffs_alembic.ini upgrade head`（venv，显式维护env）：exit0，新head0001_ref_cutoffs。
- `python -m services.api.app.statistics.reference_cutoffs.cli import --manifest data/research/zhejiang_cutoffs_2026_import.json --raw-source .cache/zj2026-source-20261013/original.html`：exit0；batch10f2c5b3-d829-54fa-a89c-cdc4a8f7a493，首次3/candidate/inserted=true，实际复核后重导inserted=false/approved_local。
- `.cache/zj2026_approve.py`调用`cli approve --review <绑定执行proof>`：exit0；用户确认USER_ZJ2026_ORDINARY_3，执行f817...fbc6d0而非旧58...hash，source b9...，状态approved_local；API角色仅所需五表SELECT。
- 新factory uvicorn loopback8004、Vite reference5174显式启动：实际可访问，Metaverified/disabled/真实3行、字段缺口null。
- `.venv/Scripts/python.exe -X utf8 -B .cache/zj2026_integrity_checks.py`：exit0；独立随机schema8项实际PG/HTTP通过，未审不读/批准/不可变/撤回与重导不复活/SELECT-only DML拒绝/owner拒绝/筛选OriginDEMO负例；只清理本次schema，主batch仍approved_local。
- bundled Node24.19.0执行`.cache/zj2026_browser.mjs`：exit0；实际Edge155.0.4283.45八项页面通过、page_errors=[]；桌面/390px截图已查看。只本地5174网络，不请求官网/商业服务。
- 原M0 `/health/ready`仍ok/demo_mode=true，5173仍HTTP200；没有改原M0源码/数据库/夹具。

## 实施差异与剩余限制

冻结概念名batch.1被明确适配成最终import.1，审核confirmation.1保留原用户答复，执行review.1另外绑定实际batch/hash；前两行原称采用原table header第一段/第二段。数据库表实际前缀reference_cutoff_*，协议字段仍同闭环目标，不改原历史。细节见[zhejiang_2026_cutoffs](../../zhejiang_2026_cutoffs.md)。

本次只从官网有界取得一个页面，不采全省所有类别、学校录取/就业/培养，不自动应用真实资格。对外再分发许可/运营主体/全量名录/官方后续更正与正式身份仍需另行落实，current数据是此捕获版本。新源码固定这3值及真hash，不是任意省/年解析器。完整Unit/Integration/Lint/TypeCheck/Build/CI/Docker：未执行（用户旧要求保留，仅恢复本Task必要闭环）。无‘全部检查通过’结论。

## 变更清单和保存

- `AGENTS.md`
- `README.md`
- `docs/tasks.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/api.md`
- `docs/reference_api.md`
- `docs/reference_workspace.md`
- `docs/zhejiang_2026_cutoffs.md`
- `docs/acceptance/data_batches/BATCH_ZJ_2026_CUTOFF_01.md`
- `apps/web/src/features/reference/ReferenceView.vue`
- `apps/web/src/features/reference/client.ts`
- `apps/web/src/features/reference/query.ts`
- `apps/web/src/features/statistics/StatisticsView.vue`
- `apps/web/src/features/statistics/CutoffResults.vue`
- `packages/contracts/reference.ts`
- `data/research/zhejiang_cutoffs_2026_local_batch.json`
- `data/research/zhejiang_cutoffs_2026_local_review.json`
- `data/research/zhejiang_cutoffs_2026_import.json`
- `data/research/zhejiang_cutoffs_2026_confirmation_mapping.json`
- `services/api/app/api/local_reference.py`
- `services/api/app/api/local_reference_cutoffs.py`
- `services/api/app/statistics/reference_cutoffs/__init__.py`
- `services/api/app/statistics/reference_cutoffs/schemas.py`
- `services/api/app/statistics/reference_cutoffs/models.py`
- `services/api/app/statistics/reference_cutoffs/service.py`
- `services/api/app/statistics/reference_cutoffs/cli.py`
- `services/api/reference_cutoffs_alembic.ini`
- `services/api/reference_cutoffs_migrations/env.py`
- `services/api/reference_cutoffs_migrations/script.py.mako`
- `services/api/reference_cutoffs_migrations/versions/0001_reference_cutoffs.py`

只有上述34路径，原HTML/DB/角色密码/运行cache/图片不提交；PRIVATE普通push后核对SHA，实际commit见本轮最终报告。
