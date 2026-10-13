# M0 实际交付与验收记录

> Privacy note (2026-10-14): private account/resource identifiers and personal home paths have been redacted for the public-release candidate. Historical outcomes are unchanged; placeholders are not live targets.

日期：2026-09-30，Asia/Hong_Kong。只实现 M0；后续里程碑未开展。

## 最终结果

| 实际命令 / 检查 | 结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest -q` | **96 passed、1 skipped、1 warning，exit 0**。包含后端 66 项与契约 30 项；PostgreSQL 实库检查跳过。 |
| `.\scripts\web.ps1 test` | **18 passed，4 个测试文件，exit 0**。包括真实数字输入保存回归。 |
| `.\scripts\web.ps1 build` | **exit 0**：`vue-tsc --noEmit` 与 Vite 7.1.7 生产构建成功，16 modules transformed。 |
| `.\.venv\Scripts\python.exe -m alembic -c services/api/alembic.ini upgrade head` | 在空 `.cache/m0-smoke.db`、`DATABASE_URL=sqlite:///./.cache/m0-smoke.db`、`M0_SQLITE_TEST_MODE=true` 下成功迁移至 `0001_m0`，exit 0。 |
| `.\.venv\Scripts\python.exe -m services.api.app.seed` | 同一演示库成功导入 **2 机构、7 证据、4 项目、9 规则**，exit 0。重复导入不覆盖私有画像与已有记录的测试通过。 |
| `uv --cache-dir .cache/uv pip check --python .venv/Scripts/python.exe` | 31 个锁定包兼容，exit 0。 |
| `.\.venv\Scripts\python.exe scripts/verify_originals.py` | 两个原始文件 SHA256 均未改变，exit 0。 |
| `Invoke-RestMethod http://127.0.0.1:8000/health/ready` | `{"status":"ok","demo_mode":true}`，SQLite 替身实例。 |
| `node scripts/browser_smoke.mjs`（以下给出本机实际运行时） | **8 个端到端检查通过，page_errors=[]，exit 0**；独立无界面 Edge `154.0.4258.37`。 |
| PostgreSQL 在线迁移、导入与集成 | **未执行**：未配置 `TEST_POSTGRES_URL`，未发现可用 PostgreSQL 服务；Docker 引擎未运行。SQLite 通过不等同 PostgreSQL 实库通过。 |
| CUA 可见浏览器验收 | **未执行**：首次与重置后启动均被 Windows sandbox `setup refresh had errors` 阻断。独立 Playwright 浏览器检查另行执行成功。 |

Python 使用 Codex 随附 **3.12.14**，项目 `.venv`；前端使用随附 **Node 24.19.0、pnpm 11.19.0**。普通用户终端 Node 是 16.13.0；`scripts/web.ps1` 仅在当前进程优先选择随附运行时。离线测试与浏览器检查没有使用模型密钥或商业 API。

## 浏览器检查的实际命令

先运行两个本地服务：

```powershell
$env:DATABASE_URL='sqlite:///./.cache/m0-smoke.db'
$env:M0_SQLITE_TEST_MODE='true'
$env:MODEL_MODE='mock'
.\.venv\Scripts\python.exe -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000
```

另开终端运行 `.\scripts\web.ps1 dev`。然后本机实际执行：

```powershell
$env:M0_PLAYWRIGHT_MODULE='file:///<USER_HOME>/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
& '<USER_HOME>\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' scripts/browser_smoke.mjs
```

这项可选检查使用环境中已有的 Playwright **1.62.1** 与 Edge。换环境需提供 Playwright 的模块位置和可用的 Edge，或自行调整浏览器 channel；不是默认 pytest/Vitest 的前提。结果与截图保存在忽略目录 `.cache/browser-smoke.json`、`.cache/m0-workspace.png`、`.cache/m0-evidence.png`，截图已查看。

实际检查：DEMO/mock 与四项目读取；用户确认保存且缺语言仍缺失；国内 eligible、英国有政策 conditional、无政策/缺期限 unknown；证据原文/范围/哈希/定位；未确认草案与缺期限；修改画像清空旧结果，实得数学 90 判 ineligible；切换 Bob 排除 Alice 画像；390px 无页面水平溢出。浏览器测试仅允许两本地服务的应用请求。

## 覆盖的业务边界

四态及明确失败优先；缺成绩/预测成绩/单位满分不一致；年度、省份、身份、体系与路径；规则和证据未审核/冲突/过期；错误原子类型与非白名单字段；跨项目主证据、后补政策与期限证据；文档哈希与原文定位；后补期限前后；客户端 owner 拒绝；两用户画像/资格/草案隔离；live 503 与事务回滚；不伪造截止时刻；DEMO 标签；迁移与夹具冲突不覆盖。

共享 TypeScript 声明与 FastAPI OpenAPI 比较 required/null/枚举/嵌套类型及响应 Envelope，且测试真实 HTTP JSON；契约检查器有故意漂移的自测。规则未调用模型，未使用 eval/exec。

## 过程中实际失败及修复

