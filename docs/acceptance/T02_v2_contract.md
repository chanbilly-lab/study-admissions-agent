# T02 · /v2 基础契约

日期：2026-10-01，Asia/Hong_Kong。状态：已完成。用户授权执行T02并沿用AI Development Rules；T01实库验收为前置，历史记录不改写。下面的契约/范围/用例已先于代码列出，实际验收后补于末尾；完成后停止。

## 实施前数据契约

1. 使用独立FastAPI子应用`create_v2_app()`，由既有应用挂载`/v2`；独立OpenAPI可通过`/v2/openapi.json`读取，schema的server为`/v2`，paths为`/config`和`/offerings`。M0主应用OpenAPI、成功及错误格式保持，正式生产隔离留给T03。本任务子应用不创建数据库/表，不导入资料、调用模型或接受私有写入。
2. 成功JSON为`{data,meta}`；meta所有字段存在：`api_version="v2"`、`request_id`为服务端32位小写hex、`data_as_of/profile_version_id/release_id/ruleset_version/profile_mode=null`、`data_mode="demo"`、`model_mode="disabled"`。不将请求时间或DEMO快照填入未发布资料日期。`X-Request-ID`与body相同，不信任客户端传入的编号。
3. `GET /v2/config`数据：`api_version="v2"`、`schema_version="v2.t02"`、`contract_stage="foundation"`、`data_mode="demo"`、`model_mode="disabled"`、`live_available=false`、`business_available=false`、`supported_scope=[]`、`supported_province=null`、`entry_year=null`。未适配真实业务，不把M0浙江/2027称为v2已支持。配置不接受查询参数。
4. `GET /v2/offerings`仅接受`limit`（默认20，1–100）及`cursor`（可选字符串，长度1–512）；拒绝额外字段及重复标量参数。返回`{items:[],page:{limit,next_cursor:null,has_more:false}}`。`OfferingReference{id:string}`只定义契约中的条目引用，没有任何项目返回。Page类型校验items数量不超过limit，has_more与非空next_cursor一致。
5. 此基础阶段未产生有效游标：任何显式cursor（包括空、过长、篡改）返回422；有效长度但未发行的游标代码`INVALID_CURSOR`，不接受后忽略，不制造假续页。真实keyset、过滤/发布绑定、授权等由后续目录Task实现。
6. 错误JSON为`{error:{code,message,request_id,details:[{field_path,code,message}]}}`，必需字段明确。验证422、安全映射HTTP401/403/404/405/409/422/429/503以及通用500；保留适当WWW-Authenticate/Allow/Retry-After头，不回显输入值、token、SQL、原HTTP detail或异常文本。未知路径404和方法405也使用v2协议。故障测试仅挂在测试实例，不加入运行路由。
7. 复用已安装Pydantic/FastAPI及stdlib，无新依赖。`scripts/generate_contracts.py`离线生成`packages/contracts/v2/openapi.json`与`generated.ts`；`--check`只比较不写文件，漂移退出非零；未知/不支持schema明确失败，不退化为any。生成排序/缩进稳定，不含生成时间或随机request_id。保留现有M0手写契约和验证器。

## 修改范围

- 后端：新增`services/api/app/api/__init__.py`及`api/v2/`（factory/router/schemas/errors），主`main.py`只接入子应用。
- 契约：新增`packages/contracts/v2/openapi.json`、`generated.ts`、离线生成脚本及专项契约测试；前端只新增类型编译验收，不改页面和现有API客户端。
- 记录：README、AGENTS当前阶段、docs/api、architecture、requirements当前实现说明、tasks/CHANGELOG/DECISIONS及本验收；不改变数据库设计、迁移、夹具、来源JSON、原始规格/docs01–05、旧验收或依赖锁。新增ADR记录隔离子应用与生成方式。

## 验收用例

