# T21 来源与导入管理工作台

2026-10-03实施前冻结；来源/导入依赖已验收，仅当前Task。真实资料及公众发布门槛保留。后续审核/发布属于T22。

## 数据契约

独立 `create_admin_v2_app` / `create_admin_app`，复用identity认证路由/安全中间件，旧foundation/identity/public_catalog/M0不改。默认无服务：身份与管理业务503，基础config可读；不连接库/创建表/读.env或调用模型。显式内部装配验证所有service同AuthService/engine/runtime。

| 方法与路径（挂载/v2） | 输入 / 输出 |
| --- | --- |
| GET /admin/context | 无参数；当前服务器强data_admin/MFA通过才返回schema_version=v2.t21、can_manage_sources/can_import、is_synthetic；学生/operations拒绝 |
| POST /admin/sources | source为T13 SourceCreateInput、expected_dataset_revision正整数、confirmed原生true；返回来源版本剔责任账号UUID，并加当前dataset_revision |
| GET /admin/sources/{source_id} | UUID、可选严格正version；返回来源版本和当前dataset_revision |
| PUT /admin/sources/{source_id} | definition、expected_dataset_revision、expected_source_version、confirmed=true；CAS失败409，不覆盖旧版 |
| POST /admin/source-files | source_id/source_version、filename、content_type(application/json或text/csv)、content_utf8、confirmed=true；只UTF8净字节≤1MiB，返回T14 FileData，无路径/键/owner |
| POST /admin/imports | T15 ImportRequest封闭字段及confirmed=true；唯一Idempotency-Key头；返回T15 ImportResult |
| GET /admin/imports/{import_id} | UUID，无其他参数；当前权限与exact原文件证明后返回最少结果 |

所有写入复用固定Origin/会话CSRF与服务端执行时强管理员；浏览器角色/owner不授权。JSON流式有界、不无限request.body、重复键/额外字段拒绝；保留content_utf8原BOM/CRLF/空格，不parse重写原文。上传只同步导入所需CSV/JSON；原文不改写并不表示所有UTF8内容可存储：既有T14严格JSON校验拒绝带BOM的JSON，不自动去除BOM。T14内部PDF隔离能力保留而不新增PDF抽取。

许可三用途分开；claimed_official只是声明。URL只文本登记，不导航/DNS/fetch。输出来源元数据不是发布资料；文件quarantined不是安全或审核证明。staged=draft/unresolved未发布，rejected=零候选，结构未知总量仍null；错误仅行号/field/code，不回显原坏值。

## 修改范围

新增admin HTTP schemas/router/facade/factory及独立生成profile、当前auth页面挂载新admin视图/业务组件与客户端，相关专项/端到端测试和治理文档。无新依赖/迁移/架构技术栈变更。首次HTTP暴露T15时，若末端鉴权SQL等待跨文件/来源期限，必须在同事务COMMIT前再证明；仅修该一服务文件并新增等待回归，不顺改其他旧问题。

前端仅服务器context成功才展示操作；退出/换主体/范围/文件/内容变化清空私有回执、确认、幂等上下文，旧响应不能覆盖新状态。确认默认false，失败不报成功；不写localStorage/sessionStorage。

## 验收与测试

默认关闭无DB/外网；合成当前强管理员来源登记→原文隔离→候选导入/错误回执闭环；匿名/学生/operations/陈旧MFA直接HTTP拒绝；Origin/CSRF/额外owner/role/重复header/坏类型拒绝。SourceCAS/URL零访问、字节精确保留/尺寸和UTF8边界、坏行整批零写、receipt幂等、源版本/许可/期限改变失败、审计失败回滚及末端等待跨期限验证。

Vue组件/客户端/状态竞态、真实本机HTTP与合成隔离PostgreSQL端到端；相关后端回归、契约漂移、Type Check、demo/auth Build及文件保护。未配置Lint/Python静态类型入口则标未执行，不以compile代替。实际结果另记[T21验收](acceptance/T21_admin_workspace.md)。
