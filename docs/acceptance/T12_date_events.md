# T12 日期事件验收

2026-10-03，状态：已完成源码、合成与隔离实库验收；正式期限/真实资料/部署关闭。T11私有分支已普通push并核对`dcbc0b3f4eb5f8147f0a180a060656595f1b876a`，当前codex/t12-date-events初始基线/索引干净；258tracked、13允许旧文件/245范围外保护。

开始前读取AGENTS/六必读文档/API/数据库/T11契约及代码/原始两份与02/03规格，确认T11依赖满足。先冻结[日期数据契约、范围、验收](../dates.md)，ADR-023；时间换算候选与未审核官方UTC分开，不自动识别任意原文矛盾，不构造证据/审核证明。已有tzdata2026.4哈希锁，未新增依赖。官方Python工程文档联网核对与应用离线测试分别记录。

## 实际检查

本批专用空库date_t12_test，loopback55438/PG16.15；每个PG用例随机schema，只清理本次schema。helper注入/恢复8个专用URL、凭据只忽略缓存且不打印。准备脚本最初字符串escape warning导致替换路径不可靠，已改raw字符串并断言helper路径/变量再运行测试；不是应用通过声明。

| 实际命令 | 本轮结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe -B -m pytest tests/unit/dates/test_t12_dates.py -q` | 43 passed，0.93s，exit0 |
| `.\.venv\Scripts\python.exe -m pytest tests/unit/catalog/test_t11_migration_config.py -q --tb=short` | 5 passed，4.70s，exit0；旧历史target明确001 |
| `.\.cache\t12-postgres\run-tests.ps1 -PytestArguments @('tests/integration/dates','-q','--tb=short')` | 首9pass/2fail是攻击fixture对FK先于namespace CHECK、长假review先于varchar检查的假设；修夹具后最终11pass/7.54s、exit0，无实现失败 |
| `.\.cache\t12-postgres\run-tests.ps1 -PytestArguments @('tests/unit/catalog','tests/unit/dates','tests/backend','tests/integration/catalog','-q','--tb=short')` | 274 passed/1既有warning，28.91s，exit0；包含T11五表/迁移及M0持久回归 |
| 同上首次还包含`tests/foundation` | 不存在此目录，exit1，未运行测试；随后按实际目录重跑，不把首命令写通过 |
| `.\.cache\t12-postgres\run-tests.ps1 -PytestArguments @('tests/contracts','tests/security/test_mode_isolation.py','-q','--tb=short')` | 333 passed/1既有warning，13.88s，exit0 |
| `.\.cache\run-web-checks.ps1 -TaskId T12` | 实际依次scripts/web.ps1 test→170passed/15files/8.15s、typecheck→exit0；bundled pnpm demo/auth run build --outDir ../../.cache/t12-{mode}-frontend-validation，两Build exit0；PATH/mode恢复 |
| `.\.venv\Scripts\python.exe -B scripts/generate_contracts.py --check --profile foundation`、`--profile identity` | 两项exit0，产物不变 |
| `.\.venv\Scripts\python.exe -B scripts/verify_contract.py`、`scripts/verify_originals.py` | M0 wire一致/两原文原字节不变，均exit0 |

日期PG11覆盖确切旧版本/年度断言、版本及synthetic复合FK、精度/NULL/假review/官方UTC CHECK、篡改计算get503不自修、并发revision/caller回滚、五catalog+date mapper零连接拒绝、001→002重复/隔离降级恢复保留旧三域数据。纯43覆盖伦敦冬夏/DST间隙与重叠、日期-only、未知/缺时区/overflow/conflict、原始字段严格性、伪UTC/审核/复制构造重验、包内loader无全局状态改变和名称空间。

## 未执行与已知限制

没有Lint/Python静态类型入口，未执行；Vue Type Check已实际执行。无UI/wire变化，浏览器未执行。全项目所有PG/身份安全回归不重复跑，仅上述相关选择；真实Keycloak/法律/生产GRANT/RLS/TLS/备份恢复/部署与真实日期原文审核未执行。source_alignment由人工/后续候选流程提供，不自动识别任意中英原文矛盾；evidence仍unresolved无T16实际FK，官方UTC仍NULL/T18审核未建。计算候选不是官方截止时间，T49 TTL及上线门槛保留。

## 变更与文档

23路径（13旧/10新）：九治理文档AGENTS/README/requirements/architecture/database/api/tasks/CHANGELOG/DECISIONS；catalog store/env与两旧T11测试仅显式历史target；docs/dates.md、本验收；四日期模块date_schemas/dates/date_models/date_store；0002；日期unit一个/PG两文件。原始输入、旧0001/M0/auth迁移、研究、生成产物/前端/依赖和原CatalogBase五模型保留。ADR-023和对应文档同步，tasks只T12完成。`.\.venv\Scripts\python.exe -B .cache/check_task.py T12`实际exit0：23路径/13旧/10新、245范围外tracked哈希、66其他卡、227本地链接、12Python内存编译、历史日志/ADR/凭据签名/生成LF通过。普通push/SHA核对后进入已授权T13。
