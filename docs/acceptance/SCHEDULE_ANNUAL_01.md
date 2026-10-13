# SCHEDULE-ANNUAL-01 源码交付与未验证记录

日期2026-10-13，项目时区Asia/Hong_Kong。用户确认每年11月1日09:00 Asia/Shanghai生成待采集/待审核批次，并再次明确仅源码完成、文档同步、PRIVATE保存，仍然不用测试。

## 范围与源码审阅

基线b8b85097a1c37e6d9a702b93f73bd4ffdbd85c05，原分支codex/uk-2027-sources，开始工作区/索引无改动；当前codex/annual-source-updates。事前契约、运行命令及未运行用例见[年度调度](../annual_source_updates.md)。只新增独立公共资料请求模块，保留旧私有jobs、禁用连接器、M0/浙江记录、API/前端/旧迁移和锁文件。

完成静态源码审阅：配置默认关闭、独立时区与年度偏移、aware时刻/DST拒绝、最新到期周期补偿、稳定年度自然键/UUID、同事务全批请求、提交后回执、同年配置冲突、维护角色/显式专用DB/public/head、固定失败码/有界退避与退出。生成的是awaiting_collection请求；尚未有候选资料时不会伪称awaiting_review或已审核。后续采集产生候选、人工审核/发布沿用原治理；当前网络/事实更新/发布恒false。

独立只读审阅发现新SQL JSON CHECK缺键可因NULL被接受，已在本Task models/新迁移改为整组IS TRUE，并明确年份/字段与列绑定；重新阅读源码确认一致。没有运行SQL、导入模块、编译或执行校验来证明效果；这项修正不属于实测通过。

## 实际操作 / 未执行

- 实际执行：PowerShell Get-Content、rg用于必读文档/源码阅读；`git -c safe.directory=D:/Projects/study status --short`、branch/log/index/实际diff审阅；创建当前codex工作分支。技术参考读取Python3.12 zoneinfo/threading与SQLAlchemy2.0 PostgreSQL官方文档，不是联网测试或数据采集。
- **未执行（用户要求）**：Unit/Integration/浏览器测试、Lint、TypeCheck、Build、compile/import、验证器/验收脚本、CI。
- **未执行**：新DB创建、角色/GRANT、Alembic upgrade/downgrade、CLI plan/tick/run、并发/事务/重启/时钟边界/信号与故障演练、外网采集、实际定时服务安装/后台启动。它们均没有通过或失败结果，不能借用旧M0/浙江验收。
- 测试数量及运行验收结论：未执行、未验证；本Task状态“已完成”只指最新授权的源码/文档交付范围。

## 修改文件（23）

1. services/api/app/ingestion/annual_updates/__init__.py
2. services/api/app/ingestion/annual_updates/schemas.py
3. services/api/app/ingestion/annual_updates/planner.py
4. services/api/app/ingestion/annual_updates/cli.py
5. services/api/app/ingestion/annual_updates/models.py
6. services/api/app/ingestion/annual_updates/db.py
7. services/api/app/ingestion/annual_updates/store.py
8. services/api/annual_updates_alembic.ini
9. services/api/annual_updates_migrations/env.py
10. services/api/annual_updates_migrations/script.py.mako
11. services/api/annual_updates_migrations/versions/0001_annual_updates.py
12. config/annual-source-updates.example.json
13. docs/annual_source_updates.md
14. docs/acceptance/SCHEDULE_ANNUAL_01.md
15. AGENTS.md
16. README.md
17. docs/tasks.md
18. docs/CHANGELOG.md
19. docs/DECISIONS.md
20. docs/requirements.md
21. docs/architecture.md
22. docs/database.md
23. docs/data_strategy.md

## 剩余问题与停止

worker/新库尚未实际运行，源码正确性与SQL/并发行为仍未验证；默认enabled=false且未注册系统定时任务。当前目标4项只是浙江省线/录取观测及英国两校条件的维护请求，不代表全部学校/专业。来源许可/实际处理器/逐字段年度证据/审核责任/发布未完成；年度一次不能保证申请季、公布后补充或勘误及时。

只有请求创建的持久性设计，没有来源采集持久重试或候选/事实自动更新；连续失败次数只在当前worker进程计数。同年配置改变会拒绝覆盖，需维护者恢复原配置或到下周期明确重启。原已批准浙江2026三条保持；source_evidence_year未知不变为请求目标年，英国年份偏移不代替官方证据。

CHANGELOG/tasks及受影响文档同步后，仅当前23个已审阅文件普通提交推送至已授权PRIVATE origin，核对远程SHA后停止。源码上传不启动定时任务或开放服务。
