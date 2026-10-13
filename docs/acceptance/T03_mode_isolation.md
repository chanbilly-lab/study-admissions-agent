# T03 · 演示/生产模式隔离

日期：2026-10-01，Asia/Hong_Kong。用户明确授权执行 T03；只实现模式与入口隔离，不部署、不开始下一 Task。实施前已阅读 AGENTS、README、六份开发文档、API/数据库文档、两份原规格及相关代码，T02 依赖已完成。

## 实施前基线

- Git 起点 main / `317b49baa9f80ea67c9ffe675c43a555f126b66d`，工作区和暂存区为空；工作分支 `codex/t03-mode-isolation`，origin 为已确认私有仓库。
- `.cache/t03-baseline-20261001/`保存 101 个跟踪文件的哈希、旧任务/日志/ADR 与规范化 M0 OpenAPI；不上传缓存。原始两份规格哈希检查通过。旧迁移、夹具、研究样本、docs/01–05 和历史验收冻结。

## 数据契约（修改代码前确定）

1. 新增冻结的 `V2RuntimeSettings`，只读进程 `V2_` 配置，不自动读取 M0 `.env`。`app_environment=development/test/production`、`data_mode=demo/verified`、`model_mode=disabled/mock/live`分开校验。production 必须 verified；verified 禁 mock；v2 live 暂无供应商，启动拒绝，不回退。旧 `DEMO_MODE`仅检查冲突，不推导模式；非法值或冲突失败。
2. 可选 `V2_DATABASE_URL`仅允许 PostgreSQL，verified 拒绝已知 DEMO 用户/库/默认密码；不连接、不建表。未配置也可运行基础读取。错误不回显密码或输入。服务端派生 `query_role=demo_only/published_readonly`，请求不能选择；这是应用读取策略，不代表已创建 PostgreSQL 用户、GRANT 或 RLS。
3. 独立 `create_public_app`要求 production+verified，仅挂 `/v2`，不导入 M0 main、模型、数据库或 seed。旧 M0 入口与 seed 在生产/verified/禁演示配置下拒绝运行。生产拒绝固定 DEMO Bearer 凭据；公开基础读取不把其他 token 当已认证身份，私有业务仍不可用。
4. v2 wire `schema_version=v2.t03`；meta 的 data_mode 为 demo|verified，model_mode 为 disabled|mock（可运行实例）。配置新增 app_environment/query_role；business_available/live_available 仍 false，scope 空、省份/年度和所有事实版本仍 null。没有真实发布事实不得填充。
5. foundation 目录读取经过应用访问策略，verified 拒绝合成/DEMO、跨数据集、未审核、未发布或撤回描述；候选污染整体返回安全 503，不返回部分行。当前没有真实发布库，即使描述看似合规也不发布目录，正常列表仍为空。标签本身不证明正式人工审核。
6. 离线 schema/TS 生成使用显式固定 development/demo/disabled 配置，不能受服务器环境影响；M0 v1 wire 和 mock/live 既有语义保留。

## 修改范围

- 后端：settings、M0入口/seed的拒绝守卫、新 production factory、v2 factory/router/schemas、应用目录读取策略；不改持久化模型、迁移、资格算法或 DEMO 夹具。
- 配置：保留 M0 `.env.example`，另建无秘密的生产基础配置示例；不覆盖用户 `.env`。
- 契约及测试：生成器/两份生成产物、直接受影响 v2 测试与 TS 编译验收、新离线 security 测试；不新增依赖。
- 文档：AGENTS、README、requirements、architecture、database、api、tasks、CHANGELOG、DECISIONS 和本验收记录。

## 测试用例与验收

- 配置矩阵：默认/显式/进程配置、生产错误模式、verified+mock/live、非法枚举/旧开关/DEMO DSN/SQLite、冻结及错误脱敏。
- 入口：生产全部 v1 路径/方法/斜杠均不可用，OpenAPI 无 v1，DEMO 凭据拒绝，未实现私有路径关闭，客户端不能改变模式。
- 离线：无 API 密钥，未配置或不可达 PostgreSQL URL 不连接；独立新进程拦 M0/DB/seed/model 导入、网络，基础读取成功；fixture 在禁演示上下文拒绝且原文件未读取。
- 数据：实际目录路径注入合成/DEMO、未审、未发、跨数据集、撤回与混合行，整体拒绝，错误无事实字段泄漏；demo 策略也不接受真实事实。
- 回归：M0四态/缺成绩/owner/live失败等原测试、规范化 v1 OpenAPI 不变；v2实际响应/生成 OpenAPI/TS 对照及环境独立生成。
- 执行相关 pytest、前端 test/typecheck/build、原文/范围/历史/文档同步检查。Lint、Python静态类型入口若未配置应明确未执行；PostgreSQL无持久化变更不以历史实库结果冒充本次验证。