- 契约检查器首轮 **10 passed / 1 failed**：不支持语法的诊断文字不一致；统一诊断后 **11 passed**。
- HTTP 契约首轮 **26 passed / 2 failed**：测试使用了不同的路径参数名；按实际 OpenAPI 模板适配，最终契约 **30 passed**。
- 前端依赖安装两次因 pnpm 11 的 esbuild 构建许可缺失退出 1；项目 `allowBuilds.esbuild=true` 后安装成功。仅此依赖允许构建脚本。
- 首轮前端测试启动失败：脚本子进程选中 Node 16；显式使用 Node 24 后通过。
- 首轮生产构建退出 2：Vitest 与 Vue 插件解析了不同 Vite 版本；使用 `overrides.vite=7.1.7` 更新锁文件后通过。
- 后端代理首轮 **48 passed / 1 skipped / 18 errors**：离线网络拦截误拦 Windows asyncio 的本地 socketpair；仅允许本地 loopback 后专项 **66 passed / 1 skipped**，主代理合并运行 **96 passed / 1 skipped**。
- 浏览器首轮保存画像超时、退出 1：Vue 数字输入产生 number，字符串 `.trim()` 校验失败。统一兼容 string/number、保留空值语义并增加两项回归后，前端 **18 passed**，浏览器 **8 项通过**。
- uv 默认缓存位置访问失败，改用项目 `.cache/uv` 后依赖锁定与安装成功。uv 创建的虚拟环境无 pip，`python -m pip check` 未运行；改用 `uv pip check` 成功。

## 变更文件

全部是新增工程文件，原始两文件保持不变。未重置、覆盖或提交用户文件；Git 初始不存在，已初始化空仓库，没有提交。

- 根目录：`AGENTS.md`、`README.md`、`.env.example`、`.gitignore`、`compose.yaml`、`pytest.ini`、`pyproject.toml`、`requirements.in`、`requirements.txt`。
- 规格：`docs/01_PRD.md`、`02_DATA_AND_RULES.md`、`03_ARCHITECTURE_API.md`、`04_MILESTONES_ACCEPTANCE.md`、`05_SOURCES_AND_REVIEW.md`（提取原文），`M0_IMPLEMENTATION_PLAN.md`、本报告。
- 配置/契约：`config/demo.json`、`packages/contracts/index.ts`。
- 后端：`services/__init__.py`、`services/api/__init__.py`、`alembic.ini`；`app/{__init__,settings,schemas,database,models,migrations,seed,catalog,eligibility,providers,planning,main}.py`；`migrations/env.py`、`script.py.mako`、`versions/0001_m0.py`。
- 夹具：`data/fixtures/build_demo.py`、`demo_catalog.json`。
- 前端：`apps/web/{package.json,pnpm-lock.yaml,pnpm-workspace.yaml,.npmrc,index.html,tsconfig.json,vite.config.ts}`；`src/{main.ts,env.d.ts,api.ts,workspace.ts,profileForm.ts,App.vue,styles.css,components/EvidenceDialog.vue}`；`tests/{api,profileForm,workspace,App}.test.ts`、`tests/fixtures.ts`。
- 后端/契约测试：`tests/backend/{__init__,conftest,test_api,test_rules,test_persistence}.py`；`tests/contracts/{test_contract_verifier,test_api_contract}.py`。
- 工具：`scripts/{verify_originals.py,verify_contract.py,web.ps1,browser_smoke.mjs}`。

原始文件 SHA256：

```text
升学咨询智能体_开发方案与审查.md
a69f01f4db5f2a2c49a4c89dd92138e10fbc51a129406834bbb2cce2a4aac2f1
Codex_升学智能体_首次开发Prompt.txt
6db9dd8c2d17ee3c4c261a3eae69f9e258fbe4294dcee6a8726eb05cdf2f05eb
```

## 剩余问题与范围限制

1. PostgreSQL 实库迁移/夹具导入尚未验证，需可用数据库后运行 opt-in 集成检查。正式数据库类型仍为 PostgreSQL。
2. Starlette TestClient 对当前锁定 AnyIO 的 deprecated `BlockingPortal` 别名产生 1 条警告；没有隐藏该警告，不影响此次离线结果。
3. 固定演示凭据不是正式认证；live 模型仅接口占位，后补依据全为合成，不能用于真实学生。画像每次确认创建新不可变初始版本；纵向版本修订与计划确认属于后续里程碑。
4. 普通沙箱终端与 CUA 初始化仍有环境错误，本轮命令经已批准的沙箱外执行完成。新 `.git` 归沙箱账户，普通用户 `git status` 会报告 dubious ownership；尝试仅恢复目录所有者被操作系统拒绝。实际状态通过 `git -c safe.directory=D:/Projects/study -c core.quotepath=false status --short` 读取，全部为未跟踪文件。可按此项目限定命令继续检查；全局 Git 配置未修改。
5. 未做真实招生事实审核、性能基准、全浏览器矩阵、真实学生部署及 M1–M6，以上均未宣称通过。

M0 到此停止。


## T01 · PostgreSQL基线补充验收（2026-10-01）

