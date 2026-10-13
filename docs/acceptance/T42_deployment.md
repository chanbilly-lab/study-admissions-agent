# T42 通用 Docker 源码完成记录（运行未验证）

2026-10-04：用户明确‘先做通用 Docker 配置’，按ADR-056完成调整后的通用源码范围。D01城市/供应商/手续继续待定，原平台适配依赖只对实际部署保留；本地配置不代表D01全部确定。用户‘不用测试’已优先执行，没有新增测试、Lint、TypeCheck、Build、预检或容器结果。

## 基线、阅读与源码范围

开始PRIVATE T41 `4009a36928c0b94864fbcaeab9aaa775a2866b42`、810tracked、空索引/干净工作区，分支codex/t42-deployment-prerequisites。先读AGENTS、README、requirements、architecture、tasks、CHANGELOG、DECISIONS、原始两份及docs01–05、API/DB/身份/存储/jobs/rights和相关代码/锁/Compose；恢复时保留前置9文档并阅读基础工厂、前端构建配置和18profile。新增`.gitattributes`部署LF规则是本Task必要范围，旧规则不变。

22路径（8旧治理/属性、14新文件），完整清单如下；其他业务源码、依赖锁、现有API/DB、M0 Compose、旧迁移/原文/旧验收不修改。未在用户追加不用测试后重跑保护哈希或文档校验；文件范围只通过必要Git diff人工审阅，不宣称脚本保护检查新通过。

