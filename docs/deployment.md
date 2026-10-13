# T42 通用 Docker 配置契约（源码完成，运行未验证）

2026-10-04用户选择‘先做通用 Docker 配置’：仅本地隔离的配置源码，不代选实际城市/供应商，不采购或开放服务。D01中国大陆目标保持，具体region/city/provider和适用手续保留null/pending。按用户‘不用测试’，所有自动检查、Lint、TypeCheck、Build、预检及容器/迁移演练未执行。本Task完成表示源码范围完成，不表示构建、实际配置或平台已验证。

## 实施前冻结的契约与修改范围

- `.dockerignore`输入白名单、deploy的API/web Dockerfile、NGINX TLS模板/入口、独立Compose、target待定记录、有限preflight/显式迁移CLI和运行说明；部署Linux文件用`.gitattributes`保持LF。保护已有业务/锁/旧迁移/M0 Compose。
- 基础镜像由操作者提供官方固定版本和sha256，无虚构摘要/默认latest；Python哈希锁和pnpm11.19.0/frozen-lockfile复用。frontend固定auth，API固定production+verified+disabled。
- foundation仅/v2配置和空目录、不持有DB秘密；maintenance单独复制必要迁移源码。TLS只绑定host loopback；API、业务库、ledger各内部网络，两库各卷，秘密外部文件按服务挂载。
- worker只有关闭的声明元数据，没有占位服务；实际启用需私有业务装配、当前权限与受信独立台账/锚点证明。
- 固定18profile，迁移明确单链并--apply才执行；启动不DDL/seed，无自动downgrade/删卷。preflight只核输入语法/有界文件/密码与URI目标匹配/TLS密钥匹配，不能证明真实镜像/region/证书身份或运行。
- 源码与运行验收分开，以下矩阵全部未执行；现有T03/T40/T41历史合成结果不能替代T42新配置证据。

## 当前实现

| 内容 | 源码位置 / 行为 | 尚未验证 |
| --- | --- | --- |
| 目标 | deploy/target.pending.json：CN目标，city/provider/region=null，发布/worker/私有能力=false | 实际地域和手续 |
| API | foundation target只复制既有生产基础模块；无M0/seed/私有业务或DB秘密 | 安装/镜像/实际路径负例 |
| 前端/代理 | auth build、NGINX TLS8443、127.0.0.1发布、三同源前缀，不信任Forwarded | 构建、TLS/SAN/信任、实际路由 |
| DB/ledger | 分别内部网络和卷，初始化密码文件，API没有DB网络 | 私网实际效果、权限、迁移、灾备独立性 |
| 秘密 | 六个独立工作区外绝对路径按服务挂载，密码≥32字符，无源码默认值 | 容器UID10001/ACL、哨兵/日志、正式秘密服务 |
| 维护 | --profile固定白名单/--apply、固定DB目标、同事务upgrade head、有界超时/固定错误 | 18链可迁移、并发/故障及恢复 |
| 回滚 | 仅已知前一镜像与兼容配置说明；未知数据库兼容时关闭 | 实际回滚/恢复及T40水位重放 |

API/web/维护工具使用非root进程与readonly/tmpfs/cap_drop，PostgreSQL复用官方初始化入口；没有Docker引擎rootless验收。Compose文件secrets不等于加密vault或已验证ACL。日志只大小轮转，30天TTL未实现；同一主机不同卷不等于独立灾备，当前不能装配真实资料权利服务。没有Keycloak/worker/数据库运行角色/锚点已启用的结论。NGINX是必要的新代理镜像组件，无新Python/npm包依赖。

## 待运行验证矩阵（全部未执行：用户要求）

| 检查 | 未来应取得的证据 |
| --- | --- |
| 镜像 | 官方版本/摘要/架构、锁安装、镜像层无禁止内容、可构建与实际重复性 |
| 模式/路径 | production/verified/disabled，DEMO/mock/live/缺秘密/debug/v1/私有路径负例 |
| 网络 | DB/API/台账私网、只有loopback TLS、跨网络隔离、同源前缀 |
| 秘密/TLS | 容器权限、哨兵不泄漏、证书SAN/期限/信任、更新流程 |
| 迁移 | 17业务链与独立ledger、新库/head/权限/超时失败关闭 |
| 健康/关闭 | 进程健康不冒充业务ready、缺配置拒绝、重启状态 |
| 回滚/恢复 | 镜像兼容、数据保持、最新独立台账重放/缺水位拒流量 |
| 常规质量 | Unit/Integration/浏览器/Lint/TypeCheck/Build与契约/原文保护 |

源码操作和未执行记录见[T42记录](acceptance/T42_deployment.md)，未来人工步骤见[deploy运行说明](../deploy/README.md)。实际平台与D01门槛没有被通用源码完成消除；D07恢复/流量/责任目标未定，D08首批登记确认也不授权真实发布。ADR-055是同日前置阻塞记录，ADR-056仅替代其对通用源码开发的阻塞解释。
