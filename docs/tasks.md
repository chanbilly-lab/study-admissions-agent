# 开发 Task 与执行规则

2026-10-14 PRIVACY-PUBLISH-01：[~] 进行中。用户要求隐私审阅／修复后公开源码；全49分支／78提交／1,685blob及元数据、远端表面已查，4文档8处home脱敏，旧提交私人邮箱仅留私有备份。干净候选待仓库管理选择及实际发布，未公开／改名／强推。见[source_publication](source_publication.md)。验收要求保留原工作／历史，公库不含本轮确认的私有标识与旧元数据，公开可见性／SHA实际核对；应用／数据／事实发布不启用，应用测试未恢复。

2026-10-14 SEARCH-SELECT-01：已完成（搜索选择源码/文档，运行未验证）。学校/专业身份搜索API与当前正式发布reader、共享级联选择/分页/取消/上下文pin，培养/毕业UI移除手填UUID/ref；资料届与身份来源招生年分开，学院/学科禁用。默认目录None、无真实可选项，不用候选/DEMO；培养/毕业仍空。全部测试/Lint/TypeCheck/Build/import/SQL/HTTP/浏览器/校验/装配/重启未执行（用户要求）。[契约](school_program_search.md)、[27文件/未验证记录](acceptance/SEARCH_SELECT_01.md)已同步；PRIVATE保存核对后停止。

2026-10-13 UI-OPT-01：已完成（展示源码/文档范围，运行未验证）。8前端文件共享主题、M0状态提示/缺失措辞/焦点、参考导航/筛选/分数卡/渐进证据及缺口说明；客户端/controllers/API/DB/数据/权限/四态保持。所有测试/Lint/TypeCheck/Build/浏览器/视觉校验未执行（原用户要求），旧截图仅作基线。见[UI优化及后续优先项](ui_optimization.md)、[16文件及未验证记录](acceptance/UI_OPT_01.md)；文档同步与PRIVATE保存后停止。

2026-10-13 SCHEDULE-ANNUAL-01：已完成（用户确认的源码/文档交付范围，运行未验证）。年度11月1日09:00 Asia/Shanghai，仅生成待采集请求，后续资料另行审核；默认关闭、不联网/更新事实/发布。新独立两表/CLI与年度去重、最近周期补偿、配置冲突/有界失败。全部测试/Lint/TypeCheck/Build/校验/迁移/worker运行未执行（用户再次要求），未创建新库或启动服务。见[年度调度](annual_source_updates.md)、[23文件及未验证记录](acceptance/SCHEDULE_ANNUAL_01.md)；文档同步与PRIVATE保存后停止。

2026-10-13新授权BATCH-UK-2027-INSTITUTIONS-01：已完成（有限研究来源登记范围）。用户确认两校英国2027本科，实际8指定官方HTML200及真实hash，专业未选、正式审核0/发布0，不进入正式DB/页面/资格。采集命令exit0；所有应用测试/Lint/TypeCheck/Build/校验未执行（原不用测试保持）。契约与完成条件见[批次范围](uk_2027_sources.md)、[实际报告](acceptance/data_batches/BATCH_UK_2027_INSTITUTIONS_01.md)；PRIVATE保存后停止，其他工作不自动继续。

2026-10-12用户确认简化全部剩余任务并逐个执行至T67；T49不重复。本批按docs/simplified_plan.md交付最小源码，原运行/真实资料/发布验收保留未验证；D01/D07等未知不阻挡默认关闭源码顺序推进，但继续阻挡真实启用。此新授权替代先前T50停止及T44源码等待限制。不运行测试/Lint/TypeCheck/Build/校验/演练，每Task文档同步和PRIVATE普通保存后下一项，T67后停止。

2026-10-13当前主Task统计：67已完成、0进行中、0阻塞、0未开始；本批最小源码范围，运行/真实验收未通过，T67停止。

2026-10-04历史主Task统计：44已完成、0进行中、0阻塞、23未开始；本批源码任务与运行验收分别记录，至T50停止。

2026-10-04批次授权与先前进度：逐个执行T21–T50；T21–T41已验收；T01–T42及T49共43主Task已完成（T42仅调整后的通用源码范围，未验证运行）、其他24未开始。每Task依赖、验收、文档同步及私有提交推送完成后才开始下一项，完成T50后停止。下方旧T20停止记录保留为历史，不撤销本次新授权。

历史授权（2026-10-03）：原批次到T40停止；现被2026-10-04延长至T50。每Task独立验收/文档/PRIVATE保存的规则保持。

2026-10-03最新授权：先明确D02，再独立依次执行T08–T20；T08–T20及必要依赖T49已完成；T01–T20/T49共21主Task完成、其他46未开始。本批到T20停止，不启动T21。D02/D06产品政策及开发告知草案已确认，正式处理责任/告知及法律适用性仍为上线门槛。[实施契约](privacy.md)。T15/T19幂等依赖T49单列，不绕过依赖；每Task验收、文档同步和提交推送后才进入下一已授权Task。以下旧阶段停止记录保留原意。

2026-10-03新授权执行T07，已完成本地验收；T01–T07已完成，其他60个主Task未开始。只实现对象授权基础，未开放后续业务；契约和本轮检查见[T07验收](acceptance/T07_object_authorization.md)。旧阶段记录保留；文档同步后按持续授权保存源码并停止。

2026-10-02新授权执行T06；2026-10-03验收完成：T01–T06已完成，其他61个主Task未开始。具体契约和实际检查见[T06验收](acceptance/T06_session_csrf.md)。只完成本Task后按持续授权保存源码并停止；下方阶段说明保留历史。

2026-10-02新授权先明确D04再执行T04；用户选择自托管Keycloak。T01–T04已完成，其他63个主Task未开始。本轮不实施T05或部署，验收和文档同步后按持续授权保存源码并停止。以下阶段说明为历史。

2026-10-01新授权执行T03，2026-10-02模式隔离验收完成；T01–T03已完成，其他64个主Task未开始。以下P04阶段说明为历史，不能撤销本次明确授权。本轮按持续规则保存源码后停止，不自动继续其他Task或部署。

规划日期：2026-10-01。P00–P04、T01、T02、T50A及E01已完成。P04私有GitHub仓库及成功Task提交推送规则已验收，本轮停止，其他65个主开发Task未开始；不自动开发T03/T49/T11/T13。T50后台仍遵守原依赖，M0保留。任务ID稳定，实施顺序按依赖；基础T49排列于T02之后，但还需留存决策及正式身份上下文。

## 使用方法与完成定义

每次只实施一个用户明确选定的 Task。本轮明确批次授权允许在上一个独立验收和源码保存后进入下一个，不能同时开发多个Task。先读 README、requirements、architecture、本文件、[CHANGELOG](CHANGELOG.md)、[DECISIONS](DECISIONS.md)，再核对依赖、相关模块文档、代码和 Git 改动，理解现状后实现验收所需的最小修改。文件路径是业务实现范围；每项仍必须同步 CHANGELOG、本文件与受影响文档。目录尚不存在时仅在对应 Task 中创建。发现无关问题记到本文件的待办记录，不顺带重构。

本表 `app/...` 是 `services/api/app/...` 的简写，`views/...` 是 `apps/web/src/views/...` 的简写；其余从仓库根目录解析。拟建目录见 README，不提前创建空实现。

每个 Task 预期是一项集中能力；若实现前发现超出一次会话，应先拆成子 Task，并保留原目标与验收，不以缩减质量交付。外部决策、供应商、领域审核或真实运行环境未齐时标明 blocked；不能靠默认猜测通过。

本批用户‘不用测试’优先：后续源码任务记录未执行及未验证事项，不将源码完成记为运行通过；依赖真实演练/领域审核/明确政策的任务仍不能猜测完成。状态只使用 `未开始`、`[~] 进行中`、`已完成`、`[!] 阻塞`。选定 Task 开始时标进行中，遇阻记录原因/解除条件；所有验收条件满足才完成，必需检查未执行不能标完成。未选定任务保留未开始，待决依赖在卡内说明，不因此自动启动。

完成报告严格按 Task / Summary / Files Changed / Documentation / Tests / Known Issues / Next Step 排列。核对本文件与 CHANGELOG 的 Task ID、状态、变更文件、测试结果一致后，再按用户持续授权提交/推送当前Task已审查改动、核对远程SHA并报告；重要技术决定另写 DECISIONS。推荐不代表自动开始。涉及数据库迁移、正式事实和部署的变更需可恢复；Git上传不授权业务部署/真实事实发布。

默认测试离线、不调用商业 API。OIDC、模型使用固定 mock；PostgreSQL 集成用独立临时库/schema，测试不得访问生产资料。live smoke 需另行明确启用；真实招生领域核验由有责任人的人工完成。

## 当前真实资料子Task

### BATCH-ZJ-2026-CUTOFF-01 · 浙江2026普通类分数线本地闭环

- **状态**：已完成
- **目标**：官方来源核验→真实数据独立入库→本地页面查询，缺失不造。
- **涉及文件**：独立reference_cutoffs模块/profile、local_reference factory、data/research批次manifest与复核收据、reference客户端/统计renderer、受影响治理/API/DB文档。
- **实现内容**：3条普通类省级线、原文字节/版本/hash、用户确认人工记录、显式批准/撤回/幂等、SELECT-only读与来源展示。
- **验收条件**：线种/来源/年省准确，缺字段null，未审/撤回不读，不混DEMO或改资格；真实PG与页面闭环可查。
- **测试方式**：只本批必要迁移/导入/HTTP/页面验证；其他全回归/Lint/Build未恢复；记录实际结果。
- **依赖**：T50/T52/T59/T63最小源码；用户已选浙江并确认3条本地参考数据，非公众发布许可。
- **实施前冻结**：[批次契约](acceptance/data_batches/BATCH_ZJ_2026_CUTOFF_01.md)。完成本批后停止，不采其他类型或全国资料。

- **实际验收**：2026-10-13原文字节/3值/人工作用真实入库，8PG/HTTP+8Edge通过；其他全回归/TypeCheck/Build未执行。原M0仍运行，闭环仅本地参考，完成本批停止。

## 本地环境维护

### E02 · 实际启动M0合成演示并验证核心流程

- **状态**：已完成
- **目标**：实际启动并通过真实浏览器确认M0主链；保持真实处理关闭。
- **涉及文件**：新docs/demo_startup_20261013.md及AGENTS/README/tasks/CHANGELOG同步；运行数据/日志/秘密仅.cache，不提交。
- **实现内容**：独立本地PG迁移/DEMO seed、loopback API/Vite启动、8项核心浏览器检查。
- **验收条件**：健康ready、四项目/确认画像/资格/证据/草案与两用户边界实际可查；用户文件不覆盖。
- **测试方式**：复用既有browser_smoke脚本的实际Edge流程；只授权本次核心检查，不执行全回归/Build。
- **依赖**：M0源码与本机既有运行时；用户2026-10-13明确启动验证授权。


- **实际结果**：2026-10-13：本机PG16.15/0001_m0与DEMO seed、API ready、网页200及8项真实Edge核心检查通过；page_errors=[]。只恢复本次有限检查，其他回归/Build仍未执行。见[报告](demo_startup_20261013.md)。

### E01 · Docker Desktop 启动修复

- **状态**：已完成
- **目标**：按用户新请求恢复本机 Docker Linux 引擎；保留项目文件及可找到的旧数据，不继续业务开发。
- **涉及文件**：本文件、`docs/CHANGELOG.md`、新增 `docs/acceptance/E01_docker_repair.md`；本机 Docker/WSL 仅在确认原因及保全后作必要修复。备份与诊断暂存 `.cache/e01-docker-20261001-105443/`，不纳入版本库。
- **实现内容**：检查版本、进程、服务、WSL 注册/磁盘和日志，有限查找备份并保全配置/注册/现存引擎盘；经明确同意只注销路径核对且仍为空的docker-desktop-data，保留原all-users模式升级至4.93.0，关闭失效Ubuntu的自动集成，建立新Docker数据环境并执行实际烟测。不注销Ubuntu，不重置项目或自动提交。
- **验收条件**：Docker Server 可连接、`docker info` 成功；实际运行一个隔离测试容器并清理本次创建的容器；原始规格及范围外项目文件不变；如需重建数据环境须先取得明确同意；记录旧数据限制与全部实际命令。
- **测试方式**：Docker/WSL 实际状态检查、容器烟测、项目哈希与原文保护检查。应用 Unit/Integration/Lint/Type Check/Build 不执行，因不改应用代码。
- **依赖**：用户“帮我修复我的docker”，随后明确同意“允许升级并重建空 Docker 环境”。有限查找未找到原数据盘，配置/注册/现存引擎盘已保全；此同意只覆盖 Docker，不覆盖 Ubuntu。
- **验收记录**：2026-10-01：官方固定安装包SHA256/Authenticode通过、安装退出0；`docker version --format '{{json .}}'`与`docker info --format '{{json .}}'`均退出0，Client/Server29.8.1、Linux引擎可用；隔离`docker run --rm --name study-e01-smoke-20261001 --network none --label study.task=E01 hello-world:latest`退出0，实际Hello from Docker，镜像拉取为联网准备；`docker ps -a`/`docker volume ls`为空、`docker compose version --short`退出0（5.5.1），WSL docker-desktop运行、Ubuntu停止/登记原值不变。范围校验退出0：仅2旧文档改+1验收新增、83范围外文件及历史记录未变、18本地链接；原文保护退出0。最初下载未完成、停止后退出1，改系统curl通过；后验收辅助代码首次语法错误、其次因新settings字段大小写误判失败，修正后最终退出0，并非引擎再次失效。应用Unit/Integration/Lint/Type Check/Build、项目Compose数据库/PG基线/重启后启动/公众部署未执行，未改应用且超出本次烟测；Docker保持运行。旧Docker数据未恢复，Ubuntu缺盘未修，详见[独立记录](acceptance/E01_docker_repair.md)。

## 文档治理任务

| Task ID | 名称 | 状态 | 验收记录 |
| --- | --- | --- | --- |
| P00 | 项目需求与技术规划 | 已完成 | 本文末尾 2026-10-01 历史记录；不代表公众功能完成 |
| P01 | 开发规则与记录同步 | 已完成 | [CHANGELOG](CHANGELOG.md) 的 P01 实际检查记录 |
| P02 | 全国真实资料策略与官方研究样本 | 已完成 | 本卡及CHANGELOG的实际文档/样本/保护检查；不代表全国已采齐 |
| P03 | 2026年全国高校资料范围确认 | 已完成 | 本卡及CHANGELOG的本轮文档/保护检查；不代表采集完成 |
| P04 | GitHub仓库与验收后提交推送规则 | 已完成 | [实施与验收](acceptance/P04_git_repository.md)；独立治理任务，不开发T03 |

### P04 · GitHub仓库与验收后提交推送规则

- **状态**：已完成
- **目标**：按用户授权创建私有GitHub仓库并上传当前项目，后续每个Task成功验收后提交和推送。
- **涉及文件**：`AGENTS.md`、`README.md`、`.gitignore`、新增`.gitattributes`、本文件、`docs/CHANGELOG.md`、`docs/DECISIONS.md`、新增`docs/acceptance/P04_git_repository.md`；只作必要本仓库Git分支/remote设置，不改应用/迁移/依赖/原规格/历史验收。
- **实现内容**：使用已登录chanbilly-lab创建私有study-admissions-agent，保留现有Git目录，建立首个基线提交；审查明确清单，排除秘密/私有运行资料；固定原规格字节和生成契约LF；记录每Task验收/文档同步后限定暂存、提交和普通推送规则，保留用户无关改动。
- **验收条件**：远程确为目标私有仓库且HEAD与本地一致；可追溯首个提交，范围外/原规格不变；环境/缓存/私钥/数据库资料未被纳入；日志和任务状态同步；不把Git上传当服务部署或招生事实发布。
- **测试方式**：只读Git/登录/可见性/remote ref核对、清单/哈希/历史/文档与忽略规则检查、暂存blob字节验证、原文及契约检查。应用测试/数据库/浏览器/部署本轮不执行：只改仓库治理，历史T02结果不计本次通过。
- **依赖**：用户“在git上面创建仓库，每轮成功完成任务后进行上传”，并明确确认当前账号下私有study-admissions-agent；Git/gh可用且已登录。既有项目无commit/remote；只对当前仓库设safe.directory，不改全局安全/身份配置。
- **验收记录**：2026-10-01：99文件基线留存，先列范围/检查计划，gh repo create --private及repo view退出0，目标chanbilly-lab/study-admissions-agent确为私有/main。Git原未提交master仅改名main，origin HTTPS不含token；显式101路径暂存、空索引/候选秘密形态/22私有路径/原文和生成blob检查通过。首个commit为819e5cb3e1640249b6d0ddb8155f5f825ee567b8（101文件），正常push -u origin main退出0；ls-remote SHA相同，远程tree101 blob/truncated=false，工作区干净。P04辅助--prepare/--stage/--stage --final、原文保护、M0契约和v2生成--check退出0；6旧改+2新增、93范围外原哈希与全部旧Task/日志/ADR保留，6文档86本地链接，完成记录按规则另提交推送并最终核对HEAD。初git log/repo view退出1分别为无commit/仓库不存在；暂存有原core.autocrlf换行warning，关键blob字节验证通过、未改全局配置，无创建/推送失败。应用Unit/Integration/Lint/Type Check/Build、PostgreSQL/浏览器/部署本轮未执行，因只改仓库治理，不引用T02为本次通过；不开发T03，详细命令见独立验收。

