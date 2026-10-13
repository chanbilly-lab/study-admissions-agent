# T20 公共目录与证据读取验收

2026-10-03，codex/t20-public-catalog从557ca402984042e4573176dd762b971b67ed7ee7开始；385 tracked、Git工作区及index干净。已读必读文档、两原规格/docs01–05与相关实现，代码前冻结[公共契约](../public_catalog.md)，T20标进行中。无新迁移/依赖，真实公开默认关闭。本文件记录实际新检查，不将历史结果计作本次通过。

以下为当时开发检查记录，最终验收结论见末节；首轮失败与未执行项保留。

## 已执行相关回归

`.cache/t20-postgres/run-tests.ps1 -PytestArguments @('tests/unit/releases','tests/integration/releases','-q','--tb=short')`：46 passed291.94s exit0，无skip/warning。仅T19纯+PG范围，不等于T20专项已通过或全项目PG。

## 专项纯测试

`.cache/t20-postgres/run-tests.ps1 -PytestArguments @('tests/unit/public_catalog','-q','--tb=short')`：首次44 passed0.72s exit0，无skip。覆盖严格query/范围、cursor全过滤和limit绑定/重复JSON键/base64及未知总量DTO；数据库专项尚待执行。

## 新profile生成器专项

`.venv/Scripts/python.exe -m pytest tests/contracts/test_t20_public_catalog_generation.py -q`：24 passed2.76s exit0，1既有Starlette warning。`scripts/generate_contracts.py --check`、`--profile identity --check`、`--profile public_catalog --check`：exit0，旧两profile产物字节匹配。TypeScript用例已纳入现Vue类型检查路径，最终前端结果待补记。

新模块首import辅助命令未设PYTHONPATH得到ModuleNotFoundError；正确路径导入暴露PROGRAM_SCOPE_FIELDS引用模块错误，已修本新proof import并compile4/Reader import exit0。这两失败不记应用通过，旧模块未修改。

完整契约/模式回归：`.venv/Scripts/python.exe -B -m pytest tests/contracts tests/security/test_mode_isolation.py -q --tb=short`：357 passed17.18s exit0，1既有Starlette/anyio warning；包含本新24项，与其专项计数不相加。

前端最终：`.cache/run-web-checks.ps1 -TaskId T20`：170 passed/15files30.98s；Vue Type Check、demo/auth两Build exit0，新公开TS契约编译用例纳入。Vite有常规outDir位于缓存的warning，产物仅忽略目录。

新增契约专项最终重复同命令24 passed2.90s exit0/1既有warning，不与2.76s旧计数相加。前端首import引用T15未导出的类型alias失败，改本新schema为已核对闭合Literal后通过，旧域未改。

严格查询专项加入fresh进程默认关闭工厂检查后：首轮44 passed/1 failed（Windows asyncio内部loopback被新test guard禁），次轮44 passed/1 failed（新test误将errorEnvelope读作meta），只修本新测试前提；第三轮45 passed1.93s exit0。fresh进程禁止数据库/身份/M0/provider导入与外部网络，确认None reader config200/business503及/v1、/v2/openapi.json404。PG首轮实际执行中，尚未声明通过。

额外真实uvicorn后台启动烟测：未执行。生成并启动隐藏后台helper的exec_command被自动审批拒绝，返回blocked by policy（没有更具体原因）；没有创建helper或启动服务，不把该项计作通过。保留fresh进程/TestClient默认关闭HTTP验收，运行说明不声称shell启动已验证。

PG首轮尚在运行，当前已见失败但计数/trace未最终确认；本新Reader的缺失release入口404被通用proof转换为409，已修该精确入口，内部失效proof仍409；补pipeline纯配置/test mode冻结及来源存储 readiness/currentcase检查。最终全量必须在冻结源码后重跑。

## PostgreSQL首轮（不是最终结果）

`.cache/t20-postgres/run-tests.ps1 -PytestArguments @('tests/integration/public_catalog','-q','--tb=short')`：20 passed/3 failed289.57s exit1，25 warnings、无skip，23个展开case。缺失release GET错误409为本Task新Reader缺陷，修为精确入口404；两新fixture前提错误为同logical重复造已批准case触发既有CAS，以及raw decimal写非decimal值先触发DB CHECK，改同case错release及合法601.00测试指纹。25warning=1既有Starlette+24本新reader实例model_fields弃用，正作最小当前模块修正；旧域不改。最终源码冻结后完整复验，首轮不可作Task完成依据。