- 默认/1/100分页成功；0、101、负数、非整数、额外筛选、重复标量、空/过长/未发行游标422；空列表200且无假续页；分页模型数量及游标一致性。
- 配置正确声明foundation/业务不可用/disabled、空支持范围、null事实版本；配置未知参数被拒绝。
- request_id每请求独立，body/header相同，客户端编号不采纳；mounted与standalone行为一致。
- 验证、HTTP错误、未知路由、405、意外500均有协议；敏感验证值/HTTP detail/异常token不泄露，受控头保留。
- 独立OpenAPI/生成TS语义与实际HTTP成功/错误一致，nullable/required/literal保持；重复生成稳定，--check能检测JSON和TS漂移且不改文件；未知schema不能吞掉。
- 子应用无需数据库迁移/seed及模型，离线检查拒绝外网；M0原有契约、合成画像/权限/四态/草案离线回归；TS编译纳入v2，前端原有测试/构建通过。
- 文件范围/原始规格/历史验收保护，Task/日志/文档状态一致，完成T02后停止。

## 实际结果

运行环境：既有`.venv` Python3.12、FastAPI0.115.12、Pydantic2.11.7、pytest8.4.1；前端通过现有web.ps1使用随附Node24.19.0/pnpm11.19.0，仅当前进程PATH。未安装新依赖/改变锁文件。测试使用合成/隔离内存SQLite、TestClient及离线网络限制；契约生成fresh-process验证不导入M0/SQLAlchemy/seed/provider，不读取.env、不调用模型/商业API。原有本机Docker修复状态不用于本次应用验收。

### 实际命令与结果

以下命令均在`D:\Projects\study`执行；当前最终稳定文件结果如下。

