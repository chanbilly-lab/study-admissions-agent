# T45 最小观测及纠错契约

2026-10-12：本批按用户要求仅完成最小源码；测试、Lint、Type Check、Build、校验、故障及告警演练均未执行。T45 原公开监控、正式纠错入口和负责人验收保留未验证。

## 实施前冻结

- `ObservabilityPolicy` 默认 `disabled`，仅显式 `synthetic` 可以采样。没有启动挂钩、HTTP endpoint、网络 exporter、告警外发或生产资料记录。
- 固定指标 `request_count`、`error`、`duration_sum`、`duration_count`、`qualification_unknown`、`review_backlog`、`job_failures`、`model_cost`；只允许固定 component 和 outcome。API 不接任意标签字典、URL、路径、request ID、用户 ID、画像、机构或专业名称。component/outcome 不是权限证明。
- 除 `review_backlog` 为最近一次显式观测整数 gauge，其余为非负整数累计；耗时总量以毫秒计，模型成本仅为合成预算微单位，币种/实际账单未知，不当作人民币。只提供 sum/count，不输出 P50/P95 或实际容量结论。每个增量有界，累计溢出明确拒绝；进程锁保护有限集合，重启后丢失，不冒充全局聚合。
- snapshot 保留固定依赖 `database`、`ledger`、`storage`、`identity`、`model` 均为 `unknown`；本模块不主动探测。空指标表示未采集，不能判为零错误或健康。`release_ready=false` 始终保留。
- 纠错候选仅固定 `category`/`state`/合成标记，不接自由文本、学生资料或发布事实。纯转换为 submitted→triaged/rejected、triaged→resolved/rejected；终态不能反复转换。resolved 只表示候选流程标记，**不表示事实已修正、已重新审核或已发布**。没有身份/权限路由、资料访问、自动撤回事实或 T34 影响重算。

## 文件范围

只新增 `services/api/app/observability/__init__.py`、`metrics.py` 和本文档，不修改 T10 的脱敏日志输出，不引入依赖、迁移、前端或服务端路由。

## 将来可执行案例（本批未执行）

| 案例 | 预期 | 结果 |
| --- | --- | --- |
| 默认关闭 | 不记录任何指标，snapshot 明确 disabled | 未执行（用户要求） |
| 任意 URL/user/画像标签或未知 metric | 固定错误，不写入 | 未执行（用户要求） |
| 并发增量和累计边界 | 锁保护，超限不部分写入 | 未执行（用户要求） |
| 未采集 / 依赖故障 | 空指标与 unknown，不误报健康 | 未执行（用户要求） |
| 未知纠错分类、非法跳跃、终态转换 | 拒绝，不能自动更改事实 | 未执行（用户要求） |

## 未验证及后续

请求中间件、规则/审核/作业采样接缝、持久指标、外部监控、正式告警与响应责任、纠错权限和审计、发布撤回流程、SLO 及法律处理渠道均未装配或未验证。D07 目标/负责人待定，不使用此前被拒绝的提案。线程锁与有限基数为源码实现，不声称已测试并发正确或生产可用。
