# T66 禁用连接器契约

2026-10-12本批不选择真实自动来源。先固定服务器RegisteredEndpoint、无URL的ConnectorRequest和恒disabled策略，再实现plan_request纯拒绝报告。白名单至多10个、引用唯一，端点只做HTTPS/身份/端口/片段/字面IP/本地后缀语法拒绝；**语法校验不是DNS/重定向SSRF防护或官方/许可核验**。请求不能含任意URL、凭据、输出路径或transport选项，永不fetch、不创建candidate、无Jobs写入。

后续若明确选择一种有许可来源，必须另行实现管理员当前权限、HTTPS/DNS每跳重验、私网拒绝、MIME/大小/速率/超时/有限重试/幂等和暂停，并独立验证；当前不能启用live或自动发布。无绕登录/验证码/付费，M0不联网。测试/校验/任何输入调用/实际HTTP全部未执行（用户要求）。