### P03 · 2026年全国高校资料范围确认

- **状态**：已完成
- **目标**：将用户已确认的2026年和大陆及港澳台全国高校范围落入规划，分开资料时间与个性化适配范围。
- **涉及文件**：`AGENTS.md`、`README.md`、`docs/requirements.md`、`docs/data_strategy.md`、`docs/tasks.md`、`docs/CHANGELOG.md`、`docs/DECISIONS.md`。不改代码、配置、数据库/API字段、原研究样本或历史记录。
- **实现内容**：D03/D08标明已确定部分和剩余事项；2026招生/考试、2026适用入学届、就业真实毕业届及港澳台原始学年分开；新增ADR-010，保留P02研究和M0浙江/2027。
- **验收条件**：七文档当前范围一致；不将2024/25/2027研究重标2026，不将高校所在地误作生源省份；港澳台体系独立，不造普通高考省线；67个开发任务字段/状态、既有记录及范围外文件保持；日志/任务同步。
- **测试方式**：离线UTF-8/本地链接、字段/状态/依赖图、当前范围/历史记录对照、哈希检查；原文保护脚本、只读Git与文档交叉审查。应用检查不执行，说明原因。
- **依赖**：P02；用户确认资料年度2026、全国高校含大陆及港澳台且体系分别建档。首版全量门槛、具体批次/审核/使用权及投入仍待决。
- **验收记录**：2026-10-01：`.\.venv\Scripts\python.exe -X utf8 .cache/p03_validate_20261001.py` 最终退出0：10份UTF-8文档、68个本地链接、67个未开始任务/402项原业务字段、249条无环依赖边、四条日志40项字段、10条ADR70项字段、2026大陆及港澳台范围和时间语义检查通过；P00–P02任务/日志及ADR-001–009历史内容保留，研究JSON哈希不变。仅7份旧文档改变，无新增纳入检查清单文件，范围外73文件哈希不变。首次校验退出1因文字关键词过窄（要求“真实毕业届”，文档用graduation_cohort字段），改为对应字段检查后通过。`.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py` 退出0，两份原始输入未变；`git -c safe.directory=D:/Projects/study -c core.quotepath=false status --short` 退出0，文件仍未跟踪，未提交。只读交叉审查无阻断问题。Unit Tests、Integration Tests、Lint、Type Check、Build、PostgreSQL实库、浏览器/部署和联网核验未执行：本轮只同步既有规划和用户确认，不改运行代码/配置/依赖/数据，不引用历史应用结果作为本次通过。

### P02 · 全国真实资料策略与官方研究样本

- **状态**：已完成
- **目标**：落实全国分数线、院校录取统计、学院/专业培养方案与实际毕业结果的需求，补充数据并明确来源、口径与分批验收。
- **涉及文件**：`AGENTS.md`、`README.md`、`docs/requirements.md`、`docs/architecture.md`、`docs/database.md`、`docs/api.md`、`docs/tasks.md`、`docs/CHANGELOG.md`、`docs/DECISIONS.md`；新增 `docs/data_strategy.md`、`data/research/official_samples.json`。不改应用、配置、依赖、迁移、DEMO 夹具或原始规格。
- **实现内容**：有界官方来源研究；全国资料层与单省个性化范围分开；类型化数据契约、覆盖/缺失/审核和历史可比性；真实研究样本隔离；新增 T50–T67 任务与 ADR-009。
- **验收条件**：样本逐项有官方 URL、年份/人群/单位/范围、研究状态和缺失原因，不填造数字；不把投档线/落实率/学科薪资误标；新增任务六项业务字段及状态/依赖完整；原开发任务和历史记录保留；原始与范围外文件哈希不变；日志状态同步。全国完整覆盖不属于本 Task 验收。
- **测试方式**：离线 UTF-8/JSON、文档链接、字段/状态/依赖图、口径与来源引用检查、哈希范围验证；原文保护脚本与只读 Git；只读交叉审查。官方联网研究单列，不属于离线应用测试。应用检查不执行并说明原因。
- **依赖**：P00/P01；用户本轮真实数据扩展要求。全国覆盖上线优先级按 D08 待定，本轮按分批资料建设规划，不扩大资格适配器。
- **验收记录**：2026-10-01：`.\.venv\Scripts\python.exe -X utf8 .cache/p02_validate_20261001.py` 最终退出0：10份UTF-8文档、64个本地链接、67个Task/402项业务字段/67个未开始状态、249条无环依赖边；原49项Task的294项业务字段和P00/P01历史记录内容保留；三条日志30项字段、9条ADR63项字段；研究14来源/14观察/34地区登记，正式审核/发布数均0；仅9份旧文档改变、2份新增，范围外纳入检查的69文件哈希不变。初次校验退出1：尾部空白被误判历史内容改变，调整为内容对照；随后退出1：新任务依赖栏把后续批次验收写成前置形成循环，已移出依赖；修正及终审调整后重跑通过。`.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py` 退出0，两份原始输入未变；`git -c safe.directory=D:/Projects/study -c core.quotepath=false status --short` 退出0，文件仍未跟踪，无提交。只读交叉审查后的课程原名、来源页面代码/统计人群、通胀依据、四态比较与公开访客契约均已同步。官方联网研究单列，部分正文/复取失败已记录，不是离线应用测试。Unit Tests、Integration Tests、Lint、Type Check、Build、PostgreSQL实库、浏览器和部署检查未执行：仅修改规划/研究记录，未改变运行代码/迁移/依赖；不使用历史测试作为本次通过。

### P01 · 开发规则与记录同步

- **状态**：已完成
- **目标**：将用户提供的 AI Development Rules 落入项目，提供可追溯的修改/决策/任务状态。
- **涉及文件**：`AGENTS.md`、`README.md`、`docs/tasks.md`、`docs/CHANGELOG.md`、`docs/DECISIONS.md`。不改应用、配置、依赖或原始规格。
- **实现内容**：六份必读文档、范围/依赖/同步规则、四种状态、七标题报告；建立 CHANGELOG 完整字段与 ADR 字段；现有 49 个开发任务逐项未开始，规划与代码状态分开。
- **验收条件**：用户八类规则完整覆盖；两份新文档可读且入口链接有效；T01–T49 ID/业务内容/依赖保留；修改限定五份文档；记录与状态一致；原始规格及应用文件哈希不变。全部检查后才完成。
- **测试方式**：离线内联 Python 校验 UTF-8、链接、字段、状态、依赖图、前后文件哈希；运行 `scripts/verify_originals.py`，只读 Git 状态及交叉审查。纯文档改动，Unit/Integration/Lint/Type Check/Build/PG/浏览器不执行并说明原因。
- **依赖**：P00 已完成；用户本轮治理规则。没有新依赖或外部服务。
- **验收记录**：2026-10-01 文档交叉审查通过；PowerShell 内联 Python（`.\.venv\Scripts\python.exe -X utf8 -`）退出0：9份 UTF-8 非空文档、51个本地链接、49个开发 Task/294项业务字段/49个未开始状态、143条无环依赖边、两条 CHANGELOG 的20项必填字段、8条 ADR 的56项必填字段；六文档必读/七标题/日志状态检查通过。前后逐字段对照确认294项业务字段和P00历史验收记录未变；文件哈希仅3份旧文档修改、2份新文档，范围外73文件未变。`.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py` 退出0，两份原文未变；只读 Git 状态退出0，文件仍未跟踪，未自动提交。应用 Unit/Integration/Lint/Type Check/Build、PG、浏览器与部署均未执行，因只修改文档。结果另见 CHANGELOG 的P01条目，不改写P00历史数字。

## 路线与依赖

| 阶段 | Task | 产出 |
| --- | --- | --- |
| 基础与准入 | T01–T10、T49 | 实库基线、/v2、持久幂等、模式隔离、正式认证/授权、隐私准入、审计 |
| 真实资料治理 | T11–T22 | 招生机会/日期、来源/存储/证据、人工导入审核发布、公共目录和管理页面 |
| 学生与资格 | T23–T29 | 不可变画像、类型化规则与独立适配器、可重放四态、比较证据页面 |
| 计划闭环 | T30–T36 | 草案、容量、确认/进度、修订、发布影响和持久通知 |
| 模型与资料权利 | T37–T41 | 条件启用的问答与模型边界、导出/删除、隐私操作页面 |
| 公众运行与发布 | T42–T48 | 部署配置、CI、恢复、监控、限流、独立验收、发布判定 |
| 全国参考资料扩展 | T50–T67 | 2026年大陆及港澳台高校、体系分别建档；覆盖/代码、分数/培养/毕业结果、分族API/页面、可选连接器和单批验收；D08剩余发布门槛待定 |

T37–T39 为条件启用：若首个公开版本模型关闭，可延期，且必须关掉对应入口。其余上线所需安全、资料审核和运维任务不可因“只是 MVP”跳过。T09 在提供顾问协作或相关监护访问时必须完成；否则关闭协作入口。未成年准入决定仍必须完成 T08。

原 M1–M6 是能力主题，不是一次开发会话：M1→T11–T22；M2 的抓取延期，人工变更→T34–T36；M3→T25–T29；M4→T37–T39；M5→T30–T36；M6 的保障分散在 T01、T07–T10、T40–T48。不继续全网采集、录取概率或自动申请。

## 基础与准入

### T01 · PostgreSQL 基线验证

- **状态**：已完成
- **目标**：补齐 M0 尚未执行的实库检查，确认可作为演进基线。
- **涉及文件**：`tests/backend/test_persistence.py`、`docs/M0_TEST_REPORT.md`（只追加新日期）、`docs/acceptance/T01_postgresql.md`、`README.md`、`AGENTS.md`、本文件、CHANGELOG；旧迁移/夹具/业务代码未改。
- **实现内容**：检查 Git/原文；独立 PostgreSQL 环境执行迁移、夹具、重复导入、降级/升级与数据保留；记录环境问题。此次不改公众功能。
- **验收条件**：实际实库命令和结果可复现；错误无静默数据覆盖；若环境缺失明确未执行，不能宣称完成实库验收。
- **测试方式**：设置专用 `TEST_POSTGRES_URL` 后执行 `pytest -m postgres`，对空库运行 Alembic/seed；现有离线回归按改动范围重跑。
- **依赖**：可用的独立 PostgreSQL；不依赖未成年准入。
- **验收记录**：2026-10-01，新建loopback55432的PostgreSQL16.15专用空库m0_t01_test，4个随机schema均清理；`.\.venv\Scripts\python.exe -m pytest tests/backend/test_persistence.py -m postgres -q`退出0：4 passed、4 deselected、1条已有警告；`.\.venv\Scripts\python.exe -m pytest -m 'not postgres' -q`退出0：96 passed、4 deselected、1条已有警告。真实CLI upgrade/current到0001_m0、seed2/7/4/9及重seed0均退出0；重复迁移/seed保留完整私有payload/owner，双用户隔离、flush后冲突回滚、空私有schema的base往返通过。PG已fast stop，status预期退出3，端口无监听。原文、Python语法、文件范围检查及Git读取退出0，冻结迁移/夹具/其余范围外74文件不变。Docker因WSL错误不可用，其Compose路径未执行；无新增应用依赖。未执行前端Unit/Type Check/Build/浏览器、Lint及部署：前端/业务未改且无已配置Lint入口。文档检查首轮因统计文字未匹配退出1，补上明确passed计数后退出0（12文档/77本地链接）；详细环境、实际失败与命令见[独立验收](acceptance/T01_postgresql.md)和[M0报告新增日期](M0_TEST_REPORT.md)。

### T02 · /v2 基础契约

- **状态**：已完成
- **目标**：为公开服务建立不破坏 M0 的 API 演进边界。
- **涉及文件**：新增`services/api/app/api/__init__.py`、`api/v2/`的factory/router/schemas/errors、`packages/contracts/v2/`、`scripts/generate_contracts.py`、`tests/backend/test_v2_api.py`、`tests/contracts/test_v2_generation.py`、`test_v2_http_contract.py`、`apps/web/tests/v2-contract-types.ts`、`docs/acceptance/T02_v2_contract.md`；修改`services/api/app/main.py`及README、AGENTS、docs/api、architecture、requirements、tasks、CHANGELOG、DECISIONS。精确22文件见独立验收。
- **实现内容**：统一 Envelope/错误/request_id、分页类型与 OpenAPI 生成流程；先接一个配置及空目录路由，不实现完整业务。
- **验收条件**：生成 TS 与 OpenAPI 一致；错误可定位；M0 /v1 契约仍可回归。
- **测试方式**：schema 漂移、分页边界、错误格式与 /v1 兼容测试；TS 类型检查。
- **依赖**：T01。
- **验收记录**：2026-10-01：先按[实施前契约与最终验收](acceptance/T02_v2_contract.md)列范围/用例，再实现独立基础子应用及离线生成。`.\.venv\Scripts\python.exe -m pytest -m 'not postgres' -q`最终退出0：306 passed、4 deselected、1条既有Starlette/AnyIO警告；新专项109项（HTTP46、生成35、实际JSON/TS/OpenAPI28），含standalone及mounted500安全/ID一致。`.\.venv\Scripts\python.exe -X utf8 scripts/verify_contract.py`和`... scripts/generate_contracts.py --check`均退出0；`.\scripts\web.ps1 -Action test/typecheck/build`三条分别执行退出0，前端18 passed，vue-tsc及Vite通过；Python语法、原文保护、范围/文档/历史检查和Git读取退出0。仅9旧文件改+13新增，77原文件哈希不变；M0主OpenAPI规范化内容不变，main只import/mount，其他Task/旧日志及ADR保留。验收辅助首次因Settings字段名错退出1，修正后因schema文本换行比较和engine属性写错再次退出1，辅助修正后通过，应用测试无失败。PostgreSQL4项本轮排除/未执行（无数据库/迁移变化，不引用T01为本次通过）；Lint/Python静态类型无已配置入口，浏览器/监听服务/生产部署与真实数据检查未执行，范围外。TS运行时约束局限已说明；无新依赖/迁移/数据/页面改动，不继续其他Task。

### T49 · 持久幂等基础

- **状态**：已完成
- **目标**：为后续创建、导入、发布和确认操作提供并发安全的幂等边界。
- **涉及文件**：`app/idempotency/`、`app/api/v2/idempotency_canonical.py`、独立幂等profile/迁移、`tests/unit/idempotency/`、`tests/integration/idempotency/`、`docs/api.md`。
- **实现内容**：actor＋operation＋key 唯一约束、规范化请求 hash、处理中/完成状态、资源引用与到期策略；业务事务和记录一致提交，不实现通知 worker。
- **验收条件**：同请求重放同一资源；异内容同 key 为409；跨用户不共用响应；重放前重验当前身份、角色/grant、用途准入及删除状态，不用旧缓存绕过撤权；并发/崩溃不重复业务写入或永久卡住。
- **测试方式**：专用 PostgreSQL 的双会话竞争、回滚/重试、不同 owner/key/请求与过期边界、撤权/撤回后重放拒绝测试；离线假主体与授权策略桩。
- **依赖**：T01–T02；持久期限策略由 D06 确认，正式路由使用 T05 的身份上下文。

- **实施前记录**：2026-10-03：T14已上传207f7ea，T49独立依赖授权；分支codex/t49-persistent-idempotency，297 tracked/索引与工作区干净。已读必读/模块文档、原规格与当前授权/隐私/审计/存储，先冻结[幂等契约](idempotency.md)。正式TTL问询待答，禁用默认与合成24h配置不代表正式政策。首次基线脚本未关Git quotepath退出1，修为当前命令core.quotepath=false后成功，无文件覆盖。

- **验收记录**：2026-10-03：48纯/19PG、相关450、契约模式333、前端170/Type Check/双Build及原文/生成/范围通过，首专项无失败。实际store唯一竞争与service账户锁分列，deferred完成约束及真实COMMIT失败回滚、final audit等候过期、当前撤权重放拒绝。24路径（9旧/15新），旧heads/HTTP/依赖不变；正式TTL与物理摘要清理仍未验收、默认真实路径关闭。见[T49验收](acceptance/T49_persistent_idempotency.md)，下一已授权T15。

### T03 · 演示/生产模式隔离

