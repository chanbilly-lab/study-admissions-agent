# UI-OPT-01 源码交付记录

2026-10-13，Asia/Hong_Kong。用户要求UI优化及其他优化建议；此前“不用测试”继续适用。本Task完成的是展示源码与文档，新的实际布局/交互/构建均未验证。

## 基线、修改和审阅

Git基线7a41279e247f90879f70d32db8688a847e02b787，codex/annual-source-updates；开始工作区与索引无改动。当前工作分支codex/ui-workspace-polish。事前契约及后续优先项见[UI优化](../ui_optimization.md)。

已完成：青绿/浅底共享样式、较大的正文/帮助文字、主要按钮和原生展开控件44px最小高度、焦点轮廓；M0仅从现有状态派生四步提示、处理中提示、筛选外仍选项目数量与显示全部入口；未连接不将未知项目总量显示为0；缺失期限/生源范围措辞不推断未公布或不适用。成绩表保留成绩/满分/实得预测及可聚焦横滚区域。

演示证据采用现有公共证据组件的generation/焦点恢复模式：加载/原文先展示、关闭按钮可聚焦、卸载/状态变化拒迟到打开；原合成证据/字段/后端授权不变。

参考页有模式页头、三类native按钮导航、主筛选/可选细分口径与独立主操作；结果短读屏状态与完整证据分开。三条省线卡片突出原线名/分数/用途，原文与技术hash可展开，官方来源/原公布时间/本地复核范围和关键未知仍显示；未填真实值、学校或覆盖率。培养与毕业资料未接入的缺口说明常显，已知UUID/对象查询作为高级入口保留。

静态独立审阅未发现未解决的必修项：新computed仅读当前state、原请求/默认筛选/四态/确认/身份切换/取消/迟到保护保持；无新包、模型调用、API/DB/worker/源文件变化。CSS共享影响三个入口，auth/admin等scoped样式仍存在；实际效果未知，不能视作全页面视觉验收。

## 实际操作与未执行项

- 实际执行：Get-Content/rg读取必读文档、两份原规格相关段、前端源码；Git状态/分支/log/实际diff阅读与当前Task内容审阅。view_image只读取此前E02和浙江批次已存在截图，用于设计基线，不是本次新截图或新UI验证。
- 旧截图：`.cache/e02-demo-20261013-518aaaae/m0-workspace.png`、`.cache/zj2026-db-20261013/zj2026-query.png`；不提交Git、不当作新通过证据。
- **未执行（用户要求）**：Unit/Integration/浏览器测试、Lint、TypeCheck、Build、验收/校验脚本、CI、编译/import检查、新浏览器打开/交互/截图/对比度测量及移动演练。
- **未执行**：API/数据库/迁移/年度worker/部署操作。本Task没有相应业务改动，已有运行状态不重新核验。
- 测试数量/通过结果：未执行；不能使用旧浏览器成功记录证明新UI。Git提交推送属于源码保存，不是应用验收。

## 变更文件（16）

1. apps/web/src/App.vue
2. apps/web/src/styles.css
3. apps/web/src/components/EvidenceDialog.vue
4. apps/web/src/features/reference/ReferenceView.vue
5. apps/web/src/features/statistics/StatisticsView.vue
6. apps/web/src/features/statistics/CutoffResults.vue
7. apps/web/src/features/curricula/CurriculaView.vue
8. apps/web/src/features/outcomes/OutcomesView.vue
9. docs/ui_optimization.md
10. docs/acceptance/UI_OPT_01.md
11. AGENTS.md
12. README.md
13. docs/tasks.md
14. docs/CHANGELOG.md
15. docs/reference_workspace.md
16. docs/requirements.md

## 已知问题及停止

本批界面/移动/读屏/焦点/缩放/对比度和TypeScript/构建未验证，不能宣称WCAG达标。省线表改卡片、hash折叠改变DOM，未来恢复浏览器检查时原测试选择器/展开步骤需要适配；当前未修改旧测试或报告。

培养/毕业仍缺真实学校/专业名录和事实；英国候选仍未发布、年度worker仍关闭，UI不能补齐这些业务门槛。后续优先可搜索对象名录、审核/覆盖状态及年度维护待办页面；必须明确API/权限，不在本Task顺便实现。原M0/本地参考/正式私有入口分开；无硬编码跨端口跳转，不处理真实学生、不部署。

CHANGELOG/tasks及参考说明同步后，仅当前16个已审阅文件PRIVATE普通提交推送，核对远程SHA后停止。