受影响PG选择项复验：同helper `-PytestArguments @('tests/integration/public_catalog','-k','draft_and_unpublished or private_evidence or immutable_original_row or anonymous_http or production_and_missing or http_query or public_reads_do_not','-q','--tb=short')`：7 passed/16 deselected69.53s exit0，7warnings（既有Starlette1+旧加载reader实例弃用6）。不相加、不代替完整验收。最后修reader的type(classification).model_fields后冻结源，最终联合45pure/23PG正在执行。

最终离线生成三个profiles `--check`、M0 `scripts/verify_contract.py` 与原文 `-X utf8 scripts/verify_originals.py` 全exit0；12 Python文件内存compile/Reader导入/三业务路径及六生成产物无CR字节检查exit0。旧输入、迁移及foundation/identity产物未改。

独立只读终审：12 Python AST exit0，未导入/写缓存；4旧foundation/identity产物与557ca402原字节相等，新两产物无CR且git属性text=set/eol=lf。无阻断，API/dataset仍是私有候选库的有限已发布投影，未将dataset.visibility改为public。末端proof确认全部所选release成员，不只是页面可见子集。

## 最终验收与文件范围

最终实际命令：`.cache/t20-postgres/run-tests.ps1 -PytestArguments @('tests/unit/public_catalog/test_t20_query.py','tests/integration/public_catalog','-q','--tb=short')`：68 passed288.28s exit0，45pure+23实库case，无skip；1既有Starlette warning，新reader弃用警告已消除。此前44/1两轮、首PG20/3与选择7通过如实保留，不与最终结果相加。已验证固定pinned version/无latest推断、私有候选库有限发布投影、来源公开许可/原文件当前指纹与期限、当前批准/冲突/范围、生产拒DEMO、匿名历史登录独立、真实SQL等待后撤回与首成员file/source过期、cursor变更/边界/覆盖未知及安全HTTP/no-store。

专库只读残留检查：random public_catalog_t20_* schemas=0、public tables=0、其他client backend sessions=0。首诊断shell引号ParserError未执行SQL，改stdin后exit0，未触碰旧数据库。正向皆明确DEMO test_fixture，不是正式招生事实/原文人工领域核验或部署验收。

未执行：Lint与Python静态类型检查（项目无入口，不临时引新依赖）；browser（页面未改）；全项目PG/POSIX/真实身份与正式事实/责任法律/SQLGRANT/RLS/附件物理恢复/清理备份/部署（当前任务与门槛外）；额外后台uvicorn启动烟测（自动审批拒绝blocked by policy，原因未进一步返回）。原元数据当前证明不等于每请求物理读取附件；未实现公开管理页面或通知消费者。T15任务外时效记录保留。

27路径（11旧/16新），完整清单：

- `AGENTS.md`
- `README.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/tasks.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/api.md`
- `docs/database.md`
- `scripts/generate_contracts.py`
- `docs/public_catalog.md`
- `docs/acceptance/T20_public_catalog.md`
- `services/api/app/api/public_catalog.py`
- `services/api/app/api/v2/public_catalog.py`
- `services/api/app/public_catalog/__init__.py`
- `services/api/app/public_catalog/schemas.py`
- `services/api/app/public_catalog/query.py`
- `services/api/app/public_catalog/reader.py`
- `services/api/app/public_catalog/proof.py`
- `packages/contracts/v2/public_catalog/generated.ts`
- `packages/contracts/v2/public_catalog/openapi.json`
- `tests/unit/public_catalog/test_t20_query.py`
- `tests/integration/public_catalog/conftest.py`
- `tests/integration/public_catalog/test_t20_public_catalog.py`
- `tests/contracts/test_t20_public_catalog_generation.py`
- `apps/web/tests/public-catalog-contract-types.ts`
- `.gitattributes`

最终范围检查：`.venv/Scripts/python.exe -B -X utf8 .cache/check_task.py T20`：27路径/11旧16新，374tracked保护、66其他任务卡及历史未变、310本地链接、12内存compile、JSON/凭据/范围检查exit0；`git diff --check` exit0。CHANGELOG/tasks的Task ID、状态、路径及实际结果一致。Git有脚本LF将转CRLF常规warning，新六生成产物明确保持LF。

本批自建PG清理：私密配置内校验精确`.cache/t08-postgres/run-34c86dd8bafa41c7b1a1739fa7e230cd/cluster`及127.0.0.1:55438、全部其他client sessions=0后，`.cache/t08-postgres/stop.ps1` exit0，port55438无listen；仅停止这一自建实例，未删除数据或改用户Docker/其它服务。该helper和环境含密钥仅忽略缓存、不提交，后续PG复跑须自行启动隔离专库。