- **状态**：已完成
- **目标**：阻止 DEMO 凭据、事实和 mock 答案进入公开真实服务。
- **涉及文件**：`services/api/app/settings.py`、`app/api/`、`app/catalog/`、`config/`、`tests/security/`。
- **实现内容**：分离 data_mode/model_mode；生产仅挂 /v2、禁演示凭据/夹具；定义真实库查询角色与配置校验。
- **验收条件**：错误配置启动失败；verified+disabled 可用确定性核心；production 不可访问 /v1。
- **测试方式**：部署配置矩阵、DEMO 数据注入拒绝、无模型密钥与接口挂载测试。
- **依赖**：T02。
- **本次范围**：2026-10-01用户明确授权；确定性核心在本Task指基础配置/空目录无密钥读取，真实资格/计划仍依赖后续任务。query_role为应用策略，PostgreSQL角色/GRANT/RLS未创建/验收，无迁移/夹具变化。实施前契约、29路径清单及测试见[独立计划与验收](acceptance/T03_mode_isolation.md)。不部署、不自动继续。
- **验收记录**：2026-10-02，独立production factory仅/v2，错误模式/DEMO DSN/别名冲突/绕过构造启动拒绝，生产v1所有方法404、DEMO在v2所有路径401，污染或无真实发布依据的非空目录整体503；独立进程无M0/DB/seed/model导入、无密钥且不连接库。`python -m pytest -m 'not postgres' -q`475 passed/4 deselected/1既有warning，web.ps1 test18/typecheck/build退出0；generation --check、M0 contract、原文、compileall退出0，范围/历史/M0 wire检查通过。初契约专项3 failed/88 passed因旧DEMO_MODE alias显式None未覆盖，修复后91 passed；误引用不存在测试文件退出4、无测试运行，纠正后M066 passed/4排除；最终安全+v2专项187 passed。Lint/Python静态类型无配置入口未执行；PG/独立监听/浏览器/生产部署/真实数据未执行且本轮无相应变更。完整实际命令与限制见验收；CHANGELOG/ADR-014及影响文档同步，源码提交推送按持续规则且以Git/最终报告核对结果为准。

### T04 · 正式身份供应商边界

- **状态**：已完成
- **目标**：形成可替换、可本地测试的标准身份接口。
- **涉及文件**：`services/api/app/auth/{__init__,schemas,provider}.py`、`config/identity/{README.md,offline.example.json,keycloak-boundary.example.json}`、`tests/unit/auth/`四文件、相关治理/身份/架构/需求/API/数据库文档；21路径详见验收。
- **实现内容**：冻结Keycloak固定issuer/client/端点与回调；精确主体元组、可替换Provider协议、纯授权描述与PKCE/nonce/state/时效绑定、固定合成离线实现。production禁offline，真实换码/JWT未实现则Unavailable；不接应用。
- **验收条件**：不接收客户端任意issuer/JWKS；精确issuer+subject唯一/重复夹具拒绝（DB约束留T05）；不自建密码或信客户端角色；冻结配置/运行时重验、安全错误、生产与模式隔离通过。
- **测试方式**：供应商替换、主体碰撞、错误配置和回调 allowlist 测试。
- **依赖**：T02；D04 供应商选型至少形成可实施配置。
- **本次范围**：2026-10-02用户选择自托管Keycloak，D04供应商路线/T04接口层部分确定；真实tenant/MFA/恢复仍待后续验收。实施前契约与范围见[T04记录](acceptance/T04_identity_provider.md)，不实施T05登录/会话/迁移或部署。
- **验收记录**：2026-10-02：身份专项131 passed；完整离线pytest606 passed、PG4 deselected、1条既有warning，均退出0。前端18项、TS typecheck、Vite build、7模块py_compile及M0/v2契约/原文保护退出0。21相关文件、98范围外文件/旧记录保护与文档状态同步核对；首次2项测试假设错误、URL/Unicode出口缺口及独立probe入口笔误已修正并复验，详见验收。Lint/Python静态类型无入口/工具，PG无持久化变化，真实Keycloak/JWT/会话/MFA/恢复/浏览器/部署均未执行，不能宣称全部检查通过。保存源码后停止，不启动其他Task。

### T05 · 登录与服务端会话

- **状态**：已完成
- **目标**：让学生通过正式身份创建安全会话。
- **涉及文件**：新增auth/{config,oidc,models,store,service,router}.py、api/identity.py、独立认证迁移、身份生成契约/配置、auth前端与专项/浏览器测试；修改必要main入口/生成器/依赖锁/行尾规则与治理文档，46精确路径见验收。
- **实现内容**：授权码回调、PKCE、签名/issuer/audience/nonce/过期验证、服务端会话、HttpOnly Secure Cookie。
- **验收条件**：伪造/过期/错误受众被拒；token 不放 localStorage；登录后更换会话标识。
- **测试方式**：离线 IdP 回调成功/失败矩阵、会话固定攻击测试与浏览器登录流程。
- **依赖**：T04。
- **本次范围**：2026-10-02用户授权，仅T05；实施前契约、增量范围和验收矩阵见[T05记录](acceptance/T05_login_session.md)。使用预登记启用账户，不自动注册；独立认证迁移链与显式身份入口保留M0/默认foundation。真实Keycloak、准入政策、注销/CSRF/管理员MFA及公众发布不在本Task验收中。
- **验收记录**：2026-10-02：最终`python -m pytest -q --tb=short`758 passed、1既有warning、退出0（含45 PG、其中41新auth/4旧M0；离线非PG713）。新身份专项128+契约20项全部通过；前端42 passed、TS、M0/auth两模式build退出0；最终浏览器8项、页面错误/外网请求0，19模块语法/契约check/原文/依赖兼容通过。首轮旧生成器3项兼容失败、Windows超长参数ID setup错误、PG测试输入CHECK定位错误及夹具CSP回调失败均修正；JWT耗时跨期、mounted缓存头与生产SQLite入口审查补强后复验。Lint/Python静态类型无入口/工具未执行；真实Keycloak、生产TLS、部署/MFA/恢复未执行。测试库与自有helper已停止，旧数据/迁移/历史保护；CHANGELOG/ADR-016及影响文档同步后按授权提交推送并停止，不启动T06，完整命令/限制见验收。

### T06 · 会话撤销与 CSRF

- **状态**：已完成
- **目标**：保护所有 Cookie 身份下的写操作。
- **涉及文件**：`app/auth/`、`apps/web/src/api/`、`tests/security/auth/`。
- **实现内容**：注销/撤销/到期、CSRF token 与 Origin 校验，管理员加强认证策略状态检查。
- **验收条件**：注销后私有请求失效；跨站写入拒绝；遗漏 CSRF 的新写路由有测试拦截。
- **测试方式**：过期/撤销、缺 token、错误 Origin、后台任务执行时会话/权限重验测试。
- **依赖**：T05；D04 的管理员策略。

- **本轮实施前记录**：2026-10-02，先核对149文件干净Git基线/规格/相关代码；契约、范围、D04默认关闭强度策略与测试矩阵见[实施与验收](acceptance/T06_session_csrf.md)。仅执行T06，后续Task不自动开始。

- **验收记录**：2026-10-02开始、2026-10-03完成。先列契约/范围/矩阵后实现，45路径见[T06](acceptance/T06_session_csrf.md)；新0002迁移保留旧链/旧session。全项目929 passed（137PG/792非PG），security/auth132 passed及最终真实factory无DDL断言1 passed，unit/auth165；前端62 passed、Type Check、默认M0/显式auth Build及新浏览器12项通过。24模块语法、两生成profile/原文/M0契约/依赖一致性与范围历史文档检查通过；初旧head失败/收集冲突/TS错误已修复验，真实命令与未执行项见验收。Lint/Python静态类型无入口未执行，真实Keycloak/管理员MFA/recovery/生产TLS/部署未执行。仅本地同步会话/显式权限接口，T07资源grant/队列未实现；默认管理员关闭。CHANGELOG及受影响文档同步，保存本Task后停止。

### T07 · 对象级授权基础

- **状态**：已完成
- **目标**：将 owner 与角色边界落实到所有私有对象。
- **涉及文件**：`app/auth/{authorization,dependencies,models,store,service,http_security}.py`、`app/api/identity.py`、新`auth_migrations/versions/0003_auth_t07.py`、`tests/integration/authorization/`、`tests/security/authorization/`，两旧head/table断言与相关文档。精确33路径见验收；不创建真实profiles或遮蔽M0 planning.py的包。
- **实现内容**：统一服务端 Principal、对象授权依赖，student/data_admin/运营权限矩阵；不建立 SaaS 多租户。
- **验收条件**：其他学生资源不可读写；数据管理员默认不能看画像；客户端 owner/role 不决定授权。
- **测试方式**：两用户对列表、对象、附件、导出和作业逐项越权测试；缓存键范围测试。
- **依赖**：T05–T06。

- **实施前记录**：2026-10-03核对T05–T06依赖与干净Git；对象/角色/事务/缓存契约及scope与矩阵见[T07实施验收](acceptance/T07_object_authorization.md)。真实业务仍关闭，仅T07，不自动启动T08/T09。

- **验收记录**：2026-10-03：先列契约/修改范围/矩阵后实施并验收。最终全项目1123 passed（200PG/923非PG），新专项131集成/63真实PG，旧认证专项450；前端62、Type Check、M0/auth两Build、当前浏览器12项通过。21模块语法、两生成profile/M0契约/原文/35依赖、范围/历史/文档/暂存检查通过。初fixture/统一handler错误及慢cache2失败修后复验；PG实锁证明撤权、退出、过期与窗口重填不会沿用旧权限。新0003保留旧session/M0，真实业务/共享grant/worker/RLS未开启；Lint/Python静态类型无入口、真实Keycloak/MFA/recovery/TLS/部署未执行。CHANGELOG与受影响文档同步，按授权保存本Task后停止，不启动T08；实际命令/失败/限制见[T07](acceptance/T07_object_authorization.md)。

### T08 · 年龄、告知与准入流程

- **状态**：已完成
- **目标**：按已确认政策决定能否创建真实画像。
- **涉及文件**：`docs/requirements.md`、`app/privacy/consent.py`、隐私迁移、`apps/web/src/features/privacy/`、`tests/security/privacy/`。
- **实现内容**：先解决 D02/D06；保存必要的年龄区间/告知版本/同意与撤回状态，准入门槛服务端执行。
- **验收条件**：未知年龄或必要授权缺失不放行；不为年龄流程额外收集无必要证件；撤回立即影响后续处理。
- **测试方式**：成年/未成年/未知/撤回/政策变更矩阵；隐私内容人工复核记录。
- **依赖**：T07；未成年政策与处理责任确认。未定则 blocked，不能默认成人上线。

- **实施前记录**：2026-10-03用户新授权先D02再逐Task执行T08–T20；D02选18+本人确认，14–17监护独立确认但首版不提供核验，未成年私有关闭；D06产品上限已选，正式责任主体/适用性保留上线门槛。先列[契约、范围和验收](privacy.md)，人工产品告知草案已由用户在本会话确认，正式告知及责任仍为上线门槛；真实处理关闭。不把旧Task停止边界解释为拒绝本轮新授权。

- **验收记录**：2026-10-03按[契约](privacy.md)实施并验收，用户已实际确认开发产品草案；正式主体/告知/法律适用性仍为上线门槛。1274 Python全回归（277PG/997其他）、T08安全102、前端116、Type Check、M0/auth Build、浏览器9及契约75通过；初期确认/告知重确认/撤回依赖及测试/视觉失败已修复复验。新增0004与两表，默认真实处理/未成年私有关闭；无依赖/真实资料/部署。Lint与Python静态类型无入口未执行，真实IdP/TLS/法律/清理未执行。CHANGELOG及受影响文档同步，按持续授权保存源码后进入已授权T09；实际命令/51文件/限制见[T08](acceptance/T08_admission_privacy.md)。

### T09 · 顾问/监护访问授权（条件必须）

- **状态**：已完成
- **目标**：提供显式、字段受限、可到期撤回的协作。
- **涉及文件**：`app/auth/grants.py`、`app/privacy/`、授权迁移、`apps/web/src/features/sharing/`、`tests/security/grants/`。
- **实现内容**：学生授权指定顾问及字段/期限；监护人同意与访问授权分别处理。
- **验收条件**：角色/监护同意不自动授予全部会话；撤回后列表、缓存与作业同步失去权限。
- **测试方式**：字段范围、到期/撤回、身份冒用及重放测试。
- **依赖**：T07–T08；首版不提供协作时关闭入口并记录延期。

- **验收记录**：2026-10-03：[契约](sharing.md)先冻结后实施。最终Python1483 passed（321PG/1162其他）、独立安全160、基础14、契约110；前端170、Type Check、demo/auth两Build、浏览器10通过。初期输入/fixture/harness失败及旧T08 milestone测试断言修复后复验；notice失败时UI仍可读授权历史并撤销/退出，正向功能关闭。增量0005四表、identity v2.t09；只合成metadata字段status/version及read/list，真实业务关闭。无新依赖、旧迁移/原文/历史验收保留。Lint/Python静态类型无入口、真实IdP/生产TLS/法律/GRANT/RLS/部署未执行；CHANGELOG及受影响文档同步，持续授权提交推送后进入T10。实际命令与失败轨迹见[T09验收](acceptance/T09_explicit_sharing.md)。

### T10 · 审计与日志脱敏

- **状态**：已完成
- **目标**：保留关键操作责任线索，避免日志泄露原始学生资料。
- **涉及文件**：`app/audit/`、审计迁移、日志配置、`tests/security/audit/`。
- **实现内容**：记录主体/动作/对象版本/结果/request_id；过滤 token、原始成绩、附件与模型输入；按 D06 留存。
- **验收条件**：审核发布、授权、导出、删除及管理员动作可追踪；无原始敏感内容进入常规日志。
- **测试方式**：日志捕获与泄漏哨兵、审计权限和失败操作记录测试。
- **依赖**：T07；留存策略 D06。

- **实施前记录**：2026-10-03 T09已上传，核对当前Git/必读文档与T07+D06依赖；先冻结[契约、范围和验收](audit.md)。正式处理/部署关闭，仅T10。

## 真实资料治理

- **验收记录**：2026-10-03：[审计契约](audit.md)先冻结后实施，增量0006最小审计及封闭日志，无新依赖/HTTP wire变化。最终Python1662 passed（365PG/1297其他）、1既有warning；基础21、独立153、配置/纯日志133，前端170/Type Check/demo+auth Build通过。首整套19failed/1641passed定位旧迁移禁用logger，显式配置恢复并补回归；默认factory全局副作用移除，审计等待后期限/权限重验。其他66卡、206范围外tracked、旧迁移/历史/原文保留；详细命令/失败及未执行Lint/Python静态类型/browser/真实配置与部署见[T10验收](acceptance/T10_audit_redaction.md)。CHANGELOG及受影响文档同步后持续授权保存，再进入已授权T11；真实处理关闭。

### T11 · 招生机会关系模型

- **状态**：已完成
- **目标**：把 Institution/Program/年度招生机会从 M0 最小快照演进为可约束模型。
- **涉及文件**：`app/admissions_catalog/models.py`、`app/admissions_catalog/schemas.py`、新增 Alembic 迁移、`tests/integration/catalog/`。
- **实现内容**：Program、AdmissionOffering 范围、复合唯一键、事实数据集与机会版本；发布 FK/成员关系由 T19 建立；保留旧迁移。
- **验收条件**：同机构不同年度/校区/渠道不碰撞；DEMO 不进入真实数据集；迁移有恢复说明。
- **测试方式**：PostgreSQL 约束、跨年/省/身份记录和迁移保留测试。
- **依赖**：T01–T03。

- **实施前记录**：2026-10-03 T10已验收上传，Git干净；T01–T03依赖满足。[数据契约/范围/测试](catalog.md)先冻结；采用admissions_catalog避免遮蔽M0 catalog.py，独立catalog profile保留旧链，发布关系仍由T19建立。

- **验收记录**：2026-10-03：80严格schema单测、30 PostgreSQL专项通过，迁移保留M0/auth；1377回归选择通过（含14既有未标记PG），395 deselected/1既有warning。前端170/Type Check/demo+auth Build、原文/契约检查通过；最终配置专项及范围/文档命令见[T11验收](acceptance/T11_admissions_catalog.md)。纯选择首轮1363pass/14缺URL setup错误与PG helper首轮29pass/1fail均保留；mapper路由同engine边界已补强复验。真实导入/发布、Lint/Python静态类型、浏览器及正式环境未执行，原因见验收。

### T12 · 日期事件契约

- **状态**：已完成
- **目标**：准确表达日期类型、精度与时区。
- **涉及文件**：`app/admissions_catalog/dates.py`、`app/admissions_catalog/date_schemas.py`、日期迁移、`tests/unit/dates/`。
- **实现内容**：event_type/local_date/local_time/timezone/precision/证据；仅可唯一换算时生成 utc_instant。
- **验收条件**：不造 23:59；申请/平等审理/后补分离；夏令时歧义需处理。
- **测试方式**：日期-only、时区/DST、不同事件、未知期限及原文不一致用例。
- **依赖**：T11。

- **实施前记录**：2026-10-03：T11已保存dcbc0b3、Git/索引干净，依赖满足；继续独立admissions_catalog路径，原始catalog.py/旧迁移不改。日期契约先冻结，候选计算与未审核的官方UTC分开，公开wire/UI和真实来源关闭。

- **验收记录**：2026-10-03：日期纯43/PG11、相关274及契约/模式333通过；前端170/Type Check/demo+auth Build、原文/生成/范围/文档通过；catalog0002，官方UTC仍NULL/draft。首PG9/2夹具假设及无效目录命令未执行测试如实保留，实际命令与未执行项见[T12验收](acceptance/T12_date_events.md)。

### T13 · 来源登记与权限记录

