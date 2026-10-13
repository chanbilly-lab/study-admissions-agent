# T42 通用 Docker 源码运行说明

2026-10-04：配置源码已提供，下面命令均为**以后手动使用的说明，本轮未执行**。用户要求不运行测试、Lint、Type Check、Build和校验脚本；没有镜像、TLS、数据库、迁移、恢复或容器运行通过的结论。实际部署城市、供应商和手续待定，`target.pending.json`保留空值。当前配置只绑定本机回环地址，不是公众发布。

## 提供的服务

`docker/api.Dockerfile`的foundation target只复制T03的production基础入口，固定production/verified/disabled，拒演示，提供`/v2/config`和空目录。它没有数据库凭据、私有服务装配、Keycloak、worker、真实模型、招生事实或M0入口。web target构建auth模式Vue静态资源，通过TLS NGINX将`/api/`、`/public/`、`/qa/`同源转到基础API；后两类及私有功能没有在该API上装配，返回未提供接口的错误不能视作完整产品可用。`business_available=false`与web健康响应的`release_ready=false`始终保留。

`db`和`ledger_db`分别使用私网及独立卷，没有主机端口；foundation API不加入DB网络。两库初始owner属于初始化/迁移权限，**不是生产运行最小权限角色**。同一主机两个卷不等于灾备独立台账；T40受信锚点、备份外存储、SQL角色/GRANT及真实私有业务恢复屏障未装配。本配置不能启用这些业务。worker只有关闭状态的元数据，无可运行占位worker。

## 操作者需准备的输入

使用Docker Compose v2及Linux容器引擎，实际版本兼容性未验证。不要使用根`compose.yaml`的M0开发密码作为本配置输入。

| 环境变量 | 要求 |
| --- | --- |
| `PYTHON_IMAGE` | 官方`python:3.12.<patch>-slim-bookworm@sha256:<64位摘要>` |
| `NODE_IMAGE` | 官方`node:24.<minor>.<patch>-bookworm-slim@sha256:<摘要>` |
| `NGINX_IMAGE` | 官方`nginx:<固定三段版本>-bookworm@sha256:<摘要>` |
| `POSTGRES_IMAGE` | 官方`postgres:16.<patch>-bookworm@sha256:<摘要>` |
| `STUDY_API_IMAGE` | 本地版本标签`study-api:<版本>`，不用latest |
| `STUDY_WEB_IMAGE` | 本地版本标签`study-web:<版本>` |
| `STUDY_TOOLS_IMAGE` | 本地版本标签`study-tools:<版本>` |
| `STUDY_SITE_HOST` | 小写DNS主机名，证书应覆盖该主机；仅本地DNS/hosts映射 |
| `STUDY_HTTPS_PORT` | 本机TLS端口，默认8443；始终发布到127.0.0.1 |
| `STUDY_TLS_CERT_FILE` / `STUDY_TLS_KEY_FILE` | 外部绝对路径，PEM证书链与匹配的无口令PEM密钥，各≤1MiB |
| `STUDY_DB_PASSWORD_FILE` / `STUDY_LEDGER_PASSWORD_FILE` | 两个独立外部密码文件；强随机、至少32字符，单行无空白、≤4096bytes |
| `STUDY_BUSINESS_URL_FILE` / `STUDY_LEDGER_URL_FILE` | 两个独立外部迁移URL文件，各≤16KiB，按下述固定目标 |

版本和真实摘要由操作者从官方镜像仓库选取并保存实际解析记录，不提供虚构摘要或默认latest。预检只检查语法，不能证明摘要存在、镜像可信、架构兼容或构建可重复。Python复用现有完整哈希锁；pnpm固定11.19.0及frozen-lockfile，未增加包依赖。NGINX是本Task新增的反向代理镜像组件。安装Python/npm依赖时需要依赖源网络；离线机器需另行准备已审核缓存/镜像，不承诺无网构建。

密码、密钥及迁移URL不要写进仓库、Compose、Vite变量、日志或本说明。秘密文件放在工作区**外**，仅设置环境变量引用绝对路径；文件必须按服务可读。迁移URL使用`postgresql+psycopg`（也接受`postgresql`），主机/用户/数据库固定：业务为`db:5432`/`study_owner`/`study_business`；台账为`ledger_db:5432`/`study_ledger_owner`/`study_ledger`。密码与对应初始化文件一致，URL用户/密码需正确百分号编码；不接受query、片段、默认postgres账户或其他目标。密码建议用至少32字节随机值的十六进制编码，避免URI歧义。

