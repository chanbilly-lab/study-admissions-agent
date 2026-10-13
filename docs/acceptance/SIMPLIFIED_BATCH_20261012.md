# 简化批次交付记录：P05、T44–T48、T50–T67

批次开始2026-10-12、最后T67实施2026-10-13（用户最新客户端日期）。本批逐个完成23个剩余Task的最小源码，T49已完成跳过；P05先列范围。原67主Task状态为源码范围完成；公众运行、数据库扩展和真实资料验收没有通过结论。已到T67停止，不自动实施后续修复/采集/发布。

## 交付与实际上传

PRIVATE origin=https://github.com/chanbilly-lab/study-admissions-agent.git，分支codex/simplified-t44-t67；只普通push，main未合并、不改remote/visibility、不强推。每次推送后读取远程分支SHA与当时HEAD核对；下面是已保存的真实收据，不是测试结果。P05保存d6529886be774b8e56b1840d6a7b1cd471b799db；T67最后SHA在最终报告/Git日志给出。

| Task | commit / 当时远程SHA | 范围状态 |
| --- | --- | --- |
| T44 | `11696304ad4bea71c0870cc850021f0e5f42cc3d` | 最小源码/未验证 |
| T45 | `10073ccba2a9724a4f09c4ccf2547631e64c7dda` | 最小源码/未验证 |
| T46 | `133a9ce83b2281e1508fb82eef12d5f8f235d4da` | 最小源码/未验证 |
| T47 | `d0ce8e204771a573faf85261c676814356b5a71d` | 最小源码/未验证 |
| T48 | `341f12807af116441f8cb2226f2417ce68962d84` | 最小源码/未验证 |
| T50 | `5b73529d00b78be33de84536ff10c29dcbaa85f8` | 最小源码/未验证 |
| T51 | `06ef8991fb7edd1e910ff4edf28a1c3e9cc09871` | 最小源码/未验证 |
| T52 | `ba4da8476a656a454575d1f29034d0ab264e7b16` | 最小源码/未验证 |
| T53 | `d653d1b321625a08c8a2fe1fe69cf1f16361f86e` | 最小源码/未验证 |
| T54 | `fe2deea739800d5f78eed423057a0fc2335424a0` | 最小源码/未验证 |
| T55 | `67818a7b55178da467437bc2915aa653c1cbc142` | 最小源码/未验证 |
| T56 | `fac036b2bb93c2021b8c032b6942d7805907b558` | 最小源码/未验证 |
| T57 | `4f7a6780a2a8134f8e4fe07cc6d5ed1cfd7db638` | 最小源码/未验证 |
| T58 | `8953685cb72a83928daea9e3ba440a8fdf632915` | 最小源码/未验证 |
| T59 | `a39147c2c2e2e5898477d7332c4a90e8d127e86d` | 最小源码/未验证 |
| T60 | `09ae15a6ac48bea6bfa1e95bf2e4fc57eebefaa9` | 最小源码/未验证 |
| T61 | `5bc48ec5df6990a513492a9803dd97ba57f6b0f6` | 最小源码/未验证 |
| T62 | `c4dc5771933a42e6e9a8f8e70c41db471558f234` | 最小源码/未验证 |
| T63 | `d05deb7244e2c75e64722a76c40185e93513836c` | 最小源码/未验证 |
| T64 | `efdbc977e3a652693dcecca6146148d3d91dd13c` | 最小源码/未验证 |
| T65 | `85931b025797f04b9d19c44cf7966d03bb05ee89` | 最小源码/未验证 |
| T66 | `61b9fb38f0982cc850729ea67781c50fb5d1ccf9` | 最小源码/未验证 |
| T67 | 本报告与本Task同commit，最终SHA见Git/最终回复 | 最小源码/未验证 |

## 当前可用接口与未来运行（本轮未执行）