- **状态**：已完成
- **目标**：使每条真实资料有使用与复查责任。
- **涉及文件**：`app/admin/sources/`、来源迁移、`docs/database.md`、`tests/integration/sources/`。
- **实现内容**：发布者/入口/用途/许可记录/负责人/复查周期；人工导入启用状态。URL 作为元数据，不自动抓取。
- **验收条件**：未完成权限审查不能正式发布；官方来源与抓取许可不混为一个状态。
- **测试方式**：角色限制、缺审查字段及非法来源协议校验。
- **依赖**：T07、T10–T11；D03 责任人。

- **实施前记录**：2026-10-03：T12已保存fb1554f，Git/索引干净；T07/T10/T11依赖满足。D03正式责任人待答，不猜负责人；合成接口先验收，真实功能缺配置关闭。[契约/范围/测试](sources.md)先冻结，不抓取或读取研究资料。

- **验收记录**：2026-10-03：新纯31/PG18通过（首PG7pass/11fail修复跨metadata FK与helper捕获后复验）；相关授权/审计/目录日期542与契约模式333通过，前端170/Type Check/demo+auth Build、原文/wire/生成及范围文档检查通过。仅T13内部来源metadata及同事务授权增量，旧0001/0002/M0/auth/HTTP保持，正式责任待答真实路径关闭；[实际命令和28路径](acceptance/T13_source_register.md)。Lint/Python静态类型无入口、browser无UI变化、全体PG/真实身份/法律/备份/部署未执行。验收同步后保存并进入已授权T14。

### T14 · 文件存储边界

- **状态**：已完成
- **目标**：隔离招生原文与私有学生文件。
- **涉及文件**：`app/storage/`、文件元数据迁移、`tests/security/storage/`。
- **实现内容**：Storage 接口、本地私有实现、命名空间/随机标识/上传大小与类型上限、隔离待解析文件。
- **验收条件**：无路径穿越；文件访问逐次鉴权；公开事实引用不泄露私有路径；正式适配器配置可替换。
- **测试方式**：越权、伪 MIME、超限、文件名/路径与授权过期测试。
- **依赖**：T07、T10；D06 类型/大小/留存策略。

- **实施前记录**：2026-10-03：T13上传9cad51c、Git/索引干净；已读必读文档/原规格文件存储段及相关权限/隐私/审计，T07/T10依赖满足。D06上限已确认，正式处理与公开附件仍关闭；仅合成隔离文件验收。先冻结Storage契约、修改范围与测试，再编码。

- **验收记录**：2026-10-03：43 Unit通过/1文件symlink权限跳过；17 PG、相关531及契约模式333、前端170/Type Check/双Build、原文/wire/生成和范围检查通过。首次目录rename竞态失败后改GENERIC_READ锁并复验；删除completion真实COMMIT失败返回pending已修复且PG重验。31路径（14旧/17新），实际命令、首次结果与未执行见[T14验收](acceptance/T14_file_storage.md)。无HTTP/UI/依赖/旧迁移变化；POSIX、生产ACL/清理/备份与部署未验收，真实处理及来源TTL配置仍关闭。下一先单列T49，再进入T15。

### T15 · 人工结构化导入

- **状态**：已完成
- **目标**：从小批量文件产生可审核候选记录。
- **涉及文件**：`app/admin/imports/`、`app/ingestion/`、导入回执迁移、`tests/integration/imports/`。
- **实现内容**：首版有界同步 JSON/CSV 手工导入、schema 校验、导入幂等、持久回执与错误报告；不做 OCR 或网页采集。超过同步资源边界拒绝或等待 T36 的持久作业，不启动临时后台任务。
- **验收条件**：重复导入不重复写；坏行/坏数字不变已发布事实；失败不清空旧版本。
- **测试方式**：重复/部分错误/脚注缺失/字段注入/大小限制用例。
- **依赖**：T11–T14、T49；T16 可先使用测试桩。

- **实施前记录**：2026-10-03：T49已上传f51574d；T15独立分支codex/t15-manual-import，312 tracked/开始索引与工作区干净。已读必读/API/DB、原规格及catalog/date/source/storage/idempotency相关代码，依赖具备；先冻结[导入契约](imports.md)。T16仅unresolved候选，不假装证据已审核；正式数据仍关闭。

- **验收记录**：2026-10-03：46纯/19PG、相关145通过及1 symlink权限skip、333契约模式、170前端/Type Check/两Build、原文与生成检查通过。首PG17pass/2fail：固定领域错误被旧幂等包装、测试MFA边界误假定，修本次service/测试后19通过；只读复核修整批位置校验与同record多字段。24路径（9旧/15新），旧head/HTTP/依赖保留。见[T15验收](acceptance/T15_manual_import.md)，真实路径关闭；保存后进入已授权T16。

### T16 · 不可变文档与证据

- **状态**：已完成
- **目标**：构建实际可定位、可重放的资料版本。
- **涉及文件**：`app/evidence/`、文档/版本/证据迁移、`tests/integration/evidence/`。
- **实现内容**：原文哈希、片段、页/行/节定位、语言、项目/年/身份/路径适用范围；版本不可覆盖。
- **验收条件**：片段能定位；修改原文产生新版本；跨项目或年度证据不能支持规则。
- **测试方式**：哈希、定位、范围、失效和修改冲突测试；人工对原文抽查。
- **依赖**：T11、T13–T14。

- **实施前记录**：2026-10-03：T15上传3cc5357；327 tracked/索引工作区干净，单独codex/t16-immutable-evidence。必读、原规格与相关source/storage/catalog/import代码已读；先冻结[证据契约](evidence.md)，不改变旧head/HTTP/依赖。人工抽查待可审阅合成原文准备后请求，不能冒称已复核。

- **自动验收记录**：2026-10-03：最终33pure/19PG通过；相关143pass+1 Windows symlink权限skip、333契约模式、170前端/Type Check/双Build、原文与生成检查通过。前两PG轮各19通过但未加载最后守卫，最后70.44s覆盖冻结代码，不累加用例。26路径（10旧/16新），其他66卡不改。见[T16验收](acceptance/T16_evidence.md)。
- **历史阻塞原因与解除条件（已解除）**：本卡测试方式要求“人工对原文抽查”；实际原文及三个片段已备[抽查材料](acceptance/T16_manual_review.md)，2026-10-03已向用户问询，尚未收到对照确认。源码/自动检查不代替人工；收到一致确认或修正并重新验收后才能完成、提交推送并进入T17。T17–T20尚未启动，真实资料/部署门槛不解除。


- **恢复记录**：2026-10-03用户直接回复“确认，继续执行 T16”，确认前述合成A/B/C原文抽查与DEMO边界，解除人工待答阻塞；不等同真实招生审核或发布。恢复时重新读取必读/原规格及T16代码、核对HEAD/index和26路径现状；只本Task改动，无源码重构，专项复验中。先完成T16保存，再依既有批次授权逐个T17–T20。

- **完成记录**：2026-10-03用户已确认合成原文抽查；本次恢复专项52 passed68.10s exit0（33pure/19PG），源码/ini/原json在恢复hash核验中保持不变。文档/原字节/范围/状态同步检查后完成，普通提交推送并核远程SHA；真实业务门槛保持，接着单独开始已授权T17。

### T17 · 类型化候选事实

- **状态**：已完成
- **目标**：将导入内容转成可审核的事实与规则候选。
- **涉及文件**：`app/facts/`、`app/facts/schemas.py`、候选迁移、`tests/unit/facts/`。
- **实现内容**：分数/单位/费用/材料/日期/要求分类、缺失原因、draft/review_required/conflicted 状态。
- **验收条件**：典型 offer/最低门槛/历史统计不混；冲突保留；未经审核不可成为硬规则。
- **测试方式**：格式/单位/缺失状态/冲突和发布查询排除测试。
- **依赖**：T12、T15–T16。


- **实施前记录**：2026-10-03：T16上传d53a363；343 tracked/Git/index干净。已读必读/原规格、T12日期/T15导入/T16证据与相关代码；先冻结[事实契约](facts.md)。不把M0 catalog.py替换成包，不改变旧heads/HTTP/依赖；真实事实与规则发布关闭。

- **验收记录**：2026-10-03：35pure/25PG、160相关、333契约模式、170前端/Type Check/双Build及原文/生成检查通过；首PG23pass/2测试前提fail，修合法到期数据/worker锁探针后最后25 passed162.52s覆盖全部源码。23路径（9旧/14新）、旧heads/HTTP/依赖保持；T15任务外时效跟进已记录未改。见[T17验收](acceptance/T17_typed_facts.md)。文档同步/普通源码保存后单独开始已授权T18，真实审核/发布关闭。

### T18 · 人工审核决定

- **状态**：已完成
- **目标**：记录审核者、证据与每项关键字段的判断。
- **涉及文件**：`app/reviews/`、审核迁移、`tests/integration/reviews/`。
- **实现内容**：通过/退回/冲突处理、版本锁与职责限制；审核不直接覆盖历史发布记录。
- **验收条件**：无定位/范围/必要字段不能通过；并发审核冲突可见；操作有审计。
- **测试方式**：缺证据、角色越权、版本冲突、冲突未解等用例。
- **依赖**：T10、T17。

- **实施前记录**：2026-10-03：T17上传94daf36；357 tracked/Git/index干净，已读必读/原规格/API/DB和facts/evidence/audit/source相关代码。先冻结[审核契约](reviews.md)；原输入读取探针encoding拼写错误无修改，纠正后已完成读取。仅合成审核，旧facts/heads/HTTP不改，真实责任门槛保留。

- **验收记录**：2026-10-03：31纯/23PG（最后163.44s无skip/warning）、93相关、333契约模式、170前端/Type Check/双Build及生成/原文/8module内存编译通过；首PG21pass/2fail、第二22pass/1fail为本新fixture/404边界期待错误，最终复验通过。独立三表/profile、不可变决策与case CAS，合成模拟人类审核，不发布。Lint/Python静态类型无入口、browser/全项目PG/POSIX/真实人工审核/生产身份/清理备份/部署未执行；原因、23文件和失败轨迹见[T18验收](acceptance/T18_human_review.md)。CHANGELOG及受影响文档已同步，保存后单独执行已授权T19。

### T19 · 发布与撤回

- **状态**：已完成
- **目标**：以不可变 release 发布真实事实/规则。
- **涉及文件**：`app/reviews/releases.py`、release/ChangeEvent/outbox 基础迁移、`app/catalog/`、`app/changes/`、`app/jobs/models.py`、`tests/integration/releases/`。
- **实现内容**：审核完整性检查、发布事务、撤回/替代、适用周期与规则集版本；首次建立待处理 ChangeEvent/outbox 记录，与发布同事务持久化。此项不实现影响分析或通知消费者。
- **验收条件**：未审/冲突/DEMO 不得进入正式 release；失败不部分发布；旧版可追溯；发布与事件一起成功/回滚。
- **测试方式**：事务回滚、重复发布、跨数据集、撤回可见性与版本重放测试。
- **依赖**：T18、T49。

- **实施前记录**：2026-10-03：T18已PRIVATE上传b3cab25，371 tracked/开始干净，已读必读/原规格/API/DB及review/source/storage/idem相关实现。先冻结[release契约](releases.md)与测试：facts-only的ruleset_version=null，不实现T25规则。正向仅明确test_fixture，正式拒绝DEMO；T20未开始。

- **验收记录**：2026-10-03：24纯、22PG（最后289.46s无skip/warning）、89相关、333契约模式、170前端/Type Check/双Build和生成/原文/8module compile通过；首纯23/1、新PG18/4及选择项4pass/18deselect真实保留，前提修正后全验。五表/profile、固定成员/唯一head、T49同TX和事件/outbox原子、失效旧依据可撤回；formal拒DEMO，正向仅test_fixture，ruleset_version=null。Lint/Python静态类型无入口、browser/全项目PG/POSIX/正式真实发布/身份/权利/清理备份/部署未执行；详见[T19验收](acceptance/T19_atomic_releases.md)。CHANGELOG及受影响文档同步，保存后单独T20并停止。

### T20 · /v2 公共目录与证据读取

- **状态**：已完成
- **目标**：让访客安全查询已发布招生机会。
- **涉及文件**：`app/public_catalog/`、`app/api/public_catalog.py`、`app/api/v2/public_catalog.py`、`scripts/generate_contracts.py`、`packages/contracts/v2/public_catalog/`、纯/PG/契约/TS测试及受影响文档。
- **实现内容**：过滤/分页/覆盖信息；公开证据仅允许已发布且可公开的片段。
- **验收条件**：待审/私有/撤回记录不可公开；范围无记录明确缺口；不返回私有存储路径。
- **测试方式**：不同年/省/路径/身份、分页上限、撤回与公开附件权限测试。
- **依赖**：T02、T16、T19。

- **实施契约**：2026-10-03代码前冻结[公共目录](public_catalog.md)。显式只读API profile，不改既有foundation/identity/M0；无新迁移或依赖。仅合成test_fixture验证，真实上线门槛不解除。

- **验收记录**：2026-10-03最终45pure/23PG合计68 passed288.28s/1既有warning，无skip；46相关、357契约模式、170前端/Type Check/demo-auth Build、三profile生成/原文/12module compile通过。首PG20/3与纯两次44/1修正保留；不相加。27路径（11旧/16新），374范围外tracked与66任务卡保护；无旧迁移/依赖/入口改变。后台uvicorn烟测遭自动审批拒绝未执行，Lint/Python静态类型无入口及browser/全项目PG/正式事实/身份/法律/SQL权限/运维部署未执行。见[T20验收](acceptance/T20_public_catalog.md)。真实公开默认关闭，保存后停止。

### T21 · 来源与导入管理页面

- **状态**：已完成
- **目标**：让数据管理员登记来源并查看导入错误。
- **实施前冻结**：独立admin HTTP profile、当前强管理员探针、来源CAS与UTF8 JSON/CSV隔离上传及幂等导入；不抓取/下载/审核发布。T15首次HTTP暴露所需末端时效保护限一服务文件，旧迁移/其余profile冻结；见[契约](admin_workspace.md)。
- **涉及文件**：`apps/web/src/views/admin/`、`apps/web/src/features/admin/sources/`、`apps/web/src/features/admin/imports/`、前端对应测试。
- **实现内容**：最小来源表单、文件/结构化导入入口、状态/错误展示，复用 UI 与 API 层。
- **验收条件**：普通学生无法操作；错误不显示成功；来源 URL 不触发访问。
- **测试方式**：组件输入/失败状态、管理员端到端及学生访问拒绝。
- **依赖**：T13、T15、T20。
- **验收记录**：2026-10-03，9专项纯/7PG、65导入回归、368契约/模式、222前端、Type Check及demo/auth Build通过；实际Edge9项检查包含于1个PG用例，未重复相加。失败轮次、未执行项与37文件清单见[T21验收](acceptance/T21_admin_workspace.md)。默认真实处理关闭，无新增依赖/迁移；验收、文档与私有保存后按新授权进入T22。

### T22 · 审核与发布管理页面

- **状态**：已完成
- **实施前冻结**：[审核发布工作台](admin_review_workspace.md)；必要admin_review HTTP/准备入口/匿名公共预览与新生成profile，复用T16–T21服务，不以fixtureUUID或管理DTO冒充闭环，旧入口/产物/迁移冻结。
- **目标**：提供原文/候选字段并排审阅和发布入口。
- **涉及文件**：`apps/web/src/views/admin/`、`apps/web/src/features/admin/reviews/`、`apps/web/src/features/admin/releases/`、前端对应测试。
- **实现内容**：定位/范围/冲突提示、逐项审核、发布预检与撤回确认。
- **验收条件**：关键缺口可见；并发失败不覆盖；公开页面显示当前 release。
- **测试方式**：审核拒绝/冲突/发布失败/撤回端到端与权限测试。
- **依赖**：T18–T21。
- **验收记录**：2026-10-03，13专项纯/8PG、100审核发布回归、383契约/模式、279前端/Type Check/demo-auth Build通过；1PG用例内13项实际Edge检查。首完整前端277/1失败与mock类型失败已修复并保留记录。44路径、无迁移/依赖，真实处理与公开保持关闭；[实际命令与边界](acceptance/T22_admin_review_workspace.md)。文档及私有保存核对后进入T23。


## 学生与资格

### T23 · 真实画像与纵向版本

- **状态**：已完成
- **实施前冻结**：[画像版本](profiles.md)，独立两表/迁移与最小私有HTTP；首建T49、追加CAS，旧M0/服务/头/契约保留，无T24 UI。
- **目标**：支持用户确认后的安全画像更新。
- **涉及文件**：`app/profiles/`、画像/评估迁移、`tests/integration/profiles/`。
- **实现内容**：profile 根实体+不可变 version、必要字段、实得/预测、确认/同意绑定、乐观锁；所在地和课程/身份分别保存。
- **验收条件**：更新不覆盖旧版；客户不能改 owner；未覆盖的课程/路径明确 unsupported；不由地区推断资格。
- **测试方式**：两用户、并发更新、缺确认、未准入、单位/满分、课程范围用例。
- **依赖**：T07–T08、T11、T49。
- **验收记录**：2026-10-03，最终48pure/51实际PG、401权限用途与幂等回归、411契约模式、279前端及Type Check/demo-auth Build通过；28新生成专项、六profile/原文/旧M0检查通过。35路径（11旧/24新）、446其他tracked原字节保留，无依赖/旧服务修改。首collection4 errors与新ErrorEnvelope辅助16fail/32pass修正后最终51pass；原错误路径命令未执行测试如实记录。真实处理关闭，见[实际命令与边界](acceptance/T23_profile_versions.md)。文档同步及私有保存后进入T24。

