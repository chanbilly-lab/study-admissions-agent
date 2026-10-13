# T41 隐私、授权与本人权利工作台

2026-10-04代码前冻结，现源码与合成隔离验收完成；仅本Task，本批T50停止。T40已PRIVATE保存；D01待定、D07旧提案拒绝且替代目标待定；T50首批34地区×2026登记已确认，真实审核/发布责任待定。只合成离线与隔离实库浏览器，正式处理关闭，无依赖/API/DB变更。

## 数据契约与修改范围

新增views/SettingsView组合现有PrivacyPanel/SharingPanel与默认折叠的RightsPanel；AuthView只替换两个面板为组合并转发原本人准入/会话事件。原notice版本/hash/本人成年声明/core撤回和共享独立接受/精确撤权逻辑复用，不改后端或旧wire。

rights client只消费T40生成RightsContext/RightsRequestData/ExportContent，不扩authority。固定同源/api、Cookie/no-store/redirect error、写即时CSRF/JSON `{owner_confirmed:true}`；无owner/payload/handler/路径输入。16KiB请求上限由旧服务保留。闭合runtime验证、UUID/kind精确绑定、有限状态与UTC日期、原UTF8 size/SHA/短期expiry、完整export JSON对象；拒畸形/不一致/过期响应，不显示原始服务错误或注入HTML。导出<=10MiB只明确当前下载，临时Blob/objectURL及时撤销。

没有自动poll/重试/写入；展开后读取能力，登录身份当前且enabled才能显式确认提交。导出与删除分别checkbox，提交/身份/范围变化清确认。已受理、正在处理、失败/取消、在线清理完成分开；只有T40 completed+online_cleanup_complete显示在线完成，仍说明最小责任记录24月/备份35天并非所有副本已清。失败固定原因/受理ID/在线30天期限可追踪；明确读取状态，重载后可输入本人受理UUID（仅标识，不收姓名/生日/证件/成绩），服务器越权404。无worker启动或浏览器轮询。

core撤回与权利访问分开，仍可本人查阅/删除；删除受理立即通知AuthView清当前画像/计划/准入并重新读现有privacy/sharing，不能旧结果重新开放。共享撤权复用原组件当前状态与清缓存。所有权利状态/原内容只内存；actor/expiry/synthetic标记变更、退出/卸载/收起、401/403、坏响应时清内容+abort+generation拒迟到，真实completed200迟到也不接收。本地会话/工件到期计时只清内存/abort旧请求，长时限分段重核，卸载取消计时，不发网络请求。无local/sessionStorage/IndexedDB/原内容日志；终止浏览器请求不取消已受理后台删除。

只改8旧治理/AuthView路径；新增privacy/rights客户端、状态、面板、SettingsView、新前端测试与专用PG/Edge验收脚本。保护其他tracked/所有旧profile/旧迁移/M0/原文；不顺带修旧面板文案或架构。

## 可测试验收

客户端：严格所有字段/false completion/固定错误/UUID-kind/SHA/限额/TTL、当前CSRF/same-origin、无owner/任意URL/自动write。状态：两明确确认、默认折叠/关闭/匿名零写、pending/failed/completed/取消、core撤回仍权利入口、身份变化/卸载/401/403/等待后迟到清理、零浏览器缓存。组件：键盘可读summary/checkbox/button、原版本/文本复用、最少保留说明、受理不等全部删除、下载明确按钮。

实际隔离PG+HTTP+Edge：本人/他人、撤回即时旧画像拒绝、本人导出及UUID越权、删除pending→故障failed/追踪→可信worker完成、退出后实际后台继续；键盘展开/确认/提交/追踪，真实HTTP200延迟跨身份清理。完整前端/TypeCheck/demo-auth Build、相关T40契约/Python、12profile/M0/原文与范围检查；Lint/Python静态无入口未执行。生产供应商/学生/法律/部署不执行。

结果见[验收](acceptance/T41_privacy_workspace.md)。
