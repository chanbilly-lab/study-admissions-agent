# T43 手动 CI 契约（源码完成，未执行）

2026-10-04，用户要求逐个到T50，继续不用测试。本Task只实现CI配置与未来运行工具，不触发本地或GitHub检查；源码完成不表示门槛已启用或运行通过。

## 数据契约、范围与验收

- `.github/workflows/quality.yml`只workflow_dispatch，execute_checks默认false，只有用户以后明确启用才运行；无push/pull_request/schedule触发，不部署、不上传数据工件。
- 只读contents权限，checkout不留凭据；官方checkout/setup-python/setup-node固定commit SHA，2026-10-04通过官方仓库tag API读取，非测试。
- Python复用现有哈希锁，Node24.19.0/pnpm11.19.0复用项目版本；依赖安装可用网络，测试进程限制loopback/本机socket，无商业密钥或真实学生资料。
- 合成PG16镜像必须明确固定版本+sha256；未来流水线仅自己的随机密码、loopback55438和独立容器/临时schema。CI绝不使用本机.env或已有数据库凭据。
- 固定十二contract profile逐项--check、M0契约/原文/问答golden、pure及有限关键PG/HTTP、Vue测试/类型/双模式Build。任何非零退出停止，不以平均通过率替代。
- PG关键门槛报告不能零用例/跳过；原有Windows浏览器/pg_dump路径不改，实际浏览器和完整恢复接入待完成。Lint没有现有入口，不引入框架充当已执行。
- 不修改API/DB/旧迁移/业务/依赖或原契约；新增workflow、scripts/ci工具和本Task文档。运行/负例/分支保护验证均未执行；没有实际‘阻止合入’结论，仓库branch protection不修改。

未来验收案例：正常分支报告、有意contract漂移、坏迁移、关键PG跳过/零用例、越界网络、失败stage停止、无秘密工件。全部未执行（用户要求）。

## 当前配置与未来使用

固定四stage：`contracts`（12profile/M0/原文/golden）、`pure`（六类现有离线目录）、`postgres`（18链独立schema、关键四态/执行/问答/本人权利PG与HTTP）、`web`（现有Vue测试/类型与demo-auth Build）。PG关键JUnit零用例、skip、错误或失败均拒绝，不静默回退SQLite。PG容器名字和密码随机，只有成功创建的本次容器才在finally移除，不访问本机库、不删除未知容器；容器不挂生产卷。

本轮没有执行workflow、安装依赖或运行上述stage。以后恢复检查时，需审阅workflow并在GitHub手动选择`execute_checks=true`及真实官方PG16固定摘要；这只恢复该次合成检查，不部署/开放业务。workflow_dispatch入口还需工作流存在于默认分支，本批不合并main，也不改branch protection；因此当前不能宣称每次改动自动检查或失败已阻止合入。恢复自动push/PR门槛需后续明确启用与分支规则配置。

Actions固定SHA依据官方仓库tag API读取：[checkout v4.2.2](https://github.com/actions/checkout/tree/11bd71901bbe5b1630ceea73d27597364c9af683)、[setup-python v5.6.0](https://github.com/actions/setup-python/tree/a26af69be951a213d495a4c3e4e4022e16d87065)、[setup-node v4.4.0](https://github.com/actions/setup-node/tree/49933ea5288caeca8642d1e84afbd3f7d6820020)。没有运行这些Actions验证当前runtime可用性。

测试进程的pytest插件在session开始限制socket/DNS为loopback/本机；这是Python进程边界，不声称阻断任意子进程网络或已验防火墙。安装/镜像下载仍需网络。JUnit只留CI临时目录、不上传数据工件，失败只显示固定stage错误，测试日志限合成夹具。旧Windows浏览器/恢复路径不做无关重构，关键HTTP门槛不能替代实际浏览器、pg_dump/restore或真实领域验收。