### T24 · 画像编辑与确认页面

- **状态**：已完成
- **本轮验收**：69新专项、348完整前端/Type Check/demo-auth Build、99画像PG相关/411契约模式与六profile检查；1实际PG内12项Edge流程（2root/7version/并发CAS/延迟成功后退出）。前六浏览器失败如实保留，详情见[验收](acceptance/T24_profile_workspace.md)。真实处理关闭，文档及PRIVATE保存核对后才T25。
- **实施前冻结**：[画像工作台](profile_workspace.md)，只前端与实际浏览器验收；复用T23六操作，旧后端/迁移/契约/M0保持。
- **目标**：提供逐路线询问的真实用户表单。
- **涉及文件**：`apps/web/src/features/profiles/`、`views/ProfileView.vue`、对应测试。
- **实现内容**：复用 M0 转换逻辑；字段解释、缺失保持缺失、确认新版本、冲突处理、授权范围展示。
- **验收条件**：数字输入可保存；空值不变零；修改使旧结果失效；未知体系不套高考字段。
- **测试方式**：M0 数字回归迁移、组件表单/版本冲突和端到端确认流程。
- **依赖**：T23。

### T25 · 类型化规则与三值逻辑

- **状态**：已完成
- **本轮验收**：178新纯规则、539相关、348前端/Type Check/demo-auth Build与六profile/原文/M0检查通过；首145pass/3fail及中间轮如实保留。16路径/490其他tracked保护，详情见[验收](acceptance/T25_typed_rules.md)。纯解释器不代表已审规则或四态，PRIVATE保存核对后才T26。
- **实施前冻结**：[规则契约](rules.md)，纯AST/三值解释器，无HTTP/DB/UI/旧M0变化。
- **目标**：扩展审核后的声明式规则，保持可解释与缺失语义。
- **涉及文件**：`app/rules/expression.py`、`app/rules/evaluator.py`、`tests/unit/rules/`。
- **实现内容**：白名单 all/any/not/exists/eq/in/gte/lte/date_before/valid_at；类型/单位校验与 true/false/unknown。
- **验收条件**：按完整表达式归约，any 的一个失败分支不等于必需条件失败；unknown 不强制转 true/false；坏类型不能误放行/误淘汰；无 eval/exec。
- **测试方式**：完整三值真值表，含 any(true,false)、any(true,unknown)、all(false,unknown)、not(unknown)；嵌套/深度限制、坏输入、数值边界与缺失回归。
- **依赖**：T17、T23。

### T26 · 国内/英国范围适配器

- **状态**：已完成
- **本轮验收**：208新专项、722相关、348前端/Type Check/demo-auth Build与六profile/原文/M0检查；18路径/499其他tracked保护。详情见[验收](acceptance/T26_scope_adapters.md)。matched不是四态，全国真实规则仍关闭；PRIVATE保存核对后才T27。
- **实施前冻结**：[范围契约](scope_adapters.md)；31省输入配置/逐省框架＋英国具体项目，scope matched不等于资格；真实规则默认缺失，T19事实不编DSL。
- **目标**：按资格、身份、周期与阶段选择适用规则。
- **涉及文件**：`app/rules/adapters/`、`app/catalog/`、`tests/unit/adapters/`。
- **实现内容**：按ADR-034全部普通高考生源省份逐省配置与英国本科独立适配；国家/学段/课程/身份/省份/科类/渠道/年度/项目/阶段过滤；真实规则绑定尚未就绪时unknown。
- **验收条件**：其他年、省、DSE/联招等不复用高考规则；所在地不决定申请身份。
- **测试方式**：跨范围矩阵、科类/路径与申请/入学阶段回放。
- **依赖**：T11、T19、T25；D03 覆盖配置。

### T27 · 后补与期限资格

- **状态**：已完成
- **本轮验收**：248新专项、1006相关、348前端/Type Check/demo-auth Build及六profile/原文/M0检查；14路径/510其他tracked保持，详情见[验收](acceptance/T27_deferrals.md)。后补许可不是conditional；PRIVATE保存核对后才T28。
- **实施前冻结**：[后补契约](deferrals.md)，纯事项许可不是conditional；申请与补交期限分别核验、日期当天未知，真实政策关闭。
- **目标**：只有适用审核政策支持时才 conditional。
- **涉及文件**：`app/rules/deferral.py`、`app/rules/adapters/`、`tests/unit/deferrals/`。
- **实现内容**：后补事项、阶段、政策和期限证据、有效时间；日期-only 不补瞬时。
- **验收条件**：必要缺成绩无政策/无期限/错项目/过期/冲突为 unknown；申请截止和后补截止分别检查；按已审核参考日历判断期限，无法确定是否过期保持待核验，不默认用服务器日期或造 UTC 瞬时。
- **测试方式**：主/后补/日期证据不匹配、截止边界、仅日期缺时区、期限当天和服务器/来源跨日测试。
- **依赖**：T12、T16、T26。

### T28 · /v2 四态评估与重放

- **状态**：已完成
- **本轮验收**：[实际记录](acceptance/T28_assessments.md)，104纯四态、23新PG、63旧PG、284契约、764相关Python、348前端/Type Check/双Build及生成/原文/M0/范围检查；正式规则/真实处理关闭，无新依赖。
- **实施前冻结**：[评估契约](assessments.md)；完整四态可满足路径、实际同事务合成发布证明及历史/当前分开，真实规则关闭。
- **目标**：返回可审计、版本绑定的完整评估。
- **涉及文件**：`app/rules/service.py`、`app/rules/router.py`、评估迁移、`tests/integration/eligibility/`。
- **实现内容**：绑定画像/release/ruleset/阶段/评估时间，资格/竞争背景/偏好/数据质量四维，规则原因与证据；服务端重新计算。
- **验收条件**：适用的完整必需表达式明确失败才 ineligible，不能因 any 未选分支失败淘汰；缺成绩无有效后补依据 unknown；旧结果可重放；无数据维度明确未知；无概率或客户端结论信任。
- **测试方式**：四态、版本重放、权限与模型断开下的资格 HTTP 测试。
- **依赖**：T23、T25–T27。

### T29 · 项目比较与证据工作台

- **状态**：已完成
- **实施前冻结**：[工作台契约](catalog_workspace.md)，仅前端/最小画像事件，无API/DB变更；实际合成PG/Edge验收，真实关闭。
- **目标**：将真实目录与四态结果整合成主工作流。
- **涉及文件**：`apps/web/src/features/catalog/`、`apps/web/src/features/eligibility/`、`apps/web/src/features/evidence/`、`apps/web/src/views/`、前端测试。
- **实现内容**：复用 M0 卡片和证据组件，加入分页/范围过滤/比较；引用项目、年度、定位、状态；历史/偏好维度无依据不算分。
- **验收条件**：不同身份或资料不会混结果；移动/键盘主流程可用；无证据原文 HTML 执行。
- **测试方式**：组件、真实 /v2 端到端、跨用户旧请求和缺期限场景。
- **依赖**：T20、T24、T28。
- **验收记录**：2026-10-04，最终474前端（126新/348旧）、529相关Python、两个真实PG用例（实际Edge154的13检查点包含于一个用例）及Type Check/demo-auth Build通过；七profile/原文/M0/JS语法/范围检查通过。32路径（10旧/22新），536其他tracked保护。首次测试夹具/类型问题、独立模式红测及全部未执行项见[T29验收](acceptance/T29_catalog_workspace.md)。Lint/Python静态类型无入口、真实身份/领域规则/法律/生产SQL权限/代理HTTPS/清理恢复/部署未执行；真实处理关闭。文档及PRIVATE保存后单独T30。

## 计划闭环

### T30 · 差距到草案任务

- **状态**：已完成
- **实施前冻结**：[草案契约](plan_drafts.md)，实际app/plans/避免遮蔽旧M0planning.py；只本Task，不排程/确认/HTTP/UI。
- **目标**：把确认目标与资格差距转成可审阅动作。
- **涉及文件**：`app/planning/drafts.py`、计划/任务迁移、`tests/unit/planning/`。
- **实现内容**：目标、准备/核验/学习类型、估时、验收标准、依赖、引用；共用任务去重。
- **验收条件**：unknown 优先核验；ineligible 不生成满足资格的申请断言；申请与后补分别保留期限依据。
- **测试方式**：四态任务金标准、共用任务、无期限与估时可修改测试。
- **依赖**：T12、T28。
- **验收记录**：2026-10-04，81专项pure、23 distinct真实PG（14owned/9独立；末端下界补丁后只复验相关节点，不累计重复）、641相关Python/4 deselected、474前端及Type Check/demo-auth Build通过；七profile/原文/M0/560受保护tracked保持。完整命令/失败/未执行/限额见[T30验收](acceptance/T30_plan_drafts.md)。26路径（8旧/18新）；旧API/迁移/M0/依赖/前端不变。512KiB极端合法组合可能503，未PG验证；Lint/Python静态入口及真实领域/身份/法律/SQL权限/生产恢复/部署未执行。文档及PRIVATE保存后单独T31。

### T31 · 工时容量与依赖排程

- **状态**：已完成
- **实施前冻结**：[容量契约](scheduling.md)，新app/plans/纯排程提案；不持久/确认，不把候选时间当官方期限。
- **目标**：形成不超确认时数的基础周计划。
- **涉及文件**：`app/plans/schedule_schemas.py`、`app/plans/scheduler.py`、`tests/unit/scheduling/`。
- **实现内容**：拓扑排序、可用时段、每周容量、内部目标和官方硬期限区分；冲突报告。
- **验收条件**：不超周工时；依赖环/期限冲突明确失败或返回方案选项；不压缩休息保证效果。
- **测试方式**：容量边界、依赖环、共享任务、日期精度/DST与排不下用例。
- **依赖**：T12、T30。
- **验收记录**：2026-10-04，100新增pure（8owned/29容量日期/63独立边界）、228相关旧pure（185计划与资格/43日期）、474前端及Type Check/demo-auth Build通过；七profile/两原文/M0/579保护tracked保持。15路径（7旧/8新），无DB/API/旧源码/迁移/依赖/前端变化。完整命令、真实失败与未执行项见[T31验收](acceptance/T31_scheduling.md)；官方精确硬期限正例、PG/HTTP/浏览器、无配置Lint/Python静态类型及真实处理/部署未执行。PRIVATE保存核对后才T32。

### T32 · 计划确认与任务进度

- **状态**：已完成
- **实施前冻结**：[确认与进度契约](plan_execution.md)，独立状态/不可变记录与plans profile，不更改T30 root或registry版本。
- **目标**：让学生显式确认草案并记录执行。
- **涉及文件**：`app/plan_execution/`、`app/api/plans.py`、execution独立迁移、plans生成契约、专项Unit/PG/HTTP测试。
- **实现内容**：确认状态机、expected_version、幂等键、任务完成记录；确认前复核相关发布版本。
- **验收条件**：旧版本/已撤回证据阻止静默确认；重复请求不重复完成；不触发外部申请动作。
- **测试方式**：确认/冲突/重复/越权/非法状态转移 HTTP 测试。
- **依赖**：T07、T30–T31。
- **验收记录**：2026-10-04，56新增pure（11domain/24wire/21contracts）、28 distinct真实PG（10owned/13独立/5HTTP；新时效guard后5独立/2HTTP相关复验不重复累计）、305完整契约及865相关旧Python、474前端/Type Check/demo-auth Build通过。33路径（11旧/22新），583其他tracked/66任务卡/旧十二迁移/七产物/原文/M0保护。首次确认过去容量409；确认后按原确认时间保留进度和历史，未知官方期限不升级。实际命令、真实失败与未执行项见[T32验收](acceptance/T32_plan_execution.md)。Lint/Python静态无入口；浏览器UI本Task未改、真实身份/事实/法律/SQL权限/部署/生产恢复未执行。PRIVATE保存核对后才T33。

### T33 · 计划与进度页面

- **状态**：已完成
- **实施前冻结**：[计划工作台](plan_workspace.md)，复用T32八操作，无API/DB变更；实际合成PG/Edge与私有迟到隔离验收。
- **目标**：让用户看见依赖、容量、来源和确认状态。
- **涉及文件**：`apps/web/src/features/plans/`、`views/PlanView.vue`、AuthView/CatalogView接缝、前端专项与真实PG/Edge测试。
- **实现内容**：草案编辑、冲突展示、确认、周计划、完成记录；无期限不补时间。
- **验收条件**：任务动作不越权；并发失败可理解；已完成任务与旧版本可见。
- **测试方式**：组件状态机、完整确认/完成端到端与键盘操作。
- **依赖**：T32。
- **验收记录**：2026-10-04：116新增前端专项（37owned/79独立）、完整590/37files、56相关Python、Type Check/demo-auth Build、1 distinct真实PG/Edge用例15检查点通过；原先实库browser初始化race失败已复现修复，重复仍计1节点。29路径（9旧/20新），607其他tracked/66卡/八生成profile/旧后端/迁移/依赖/原文/M0保护。可读局部截图人工核，390px/键盘/原SHA及UTC微秒/零里程碑本人声明；命令/所有失败/未执行见[T33验收](acceptance/T33_plan_workspace.md)。Lint/Python静态无入口；官方精确截止/真实身份资料/法律/SQL权限/HTTPS代理/部署未执行。PRIVATE保存核对后才T34。

### T34 · 发布变更影响

- **状态**：已完成
- **实施前冻结**：[发布影响契约](changes.md)；仅独立发布业务diff/评估计划needs_review sidecar与实际合成PG，不改旧事实/结果/进度/outbox/API/UI；
- **目标**：经审核发布变化后标记相关计划。
- **涉及文件**：`services/api/app/changes/`、`services/api/changes_migrations/`与ini、`tests/unit/changes/`、`tests/integration/changes/`、`docs/changes.md`及治理/需求/架构/数据库/验收文档。
- **实现内容**：比较业务字段与引用关系；相关评估/计划标 needs_review，保留前后版本和原因。
- **验收条件**：无关变化不替换计划；关键变化不被哈希噪声遗漏；撤回证据影响可追踪。
- **测试方式**：条件/日期/年度/撤回与非业务变化矩阵。
- **依赖**：T19、T28、T32。
- **验收记录**：2026-10-04，最终86纯专项/4.40s与16distinct PG通过（owned7/144.60s、安全9/152.71s；identity补强后added节点1/28.44s再次通过，不累计）；723相关Python/55.59s、590前端/37文件、Type Check、demo/auth Build、八生成profile与原文/M0核对通过；PG首8通过1失败后修复并完整9通过；完整实际命令/失败/未执行见[T34验收](acceptance/T34_changes.md)。25路径（8旧/17新）、628其他tracked/66卡/旧原文与迁移保护；文档与PRIVATE保存后才下一Task。

### T35 · 画像/规则变化后的修订草案

- **状态**：已完成
- **实施前冻结**：[明确修订契约](plan_revisions.md)；仅独立proposal/接受拒绝/有限旧历史与本人新draft替代关系，不改原确认完成，不自动credit/最终confirm；
- **目标**：以新版本建议修订，保留历史与执行记录。
- **涉及文件**：`services/api/app/plan_revisions/`、`app/api/revisions.py`、独立revisions迁移、`packages/contracts/v2/revisions/`、PlanView接缝及新revisions前端、Unit/PG/HTTP/Edge专项。
- **实现内容**：新成绩/证据触发草案、差异展示、用户确认替代关系、完成记录引用保留。
- **验收条件**：不静默覆盖确认计划；不将已完成任务重置；拒绝修订仍可看旧版。
- **测试方式**：成绩变化、期限变化、确认/拒绝/并发及完成保留端到端。
- **依赖**：T23、T33–T34。
- **验收记录**：2026-10-04，57新pure、19 distinct PG/HTTP/Edge（5 owned、13独立、1实际Edge）；321契约/350相关Python、635前端/Type Check/demo-auth Build与9生成核对完成，完整实际失败及末版复验见验收；完整实际命令/失败/未执行见[T35验收](acceptance/T35_plan_revisions.md)。45路径（12旧/33新）、641其他tracked/66卡/旧原文与迁移保护；文档与PRIVATE保存后才下一Task。

### T36 · 持久 outbox 与站内提醒