- `.dockerignore`
- `.gitattributes`
- `AGENTS.md`
- `README.md`
- `deploy/README.md`
- `deploy/__init__.py`
- `deploy/compose.generic.yaml`
- `deploy/docker/api.Dockerfile`
- `deploy/docker/nginx.conf.template`
- `deploy/docker/proxy.conf`
- `deploy/docker/start-web.sh`
- `deploy/docker/web.Dockerfile`
- `deploy/migrate.py`
- `deploy/preflight.py`
- `deploy/target.pending.json`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T42_deployment.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/requirements.md`
- `docs/tasks.md`

## 提供的源码与边界

foundation/API与maintenance工具分离，API无DB凭据；web固定auth且同源TLS，NGINX UID10001、loopback入口及不信任Forwarded头。业务库和ledger分别私网/卷，运行API不接DB网络，worker关闭。外部秘密文件独立服务挂载，无默认密码；固定官方版本+摘要参数和原包锁。只读预检不连接网络/SQL且不等于发布检查，单链迁移须profile+--apply并限制目标/超时，无启动DDL、seed、downgrade或删卷。

实际镜像可构建/可复现、路径/模式、秘密/权限、网络、TLS、数据库、迁移/重启/回滚与最新台账重放均尚未验证。运行健康只声明基础进程，不表示业务或发布ready。维护初始化owner不是生产SQL最小权限；同主机卷不是灾备独立性；完整私有业务/Keycloak/worker/锚点没有装配。

## 当前实际操作与未执行

- `Get-Content -LiteralPath <相关源码/文档>`、`rg --files`/`rg -n ...`：读取当前状态与相关实现；没有运行应用或调用商业服务。
- `git -c safe.directory=D:/Projects/study -c core.quotepath=false status --short --branch`、`git ... diff --stat`、`git ... diff -- .gitattributes`及暂存diff：必要Git基线/源码保存人工审阅；不是测试通过证据。
- `.venv/Scripts/python.exe -X utf8 -B .cache/finalize_t42_source.py`：仅编辑T42文档，不执行验收校验。
- 测试/Lint/TypeCheck/Build/契约生成/原文哈希检查、`deploy/preflight.py`、Docker config/build/up/health、迁移与恢复：全部未执行（用户要求）。操作说明里的命令是未来步骤，不是本轮命令结果。

## 未验证事项与保存

D01实际平台/手续、真实TLS证书和UID/ACL、基础镜像存在/可信/兼容、包可安装和实际构建、Compose内网/loopback行为、18链迁移、日志秘密哨兵与30天清理、灾备独立台账/锚点、最小SQL权限和兼容回滚未验证。用户拒绝D07旧目标，没有RPO/RTO/容量及责任人替代；T44–T46不能假定通过。D08仅首批登记已确认，真实审核/发布责任待定。

T42状态已完成仅对应明确调整的源码范围；CHANGELOG/tasks/ADR-056及受影响规范同步。按PRIVATE持续授权仅暂存上述22路径，普通提交推送当前工作分支，实际提交SHA及远程核对在本轮最终报告给出；不提交秘密/.cache/产物，不强推、不部署。

## 以下为同日前置阶段历史记录

下方‘阻塞/9文档/未上传’和检查结果只对应用户选择通用源码之前，不表示当前状态；原文保留。后续范围以本页上文与ADR-056为准。

# T42 部署前置核对（阻塞，未完成）

2026-10-04：仅当前文档阶段；没有实现可构建部署配置，不称验收完成。本批逐个至T50授权保持，当前阻塞在T42。

同日用户追加“不用测试”：之后不运行自动测试、Lint、Type Check、Build或验收校验脚本。本次只同步这一执行要求，未修改应用；下方已执行结果属于追加指令前的版本，不作为本次更新通过的证据。D01仍待定。

## 基线与范围

PRIVATE T41 `4009a36928c0b94864fbcaeab9aaa775a2866b42`，810tracked/初空索引与干净工作区；新codex/t42-deployment-prerequisites。开始前读取39份治理/原始两份/docs01–05/API/DB/身份/存储/jobs/rights与当前源码/依赖/Compose文件，冻结[前置契约](../deployment.md)。7旧治理允许/803其他tracked保护，无应用/配置/依赖/迁移修改。

## 阻塞证据与解除条件

[原T42任务卡](../tasks.md)依赖城市/供应商及适用备案流程确认，且验收要求平台和地域符合D01；[requirements的D01](../requirements.md)及用户本批答复均为“待定”。不能由大陆目标推导具体平台/region，不能用本地合成环境代替未选平台的已适配结论。D07提案“不采用”已保留，未设置替代目标；D08只有限来源/覆盖登记已确认，真实审核发布负责人仍待定。

解除：明确D01实际城市/供应商/平台与流程责任，然后重读当前Git/源码/文档并实现；按用户最新要求跳过测试和Build，明确尚未验证的矩阵，不以源码实现冒充运行通过。构建引擎状态留待恢复验证后核实。T43–T50未启动；T49此前已完成，续批时不重复。

## 实际命令与结果

以下命令在用户追加“不用测试”之前执行；追加后的文档变更未重跑这些检查。

- `docker version --format '{{.Client.Version}} {{if .Server}}{{.Server.Version}}{{end}}'`：exit1。CLI29.8.1，Docker Desktop Linux Engine npipe不存在，Server版本不可读；不称镜像检查通过。只读取，不重装/重建/移动用户环境。
- `.venv/Scripts/python.exe -X utf8 -B .cache/check_task.py T42 --blocked`：exit0；9文档路径（7旧/2新）、803范围外tracked哈希不变、其他66任务卡和旧CHANGELOG/ADR保持、441本地文档链接存在，无源码/秘密/产物混入，索引仍为空。这里只通过文档阶段检查，不表示T42全部验收。
- `.venv/Scripts/python.exe -X utf8 -B scripts/verify_originals.py`：exit0；两原始输入均UNCHANGED。
- `.venv/Scripts/python.exe -X utf8 -B .cache/t42-status-check.py`：exit0；67主Task=42完成/1阻塞/24未开始，D01/D07记录与用户答复一致、当前HEAD仍为PRIVATE已核对T41，T42仅本地文档且索引为空。

## 未执行

应用Unit/Integration/TypeCheck/Build：未执行，当前没有应用代码变化，原卡部署前置未定；Lint/Python静态类型无配置入口。镜像构建、网络/健康、秘密哨兵、TLS、合成staging和回滚：未执行，没有T42Dockerfile/运行配置且daemon未连。真实资源/身份/SQL角色/学生/法律手续/采购/公开部署未执行，未授权本Task自动执行。

## Git与文件

仅以下9份文档本地改动；本Task未验收，按成功Task保存规则不暂存/提交/推送。没有重置索引、覆盖用户内容、创建可执行生产配置或变更M0。HEAD保持T41 PRIVATE已验证提交。

- `AGENTS.md`
- `README.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T42_deployment.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/requirements.md`
- `docs/tasks.md`
