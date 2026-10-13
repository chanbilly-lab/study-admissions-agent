# T11 招生机会关系模型验收

日期：2026-10-03，状态：已完成源码、合成与隔离实库验收；正式事实/真实资料与部署关闭。

开始前读取AGENTS/README/requirements/architecture/tasks/CHANGELOG/DECISIONS及API/数据库、两份原始输入和相关代码，确认T01–T03依赖已完成。T10已保存并核对远程`e06b07e98194f724fa134c177560f487d7f4e408`；当前新分支codex/t11-admissions-catalog，初始工作区/索引干净，245tracked哈希基线。九份相关旧文档允许更新，全部既有代码冻结。先冻结[契约、范围与验收](../catalog.md)，ADR-022。

发现M0 `app/catalog.py`仍由main直接导入，拟同名包会遮蔽它，因此采用独立admissions_catalog路径及catalog前缀/迁移profile。本轮模型不导入真实资料，不开放公众目录或真实学生处理，无新依赖。

工程联网核对SQLAlchemy复合FK/约束和Pydantic严格字段官方文档成功；既有本机版本2.0.41/2.11.7/1.16.2，不升级依赖。实际检查如下，不把历史T10通过数计为本Task实跑。

## 当前实际过程

新建本批自有专用空库catalog_t11_test（PG16.15、loopback55438），不接用户/生产库；复用本批测试cluster，各集成测试另建随机schema并清理。`.cache/t11-postgres/run-tests.ps1`过程注入/恢复七个专用测试URL，凭据仅存忽略缓存，不打印/上传。

本Task新实跑：`scripts/web.ps1 -Action test` →170 passed/15files、8.18s、exit0；`-Action typecheck` exit0。进程VITE_APP_MODE=demo/auth，bundled pnpm `--dir apps/web run build --outDir ../../.cache/t11-{demo/auth}-frontend-validation`，两Build exit0；PATH和mode以try/finally恢复。cache外outDir正常不自动清空提示，不是失败；前端源码/依赖未改。

## 实际命令与结果

| 命令 | 本轮实际结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe -B -m pytest tests/unit/catalog/test_t11_schemas.py -q` | 80 passed，0.78s，exit0 |
| `.\.venv\Scripts\python.exe -m pytest tests/unit/catalog/test_t11_migration_config.py -q --tb=short` | 5 passed，4.64s，exit0；显式URL、离线DDL/日志无副作用、冻结迁移与模型一致 |
| `.\.cache\t11-postgres\run-tests.ps1 -PytestArguments @('tests/integration/catalog','-q','--tb=short')` | 首轮29pass/1fail：varchar超长为DataError22001而helper只认IntegrityError；修helper后30pass/15.24s。独立审查发现Session mapper可另绑engine，修5mapper guard及同例后最终30pass/15.55s，exit0 |
| `.\.venv\Scripts\python.exe -B -m pytest tests -m 'not postgres' -q --tb=short` | 首轮1363pass/14setupERROR/395deselected/1既有warning，T09_service既有14未标记PG需URL；不是新功能失败 |
| `.\.cache\t11-postgres\run-tests.ps1 -PytestArguments @('tests','-m','not postgres','-q','--tb=short')` | 注入测试库后1377pass/395deselected/1既有warning，64.00s，exit0。此选择含14真正PG，不能说全部纯单测；未改无关marker |
| `.\.venv\Scripts\python.exe -B scripts/generate_contracts.py --check --profile foundation`、`--profile identity` | 两项exit0，生成产物不变 |
| `.\.venv\Scripts\python.exe -B scripts/verify_contract.py` | M0 OpenAPI/TS一致，exit0 |
| `.\.venv\Scripts\python.exe -B scripts/verify_originals.py` | 两原始输入原字节不变，exit0 |

最终PG覆盖11个招生维度、五项目范围、非空unknown/NA/case区分、同名机构独立、并发防重、复合FK/CHECK/RESTRICT、确切版本及乐观冲突回滚；独立迁移重复/降级恢复逐行保留M0和auth。store异常必须由调用者退出外层事务回滚。mapper自定义路由已在连接前拒绝，防止可信维护接口错库写入。此30项未因该修复扩数量；85纯单测是分别实跑，并非重新宣称全部Python1777通过。

## 未执行与已知问题

Lint/Python静态Type Check无现有入口或配置，未执行；实际Vue Type Check已执行。浏览器未执行，HTTP/UI无变化；其他395被选择排除用例未在T11重新整套执行，T11专项及M0/auth迁移保留已跑。真实Keycloak/MFA/法律/生产GRANT/RLS/TLS/备份恢复/部署/真实资料导入和事实发布均未执行。可信SQL未加不可变trigger/RLS，store不是授权API；T19确切release成员未实现。既有T09 marker问题记录，不顺带改；T49 TTL及其他上线门槛仍待定。

## 变更文件与文档

22路径（9旧文档/13新），完整清单：

- AGENTS.md、README.md、docs/CHANGELOG.md、docs/DECISIONS.md、docs/api.md、docs/architecture.md、docs/database.md、docs/requirements.md、docs/tasks.md。
- docs/catalog.md、docs/acceptance/T11_admissions_catalog.md。
- services/api/app/admissions_catalog/__init__.py、models.py、schemas.py、store.py；services/api/catalog_alembic.ini；services/api/catalog_migrations/env.py、versions/0001_catalog_t11.py。
- tests/unit/catalog/test_t11_schemas.py、test_t11_migration_config.py；tests/integration/catalog/conftest.py、test_t11_relations.py。

ADR-022、契约/数据库/API/架构/需求同步，tasks只T11标完成；CHANGELOG记录上述实际失败/复验及限制。`.\.venv\Scripts\python.exe -B .cache/t11-validate.py`实际exit0：22路径/9旧/13新、236范围外tracked哈希、66其他Task卡、218本地文档链接、10Python内存编译、历史日志/ADR及生成LF均通过。旧迁移/验收/原文/研究/前端/依赖保留；完成暂存审查和普通提交/远程SHA核对后继续已授权T12。

保存实际记录：首源码commit `d19c29568784fb604ca96ef7700673085fd31f67`已普通push，私有origin及远程SHA一致、工作区干净。暂存URL正则检查曾误报配置单测中的`{SECRET_SENTINEL}`占位表达式；shell未传递该Python失败，所以该次扫描不能写通过。随后逐行确认唯一合成测试常量和无连接端口1用途，并对该精确已审核占位表达式豁免后重新检查22个HEAD文件；没有真实凭据/工件签名。补充此验收记录用独立普通commit保存，不改写首commit；后续辅助检查显式传播退出码。