- **状态**：已完成
- **实施前冻结**：[持久作业与站内提醒](jobs_notifications.md)；PostgreSQL租约/fencing/重试与默认关闭本人站内提醒；旧outbox不变，不发邮件SMS、不提前执行T40删除；
- **目标**：可靠处理发布影响与站内通知，不依赖 Web 临时后台任务。
- **涉及文件**：app/jobs、app/notifications、app/api/notifications.py、services/api/worker.py、jobs_migrations/ini、notifications Vue模块、新专项与契约工件、docs/jobs_notifications.md及治理文档。
- **实现内容**：PostgreSQL 持久任务、幂等键、重试/租约/失败状态，站内通知和偏好；不发送邮件/SMS。
- **验收条件**：进程重启可续处理；重复事件不重复提醒；通知/导出/模型等用户作业执行时重验授权/删除状态；删除与留存清理使用受理时核验的专用系统授权，用户会话已撤销仍能完成，不能扩大数据范围。
- **测试方式**：PostgreSQL 多消费者、崩溃重试、到期租约、撤权后取消通知/导出、会话撤销后继续受理删除和通知幂等测试。
- **依赖**：T10、T34；有持久异步需求再创建 worker，不默认引入 Redis。
- **验收记录**：2026-10-04，36新增pure/12新contract；16 distinct实际PG/HTTP（8owned、8独立含新增jobTTL）；712相关Python回归；684前端/43files、49新专项、TypeCheck/demo-auth Build；十profile与原M0契约一致；失败修复与未执行见验收。；完整实际命令/失败/未执行见[T36验收](acceptance/T36_jobs_notifications.md)。47路径（12旧/35新）、674其他tracked/66卡/旧原文与迁移保护；文档与PRIVATE保存后才下一Task。

## 模型与资料权利

### T37 · 可替换模型与调用预算（条件启用）

- **状态**：已完成
- **实施前冻结**：[可替换模型接口与离线预算](model_gateway.md)；仅disabled/mock接口及离线预算，live关闭，无数据库/HTTP/供应商采购或真实数据流；
- **目标**：接入受限制的模型提供商，保持核心无密钥可用。
- **涉及文件**：services/api/app/model_gateway/、新离线unit/async service专项、docs/model_gateway.md及治理文档。
- **实现内容**：disabled/mock/live、结构化输出、超时/并发/预算/用量；仅传必要字段；供应商数据流审查。
- **验收条件**：verified 不可使用 mock；live 故障明确失败；无密钥核心正常；预算拒绝可解释。
- **测试方式**：离线 provider stub、超时/额度/结构错误/错误模式矩阵；live smoke 另行启用。
- **依赖**：T03、T10、T28；D05 供应商/地域/预算审查。
- **本次验收边界**：按用户明确选择仅接口/预算/离线验证完成；真实供应商、地域、数据流和计费审查未执行，live smoke延期，正式模型关闭。
- **验收记录**：2026-10-04，90新增离线async专项（26owned/64独立）、651相关Python和143模式-M0；684前端/43files、TypeCheck/demo-auth Build；十profile/M0契约保持；首次75pass/12fixturefail及实际provider故障修复完整保留；完整实际命令/失败/未执行见[T37验收](acceptance/T37_model_gateway.md)。17路径（7旧/10新）、714其他tracked/66卡/旧原文与迁移保护；文档与PRIVATE保存后才下一Task。

### T38 · 范围检索与引用验证（条件启用）

- **状态**：已完成
- **实施前冻结**：[范围检索与严格引用验证](qa_retrieval.md)；当前适用发布证据的类型化只读检索/原子引用核验；无HTTP/前端/模型live/迁移或全国采集；
- **目标**：只用本次适用发布证据回答有限招生问题。
- **涉及文件**：services/api/app/qa/、tests/unit/qa/及隔离PG、data/evals/qa/与离线校验；.gitattributes和治理文档。
- **实现内容**：结构化/关键词检索，先范围过滤；ID/数值/日期校验；仅类型化只读工具，无任意 SQL/Shell。
- **验收条件**：无依据有限说明或 unknown；跨年/项目引用拒绝；原文指令不能修改规则/读取他人资料。
- **测试方式**：注入、引用不存在/错范围/坏数值日期/无依据评测，固定人工金标准。
- **依赖**：T16、T20、T28、T37。
- **验收记录**：2026-10-04，106纯/评测校验（19owned/57独立/30gold校验）、10 distinct实际PG（5owned/5独立）、24/24固定合成gold；528相关Python/143模式-M0；684前端/43files、TypeCheck/demo-auth Build；十profile/M0/两原文保持，首环境与夹具失败完整记录；完整实际命令/失败/未执行见[T38验收](acceptance/T38_qa_retrieval.md)。22路径（8旧/14新）、723其他tracked/66卡/旧原文与迁移保护；文档与PRIVATE保存后才下一Task。

### T39 · 证据问答入口（条件启用）

- **状态**：已完成
- **实施前冻结**：[有限证据问答入口](qa_entry.md)；独立公共QA profile/有限HTTP与显式折叠UI；只公开项目scope与固定意图，无画像/计划写/真实live；
- **目标**：让用户清楚区分官方事实、通用建议与模型关闭状态。
- **涉及文件**：`app/api/qa.py`、`app/qa/{http_schemas,service,router}.py`、独立qa契约profile/生成器、`apps/web/src/features/qa/`及AuthView/CatalogView/Vite最小接缝；新unit/契约/PG/Edge测试、治理文档。
- **实现内容**：有限问答、引用展开、明确未知/超时/预算；输出不修改画像、计划或事实。
- **验收条件**：disabled/live 失败入口明确；不补 DEMO 答案；显示来源版本与局限。
- **测试方式**：无 key、错误引用、跨用户、输出注入与失败状态端到端。
- **依赖**：T37–T38；未启用则关闭入口并记录延期。
- **验收记录**：2026-10-04，61新pure/9契约、10 distinct实际PG-HTTP（9专项＋1实际Edge/8检查点），704相关Python/143模式-M0；742完整前端及末补丁59专项、TypeCheck/demo-auth Build通过；11profile/M0/原文保持。首次前提与新no-store缺陷修正保留，不累计重复轮次；完整实际命令/失败/未执行见[T39验收](acceptance/T39_qa_entry.md)。36路径（13旧/23新）、732其他tracked/66卡/旧原文与迁移保护；文档与PRIVATE保存后才下一Task。

### T40 · 数据导出与删除作业

- **状态**：已完成
- **实施前冻结**：[资料权利与独立删除台账](data_rights.md)；有界本人导出/持久删除/独立最新减权台账及实际旧备份重放；非真实处理/部署；
- **目标**：落实用户查阅、撤回与删除流程。
- **涉及文件**：`app/privacy/rights/`、`app/api/rights.py`、rights/rights_ledger两迁移及十二profile；现有auth/privacy/grants/storage/changes必要guard接缝；新pure/契约/PG/HTTP/实际restore测试及受影响规范。
- **实现内容**：授权导出、删除作业及状态，覆盖画像/计划/附件/缓存/索引/幂等私有响应与导出工件；登记备份到期，并建立独立于业务备份的最小删除/撤权台账与完整性水位。
- **验收条件**：提交后按政策停止后续处理；身份重验；受理后撤销会话不阻断专用删除作业；不泄露其他用户；缺少最新台账时不得恢复服务。
- **测试方式**：两个用户导出/删除、失败重试、附件/幂等缓存/导出覆盖；先备份后删除再恢复旧备份，必须重放最新台账；台账缺失时拒开放流量。
- **依赖**：T08、T10、T14、T23、T32、T36；D06 留存政策。
- **验收记录**：2026-10-04，30新pure/11契约、18 distinct实际PG-HTTP（包含1实际pg_dump/pg_restore及文件恢复），713相关Python/1旧symlink skip、743前端/TypeCheck/demo-auth Build通过；12profile/M0/原文保护。初失败及末新增安全检查保留，不累计重复轮次；完整实际命令/失败/未执行见[T40验收](acceptance/T40_data_rights.md)。51路径（22旧/29新）、746其他tracked/66卡/旧原文与迁移保护；文档与PRIVATE保存后才下一Task。

### T41 · 隐私与授权操作页面

- **状态**：已完成
- **实施前冻结**：[隐私与授权操作页面](privacy_workspace.md)；只复用隐私/共享面板与T40本人权利六操作，明确确认/有限追踪/迟到清理，真实关闭；
- **目标**：提供可理解的资料权利入口。
- **涉及文件**：`views/SettingsView.vue`、`features/privacy/rights/{client,useRights,RightsPanel}`、AuthView最小接缝；新三前端专项与fixture、实际PG/HTTP/Edge harness及界面/验收文档。
- **实现内容**：告知版本/同意状态、授权撤回、导出/删除确认、进度和保留范围说明。
- **验收条件**：不能把请求已接收显示为全部已删除；可追踪失败；无不必要资料收集。
- **测试方式**：撤回即时生效、删除 pending/failed/completed、越权与键盘端到端。
- **依赖**：T08、T40；若有协作还依赖 T09。
- **验收记录**：2026-10-04，62新前端专项（38client/17state/7panel）、完整805/49files、VueTypeCheck/demo-authBuild，228相关Python及1实际PG/HTTP/Edge十一检查点通过；12profile/M0/原文保护，初type/harness失败保留，不重复累节点；完整实际命令/失败/未执行见[T41验收](acceptance/T41_privacy_workspace.md)。21路径（8旧/13新）、789其他tracked/66卡/旧原文与迁移保护；文档与PRIVATE保存后才下一Task。

## 公众运行与发布

### T42 · 通用 Docker 配置（实际部署目标待定）

- **状态**：已完成
- **最新用户指令**：2026-10-04选择‘先做通用 Docker 配置’，范围调整为本地隔离配置源码；‘不用测试’优先于通用测试要求。本次完成定义是配置/CLI/说明源码与文档一致，运行检查全部保留未执行，不称镜像可构建或真实部署已完成（ADR-056）。
- **实施前冻结**：[通用配置契约](deployment.md)的输入/范围及未执行矩阵；原D01阻塞历史保留在[记录](acceptance/T42_deployment.md)。
- **目标**：提供可审阅的通用Docker源码，实际城市/供应商/地域适配和手续后定；保持真实业务与公众服务关闭。
- **涉及文件**：`.dockerignore`、`.gitattributes`部署LF规则、`deploy/`、七治理文档、deployment与acceptance，共22路径。
- **实现内容**：既有foundation API、auth静态前端/TLS同源代理、loopback端口、私网业务库/台账库与不同卷、外部秘密引用、版本摘要参数、有界只读预检、固定18profile的显式单链迁移、停止与兼容回滚说明。worker关闭，保留后续私网位置，不冒充已装配。
- **源码验收条件**：配置不含默认密码/真实资料；API无DB秘密，库无主机端口；固定生产verified/disabled，运行镜像不装配M0/seed/debug/私有业务；迁移必须选profile+--apply，启动不DDL，源码/未执行项同步。已按这些源码范围完成；不存在实际运行通过的结论。
- **运行验证**：镜像构建/可复现性、配置负例、秘密哨兵、网络/健康/TLS、迁移链与恢复/回滚、Lint/TypeCheck/单元/集成/浏览器均未执行（用户要求），不使用旧结果代替。
- **依赖**：T03、T06、T14、T36；通用源码不依赖已选城市/供应商。实际平台及公开启用仍需D01、独立台账/锚点与最小权限及相关发布门槛。
- **完成记录**：2026-10-04源码与文档已完成，按PRIVATE持续授权保存当前Task。D01仍待定；D07旧提案未采用、替代目标未定，T44–T46相关依赖不撤销。

### T43 · 持续集成与契约漂移检查

- **状态**：已完成
- **目标**：每次改动执行相关自动化质量门槛。
- **涉及文件**：`.github/workflows/` 或选定 CI 配置、`scripts/`、测试配置、`packages/contracts/v2/`。
- **实现内容**：锁定依赖、离线单测、PostgreSQL 临时库、契约生成 diff、TS/构建与关键端到端。
- **原运行验收条件（未验证）**：坏迁移/漂移/严重失败阻止合入；无真实资料或商业密钥；不能用平均通过率遮盖严重个案。
- **测试方式**：有意漂移/坏规则/坏迁移分支验证 CI 拒绝，正常分支留实际报告。
- **依赖**：T02、T20、T29、T33、T40、T42。

- **当前源码记录**：2026-10-04；完成默认关闭的手动CI源码，推送不触发测试；固定契约、离线Python、独立PG/迁移及Vue四stage。按用户不用测试，源码完成与原运行验收分别记录；见[契约](ci.md)和[记录](acceptance/T43_source.md)。
- **未完成/未验证**：流水线/坏迁移/漂移/网络负例与分支门槛未验证；workflow仅工作分支、默认分支入口和branch protection未配置；旧Windows浏览器/pg_dump路径尚未接入，关键HTTP不能代替浏览器/完整恢复

### T44 · 备份、恢复与删除重放

- **状态**：已完成
- **目标**：用实际演练证明能恢复服务与资料权利状态。
- **涉及文件**：`deploy/backup/`、`scripts/`、`app/privacy/`、恢复集成测试和运行文档。
- **实现内容**：加密备份/最小访问、独立恢复库，从业务备份之外的最新删除/撤权台账验证完整性水位并重放，恢复后自检；按确认 RPO/RTO 留存。
- **原运行验收条件（未验证）**：实际恢复可读发布版本与有效私有数据；已删除/撤回内容不可重新服务；结果有时间证据。
- **测试方式**：专用 PostgreSQL+文件备份恢复演练；先备份A、后删除/撤权B、再恢复A并重放B；损坏备份/台账缺失/水位落后时拒流量。
- **依赖**：T40、T42；D06/D07 留存、RPO/RTO。

- **当前源码记录**：2026-10-04；仅完成T44相关代码与依赖核对，备份/恢复尚未实现；D07替代目标及本批仅源码继续的范围澄清待答。按用户不用测试，源码完成与原运行验收分别记录；见[契约](backup_scope.md)和[记录](acceptance/T44_source.md)。
- **未完成/未验证**：D07的恢复/容量目标与责任未定；原T44要求实际恢复证据，本批不用测试；未收到调整原顺序/验收范围的答复，不将等待视为同意，不继续T45–T50

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；合成有界AESGCM备份包、固定维护计划与T40恢复屏障接缝；范围：deploy/backup/__init__.py, deploy/backup/archive.py, deploy/backup/maintenance.py。可测试标准：篡改/错密钥/到期/超限拒绝；仅合成模式、独立空目标计划；缺受信guard拒恢复ready。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；合成有界AESGCM备份包、固定维护计划与T40恢复屏障接缝。源码/文档完成；原运行及真实发布验收未执行，保留：实际PG dump/restore、加密密钥ACL/轮换、独立灾备、RPO/RTO与正式运行责任未验证。见[本次记录](acceptance/T44_20261012.md)。

### T45 · 监控、故障与纠错入口

- **状态**：已完成
- **目标**：让公开服务异常和错误事实可发现、可处理。
- **涉及文件**：`app/observability/`、`deploy/monitoring/`、`apps/web/src/features/feedback/`、监控测试。
- **实现内容**：请求耗时/错误率/规则未知率/审查积压/作业失败/模型成本指标，告警责任、状态/反馈入口与响应流程。
- **验收条件**：无原始画像指标标签；依赖故障明确；撤回错误事实与影响处理有责任人。
- **测试方式**：故障注入、告警触发、脱敏、纠错请求权限与处理状态测试。
- **依赖**：T10、T19、T36、T42；D07 运行负责人和目标。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；默认关闭的有限指标汇总与纠错候选状态契约；范围：services/api/app/observability/__init__.py, services/api/app/observability/metrics.py。可测试标准：非法metric/私有标签拒绝；固定低基数计数/锁；纠错不自动改事实。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；默认关闭的有限指标汇总与纠错候选状态契约。源码/文档完成；原运行及真实发布验收未执行，保留：持久反馈HTTP/告警、运行采集器、负责人/SLO及故障脱敏演练未实现或未验证。见[本次记录](acceptance/T45_20261012.md)。

### T46 · 限流、配额与容量验证

- **状态**：已完成
- **目标**：在确认流量/预算内保护公开接口和高成本操作。
- **涉及文件**：反向代理配置、`app/limits/`、预算表/配置、`tests/security/limits/`、负载脚本。
- **实现内容**：匿名/登录/管理员不同限制、导入/导出上限、账号原子配额、模型上限；基于确认负载测量 P50/P95。
- **验收条件**：超限明确 429 或业务错误；重试不重复计费；并发配额不超发；报告真实容量，未达目标明确失败。
- **测试方式**：并发限额、重试/幂等/重启、负载与故障降级；模型仅 stub。
- **依赖**：T05、T15、T36、T42、T45；D07。live 上限另依赖 T37。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；显式合成窗口配额、并发预留和幂等计费收据；范围：services/api/app/limits/__init__.py, services/api/app/limits/quota.py。可测试标准：默认关闭/缺阈值拒绝；并发锁/超限429；同request同hash不重复扣费、不同hash409；倒退时钟关闭。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；显式合成窗口配额、并发预留和幂等计费收据。源码/文档完成；原运行及真实发布验收未执行，保留：仅单进程内存，不提供生产配额/HTTP装配/多实例/重启持久性或容量测量，D07阈值未知。见[本次记录](acceptance/T46_20261012.md)。

### T47 · 固定评测与独立领域抽查

