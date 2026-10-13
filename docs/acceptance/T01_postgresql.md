# T01 PostgreSQL基线验收计划

日期：2026-10-01；状态：已完成。仅T01，来源登记在本Task完成后另行执行。

## 数据契约与修改范围

复用冻结0001_m0、DEMO夹具和/v1接口，七业务表及其原字段不变。专用空测试库，每个用例随机schema，服务/端口仅本地；不连接用户已有数据库，不写.env，不修改Compose或依赖锁。合成画像必须confirmed=true，由服务端DEMO凭据解析owner。

计划修改tests/backend/test_persistence.py，新增隔离PG测试fixture及用例；README/AGENTS/tasks/CHANGELOG同步，M0_TEST_REPORT只追加新日期。此验收计划独立保存。数据库业务设计、API字段、旧迁移与夹具保持原样。

## 实际验收用例

1. 空库/空schema upgrade(head)，检查七业务表+alembic_version、0001_m0、外键/唯一约束/索引。
2. seed首次2机构/7证据/4项目/9规则，第二次0新增；中文/JSON/布尔/原文SHA256完整往返。
3. 通过真实PG绑定的TestClient确认合成画像、产生资格与草案；重复upgrade(head)+seed后完整payload、owner及FK不变，两用户隔离。
4. 用一份先添加新记录后触发旧ID冲突的夹具，验证已flush新写入整体回滚，旧记录和私有资料不变；坏hash拒绝后同样保留。
5. 另一个可丢弃空schema执行head→base→head→seed；base明确删除全部业务表，不宣称保数据。schema由测试创建，清理只针对该随机schema。
6. 实际CLI在新建专用空库upgrade/seed/重导，并记录PG版本、数据库/schema隔离与关闭状态。

## 检查与记录

相关PG集成测试、离线Python回归和原文/哈希保护检查；没有修改前端，前端Unit/Type Check/Build不重跑并明确原因。PG缺环境时不能用SQLite结果标T01完成。

环境准备可以使用已安装Docker或仅在.cache中创建的临时PG运行环境，不改系统服务/全局配置，不停止用户已有数据库。工具准备下载与执行期间测试分开记录；应用测试不访问商业API或外部网站。保留原2026-09-30结果，另追加T01实际命令、失败/通过与剩余限制。


## 实际结果（2026-10-01）

PG测试4 passed、4 deselected、1 warning；离线回归96 passed、4 deselected、1 warning，均退出0；无实库用例跳过。真实CLI upgrade/current/seed/reseed均退出0。报告[新增日期](../M0_TEST_REPORT.md)列实际命令和失败，不能使用旧日期的96 passed/1 skipped作为本日结果。

PostgreSQL16.15来自[官方Windows下载入口](https://www.postgresql.org/download/windows/)指向的[EDB二进制ZIP](https://www.enterprisedb.com/download-postgresql-binaries)，文件postgresql-16.15-4-windows-x64-binaries.zip。工作区.cache独立运行，initdb UTF8/locale C、SCRAM host，pg_ctl仅监听127.0.0.1:55432，新建空库m0_t01_test。未修改Compose16.6-alpine、.env或安装系统服务。Docker启动尝试失败，WSL引擎异常；该路线未验证。冻结基线的PG16主版本验证完成，不宣称不同镜像环境通过。

临时准备脚本在忽略目录，仅供本机复现，不是新增部署工具。程序/cluster留在.cache且服务已关闭，未删除用户文件。复现时另选不存在的cluster和空库；禁止对当前用户库运行downgrade。

```powershell
# TEST_POSTGRES_URL和DATABASE_URL仅在当前进程设为新建专用空库；不要公开密码。
.\.venv\Scripts\python.exe -m pytest tests/backend/test_persistence.py -m postgres -q
.\.venv\Scripts\python.exe -m pytest -m 'not postgres' -q
.\.venv\Scripts\python.exe -m alembic -c services/api/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m services.api.app.seed
.\.venv\Scripts\python.exe -m services.api.app.seed
.\.venv\Scripts\python.exe -m alembic -c services/api/alembic.ini current
```

实际psql计数SQL：

```sql
SELECT version(), current_database();
SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;
SELECT 'institutions' AS table_name,count(*) FROM institutions
UNION ALL SELECT 'evidence',count(*) FROM evidence
UNION ALL SELECT 'offerings',count(*) FROM offerings
UNION ALL SELECT 'rules',count(*) FROM rules
UNION ALL SELECT 'profile_versions',count(*) FROM profile_versions
UNION ALL SELECT 'eligibility_results',count(*) FROM eligibility_results
UNION ALL SELECT 'plan_drafts',count(*) FROM plan_drafts;
SELECT count(*) AS leftover_test_schemas FROM pg_namespace WHERE nspname LIKE 'm0_test_%';
```

最后七业务表+alembic_version，计数2/7/4/9/0/0/0，剩余测试schema0。pg_ctl fast stop退出0，status预期退出3，端口55432监听0。

范围保护检查退出0：6份旧文件修改，新增本验收文档，范围外74文件不变；0001_m0/DEMO夹具与原始输入保留。旧报告原字节作为新增节的前缀保留。T01卡和CHANGELOG状态/命令/结果同步；只读复核无阻断缺陷。未运行前端、Lint、部署/性能/恢复检查，理由见报告。
