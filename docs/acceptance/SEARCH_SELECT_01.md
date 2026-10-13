# SEARCH-SELECT-01 源码交付与未验证记录

日期2026-10-14，Asia/Hong_Kong。用户要求学校/专业搜索选择替代手填UUID，缺失不编造、仍不测试、文档后PRIVATE上传。

## 基线与完成范围

Git基线457947c8cab6f00e7133c067d625144d957b24c4，原codex/ui-workspace-polish；开始工作区/索引无改动。当前codex/school-program-selection。实施前契约及后续启用约束见[搜索选择](../school_program_search.md)。完成的是12个代码文件及相关文档，真实目录装配/运行验收未完成。

后端新增两个有界GET与具体PublishedDirectoryReader：SQL按字面名称/国家/父学校过滤，按身份UUID去重排序后分页；依托T20当前formal发布、源/证据与时限证明、水位和末次配置核对。默认None空目录、无新目录DB访问；不读取研究候选/DEMO/浙江省线来造选项。identity_evidence_entry_year只记录身份来源招生年；不用于推断培养/毕业届。

前端新增独立闭合TS/64KiB/15秒目录client、显式搜索/原生级联选择、两级取消/generation/分页水位，父用途与资料条件有本地context_key pin防迟到事件。培养仅已选program.id；毕业学校/专业各自准确subject_ref，学院/学科暂无身份字典时禁用。旧手填UUID/subject_ref UI移除，目录未启用/无匹配/失败/选择失效则无法查询；选身份不表示当届资料存在。原数据查询API/客户端、统计页/M0/旧生成契约、表及迁移均不改。

## 静态审阅与实际操作

- 实际执行Get-Content/rg：必读治理、两份原规格相关段、T11/T20/参考模块与前端源码；Git状态/分支/log/实际diff与当前Task文件内容审阅。
- Root与两独立代理仅阅读审阅，未发现未解决的必修问题；当前proof重新校验hint姓名/country/父级、游标base64url/filters/水位、20条上限、带前导空格DEMO名拒绝、HTTP422/409/503边界及HTTP404不冒充目录缺失均已核对源码。
- 前端本地事件purpose/context_key不发给HTTP；父条件修改立即取消资料请求/清选，旧child上下文回调被拒绝。同名不同UUID不合并/自动选首项；可核对来源招生年和身份信息。
- 关键词Enter加入composition/keyCode229守卫，不在中文组合输入时触发搜索；普通Enter只显式搜索目录、阻止父数据表单隐式提交。仅阅读源码，IME行为未验证。
- **未执行（用户要求）**：Unit/Integration/浏览器测试、Lint、TypeCheck、Build、compile/import、生成/校验/验收脚本、CI、SQL/新HTTP/分页/撤回/时限/并发/跨年/真正迟到响应/移动/键盘/视觉演练。
- **未执行**：部署、数据库/迁移、正式身份来源装配、原服务重启、真实学校/专业导入与采集/审核发布。旧运行实例不会自动加载新Python路由；本批未声称新搜索正在运行。
- 实测通过数：未执行；只源码交付，不使用旧UI或T20历史通过作为新结果。

## 修改文件（27）

1. services/api/app/reference_directory/__init__.py
2. services/api/app/reference_directory/schemas.py
3. services/api/app/reference_directory/reader.py
4. services/api/app/api/reference_directory.py
5. services/api/app/api/reference.py
6. services/api/app/api/local_reference.py
7. packages/contracts/referenceDirectory.ts
8. apps/web/src/features/reference/directory/client.ts
9. apps/web/src/features/reference/directory/useDirectorySelection.ts
10. apps/web/src/features/reference/directory/SchoolProgramPicker.vue
11. apps/web/src/features/curricula/CurriculaView.vue
12. apps/web/src/features/outcomes/OutcomesView.vue
13. docs/school_program_search.md
14. docs/acceptance/SEARCH_SELECT_01.md
15. AGENTS.md
16. README.md
17. docs/tasks.md
18. docs/CHANGELOG.md
19. docs/DECISIONS.md
20. docs/requirements.md
21. docs/architecture.md
22. docs/api.md
23. docs/database.md
24. docs/reference_api.md
25. docs/reference_workspace.md
26. docs/data_strategy.md
27. docs/ui_optimization.md

## 剩余问题与停止

默认目录尚未启用，没有真实可选择项。英国两校研究仅候选，不能绕审核填入；旧培养/毕业接口仍空，目录选项存在也不提供实际统计或当届培养。学院/学科、官方代码/别名/拼音/校区标签与完整覆盖未实现；同名对象需核对来源身份，不猜校区或拼接UUID。

查询依赖既有T20内部当前证明方法，未来T20变化须同步适配；真实SQL搜索/分页/Unicode大小写/版本变化/取消/DOM与类型构建未验证。身份选择证明不是长期授权，后续真实资料reader仍须逐次核对对象、年份、公开许可与当前证据，不信前端选择结果自报授权。

文档与任务状态同步后，仅本Task27个必要文件普通提交推送到已授权PRIVATE origin；不启动测试、服务/迁移/采集/后续任务。核对远程SHA后停止。