- **状态**：已完成
- **目标**：证明严重业务错误被拦截，真实资料经过责任审核。
- **涉及文件**：`data/evals/`、`tests/e2e/`、`docs/acceptance/`；发现影响本任务的缺陷时最小修复相关文件。
- **实现内容**：先建立可单会话维护的首批关键金标准，按项目/文档/年度分留出；重放严重资格/期限/权限/删除案例，人工抽查原文。
- **验收条件**：所有关键发布字段有审核记录；固定集严重错误为 0；样本数/分母/版本/失败可查；不能宣称全世界可靠。
- **测试方式**：全回归、已审核事实重放、人工领域抽查记录；目标 100 例分增量扩展，不伪造已完成数量。
- **依赖**：已实现的所有公众 MVP 功能、T43–T46；数据审核责任人与资料。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；十项关键合成验收设计与未执行报告契约；范围：data/evals/critical_20261012.json, services/api/app/evaluation/__init__.py, services/api/app/evaluation/report.py。可测试标准：未执行不算通过；重复case拒绝；passed须命令/版本证据；严重失败或缺案例阻挡。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；十项关键合成验收设计与未执行报告契约。源码/文档完成；原运行及真实发布验收未执行，保留：本批无评测执行或真实领域抽查，十项只是设计样本，不代表100例或严重错误为零。见[本次记录](acceptance/T47_20261012.md)。

### T48 · 公众发布准入判定

- **状态**：已完成
- **目标**：生成可审阅的发布结论，确认所有必要门槛。
- **涉及文件**：`docs/acceptance/public_release.md`、运行/部署文档、`docs/tasks.md`。
- **实现内容**：核对地域/年龄/备案与适用义务、供应商、数据覆盖、认证/授权、删除/恢复、监控/成本、领域审核和自动化报告；明确关闭延期入口。
- **验收条件**：逐项 evidence/owner/status；任何严重失败或必要决策缺失均阻挡发布；区分 ready 与已实际部署。
- **测试方式**：检查清单与报告交叉核对、模拟缺失门槛；用户审阅具体发布包后另行决定部署，任务本身不自动开公众服务。
- **依赖**：T08、T19、T40–T47；必要时 T09/T37–T39；D01–D07 对应上线决策。

## 全国参考资料（原规划；本批最小源码完成，真实验收保留）

契约与来源见 [data_strategy](data_strategy.md)。原 T01–T49 业务字段与依赖保留；新增任务只描述未来实现。T50–T58 是有限类型模型/导入与比较，T59–T62 分API族，T63–T65 分页面，T66可选连接器，T67每批创建小子任务。所有真实源与使用权审核由责任人完成，不能把当前研究样本标已发布。首版强制范围按D08，不自动给既有Task追加全国验收。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；有限发布门槛报告与缺失证据阻挡判定；范围：services/api/app/release_gate/__init__.py, services/api/app/release_gate/decision.py。可测试标准：缺门槛/owner/证据/未执行/失败阻挡；自报通过仅待核验；永不部署。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；有限发布门槛报告与缺失证据阻挡判定。源码/文档完成；原运行及真实发布验收未执行，保留：真实D01–D08、身份/权限/恢复/监控/容量/领域审核与本批运行验证缺失，当前公众发布blocked。见[本次记录](acceptance/T48_20261012.md)。

### T50 · 地区、发布主体与覆盖登记

- **状态**：已完成
- **目标**：建立全国资料范围和来源责任的可验证目录。
- **涉及文件**：app/statistics/regions.py、app/admin/sources/、coverage迁移、tests/unit/coverage/；受影响规范同步更新。
- **实现内容**：登记大陆31省级地区及港澳台独立路径、authority子范围、资料类型/年度/届、未知总量与状态；只导入小型登记夹具，不采集全部事实。
- **验收条件**：地区不重复；兵团不重复计省；HK/MO/TW高考类型不适用；分母未知不算完整率；研究/已审/已发布数分开。
- **测试方式**：区域/子范围及不适用、未知分母、样本/正式计数单测；专用PG约束/迁移及权限测试。
- **依赖**：T11、T13；D08决定优先批次/负责人。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；34地区×2026覆盖登记与有限本地候选导入基础；范围：services/api/app/statistics/__init__.py, services/api/app/statistics/regions.py, services/api/app/statistics/coverage.py, services/api/app/statistics/candidates.py。可测试标准：地区唯一/兵团子范围；港澳台gaokao不适用；分母无证据为null；候选整批/重复键/超限拒绝，pending不发布。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；34地区×2026覆盖登记与有限本地候选导入基础。源码/文档完成；原运行及真实发布验收未执行，保留：无新PG表/迁移/正式来源owner或已审核全国事实，候选仅本地模型/bytes；真实覆盖与持久事务/审核发布待实现。见[本次记录](acceptance/T50_20261012.md)。

### T50A · 2026年全国高校来源候选文件登记

- **状态**：已完成
- **目标**：登记大陆31省级地区及港澳台的官方来源候选、原始年度与访问/资料缺口，形成后续人工核验入口。
- **涉及文件**：data/research/source_registry_2026.json、scripts/verify_source_registry.py、tests/research/test_source_registry.py、docs/acceptance/T50A_source_registry.md；README、AGENTS、requirements、architecture、data_strategy、tasks、CHANGELOG、DECISIONS。
- **实现内容**：先固定候选契约及测试，人工有界读取官方名录/招生入口；来源身份、访问、年映射、许可/审核分开，34地区×7类型登记缺口；只读离线校验。T50后台及其依赖不启动。
- **验收条件**：34地区唯一及238单元完整；引用可追溯；待审未发布、导入/审核/发布0、获取/资格关闭；缺未知年/总量/hash不猜；原样保留P02与M0；负例校验明确失败、不写文件。
- **测试方式**：登记验证器、相关离线pytest、原文/范围/历史保护、文档链接与日志/Task/ADR检查；有界官方联网研究单列，失败和未读取如实记录。
- **依赖**：T01已完成；用户明确授权来源登记及2026大陆/港澳台范围。文件登记不依赖未实施后台，不解除T50的T11/T13和责任人依赖。
- **验收记录**：2026-10-01：`.\.venv\Scripts\python.exe -X utf8 scripts/verify_source_registry.py`退出0：48来源/34地区/238单元（166有候选、66未登记、6不适用），正式审核/发布/高校导入0、分母/覆盖率null；`... -m pytest tests/research/test_source_registry.py -q`退出0：101 passed、无warning。原文脚本、py_compile及`.cache/t50a_validate.py`文档/引用/范围/历史保护检查退出0（13文档、93本地链接、11条ADR）；8份旧文档改、4新增，73范围外文件不变，T01验收/旧迁移/P02/原始输入保留；Git仍未跟踪，无提交。联网研究单列：31省级端点各打开一次，7正文/2外壳/16超时/2HTTP错误/4工具不可访问；全部48来源16正文/3部分/29不可取得。只读核验发现父导航备注仍称端点未访问，已按实际单次检查改正并重验。首次CLI两次退出1来自过窄角色兼容约束，已修正后通过；文档辅助更新遇换行/树缩进匹配退出1后适配完成，未发生应用测试失败。前后端业务/PG/Build/浏览器/Lint/Type Check/部署未执行：本子Task只改候选登记及stdlib验证，无相关运行代码/配置变更，工具无已配置Lint/静态类型入口。详细访问/命令/限制见[独立验收](acceptance/T50A_source_registry.md)。


### T51 · 学院、专业和年度代码映射

- **状态**：已完成
- **目标**：避免同名学校/学院/专业与专业组错连。
- **涉及文件**：app/curricula/identities.py、academic_units/crosswalk迁移、tests/unit/crosswalk/；受影响规范同步更新。
- **实现内容**：复用T11机构与program实体，增加学院层级、国家专业目录版本和省年组/招生专业码映射；仅固定少量身份边界夹具。
- **验收条件**：独立学院与校内学院分开；同名不自动合并；改名/重组/校区及组成员有效范围可追踪；未审核映射不用于事实连接。
- **测试方式**：同名/改名/年度码复用/多专业组/跨校区测试；PG FK/粒度/有效范围检查。
- **依赖**：T11、T13、T50；正式名录来源与映射审核责任人。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；学院层级与省年招生代码映射候选；范围：services/api/app/curricula/__init__.py, services/api/app/curricula/identities.py, services/api/app/statistics/candidates.py。可测试标准：同名不合并；校内学院/独立机构分开；生源省年/校区/有效年度；pending映射不能连事实。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；学院层级与省年招生代码映射候选。源码/文档完成；原运行及真实发布验收未执行，保留：仅严格候选模型，无官方代码名录/PGFK/映射审核及正式连接，原名称与代码不自动标准化。见[本次记录](acceptance/T51_20261012.md)。

### T52 · 省级控制线和分段线模型与导入

- **状态**：已完成
- **目标**：按考试范围保存省线原义。
- **涉及文件**：app/statistics/cutoffs.py、cutoff迁移、app/ingestion/、tests/unit/cutoffs/；受影响规范同步更新。
- **实现内容**：建立类型化cutoff契约、验证与人工导入候选；用一省一年小型授权夹具，保留原名/总分/加分定义/证据，复用审核发布。
- **验收条件**：分段线不转本科线；特殊线独立；跨省/年/科类不合并；无总分留空；重导幂等；不能生成当前资格规则。
- **测试方式**：一段/本科控制/特殊线区别、缺总分、单位/年份/重复导入测试；PG约束/事务回归。
- **依赖**：T15–T19、T50；本Task只实现候选导入。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；精确考试范围和省线类型候选及单条DEMO夹具；范围：services/api/app/statistics/cutoffs.py, data/fixtures/reference/DEMO_cutoff_2026.json。可测试标准：段线/本科/特殊线区别；总分未知留空；港澳台gaokao拒绝；缺值原因/重导摘要/整批拒绝。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；精确考试范围和省线类型候选及单条DEMO夹具。源码/文档完成；原运行及真实发布验收未执行，保留：无实际省分数或PG持久化/审核发布；归一候选hash不是原文字节hash，缺2026真实资料不回填。见[本次记录](acceptance/T52_20261012.md)。

### T53 · 一分一段与位次区间

- **状态**：已完成
- **目标**：给出有定义的分数分布，避免伪精确个人位次。
- **涉及文件**：app/statistics/distributions.py、distribution迁移、tests/unit/distributions/；受影响规范同步更新。
- **实现内容**：分数段人数/累计方向/同分和考生总体定义；生成同分区间，仅处理一种已定义统计格式。
- **验收条件**：累计值单调及人数关系可验证；未知总体/加分/同分排序明确限制；跨改革或科类不可直接套用；不估录取概率。
- **测试方式**：升降序累计、并列分数、缺分段/总人数、格式错误及改革范围测试；PG导入与重放。
- **依赖**：T15–T19、T50、T52。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；完整降序累计分布验证与合成同分位次区间；范围：services/api/app/statistics/distributions.py。可测试标准：严格降序/累计人数关系；缺总体或定义unknown；完整表同分区间；缺段不伪精确。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；完整降序累计分布验证与合成同分位次区间。源码/文档完成；原运行及真实发布验收未执行，保留：仅纯候选及一种降序格式，未导入真实分布/PG/个人排序，不生成录取概率。见[本次记录](acceptance/T53_20261012.md)。

### T54 · 院校专业组和专业历史录取模型

- **状态**：已完成
- **目标**：分清投档、最终录取与统计粒度。
- **涉及文件**：app/statistics/admissions.py、admission_observations迁移、app/ingestion/、tests/unit/admissions/；受影响规范同步更新。
- **实现内容**：建立省年批次/轮次/组/专业范围和metric_kind候选导入；最小一份表格式，不把各组折叠成学校一分。
- **验收条件**：投档最低/终录取最低/平均/位次区分；单科列不自动变资格；地方机构码不当全国PK；unmapped不隐式连接。
- **测试方式**：多组/征集与普通批、同分列、年度代码变化/来源冲突/缺映射测试；PG粒度/幂等/发布约束。
- **依赖**：T15–T19、T50–T52。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；省年组专业粒度的历史投档与录取观测候选；范围：services/api/app/statistics/admissions.py。可测试标准：投档/终录取/均分/位次分开；group/program粒度校验；映射pending不关联；无学校通用分。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；省年组专业粒度的历史投档与录取观测候选。源码/文档完成；原运行及真实发布验收未执行，保留：无真实录取数据/PG/代码审核与发布，不估录取概率或将单科统计变资格。见[本次记录](acceptance/T54_20261012.md)。

### T55 · 名额与费用补充事实契约

- **状态**：已完成
- **目标**：补充影响选择的名额和成本，先完成一种表格式。
- **涉及文件**：app/statistics/quotas.py、app/catalog/facts/、quota迁移、tests/unit/supplementary/；受影响规范同步更新。
- **实现内容**：计划initial/executed/remaining/admitted/enrolled定义及来源须知；费用复用T11/T12事实，补币种/周期/适用年/身份/校区校验；本Task不新增全套选科/认证解析器。
- **验收条件**：执行计划数不改为实际录取；表头与须知冲突需复核；费用没有周期不算总成本；未来年/住宿未知不猜。
- **测试方式**：计划/人数定义、收费周期/国际生范围/校区及缺失单测；PG字段/事务与契约回归。
- **依赖**：T11–T12、T15–T19、T51、T54；本Task不要求完成其他补充字段的实际数据批次。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；人数口径和适用身份费用候选；范围：services/api/app/statistics/quotas.py。可测试标准：计划/执行/剩余/录取/入学不混；负数/未知币种周期拒或留空；合成实体引用一致。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；人数口径和适用身份费用候选。源码/文档完成；原运行及真实发布验收未执行，保留：无真实人数/费用、PG或发布；周期未知不算总成本，住宿与未来年度不填假值。见[本次记录](acceptance/T55_20261012.md)。

### T56 · 按入学届的培养方案契约与导入

- **状态**：已完成
- **目标**：保存专业培养版本及课程关系。
- **涉及文件**：app/curricula/schemas.py/service.py、curriculum迁移、app/ingestion/、tests/unit/curricula/；受影响规范同步更新。
- **实现内容**：增加curriculum版本及module；入学届/教学年/学制/学位/课程码/必选修/学分/学时/实践；用小型格式候选导入，不处理所有学校文档。
- **验收条件**：2025/2026届不覆盖；教学年不能自动映射入学届；排版歧义学分null；未来模块provisional；身份/专业匹配待审核不发布。
- **测试方式**：届/学年错配、学分歧义/单位、版本/模块及专业组映射测试；PG迁移/发布关系与M0隔离。
- **依赖**：T15–T19、T51；本Task只实现候选导入。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；按入学届保存培养版本和有界课程候选；范围：services/api/app/curricula/schemas.py。可测试标准：入学届/教学年分开；课程code唯一/有界；歧义学分null；未来课程provisional；引用合成隔离。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；按入学届保存培养版本和有界课程候选。源码/文档完成；原运行及真实发布验收未执行，保留：无真实培养方案或PG/版本发布，未知当届不复用旧届，候选不代表完成专业映射。见[本次记录](acceptance/T56_20261012.md)。

### T57 · 实际毕业人群与指标契约

- **状态**：已完成
- **目标**：逐指标保留真实统计人群、方法与分母。
- **涉及文件**：app/outcomes/schemas.py/service.py、outcome迁移、app/ingestion/、tests/unit/outcomes/；受影响规范同步更新。
- **实现内容**：分report/population/metric，工作/升学/落实/薪资独立；毕业届/观察期/样本/回应率/抑制与周期、税前后；小型授权夹具导入候选，无模型填值。
- **验收条件**：学校/学科数据不写入专业值；样本和毕业届不共用；响应率不反算受邀人数；未知薪资周期及正文不可用留空；聚合层级约束。
- **测试方式**：就业与升学、同页不同届/样本、学校/专业错用、小样本/分母/薪资未知测试；PG CHECK/FK、发布与隔离回归。
- **依赖**：T15–T19、T51；真实就业来源正文、使用权及审核人。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；逐指标毕业人群、观察窗口、分母与薪资定义候选；范围：services/api/app/outcomes/__init__.py, services/api/app/outcomes/schemas.py。可测试标准：专业/学科/学院/学校粒度；届/样本/回应不同；抑制无数值；薪资周期未知不换算。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；逐指标毕业人群、观察窗口、分母与薪资定义候选。源码/文档完成；原运行及真实发布验收未执行，保留：无真实毕业结果/PG/审核发布；指标样本、分母、周期未知保留，不将落实率当就业率。见[本次记录](acceptance/T57_20261012.md)。

### T58 · 确定性可比性检查

- **状态**：已完成
- **目标**：阻止跨口径数据被拼成排名。
- **涉及文件**：app/statistics/comparability.py、app/outcomes/comparability.py、tests/unit/comparability/；受影响规范同步更新。
- **实现内容**：仅实现纯确定性检查：考试年/改革/科类/批次/组成员/总分与就业层级/学位/人群/届/观察期/方法/薪资；返回四类可比性及原因，不做推荐评分。
- **验收条件**：关键字段缺失unknown；对象/方法不同not_comparable；条件受限limited；历史数据不影响资格、没有概率/预测收入/跨币种隐式换算。
- **测试方式**：固定真值/边界矩阵、同分与跨改革/组变/统计口径/单位/缺失单测；断言资格结果不被改写。
- **依赖**：T51–T57；逐指标定义已确定。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；统计和毕业指标的确定性四类可比性检查；范围：services/api/app/statistics/comparability.py, services/api/app/outcomes/comparability.py, services/api/app/statistics/candidates.py。可测试标准：关键定义缺失unknown；对象/年/口径差异不可比；样本差异limited；相同定义comparable且不改资格。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；统计和毕业指标的确定性四类可比性检查。源码/文档完成；原运行及真实发布验收未执行，保留：仅纯定义比较，不证明已审数据/发布；没有排名、预测收入或隐式币种换算。见[本次记录](acceptance/T58_20261012.md)。