Compose的[file型secrets](https://docs.docker.com/reference/compose-file/secrets/)通过文件挂载提供给对应服务；它不是加密秘密管理平台，不能靠`uid/gid/mode`配置声称已改变绑定文件权限。主机ACL/POSIX权限及非root UID10001读取TLS/迁移文件必须另验；[NGINX要求私钥可被master进程读取](https://nginx.org/en/docs/http/configuring_https_servers.html)。预检在主机读取成功不证明容器读取成功。不要公开TLS密钥，也不要将数据库密码挂给API或web。

## 未来本地启动步骤（未执行）

在仓库根目录的PowerShell进程内明确设置以上环境变量。文件引用示例：`$env:STUDY_TLS_CERT_FILE = 'D:/study-runtime-secrets/tls.crt'`；该路径只是示例，不表示已有文件或已选择部署地域。不给密码/URL样例值或自动生成/覆盖用户文件。

```powershell
# 只读输入筛查；不连接网络、SQL，不表示运行验收通过。
.venv/Scripts/python.exe -X utf8 -B deploy/preflight.py

# 未来允许构建/验证后再执行；本轮没有执行。
docker compose -f deploy/compose.generic.yaml --profile tools build api web migrate
docker compose -f deploy/compose.generic.yaml up -d db ledger_db api web
```

root `.dockerignore`采用构建输入白名单，排除.env、密钥、附件/研究数据、测试/夹具、.cache、备份、数据库/WSL磁盘和node_modules；maintenance复制迁移/模型所需源码，但排除M0入口/seed及旧M0迁移链。foundation仅复制固定基础模块，API/web/维护工具进程非root、readonly，配置tmpfs与cap_drop；PostgreSQL仍复用官方初始化入口，不声称Docker引擎rootless。源码规则不替代实际镜像层审阅；该审阅本轮未执行。`.gitattributes`确保Linux入口与配置在Windows checkout保持LF。

未来本机访问`https://<STUDY_SITE_HOST>:<端口>/`，基础配置为`/api/v2/config`。证书SAN、期限、客户端信任及同源链路应另验证；预检只核证书与私钥匹配，不能声称TLS身份已通过。反向代理不信任/转发客户端Forwarded类头；完整OIDC固定origin/proxy信任需后续服务装配，不能靠该代理默认获得认证支持。

## 显式迁移（未执行）

维护镜像默认只显示help；业务启动不DDL/seed。只允许从固定18profile中明确选择一条，必须`--apply`；同一事务升级该链head，连接5秒/语句120秒/锁10秒上限，失败只固定错误码，不打印秘密URL或SQL诊断。超时失败须人工检查并恢复，不自动猜测已完成。

```powershell
# 台账使用自己的工具服务和秘密，不能通过业务库服务执行。
docker compose -f deploy/compose.generic.yaml --profile tools run --rm ledger_migrate --profile rights_ledger --apply

# 先逐条迁移业务依赖；以下是第一条命令，其余按顺序替换--profile。
docker compose -f deploy/compose.generic.yaml --profile tools run --rm migrate --profile auth --apply
```

业务顺序：`auth → catalog → storage → idempotency → imports → evidence → facts → reviews → releases → profiles → assessments → plans → execution → changes → revisions → jobs → rights`。最后rights链核前16head；不自动运行整个列表。维护角色只用于该隔离新库，既有未知数据或head不得直接尝试。已有迁移原样保护，M0链不在工具白名单。DDL完成也不生成初始管理员、授权、同意、真实事实或台账锚点，不会开启业务。数据库初始化秘密仅首次空卷生效；修改密码文件不会自动轮换已有数据库密码。

## 停止、回滚与后续门槛

未来可用`docker compose -f deploy/compose.generic.yaml down`停止本地配置，**不加`-v`**。不存在本轮实际启动需清理的容器/卷。回滚API/web需明确保存前一镜像摘要/配置及数据库兼容结论；确认后改版本引用再替换服务。不提供自动downgrade、删卷、重置库或回滚用户资料的脚本。

已迁移数据库无法证明旧程序兼容时，保持业务关闭，另行按T44验证恢复与最新删除/撤权台账重放；不能直接将旧备份接回服务。当前没有执行备份/恢复、RPO/RTO或容量测量，D07目标和责任人待定。json-file日志只按大小轮转，不实施D06的30天TTL，也不保证所有NGINX/驱动错误已脱敏；需要实际日志哨兵验证与清理流程。本配置无秘密管理平台、证书续期、生产权限/备份/监控或公网防护完成的结论。

完整状态见[源码记录](../docs/acceptance/T42_deployment.md)和[部署契约](../docs/deployment.md)。所有测试/Lint/TypeCheck/Build/预检/镜像与容器演练本轮未执行（用户要求），真实处理与公众发布关闭。