## 实际结果

2026-10-02完成。独立production入口只挂/v2，无M0/数据库/模型初始化；矩阵、DEMO凭据/fixture/候选拒绝与无密钥基础读取均由真实配置/HTTP/新进程测试验证。仅应用策略与空目录；真实公众业务未开放，无数据库迁移、新依赖或部署。实施前契约保留。

### 实际文件清单

23个旧文件修改：

- `.env.example`
- `AGENTS.md`
- `README.md`
- `services/api/app/settings.py`
- `services/api/app/main.py`
- `services/api/app/seed.py`
- `services/api/app/api/v2/__init__.py`
- `services/api/app/api/v2/router.py`
- `services/api/app/api/v2/schemas.py`
- `scripts/generate_contracts.py`
- `packages/contracts/v2/openapi.json`
- `packages/contracts/v2/generated.ts`
- `apps/web/tests/v2-contract-types.ts`
- `tests/backend/test_v2_api.py`
- `tests/contracts/test_v2_generation.py`
- `tests/contracts/test_v2_http_contract.py`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/api.md`
- `docs/tasks.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`

6个新增文件：

- `services/api/app/api/public.py`
- `services/api/app/api/catalog_access.py`
- `config/production-foundation.env.example`
- `tests/security/conftest.py`
- `tests/security/test_mode_isolation.py`
- `docs/acceptance/T03_mode_isolation.md`

### 实际命令及结果

以下从项目根目录执行；日期2026-10-02，均为本次实际执行，不引用旧Task通过数。

| 命令 | 实际结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest -m 'not postgres' -q` | 退出0；475 passed、4 deselected、1 warning，14.66s；包括M0回归、141安全、39生成、52HTTP契约及46v2原专项 |
| `.\.venv\Scripts\python.exe -m pytest tests/security/test_mode_isolation.py tests/backend/test_v2_api.py -q` | 最终退出0；187 passed、1既有warning；首版专项177 passed，完整middleware/candidate重验追加后187 |
| `.\.venv\Scripts\python.exe -X utf8 -m pytest tests/contracts/test_v2_generation.py tests/contracts/test_v2_http_contract.py -q` | 最终退出0；91 passed、1既有warning；首轮3 failed/88 passed，见下方修复记录 |
| `.\.venv\Scripts\python.exe -m pytest tests/backend/test_api.py tests/backend/test_rules.py tests/backend/test_persistence.py -m 'not postgres' -q` | 退出0；66 passed、4 deselected、1既有warning |
| `.\.venv\Scripts\python.exe -X utf8 scripts/generate_contracts.py` | 退出0；产物已更新并固定LF |
| `.\.venv\Scripts\python.exe -X utf8 scripts/generate_contracts.py --check` | 退出0；两生成产物与实际factory协议一致 |
| `.\.venv\Scripts\python.exe -X utf8 scripts/verify_contract.py` | 退出0；M0 required/null/literal/type/array/record一致 |
| `.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py` | 开始及最终均退出0；原两份输入SHA256未变 |
| `.\scripts\web.ps1 -Action test` | 退出0；4文件、18 passed |
| `.\scripts\web.ps1 -Action typecheck` | 退出0；vue-tsc --noEmit，含更新后的编译验收 |
| `.\scripts\web.ps1 -Action build` | 退出0；vue-tsc + Vite7.1.7，16模块构建；dist未上传 |
| `.\.venv\Scripts\python.exe -m compileall -q services/api/app scripts/generate_contracts.py tests/security tests/backend/test_v2_api.py tests/contracts/test_v2_generation.py tests/contracts/test_v2_http_contract.py` | 退出0；语法检查，不能当静态类型或Lint |
| `git -c safe.directory=D:/Projects/study diff --check` | 退出0；现有core.autocrlf的LF/CRLF提示非失败，未改全局配置 |
| `.\.venv\Scripts\python.exe -X utf8 .cache/t03_validate_20261002.py` | 退出0；29路径变化、78范围外文件哈希不变、旧日志/ADR/其他Task及规范化M0 OpenAPI保留；缓存不上传 |
| `.\.venv\Scripts\python.exe -X utf8 .cache/t03_validate_20261002.py --final` | 退出0；29路径/78保护文件/121本地链接、T03任务与日志完成状态一致、全部变更路径已记入本验收；M0 wire与历史未变 |
| `.\.venv\Scripts\python.exe -X utf8 .cache/t03_validate_20261002.py --final --stage` | 修正辅助统计后退出0；实际暂存29路径一致、无高置信token/私钥形态、无私有运行文件或产物；生成blob为LF |
| `gh repo view chanbilly-lab/study-admissions-agent --json nameWithOwner,isPrivate,defaultBranchRef,url` | 退出0；已核实私有、main默认分支和origin；只为源码治理联网，与离线测试分开 |

