# E02 本地M0演示启动与核心流程验证

2026-10-13用户明确要求‘实际启动演示版，确认核心流程能走’，覆盖本次合成环境启动/健康/实际浏览器核心验证；此前本批不用测试继续约束其他回归/构建，不解释为授权全部检查或真实服务。开始前已读AGENTS/README/requirements/architecture/tasks/CHANGELOG/DECISIONS、M0契约/原规格/相关应用与已有浏览器脚本；Git基线PRIVATE `ba5ed63f46f5063288a6371f38f1be8743c53f86`、索引和工作区为空。

## 实施前范围与验收

- 保持应用/依赖/迁移/夹具原样，先使用已有PostgreSQL运行时新建专用本地合成库，loopback专用端口；不重用用户/生产数据库，不覆盖.env或旧.cache文件。
- 现有M0迁移与seed只在新库明确执行，启动app不DDL/seed。配置development/demo、mock无需商业密钥、浙江/2027合成范围，评估2026-10-13；原资料截至日期保持2026-09-30。
- 固定API127.0.0.1:8000和Vue demo127.0.0.1:5173/strictPort，不向外发布。
- 实际浏览器完成确认合成画像→四DEMO项目→确定性资格→合成证据→未确认草案；兼验数学不足ineligible、缺语言无后补unknown、两用户隔离及390px。
- 复用现有browser_smoke.mjs，独立headless Edge、本地请求白名单，不控制用户浏览器账号，不联网采真实事实。新验收输出使用新目录/文件，不覆盖旧图片/结果。

当前状态：已完成。以下为本次实际结果，服务继续运行。


## 当前访问与配置

- 网页：[http://127.0.0.1:5173/](http://127.0.0.1:5173/)；API文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。只绑定本机回环，无公众部署。
- 独立PostgreSQL 16.15，端口55439/数据库admissions_demo_e02_20261013；真实连接非SQLite。迁移head0001_m0，2机构/4项目/7证据/9规则全部DEMO。首次seed上述数量，第二次seed全部0，无覆盖。
- development/demo，MODEL_MODE=mock、V2模型disabled；浙江/2027仅既有合成范围，评估2026-10-13、数据截至2026-09-30分开。未调用模型密钥/商业API。
- 后台API、Vite和PG保留运行；runtime私有配置/凭据、数据库、日志和图片均.cache且不提交。原.env未写，用户旧数据库/缓存/历史验收保留。

## 实际命令与结果

| 操作 | 本次结果 |
| --- | --- |
| `docker version --format '{{.Client.Version}} {{if .Server}}{{.Server.Version}}{{end}}'` | 失败：CLI29.8.1存在，Linux Engine npipe缺失；没有修复/重建Docker数据 |
| `.cache/t01-postgres/runtime/pgsql/bin/pg_ctl.exe --version` | PostgreSQL16.15已存在，未下载或安装 |
| `.cache/e02_setup_20261013.ps1`内新目录initdb及pg_ctl start | PG初始化/启动成功；PowerShell Start-Process -Wait随后等待后台子进程树导致辅助脚本未完成，终止仅本次setup wrapper，PG和数据保留。等待改为WaitForExit，未修改应用 |
| `.cache/e02_resume_20261013.ps1` | exit0：复用本次已新建PG，明确创建空合成库、现有Alembic迁移/seed/重复seed，并启动API和Vite；秘密URL不输出 |
| `.venv/Scripts/python.exe -X utf8 -B .cache/e02_prepare_database.py`（上述脚本内部） | exit0：创建专用数据库/0001_m0；首次seed2/7/4/9，重复seed0/0/0/0 |
| `python -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000 --no-access-log`（项目venv后台启动） | 启动成功；/health/ready status=ok/demo_mode=true |
| bundled Node执行`apps/web/node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173 --strictPort` | Vite7.1.7启动成功，网页HTTP200；VITE_APP_MODE=demo，API /api代理8000 |
| `Invoke-RestMethod http://127.0.0.1:8000/health/ready`、`.../v1/config`及`Invoke-WebRequest http://127.0.0.1:5173/` | 数据库就绪、mock、浙江/2027与网页200实际响应 |
| `.venv/Scripts/python.exe -X utf8 -B .cache/e02_browser_copy.py` | exit0：从原browser_smoke.mjs复制到新的忽略目录，只改变结果/图片输出路径，旧报告未覆盖 |
| bundled Node24.19.0执行`.cache/e02-browser-smoke-20261013.mjs`，M0_PLAYWRIGHT_MODULE为现有Playwright本机文件 | exit0：实际headless Edge155.0.4283.45，8项passed，page_errors=[]；HTTP只允许本地5173/8000 |
| `.venv/Scripts/python.exe -X utf8 -B .cache/e02_record_runtime.py` | exit0：实际PG16.15/head0001_m0/2机构4项目7证据查询；仅本次专用库 |

后台环境变量只作用于本次进程；没有写入全局系统环境或仓库.env。演示URL当前可用不保证关机/进程停止后自动恢复，未安装开机服务。再次启动请按README选择M0开发数据库；本次缓存runtime可由本机维护者使用，不能上传其私有JSON。API启动不会自动迁移/seed。

## 8项实际浏览器结果

- DEMO/mock labels and four projects loaded from running API
- Explicitly confirmed profile persisted; blank language remains missing
- Missing language: eligible / conditional / unknown / unknown rendered with real results
- Synthetic evidence dialog displays source, project scope, hash and locator
- Unconfirmed draft generated; unpublished deadline remains null without invented time
- Profile edit invalidates old results/draft; achieved low math becomes ineligible
- User switch clears conclusions and excludes Alice profile IDs
- 390px viewport has no document horizontal overflow


本次截图已实际查看：DEMO/mock、浙江/2027、合成画像与证据scope/hash显示清楚。合成语言缺失得到eligible/conditional/unknown/unknown；数学改90后国内ineligible。草案仍draft、所有任务user_confirmed=false，未知期限为null不编23:59。独立浏览器已退出，服务保持运行，用户浏览器账号不受影响。

## 文件与未执行

本次只改AGENTS.md、README.md、docs/tasks.md、docs/CHANGELOG.md和本报告；没有应用代码/依赖/迁移/夹具修改。Git普通提交/推送当前已核实PRIVATE分支，实际SHA见最终回复。运行数据/密码/日志/截图不提交。

完整Unit/Integration回归、Lint、TypeCheck、生产Build、CI、Docker镜像/容器、T42–T67新功能及真实资料/身份/部署验收：未执行，用户本次只恢复演示启动及核心流程检查。Docker仍不可用，但本次使用实际本地PG，不是SQLite替身。不宣称正式咨询系统/全国真实资料已经可用。