### T59 · 省线与覆盖只读API

- **状态**：已完成
- **目标**：公开有限已发布省线及诚实覆盖。
- **涉及文件**：app/api/v2/statistics_cutoffs.py、coverage路由、packages/contracts/v2/、tests/contracts/；受影响规范同步更新。
- **实现内容**：实现GET覆盖及province-cutoffs；类型化必需筛选、稳定分页/release、missing_reason、审核范围和限额；不一起实现其他资料API。
- **验收条件**：只读真实已审已发布；无年份记录不回填最新/DEMO；总量未知为null；私有/撤回404；TS/实际序列化一致。
- **测试方式**：权限/release/分页/筛选422、缺年/未适配/null契约与PG查询；TS类型检查。
- **依赖**：T02–T03、T19、T50、T52；与T46限额策略对齐。省线/覆盖查询不执行比较，无需等待培养/就业模型完成。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；独立默认空数据的省线与覆盖只读API及TS契约；范围：services/api/app/api/reference.py, services/api/app/api/reference_contract.py, services/api/app/api/reference_cutoffs.py, packages/contracts/reference.ts。可测试标准：必需省年/未知参数/重复参数422；空release/分母null；不读取候选/DEMO/DB；有界limit/无cursor。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；独立默认空数据的省线与覆盖只读API及TS契约。源码/文档完成；原运行及真实发布验收未执行，保留：API只是未启用资料的空响应；无正式published reader/PG/撤回查询或运行契约验证，生产工厂不装配此入口。见[本次记录](acceptance/T59_20261012.md)。

### T60 · 分布与历史录取查询API

- **状态**：已完成
- **目标**：查询明确考试范围的位次区间及历史观测。
- **涉及文件**：app/api/v2/statistics_admissions.py、packages/contracts/v2/、tests/contracts/；受影响规范同步更新。
- **实现内容**：实现score-distributions、admissions及有界已发布统计comparisons，复用T59协议；返回原定义/实际粒度/比较原因。
- **验收条件**：投档与终录取不混；省/年/组必须可定位；同分只返有依据区间；撤回/不公开不能比较；不返回录取概率。
- **测试方式**：多组/批次、筛选/分页、未映射、撤回与跨年比较契约；PG查询及TS检查。
- **依赖**：T53–T55、T58–T59；T46限额。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；分布、历史录取与指定记录比较的空查询接口；范围：services/api/app/api/reference_admissions.py, services/api/app/api/reference.py。可测试标准：有界省年/组专业筛选；未知和重复参数拒绝；比较不接任意候选payload；空数据不输出概率。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；分布、历史录取与指定记录比较的空查询接口。源码/文档完成；原运行及真实发布验收未执行，保留：无正式统计reader/数据库分页或可读取发布记录；比较接口只返回未启用缺口，不执行虚假比较。见[本次记录](acceptance/T60_20261012.md)。

### T61 · 培养方案查询API

- **状态**：已完成
- **目标**：查询指定专业入学届的已发布培养版本。
- **涉及文件**：app/api/v2/curricula.py、packages/contracts/v2/、tests/contracts/；受影响规范同步更新。
- **实现内容**：实现programs/{program_id}/curricula；入学届/教学年独立筛选、版本、模块/evidence及缺口，复用公开release协议。
- **验收条件**：查2027不能默认回2026；未来模块标provisional；无适用方案null/缺口；映射/发布/撤回与粒度保持正确。
- **测试方式**：跨届/教学年、未映射/版本/撤回、排版歧义与模块契约；PG/TS检查。
- **依赖**：T56、T59。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；明确专业UUID与入学届的空培养方案查询；范围：services/api/app/api/reference_curricula.py, services/api/app/api/reference.py, services/api/app/api/reference_contract.py。可测试标准：entry_cohort与teaching_year独立；查2027不回2026；程序UUID非法422；缺方案空/不启用。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；明确专业UUID与入学届的空培养方案查询。源码/文档完成；原运行及真实发布验收未执行，保留：无正式培养reader/真实方案或PG，API仅明确当届缺口，所有HTTP/TS/构建未验证。见[本次记录](acceptance/T61_20261012.md)。

### T62 · 实际毕业结果查询API

- **状态**：已完成
- **目标**：返回逐指标的真实人群与缺口。
- **涉及文件**：app/api/v2/outcomes.py、packages/contracts/v2/、tests/contracts/；受影响规范同步更新。
- **实现内容**：实现outcomes查询；请求/实际层级分开、逐指标population/届/方法/样本/回应率/薪资定义；专业缺失时仅另列标明上级汇总。
- **验收条件**：专业数值不套学校/学科；无法比较明确原因；薪资周期未知不标月薪/年薪；不使用研究样本作为已发布数据。
- **测试方式**：请求专业只有学科、不同届样本、正文失败/抑制、权限/撤回/分页契约；PG/TS检查。
- **依赖**：T57–T59；T46限额。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；按请求层级、毕业届和对象的空结果查询；范围：services/api/app/api/reference_outcomes.py, services/api/app/api/reference.py。可测试标准：graduation_cohort独立筛选；层级明确；专业缺失不回学校/学科；样本/工资未知不伪造。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；按请求层级、毕业届和对象的空结果查询。源码/文档完成；原运行及真实发布验收未执行，保留：没有真实结果reader/上级汇总或PG发布查询，items为空，不提供实际就业结论。见[本次记录](acceptance/T62_20261012.md)。

### T63 · 全国历史统计查询页面

- **状态**：已完成
- **目标**：让访客理解线种、粒度和支持范围。
- **涉及文件**：apps/web/src/features/statistics/、apps/web/tests/、packages/contracts/v2/；受影响规范同步更新。
- **实现内容**：实现省年/科类/批次查询、分布/历史统计视图、来源和覆盖/比较限制；个性化入口显示仍仅单省适配。
- **验收条件**：一段不标本科线；多组不折成学校一分；缺年/失败不回填DEMO；不可比/未采集状态可读、键盘/移动端可用。
- **测试方式**：离线假API交互、筛选/竞态/缺口/错误/可比性测试；类型/构建及必要浏览器流程。
- **依赖**：T59–T60、T21。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；可达的全国统计只读查询页和有界空数据客户端；范围：apps/web/src/features/reference/client.ts, apps/web/src/features/reference/query.ts, apps/web/src/features/reference/ReferenceView.vue, apps/web/src/features/statistics/StatisticsView.vue, apps/web/src/main.ts, apps/web/vite.config.ts。可测试标准：显式查询；筛选变化清结果/迟到取消；错误不回DEMO；正确线种/组粒度/缺口；新mode可达。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；可达的全国统计只读查询页和有界空数据客户端。源码/文档完成；原运行及真实发布验收未执行，保留：无真实数据可展示或页面交互/类型/Build验证；目前仅空查询，未接生产部署。见[本次记录](acceptance/T63_20261012.md)。

### T64 · 培养方案比较页面

- **状态**：已完成
- **目标**：按专业与入学届展示课程和毕业要求。
- **涉及文件**：apps/web/src/features/curricula/、apps/web/tests/；受影响规范同步更新。
- **实现内容**：实现培养方案版本/届选择、学位/课程表/学分/证据，区分教学年与未来模块；不复制全部PDF。
- **验收条件**：届/学年清楚；学分歧义显示待核验；未公布当届不回填旧届；课程就业方向不当就业统计。
- **测试方式**：离线假API跨届/未知/加载竞态/证据与键盘交互；类型检查、构建。
- **依赖**：T61、T21。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；可达培养入学届查询与当届缺口页面；范围：apps/web/src/features/curricula/CurriculaView.vue, apps/web/src/features/reference/client.ts, apps/web/src/features/reference/ReferenceView.vue。可测试标准：UUID/入学届/教学年显式；切换页卸载清内容；当届未知不回旧届，不造课程表。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；可达培养入学届查询与当届缺口页面。源码/文档完成；原运行及真实发布验收未执行，保留：当前只空培养查询，未展示真实版本/课程/证据或执行界面/类型/Build检查。见[本次记录](acceptance/T64_20261012.md)。

### T65 · 毕业结果与质量页面

- **状态**：已完成
- **目标**：显示实际统计层级、时间和样本局限。
- **涉及文件**：apps/web/src/features/outcomes/、apps/web/tests/；受影响规范同步更新。
- **实现内容**：实现逐指标的人群/届/样本/分母/来源和缺口、上级汇总另列、比较原因；无收益预测或排名。
- **验收条件**：工作或升学/落实不标纯就业；学科薪资不标某专业；未知周期/分母不猜；小样本和不可比明确展示。
- **测试方式**：离线假API不同样本/届/层级、分母未知/正文失败/抑制与可比性交互；类型/构建/必要浏览器。
- **依赖**：T62、T21。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；可达的毕业届、统计层级和指标缺口页面；范围：apps/web/src/features/outcomes/OutcomesView.vue, apps/web/src/features/reference/client.ts, apps/web/src/features/reference/ReferenceView.vue。可测试标准：工作/升学/落实/薪资分开；专业不回上级；分母/工资周期未知；切换清结果/失败不填值。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；可达的毕业届、统计层级和指标缺口页面。源码/文档完成；原运行及真实发布验收未执行，保留：仅空结果/局限说明，无真实指标展示或页面测试/类型/Build验证。见[本次记录](acceptance/T65_20261012.md)。

### T66 · 可选有限来源连接器

- **状态**：已完成
- **目标**：降低已登记来源的重复获取成本，保持人工发布。
- **涉及文件**：app/ingestion/connectors/、app/jobs/、tests/security/connectors/、docs/api.md；受影响规范同步更新。
- **实现内容**：若另行选择，只做一种有限白名单来源、管理员触发、HTTPS/DNS/重定向防SSRF、大小/MIME/页数/速率/超时/有限重试与幂等；候选输出，无自动规则/发布。
- **验收条件**：许可/允许获取条件已确认；不接任意URL，不绕登录/验证码/付费；失败显式留存，不以旧值冒充新；可暂停，M0不联网。
- **测试方式**：离线假HTTP/DNS/文档恶意输入、重定向/内网/超限/失败/重复任务测试；PG作业重试。
- **依赖**：T13–T19、T36、T50及已选择的数据类型导入Task；来源使用权/获取政策；首版可继续人工导入，本Task非默认必做。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。

- **本次实施契约**：2026-10-12；默认禁用的固定来源连接器请求契约；范围：services/api/app/ingestion/connectors/__init__.py, services/api/app/ingestion/connectors/policy.py。可测试标准：任意URL不能提交；未登记来源拒绝；只HTTPS固定语法和有界项；永不fetch或绕登录。本轮不执行检查。

- **简化源码完成记录**：2026-10-12；默认禁用的固定来源连接器请求契约。源码/文档完成；原运行及真实发布验收未执行，保留：未选实际来源/许可，DNS/重定向SSRF防护与实际获取/重试/作业未实现，live恒关闭。见[本次记录](acceptance/T66_20261012.md)。

### T67 · 单批真实资料审核与覆盖验收

- **状态**：已完成
- **目标**：验证一批实际数据，从来源到发布覆盖闭环。
- **涉及文件**：docs/acceptance/data_batches/、有权限的人工导入/审核记录、coverage发布配置；受影响规范同步更新。
- **实现内容**：每次先创建独立BATCH-地区-年度-类型或学校-专业-届子Task，列有限源/预期字段/已知分母/许可/责任人；导入、抽查原文/代码/人群、审核发布/撤回并记录失败。
- **验收条件**：只验指定批次；数量/分母/字段/审核/失败可查；未知不算覆盖；原文/hash/许可不齐不发布；不将首批写成全国完整采集；不自动继续下一批。
- **测试方式**：所选类型离线回归、PG发布/撤回/幂等、领域负责人原文抽查记录及对应只读查询/UI检查；外网核验与离线测试分别报告。
- **依赖**：T19、T50及该批所需T51–T65；T66仅自动获取时依赖；D03/D08明确范围、使用权与审核人。

- **本次实施契约**：2026-10-13；单批候选审核清单和缺项阻挡判定；完成本批后停止；范围：services/api/app/statistics/batches.py, data/fixtures/reference/DEMO_batch_2026.json, services/api/app/outcomes/schemas.py。可测试标准：未知分母不能报全量；原文hash/许可/审核人缺失阻挡；合成不真实发布；观察日期不接受时间戳。本轮不执行检查。

- **简化源码完成记录**：2026-10-13；单批候选审核清单和缺项阻挡判定；完成本批后停止。源码/文档完成；原运行及真实发布验收未执行，保留：真实单批导入/原文/许可/独立审核/发布与撤回均未完成；原规划PG/运营/质量门槛保留，本批未执行任何检查。见[本次记录](acceptance/T67_20261012.md)。

## 历史推荐的下一实施 Task

2026-10-03当前：T01–T20及T49已完成，共21个主Task；其他46未开始。下一仅推荐T21来源与导入管理页面，先读当前文档并冻结管理接口/界面验收；本批已到T20，推荐不授权开始T21。以下T06阶段推荐与待决记录保留为历史，最新D01–D08以requirements为准。


T01–T06/T50A/E01及P00–P04已完成。下一推荐T07对象级授权基础，先冻结actor/action/owner/grant契约与矩阵；本轮完成T06后停止，推荐不授权自动开始。真实D04/D02/D06与公众发布门槛保留；T49仍需D06及正式身份上下文，全国T50后台仍依赖T11/T13，不能机械按编号或提前采集/发布。

## 已知问题与待决记录

- 未成年准入尚待用户/责任人决策；高中目标人群包含未成年可能性，不能无限期留空后上线。
- 国内参考资料目标年度2026、全国高校含大陆及港澳台已确认；个性化首个真实生源省份/项目、英国入学周期、审核负责人、模型/存储供应商、留存/SLO/RPO/RTO/预算、备案及其他适用事项仍待确定。D04身份已选自托管Keycloak，真实tenant/版本/地域、管理员MFA与恢复实际配置验收待补。
- M0 的固定 token、synthetic-only 模型、固定规则版本、单字符串日期、一项目一草案任务与 JSON 快照均是演示实现；按相关 Task 演进，不在本轮顺带重构。
- M0 /v1 conditional 草案没有完整的“申请期限＋后补期限”任务链；纳入 T27/T30 验收，当前不改代码。
- M0历史测试不是公众验收；T01于2026-10-01重新执行4项实库及96项离线回归，结果限M0。T50A仅候选登记校验，不重复运行应用/部署检查。
- 原 Git 未提交，沙箱所有权提示有历史记录；后续 Task 先检查实际状态，不修改全局 Git 配置或重置用户文件。
- D08目标年度2026和全国高校地域含大陆及港澳台已确定；首版全量门槛/批次/审核和使用权责任/投入待定。P02研究14条观察原年/届保留，无国内就业数值、无正式原文快照/发布，正式覆盖分子为0；不以旧年招生/培养填补2026缺口。各类公开程度不同，不能承诺每校每专业都有数据；详见data_strategy。

## P00 本轮规划验收记录（2026-10-01）

以下为 P00 历史记录，保持原结果；P01 的检查另记，不更新这些历史数字。

- **完成内容**：需求、固定技术栈、模块化单体、前后端/数据库/API/认证/文件存储/部署方案、目标目录与 49 个未开始的 Task；完成只读交叉审查。本轮到此停止。
- **变更文件**：增补 `README.md`、`AGENTS.md`；新增本目录的 `requirements.md`、`architecture.md`、`database.md`、`api.md`、`tasks.md`。应用代码、配置、依赖、迁移及原始规格未修改。
- **实际命令与结果**：`.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py`，退出码0，两份原始输入 SHA256 保持不变。PowerShell 以内联脚本向 `.\.venv\Scripts\python.exe -` 传入文档校验，退出码0：7 个 UTF-8 非空文档、20 个本地 Markdown 链接、49 个唯一 Task、294 项必填字段、143 条显式依赖边，依赖图无环。校验不访问外部 URL，也不执行应用。
- **Git 检查**：`git -c safe.directory=D:/Projects/study -c core.quotepath=false status --short`，退出码0；仓库文件仍全部未跟踪，不存在可比较的已提交基线，未更改全局 Git 配置，未自动提交。
- **未执行检查**：本轮未运行 pytest、前端测试/构建、PostgreSQL 实库迁移、浏览器或部署验证；M0 报告是历史结果，不能代表公众 MVP 通过。
- **已知问题**：D01–D07 的剩余决策、历史实库验证缺口及全部公众功能尚待完成；未成年准入待定。专业适用性审查、真实数据审核、供应商与运行验收均未完成。
- **推荐下一项**：T01 PostgreSQL 基线验证，当前未开始。

- **2026-10-12简化范围**：本批以[simplified_plan](simplified_plan.md)对应行及逐Task契约为源码完成标准；原目标/数据库/真实审核/运行验收不作已完成声明。默认真实关闭，测试/演练不执行，完成最小源码与文档后可继续下一项。