专项另有后端TestClient探针18个路径/方法组合、模块与测试py_compile退出0，已被最终pytest/compileall覆盖。代码/文档独立只读终审未发现安全阻断，发现api旧入口描述并修正，不重复应用测试。

### 失败与修复记录

- 首轮contracts专项真实为3 failed/88 passed：Pydantic Settings合并旧DEMO_MODE alias导致显式legacy_demo_mode=None未覆盖非法进程值。V2RuntimeSettings将显式字段规范化到同一alias，未改进程环境或绕验证；重跑91 passed，最终全套通过。
- 后端最初pytest命令误引用不存在的`tests/backend/test_eligibility.py`，退出4、无测试运行；纠正为上表test_rules.py后66 passed，不把命令错误隐藏为成功。
- 最终暂存辅助第一次`--final --stage`退出1：新文件进入索引后不再属于untracked，辅助仅按untracked统计导致误报范围不一致；实际索引29路径正确。辅助改为同时核对基线之外的索引新增文件与untracked，重新验证；未改源码、用户索引或扩大提交范围。
- 审查发现URL query可覆盖连接身份、Pydantic copy/construct可跳校验、DEMO依赖未覆盖OpenAPI/redirect，以及typed候选污染可能500；本Task补校验与完整middleware，再由真实拒绝测试通过。没有以过滤污染行后返回部分目录代替失败。

### 未执行与实际限制

- PostgreSQL4项被`not postgres`明确排除、未执行：本Task无数据库结构/连接/权限变更；T01历史实库通过不作为本次结果。query_role仅应用策略，不是已经创建/验证PostgreSQL用户、GRANT/RLS或真实发布表；后续T11–T19/T20和数据库权限验收不得省略。
- Lint与Python静态类型检查未执行：读取pyproject.toml/package.json确认只有pytest和前端test/typecheck/build入口，ruff/mypy find_spec为false；不为本Task加无关依赖。TS类型和Python语法已实际运行，不能当Lint。
- uvicorn独立监听烟测、浏览器E2E、Docker/Compose、生产部署均未执行：未改UI/部署，本轮HTTP通过独立factory、mounted TestClient及干净子进程验收；README提供本机验证命令，但不把说明当执行证据。
- 真实身份/用户资料、招生事实审核/发布、资格/计划、模型live或商业API未实现/未调用；无API密钥可用仅指基础配置/空目录。M0前端仍合成演示，不能连此入口就声称公众业务完成。D01–D08未因此解除。
- 既有Starlette/AnyIO弃用warning保留；TS不能完整强制模式跨字段/数值/长度/封闭对象/Page关系，运行矩阵由启动配置及HTTP测试验证。无T03阻断项。

### 结束与上传边界

[tasks](../tasks.md)与[CHANGELOG](../CHANGELOG.md)的T03状态、文件、测试已同步，ADR-014和API/架构/需求/数据库说明同步。其他64个主Task未开始；推荐先确定D04可实施身份配置再选T04，不自动开始。

按用户持续授权仅暂存上述29路径，审查实际cached diff及秘密形态后普通commit/push到已核实的私有origin和codex/t03-mode-isolation。上传与SHA的最终事实以本轮Git核对及最终报告为准；源码保存不授权业务部署、事实发布或真实用户数据处理。不改main历史、不强推，不纳入.cache、node_modules、dist或用户.env。