- 合成加密备份/维护计划，有限指标/配额，评测设计和缺证据发布判定为独立内部工具。
- 34地区/2026覆盖模型、严格类型候选人工JSON（≤1MiB/200行）和纯比较。文件夹具全部DEMO；候选digest是归一候选hash，不是来源原文hash。没有新统计/培养/结果PG迁移或正式发布接缝。
- 独立reference factory只空数据/缺口，无真实reader；reference Vue入口包含统计/培养/结果三页，查询不自动fetch、不回旧年/DEMO，model disabled。
- T66无实际fetch；T67单批DEMO清单blocked，原文/许可/真实审核人未完，published=0/分母unknown，不称全国采齐。

以后如需本地手动启动（不等于公众部署），明确参考factory和reference模式：

```powershell
# 本批没有执行下面命令，也未验证能启动/构建。
.venv/Scripts/python.exe -m uvicorn services.api.app.api.reference:create_reference_app --factory --host 127.0.0.1 --port 8004
$env:VITE_APP_MODE = 'reference'
pnpm --dir apps/web dev
```

现有通用Docker仅foundation/auth，未装配reference/私有业务。每页需已知真实对象ID；当前没有对象名录/已发布数据，访问只会得到明确空缺口或不可用；不能由学校名称猜ID。

## 实际命令与检查状态

已执行：Get-Content/rg读取文档、原规格/源码；git status/diff及暂存内容人工审阅；按各Task精确文件git add；git commit、普通push与ls-remote；gh repo view核PRIVATE。`.cache/p05_edit.py`、task12.py和本报告编辑脚本仅写文档；save/commit脚本只做源码版本保存。不执行新模块、factory、OpenAPI生成或示例调用。

未执行（用户要求）：所有Unit/Integration/前端/浏览器、Lint、TypeCheck、Build、契约/保护哈希/链接/验收校验脚本、CI、Docker配置/镜像/容器、PG迁移/备份/恢复/故障/容量、连接器HTTP及真实领域抽查。没有新通过数量，历史结果不代替本批。源码阅读不等于运行验证。期间文件读取引用旧不存在路径、一次文档patch定位失败及汇总编辑脚本首次SyntaxError（文档未生成导致首次暂存拒绝），纠正后继续；这些不是应用测试失败/通过，首次失败没有提交。

## 保留问题

原D01实际地域/供应商/手续，D04真实身份/MFA/恢复，D07运营/恢复/流量/预算与责任，D03/D08真实适用证据/全量分母/审核负责人仍待定；生产开关关闭。真实SQL最小权限/密钥ACL/灾备独立性、物理TTL、监控/多实例持久配额、SSRF实际获取链、正式PG/发布reader、真实课程/就业renderer和统计比较API均未实现或未验证。报告门槛齐备只能needs_independent_verification，不签发启用授权。

培养版本教学年不自动继承到未标教学年的模块；未知模块计划保持未知，不能由文档版本年推future/已排程。观察日期的隐式timestamp/datetime转date已在T67收紧。P05历史日志写‘22项’是计数笔误，实际本批是23个剩余Task（5项T44–48＋18项T50–67），这里明确纠正，不改历史记录。

## 批次变更文件

以下从Git已保存diff与当前最后Task清单编译；不含.env、密钥、真实附件、数据库、.cache或产物。每Task具体范围另见对应日期记录。

