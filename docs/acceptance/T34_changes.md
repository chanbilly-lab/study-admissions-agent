# T34 发布变更业务比较与影响追踪验收

2026-10-04源码及合成隔离验收完成；PRIVATE保存以后续实际Git核对为准，真实处理关闭。

## 基线与范围

PRIVATE 43b8105bd75d1f47eee224c43351faf20ddb0e4a/636tracked，codex/t34-release-change-impacts；初工作区/索引为空。必读治理/原规格/docs01–05/相关模块已核，代码前冻结[契约](../changes.md)。8旧路径允许、628其他tracked保护，旧head/原规格/M0/历史保持。

## 实际检查

所有下列为本Task实际新运行，合成测试使用专用PostgreSQL16.15/随机schema，不使用真实学生资料或商业API。

- `python -X utf8 -B -m pytest tests/unit/changes -q --tb=short`：最终86 passed/4.40s，exit0，无warning/skip；新增目标重复身份匹配/三字段不匹配2节点已包含，不与先前84次结果重复计数。
- `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/changes/test_t34_store.py','-q','--tb=short')`：7 passed/144.60s，exit0，无warning/skip。首次发布积压、真正确认/完成后窗口替代、参考变化false、撤回后轨迹、损坏hash、migration down/up/13旧head与新增已审核字段均实际验证；先前单节点1 passed/15.24s是其中同一节点，不重复计数。
- `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/changes/test_t34_safety.py','-q','--tb=short')`：最终9 passed/152.71s，exit0，无warning/skip；首轮8 passed/1 failed/137.92s，关闭配置仍触发诊断SQL的实际失败已修，新profile的9条path_separator警告也已消除。实际两Session锁等待去重、数据库延迟COMMIT失败完整回滚与重试、强制必需owner审计失败回滚、caller既有写回滚、错误mapper零外部连接、授权/原notice到期、晚建历史计划继承、原完成记录不变、processor只读target JSON子字段均已验证。
- 目标重复身份补强后真实新增字段单节点复验：`test_t34_store.py::test_new_field_in_published_replacement_marks_existing_target` 1 passed/28.44s，exit0，无warning/skip；属于原7同节点复验，不增加distinct计数；完整7/9分别是该局部补强前运行；纯全局每侧最多50成员追加guard后31 owned/53独立新进程通过，正常PG流程无变更。
- `python -X utf8 -B -m pytest tests/unit/releases tests/unit/planning tests/unit/scheduling tests/unit/plan_execution tests/unit/rules tests/contracts -q --tb=short`：723 passed/55.59s，exit0，1条现有Starlette BlockingPortal警告。
- `.cache/run-web-checks.ps1 -TaskId T34`：前端590 passed/37文件/20.29s；`scripts/web.ps1 -Action typecheck` exit0；`pnpm --dir apps/web run build --outDir ../../.cache/t34-{demo,auth}-frontend-validation`两模式exit0，1.41/1.88s、各112模块。缓存outDir提示非失败；无前端变更。
- `python scripts/generate_contracts.py --profile <profile> --check`：foundation/identity/public_catalog/admin/admin_review/profiles/assessments/plans八profile各exit0，无生成变更。
- `python scripts/verify_originals.py`、`python scripts/verify_contract.py`：各exit0，两个原文与M0契约一致。
- `.cache/check_task.py T34`及实际暂存diff/blob核对：实际exit0：25路径（8旧/17新）、628其他tracked/66其他卡保持、405文档链接/14Python内存编译、历史与凭据/工件检查通过；暂存与PRIVATE保存仍以下续Git实际核对为准；保护628其他tracked、66其他任务卡、历史、旧head、链接/凭据/工件与内存编译；PRIVATE/branch/origin/commit/push/SHA核对在保存时执行。初索引为空，显式路径暂存。

纯模块早期新夹具64字符小数实际写成66字符造成各1失败，均改成明确64并复验；重复执行不累计成额外测试。读取时少数猜测路径不存在已通过rg纠正，不当作应用测试通过或失败。

## 未执行与已知问题

Lint、Python静态Type Check未执行：项目无对应入口/配置，未新增依赖。HTTP/浏览器界面验收未执行：T34只有内部服务，无新增路由/UI。真实模型、真实学生/学校发布、全网采集、未成年私有功能、正式Keycloak、法律审查、PostgreSQL正式角色/GRANT/RLS、HTTPS/部署及生产备份恢复均未执行。前端Type Check与双模式Build已实际执行，不与Python静态检查混称。

真实处理、公众发布与供应商/法律/SQL权限门槛仍关闭。轨迹最多100条，超过明确409，分页未实现；规则发布ruleset仍NULL，官方精确UTC仍unknown，未宣称真实规则/精确截止日正例。省份混合范围矩阵为纯专项，真实新增条件为实际发布PG，不伪称混省发布PG。T40须协调删除私有impact与immutable receipt历史计数；本Task尚无删除服务。现有Starlette BlockingPortal警告与Vite缓存outDir提示保留。

## 修改文件

- `AGENTS.md`
- `README.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T34_changes.md`
- `docs/architecture.md`
- `docs/changes.md`
- `docs/database.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `services/api/app/changes/__init__.py`
- `services/api/app/changes/comparator.py`
- `services/api/app/changes/models.py`
- `services/api/app/changes/schemas.py`
- `services/api/app/changes/service.py`
- `services/api/app/changes/store.py`
- `services/api/changes_alembic.ini`
- `services/api/changes_migrations/env.py`
- `services/api/changes_migrations/versions/0001_changes_t34.py`
- `tests/integration/changes/conftest.py`
- `tests/integration/changes/test_t34_safety.py`
- `tests/integration/changes/test_t34_store.py`
- `tests/unit/changes/test_t34_comparator.py`
- `tests/unit/changes/test_t34_identity.py`
- `tests/unit/changes/test_t34_safety.py`
