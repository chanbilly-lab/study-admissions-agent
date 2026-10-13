# T44 最小合成备份源码

2026-10-12：用户要求简化并逐个推进剩余 Task 到 T67；本任务仅提供下面的源码能力。按照“无需测试”的要求，测试、Lint、Type Check、Build、运行校验、加密备份或恢复演练均未执行。原 T44 的生产恢复验收不由本次源码替代；D07 的 RPO、RTO、负责人保持待定。

## 实施前冻结的数据契约

- `BackupPolicy` 默认 `disabled`；仅显式 `synthetic` 可用。调用者提供已经确认是合成资料的内存 `bytes`，本模块不查询数据库、不遍历文件、不收真实资料。合成标签是开发范围声明，不能证明任意字节不含真实资料。
- 固定二进制包为 magic、4 字节 metadata 长度、闭合版本 metadata、12 字节随机 nonce、AES-256-GCM ciphertext/tag。密钥必须为调用者提供的 32 字节，不写入包、日志、配置或文件；复用现有锁定的 `cryptography`，不加依赖。
- metadata 仅含版本、随机备份 UUID、UTC capture/expiry、原始大小、SHA-256 和固定合成/未验证/未开放状态；metadata 作为认证附加数据。payload 为 1 byte–10 MiB，metadata 最多 4 KiB，expiry 晚于 capture 且最多 35 天。该上限复用 D06 产品期限，不是 RPO/RTO 或法定期限。篡改、错误密钥、重复字段、过期、未来 capture、超限整体拒绝，不截断。
- `DatabaseTarget` 只接受 loopback、明确端口和 `t44_synthetic_` 数据库名。固定 `pg_dump`/`pg_restore` argv 仅为维护计划，不调用 shell/subprocess、SQL 或文件写入；目标必须与来源不同，计划还要求维护者实际证明目标为空，不能用命名约定或勾选声明当核验。没有 clean/create/force 或覆盖真实/未知库的入口。
- 解密返回合成 bytes 不意味着恢复完成或流量就绪。恢复之后只能由服务器内部、已装配的真实 T40 `RightsGuard` 建立固定维护上下文；复用其 `validate_configuration()`、`replay()`、`ensure_ready()`。缺台账/锚点或水位不匹配沿原 guard 关闭，包的完整性不能证明最新授权。无 guard、不同目标或配置漂移拒绝；即使重放成功，返回仍为 `traffic_ready=false`，没有启用服务 API。

## 修改范围

仅新增 `deploy/backup/__init__.py`、`archive.py`、`maintenance.py` 及本文档。旧迁移、T40 guard/ledger、默认工厂、前端、依赖锁和真实配置不改。治理、Task 状态及 CHANGELOG 由当前任务负责人同步。

## 可测试验收（本批全部未执行）

| 项目 | 预期 | 当前结果 |
| --- | --- | --- |
| disabled 模式 | 零加密/解密、无文件或数据库工作 | 未执行（用户要求） |
| 合成 round trip | 精确恢复原 bytes/大小/hash、随机 nonce | 未执行（用户要求） |
| 包/metadata/ciphertext 损坏、错误密钥 | 固定错误，不能泄露原内容或钥匙 | 未执行（用户要求） |
| 重复字段、超限、过期、capture 在未来 | 整体拒绝 | 未执行（用户要求） |
| 非 loopback/未知库/相同来源目标 | 无维护计划 | 未执行（用户要求） |
| A 备份、B 删除、恢复 A | 服务器最新独立台账重放 B 后仍需流量装配门槛 | 未执行（用户要求） |
| 缺台账/锚点/水位及配置漂移 | T40 guard 关闭；包 hash 不能绕过 | 未执行（用户要求） |

## 未来维护步骤与剩余门槛

未来操作者先取得专用合成库授权，确认来源只含合成数据、准备外部 PG 凭据、独立台账/锚点与新空恢复目标，再读取维护计划。计划中的 `--no-password` 避免交互提示；凭据由维护环境的外部 `PGPASSFILE` 等机制准备，不进入 argv。本模块没有执行器，不能把计划当已备份或已恢复。

真实 dump、文件范围清单、密钥托管/轮换/ACL、备份到期物理清理、台账灾备独立性、生产 SQL 最小权限、RPO/RTO、实际 restore 与服务恢复均未实现或未验证。35 天 expiry 只拒绝交付过期包，不证明磁盘副本已删除。没有演练时间证据，不宣称达标或公众服务可用。