- `AGENTS.md`
- `README.md`
- `apps/web/src/features/curricula/CurriculaView.vue`
- `apps/web/src/features/outcomes/OutcomesView.vue`
- `apps/web/src/features/reference/ReferenceView.vue`
- `apps/web/src/features/reference/client.ts`
- `apps/web/src/features/reference/query.ts`
- `apps/web/src/features/statistics/StatisticsView.vue`
- `apps/web/src/main.ts`
- `apps/web/vite.config.ts`
- `data/evals/critical_20261012.json`
- `data/fixtures/reference/DEMO_batch_2026.json`
- `data/fixtures/reference/DEMO_cutoff_2026.json`
- `deploy/backup/__init__.py`
- `deploy/backup/archive.py`
- `deploy/backup/maintenance.py`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/SIMPLIFIED_BATCH_20261012.md`
- `docs/acceptance/T44_20261012.md`
- `docs/acceptance/T44_source.md`
- `docs/acceptance/T45_20261012.md`
- `docs/acceptance/T46_20261012.md`
- `docs/acceptance/T47_20261012.md`
- `docs/acceptance/T48_20261012.md`
- `docs/acceptance/T50_20261012.md`
- `docs/acceptance/T51_20261012.md`
- `docs/acceptance/T52_20261012.md`
- `docs/acceptance/T53_20261012.md`
- `docs/acceptance/T54_20261012.md`
- `docs/acceptance/T55_20261012.md`
- `docs/acceptance/T56_20261012.md`
- `docs/acceptance/T57_20261012.md`
- `docs/acceptance/T58_20261012.md`
- `docs/acceptance/T59_20261012.md`
- `docs/acceptance/T60_20261012.md`
- `docs/acceptance/T61_20261012.md`
- `docs/acceptance/T62_20261012.md`
- `docs/acceptance/T63_20261012.md`
- `docs/acceptance/T64_20261012.md`
- `docs/acceptance/T65_20261012.md`
- `docs/acceptance/T66_20261012.md`
- `docs/acceptance/T67_20261012.md`
- `docs/acceptance/data_batches/DEMO_2026_cutoff.md`
- `docs/acceptance/public_release.md`
- `docs/admissions_minimal.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/backup_minimal.md`
- `docs/backup_scope.md`
- `docs/comparability_minimal.md`
- `docs/connectors_minimal.md`
- `docs/coverage_minimal.md`
- `docs/curricula_minimal.md`
- `docs/cutoffs_minimal.md`
- `docs/database.md`
- `docs/distributions_minimal.md`
- `docs/evaluation_minimal.md`
- `docs/identities_minimal.md`
- `docs/limits_minimal.md`
- `docs/observability_minimal.md`
- `docs/outcomes_minimal.md`
- `docs/quotas_minimal.md`
- `docs/reference_api.md`
- `docs/reference_workspace.md`
- `docs/requirements.md`
- `docs/simplified_plan.md`
- `docs/tasks.md`
- `packages/contracts/reference.ts`
- `services/api/app/api/reference.py`
- `services/api/app/api/reference_admissions.py`
- `services/api/app/api/reference_contract.py`
- `services/api/app/api/reference_curricula.py`
- `services/api/app/api/reference_cutoffs.py`
- `services/api/app/api/reference_outcomes.py`
- `services/api/app/curricula/__init__.py`
- `services/api/app/curricula/identities.py`
- `services/api/app/curricula/schemas.py`
- `services/api/app/evaluation/__init__.py`
- `services/api/app/evaluation/report.py`
- `services/api/app/ingestion/connectors/__init__.py`
- `services/api/app/ingestion/connectors/policy.py`
- `services/api/app/limits/__init__.py`
- `services/api/app/limits/quota.py`
- `services/api/app/observability/__init__.py`
- `services/api/app/observability/metrics.py`
- `services/api/app/outcomes/__init__.py`
- `services/api/app/outcomes/comparability.py`
- `services/api/app/outcomes/schemas.py`
- `services/api/app/release_gate/__init__.py`
- `services/api/app/release_gate/decision.py`
- `services/api/app/statistics/__init__.py`
- `services/api/app/statistics/admissions.py`
- `services/api/app/statistics/batches.py`
- `services/api/app/statistics/candidates.py`
- `services/api/app/statistics/comparability.py`
- `services/api/app/statistics/coverage.py`
- `services/api/app/statistics/cutoffs.py`
- `services/api/app/statistics/distributions.py`
- `services/api/app/statistics/quotas.py`
- `services/api/app/statistics/regions.py`