本节是新增日期记录；上面的2026-09-30命令、跳过和剩余问题保持原样，不代表本日结果。此次仅增强持久化测试，未改M0业务、0001_m0或DEMO夹具。

环境：项目Python3.12.14；专用空库m0_t01_test；临时PostgreSQL16.15，UTF-8，127.0.0.1:55432，SCRAM本地凭据。数据库程序/数据只放忽略目录.cache/t01-postgres，未写.env、系统服务或用户已有数据库。下载安装准备需要网络；以下应用测试只访问本地数据库/测试客户端，不调用网站、模型或商业API。

| 实际命令/检查 | 本日结果 |
| --- | --- |
| `docker --context desktop-linux version --format '{{json .Server}}'` | 退出1；尝试启动已有Docker Desktop后，WSL数据发行版keepalive异常/网络名不可用，引擎仍不可用。没有修改WSL或系统配置。 |
| `curl.exe --fail --location --silent --show-error --max-time 600 --output .cache/t01-postgres/postgresql-16.15-4-windows-x64-binaries.zip https://get.enterprisedb.com/postgresql/postgresql-16.15-4-windows-x64-binaries.zip` | 退出0；官方ZIP371449528字节。准备下载，非离线应用测试。 |
| `.\.venv\Scripts\python.exe -X utf8 .cache/t01-postgres/extract.py`；`.\.cache\t01-postgres\prepare.ps1` | 均退出0；只解压bin/lib/share，initdb新cluster，pg_ctl启动、createdb和版本/空库检查成功；初始public表0。 |
| `.\.venv\Scripts\python.exe -m pytest tests/backend/test_persistence.py -m postgres -q` | **4 passed、4 deselected、1 warning，退出0**；在当前进程从忽略的url.private载入TEST_POSTGRES_URL，未把临时密码写入文档。 |
| `.\.venv\Scripts\python.exe -m pytest -m 'not postgres' -q` | **96 passed、4 deselected、1 warning，退出0**。 |
| `.\.venv\Scripts\python.exe -m alembic -c services/api/alembic.ini upgrade head`；`... current` | DATABASE_URL为专用PG、M0_SQLITE_TEST_MODE=false、MODEL_MODE=mock；均退出0，0001_m0 (head)。 |
| `.\.venv\Scripts\python.exe -m services.api.app.seed`，连续两次 | 均退出0；第一次2机构/7证据/4项目/9规则；第二次各0新增。 |
| 临时`psql.exe -h 127.0.0.1 -p 55432 -U t01_demo -d m0_t01_test -X -v ON_ERROR_STOP=1`，查询pg_tables/七表计数/pg_namespace | 退出0；七业务表+alembic_version，2/7/4/9及三私有表0；残留m0_test_ schema为0。完整SQL见[独立验收](acceptance/T01_postgresql.md)。 |
| 临时`pg_ctl.exe stop -D .cache/t01-postgres/cluster -m fast -w -t 30`；`pg_ctl.exe status -D ...` | stop退出0；status退出3（预期无服务）；Get-NetTCPConnection确认55432监听0，环境关闭检查整体退出0。 |
| `.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py`；`... -m py_compile tests/backend/test_persistence.py` | 均退出0；两原始文件未变、测试Python语法有效。 |
| `.\.venv\Scripts\python.exe -X utf8 .cache/t01_validate.py` | 退出0；范围外74文件SHA256不变，旧M0报告原字节保留，6旧文件修改+1新增验收文档，任务/日志状态与结果同步。 |
| `git -c safe.directory=D:/Projects/study -c core.quotepath=false status --short` | 退出0；仍全部未跟踪，未重置或提交，未改全局配置。 |

文档检查首轮退出1：独立验收使用“4项PG/96项回归”，校验要求passed统计文字；补上确切数量后复跑退出0（12文档/77本地链接）。应用测试首轮即通过。

覆盖：精确冻结表/外键/索引/画像唯一约束；中文/JSON/布尔与原文hash；API确认两用户画像，写资格/计划后repeat head+seed完整私有数据不变并拒绝越权；已执行新机构INSERT再发生旧ID冲突的整笔回滚；无效hash拒绝；独立空私有schema执行head→base→head与重导。base会删除七业务表，不能解释为保留数据。

修改：tests/backend/test_persistence.py；README、AGENTS、tasks、CHANGELOG；新增docs/acceptance/T01_postgresql.md；本报告仅追加。没有新增应用依赖，旧迁移/夹具/配置/运行代码未改。

未执行：Compose中的16.6-alpine容器路线（Docker引擎失败）；前端Unit/Type Check/Build/浏览器（前端未改）；Lint（无项目配置入口）；公众功能、部署、备份恢复/性能（本Task未涉及）。仍有1条已知Starlette/AnyIO弃用警告，本Task不顺带升级依赖。验证结论仅限M0基线，不代表公众版本可上线。

T01验收完成，CHANGELOG/tasks已同步。按用户授权，下一项来源登记另设独立Task；其实现不会自动启动T50后台或发布事实。
