# SCHEDULE-ANNUAL-01 年度资料更新调度

2026-10-13实施前契约。用户确认每年11月1日09:00、Asia/Shanghai；当前只创建待采集/待审核请求，来源未获许可时不自动联网。用户此前“不用测试”保持，本Task交付源码，运行验收另记未验证。

2026-10-13源码/文档交付完成，用户再次确认继续并PRIVATE上传、仍不测试。实际未执行项与23文件清单见[交付记录](acceptance/SCHEDULE_ANNUAL_01.md)。本轮未迁移/启用worker，当前定时任务尚未实际运行。

## 数据与修改范围

- 固定闭合配置annual.source.schedule.1：schedule_id/revision、enabled默认false、开始周期2026、IANA时区、月/日/时/分、60–3600秒唤醒间隔、最多10个目标和有界失败重试。日期只支持1–28日，避免闰年策略；模糊/不存在的本地时刻拒绝。
- 每目标记录内部ref、资料类型、省份或英国机构/课程/College/路径/科类/批次/轮次/入学季和年度偏移，旧研究来源仅作为发现线索，无真实来源许可或自动URL替年。
- 国内province_cutoffs/admission_observations目标按周期年、英国entry_requirements按周期年+1；偏移可显式配置。source_evidence_year始终null，取得适用证据后才另建候选版本；目标年不证明官方已公布。
- 年度计划annual.source.plan.1与每请求awaiting_collection，网络/事实更新/发布标志恒false；纯planner不读取研究原文、学生或正式事实。
- 新独立PostgreSQL两表annual_source_cycles/annual_source_update_requests与独立迁移。稳定(schedule_id,cycle_year)唯一键，全请求同事务；配置及请求快照不可变。并发/重启不得重复，同一年度配置变化报冲突，不改旧批次。
- 单独CLI plan/tick/run，写入必须配置enabled=true并--apply，显式ANNUAL_UPDATES_DATABASE_URL；不回退M0或.env，不在FastAPI启动建表/跑任务。worker仅按间隔检查内部日期；进程停机后只补最近已到期周期，从2026起，不一次追补多年。
- 不改旧T36 jobs/T66禁用连接器、M0、浙江固定2026三条、生产factory/API/前端/旧迁移；无新第三方依赖。新增小模块、配置、独立迁移及相关治理文档。

## 源码验收与待运行用例

源码审阅须覆盖：默认关闭零DB/网络；目标年度分离；aware时间/IANA/月份边界、首次触发/迟启动补偿；同年去重/并发完整事务/配置冲突；只显式维护角色、版本与DSN；失败不标成功、退出/有界退避；来源/学年未知不改成最新；旧数据/发布/资格无写入口。

未来运行用例（本批均未执行）：触发前后/跨UTC年界、2026→国内2026/英国2027、2027→2027/2028、DST歧义/空洞、非法日期/字段/重复目标、disabled零连接、同年多次及两进程竞争、事务中断回滚/重启、配置修订拒覆盖、错误角色/head、数据库失败五次退出、SIGTERM、网络零请求、原M0/浙江数据未变。

真实采集/解析/来源年份核验、人工审核和发布不属于当前调度器。年度任务并不代表年度数据已经更新；每年一次也不能代替公布后的补充采集、勘误/撤回和申请季条件复查。

## 源码入口与运行方法（本轮均未执行）

独立模块`services.api.app.ingestion.annual_updates`，不使用FastAPI内定时器、额外调度框架或外部商业服务。独立worker唤醒时比较配置的内部时刻；临近触发会缩短等待，同一周期在数据库中最多一批。主机/进程仍须运行；`run`是前台进程，不自行安装开机自启、Windows计划任务、cron或容器。实际服务托管由后续部署任务落实。

从仓库根目录运行，先复制示例到本地非提交配置并按需要修改；不要将密码加入JSON。示例默认enabled=false，包含4类目标：浙江普通类省线、浙江投档/最终录取观测待办、两校本科条件复核待办。投档/最终录取需各自定义和具体学校/组/专业范围；当前请求仍待选源/补全范围，不代表真实观测已采齐。`source_hints`只是旧研究入口发现线索，2026源不能证明后来年度，也不是正式SourceVersion或获许可自动端点。

```powershell
# 预览：不写DB、不采集。默认关闭配置返回disabled。
.venv/Scripts/python.exe -X utf8 -B -m services.api.app.ingestion.annual_updates.cli plan --config config/annual-source-updates.example.json

# 新建独立annual_source_updates PostgreSQL库/角色后，由维护者显式迁移。
# ANNUAL_UPDATES_DATABASE_URL仅从安全的进程环境注入；禁止提交或打印密码。
.venv/Scripts/python.exe -X utf8 -B -m alembic -c services/api/annual_updates_alembic.ini upgrade head

# 本地配置enabled=true：tick无--apply只预览；加--apply到期才持久化。
.venv/Scripts/python.exe -X utf8 -B -m services.api.app.ingestion.annual_updates.cli tick --config .cache/annual-source-updates.local.json --apply

# 明确启用持续调度：只生成待采集请求，不访问学校网站。
.venv/Scripts/python.exe -X utf8 -B -m services.api.app.ingestion.annual_updates.cli run --config .cache/annual-source-updates.local.json --apply
```

本批没有执行以上命令，也没有创建annual_source_updates库、执行迁移或启动任何worker。无API密钥需求；现有M0/浙江本地服务不变。

连接必须是显式`postgresql+psycopg://`、localhost/127.0.0.1/::1、数据库名annual_source_updates、public schema，无连接query/options；不读取.env、不允许M0/浙江库或DEMO凭据。维护角色应为非superuser/createdb/createrole/replication/bypassrls，仅对两表SELECT/INSERT、version表SELECT及public USAGE；迁移由专用owner执行。JSON版本/字段/大小、字段与列一致、完整请求数量由源码约束；运行角色/DDL触发器/并发效果尚未实测。新迁移downgrade拒绝自动删表，后续必要恢复须单独安排。

## 结果与维护语义

- `disabled`：零DB写入，worker退出；暂停须把本地配置enabled改false，恢复后须显式重新启动进程。
- `not_due`：尚无到期周期，零DB访问；给出下一内部时刻。不是官方公布日。
- `dry_run`：给出计划与请求，未持久化；plan或未加--apply的tick永不写库。
- `requests_created`：整批维护请求提交成功；每行awaiting_collection，facts_updated/published/network_requested均false。
- `already_requested`：该年度已经存在完整同配置请求，不重复添加；不是资料已更新。
- `configuration_conflict`：同一schedule_id/周期有不同配置摘要，保留原记录，worker退出。恢复原配置或到下一周期明确选择新配置；不能改schedule_id/目标ref来绕过去重。revision、检查间隔等改变也会影响摘要。
- 数据库故障：默认最多5次连续失败、60/120/240/480秒有界退避（受检查间隔上限）；失败不写“完成”。达到上限退出，需维护者处理后重启；故障次数是本进程计数，不是来源采集的持久重试台账。

SIGINT/SIGTERM取消等待；正在进行的有界DB事务先完成或回滚，再退出。进程停机跨年度只补最近一期到期请求，不自动补全所有历史年。配置ID应稳定、变更要保留版本并人工处理冲突；没有实现从任务入口取消旧批次或自动改正式事实。

若2026周期启用，到期请求的国内考试年2026、英国目标入学年2027；2027周期分别为2027/2028。这是请求映射，源年仍未知。用户手动导入新资料时必须新原文/新批次/新审核；浙江2026已批准三条不改。申请季需要更频繁核验，年度任务只提供基础复查，不承诺招生资料全年最新。