| 实际命令 | 结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest -m 'not postgres' -q` | 退出0：**306 passed、4 deselected、1 warning**。197既有离线检查+109新专项（后端HTTP46、生成35、HTTP/schema/TS28）；4 deselected为PostgreSQL专项，不计通过 |
| `.\.venv\Scripts\python.exe -X utf8 scripts/generate_contracts.py` | 退出0；初次生成两个新产物，无旧文件覆盖 |
| `.\.venv\Scripts\python.exe -X utf8 scripts/generate_contracts.py --check` | 退出0；两个产物匹配，独立只读审查确认哈希/mtime不变；漂移失败行为在测试的临时目录验证 |
| `.\.venv\Scripts\python.exe -X utf8 scripts/verify_contract.py` | 退出0：M0 TS/OpenAPI语义一致 |
| `& .\scripts\web.ps1 -Action test` | 退出0：4文件、**18 passed**，现有M0交互/API回归 |
| `& .\scripts\web.ps1 -Action typecheck` | 退出0：vue-tsc --noEmit，纳入generated.ts及新v2-contract-types.ts的正/反向编译验收 |
| `& .\scripts\web.ps1 -Action build` | 退出0：vue-tsc及Vite7.1.7构建成功，16模块；仅生成ignored dist |
| `.\.venv\Scripts\python.exe -m py_compile services/api/app/main.py services/api/app/api/__init__.py services/api/app/api/v2/__init__.py services/api/app/api/v2/schemas.py services/api/app/api/v2/errors.py services/api/app/api/v2/router.py scripts/generate_contracts.py tests/backend/test_v2_api.py tests/contracts/test_v2_generation.py tests/contracts/test_v2_http_contract.py` | 退出0，10份Python语法检查；不是Lint或静态类型检查 |
| `.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py` | 退出0：两份原始输入哈希未变 |
| `.\.venv\Scripts\python.exe -X utf8 .cache/t02_validate_20261001.py --final` | 最终退出0：范围、UTF-8/本地链接、其他Task/历史记录、M0规范化OpenAPI、mount/独立schema及任务/日志/ADR同步检查；辅助位于ignored cache，使用本轮86文件基线 |
| `git -c safe.directory=D:/Projects/study -c core.quotepath=false status --short` | 退出0；项目仍未跟踪，无提交/重置/清理/全局safe.directory更改，按哈希基线判断本轮范围 |

协作局部测试也真实执行：后端文件初44、补挂载500后最终46 passed；生成器初30、强化未知结构拒绝后最终35 passed；HTTP契约28 passed（与初后端合跑72 passed）。主代理完整回归最终306 passed，局部数量不重复累加。Starlette/AnyIO的1条DeprecationWarning来自既有安装依赖；无应用测试失败。

辅助检查第一次退出1：写成不存在的Settings字段`m0_sqlite_test_mode`，实际字段为`sqlite_test_mode`。修正后第二次退出1：比较序列化文本换行而非同样规范化schema，且清理错误写为`app.state.database.engine`；改为两侧规范化JSON和实际`app.state.engine`后退出0。未修改应用来迁就辅助，不掩盖这些失败。最终辅助再次核对完成状态通过。

### 精确变更清单

修改9份原文件：

- `services/api/app/main.py`：只增加v2 import/mount两行，主OpenAPI规范化内容与任务前一致。
- `README.md`、`AGENTS.md`：当前状态、运行/生成说明及授权边界。
- `docs/requirements.md`、`docs/architecture.md`、`docs/api.md`：基础协议已实现、未来业务未实现和TS约束局限。
- `docs/tasks.md`、`docs/CHANGELOG.md`、`docs/DECISIONS.md`：T02完成记录、实际检查、ADR-012。

新增13份文件：

- `services/api/app/api/__init__.py`
- `services/api/app/api/v2/__init__.py`
- `services/api/app/api/v2/schemas.py`
- `services/api/app/api/v2/errors.py`
- `services/api/app/api/v2/router.py`
- `scripts/generate_contracts.py`
- `packages/contracts/v2/openapi.json`
- `packages/contracts/v2/generated.ts`
- `tests/backend/test_v2_api.py`
- `tests/contracts/test_v2_generation.py`
- `tests/contracts/test_v2_http_contract.py`
- `apps/web/tests/v2-contract-types.ts`
- `docs/acceptance/T02_v2_contract.md`

77份范围外原文件哈希未变，包括原始两份输入、docs01–05、旧验收、M0契约/规则/夹具/迁移、研究JSON、配置/依赖锁及前端页面/API客户端。其他Task卡、P00历史、旧CHANGELOG和ADR-001–011内容保持；AGENTS只更新当前阶段。cache存本轮快照/辅助，dist与测试缓存不纳入变更清单。未删除任何项目文件。

### 未执行检查及限制

- PostgreSQL4项专项本轮明确排除、未执行：无数据库/迁移/持久化变化，T02factory独立且不使用数据库；T01历史实库通过不作为本次结果。Docker/Compose项目库未启动。
- Lint及Python静态类型检查未执行：项目无已配置入口，ruff/mypy未安装；未新增无关依赖。已实际执行TS类型和Python语法检查，不能替代称为Lint。
- 浏览器E2E、独立uvicorn监听服务烟测未执行：仅基础接口/类型变化，未改UI；HTTP使用TestClient验证standalone及M0-mounted成功/422/404/405/500，没有宣称真实浏览器或监听进程验收。
- 生产部署、正式身份/私有写入、真实学生/已发布招生资料、模型live/商业API、keyset及全网采集未实施/未验收，均超出T02；config明确业务不可用且模型disabled，空列表不宣称全国零项目。
- 生成TS保留wire形状/必需/null/literal，但数值/长度、空scope、封闭对象和Page跨字段关系不能由TS全面保证；空查询interface也不能由TS禁止所有参数。OpenAPI/服务端验证这些约束，实际HTTP/schema测试覆盖。

无T02阻断项。[tasks](../tasks.md)与[CHANGELOG](../CHANGELOG.md)的状态/文件/测试已同步，[ADR-012](../DECISIONS.md)仅在T02基础范围标已实施。67主Task中T01/T02已完成、65未开始，T50A/P00–P03/E01保持已完成。下一功能推荐T03，须另行选定，不自动开始。

## 实施依据

沿用既有API规划和安装版本；已核对FastAPI支持[独立子应用](https://fastapi.tiangolo.com/advanced/sub-applications/)、0.115.0起的[查询参数模型与额外字段拒绝](https://fastapi.tiangolo.com/tutorial/query-param-models/)及[错误处理](https://fastapi.tiangolo.com/tutorial/handling-errors/)。技术栈保持，无公众发布授权。
