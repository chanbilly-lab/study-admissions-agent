# 浙江2026普通类分数线：本地参考闭环

2026-10-13，本批只有浙江普通类第一段、第二段和特殊类型招生控制线三条。官方原文核验、原始HTML保存、用户确认、独立PostgreSQL入库及页面查询已经完成；其他省/年/类别、学校投档录取线、个人资格和公众发布不属于本批。

## 数据与证据

| 原称 / 线种 | 2026数值 | 适用范围及限制 |
| --- | --- | --- |
| 第一段 / segment_first | 494分 | 浙江普通类分段线，不改称本科控制线 |
| 第二段 / segment_second | 266分 | 浙江普通类分段线，不代表高校最终录取线 |
| 特殊类型招生控制线 / special_category | 594分 | 原注用于强基、军校等提前录取或特殊类型招生，不产生个人资格结论 |

来源：[浙江省教育考试院原文](https://www.zjzs.net/art/2026/6/25/art_155_12467.html)。原公布标签2026-06-25 13:22，原文未明确时区，不自动转换；取证UTC=2026-10-12T16:39:53.338904Z，与公布日期分开。原HTML68359字节，SHA256 `b9fd87a8a202b37d6ff9e4f1efb8fdef394213448ffe983b9f5e7361e4dfb38a`；未拿摘要当原文hash。原字节仅缓存/内部source表，不放前端静态目录/仓库，不对外全文再分发。

本页未明确普通类满分与加分定义，数据库/API/页面全部null＋not_stated_in_source，不推750、不填默认规则。艺术/体育/单独考试未导入本批，不表示原文没有这些资料。查询2025、其他省或这些类别显示not_collected/scope_not_supported/not_applicable，不回2026或DEMO。

## 本地来源与审核链

官方站点核验、原字节取得、人工确认及对外再分发许可分开。用户于2026-10-13明确确认这3条用于本地参考；review_ref=USER_ZJ2026_ORDINARY_3，仅是本次对话人工复核引用，不冒充已部署管理员身份/MFA或官方发布负责人。public_reuse_permission=unknown、T19正式release_id=null，公众部署保持关闭。

data/research中的local_batch/local_review保存首研究稿和用户确认，旧候选摘要58aed...保留；import.json是显式协议适配（原名使用table header第一段/第二段），canonical完整模型会规范UTC和固定顺序，执行摘要 `f8171cdb6fcb680478e6b1948989fb5f23aa65c477331dc3fee355a903fbc6d0`。confirmation_mapping.json记录同一原文字节、同一三数值与这两份清单的衍生关系；新review proof绑定真实batch_id `10f2c5b3-d829-54fa-a89c-cdc4a8f7a493`、新执行摘要及source hash，未把旧hash直接当新hash。

## 持久化与操作边界

独立ReferenceCutoffsBase/新reference_cutoffs_alembic.ini，四表reference_cutoff_sources/batches/records/reviews与version表。source存原字节/sha及闭合来源；records具有类型化line_kind/value与JSON快照；batch只单向candidate→approved_local→withdrawn，review追加不可变。UPDATE/DELETE/TRUNCATE拒绝，deferred约束要求三完整记录与状态/复核一致；读取也重核原字节/manifest/typed行/审核链。重导幂等，已撤回不重生，不按旧响应缓存查询。

使用本机既有PG16.15集群的新reference_zj_2026数据库，独立维护owner和API SELECT-only角色；原M0数据库/表/凭据未改。reader无superuser/CREATEDB/CREATEROLE/BYPASSRLS、无public CREATE/TEMP或表DML，default_transaction_read_only=on，每查询核权限与只读事务。API不接受客户端owner/审核状态/批次写入，不读取.env或M0 DATABASE_URL。

现有T18/T19严格绑定招生项目版本，本批不虚构offering去满足FK，也不改其正式流程。此新本地参考周期只覆盖这一次明确确认的省级三条汇总；新省/年/来源版本需另做独立批次与核验，不自动泛化或撤销原公众门槛。

## 当前运行及未来显式维护

[打开本地真实参考查询](http://127.0.0.1:5174/)；默认浙江2026省线，需点击“查询当前范围”。[本地API查询](http://127.0.0.1:8004/v2/reference/province-cutoffs?year=2026&region_key=cn_region_11&limit=20)。演示页面仍在5173，M0与真实参考不混用。

服务端入口 `services.api.app.api.local_reference:create_local_reference_app`，只loopback Host/client/Origin、不信Forwarded，固定verified/disabled。原create_reference_app依旧为空，默认生产factory/M0不自动装配新reader；客户端仅province_cutoffs接受reference.cutoffs.local.1，其他资源保持旧空协议。source/批次/人工范围/缺字段展示真实，max/bonus、全国分母和ratio保持null。

维护需要操作者准备专用空PG与外置秘密；下面是本次使用的命令结构（环境变量仅设置本机维护/读DSN，不把密码写进源码/文档）：

```powershell
# 明确设置REFERENCE_CUTOFFS_DATABASE_URL（维护）后
.venv/Scripts/python.exe -X utf8 -B -m alembic -c services/api/reference_cutoffs_alembic.ini upgrade head
.venv/Scripts/python.exe -X utf8 -B -m services.api.app.statistics.reference_cutoffs.cli import --manifest data/research/zhejiang_cutoffs_2026_import.json --raw-source <实际取得的原HTML文件>
.venv/Scripts/python.exe -X utf8 -B -m services.api.app.statistics.reference_cutoffs.cli approve --review <绑定实际batch/source/执行摘要的维护复核JSON>
# 给读角色授所需五表SELECT/USAGE，并设置REFERENCE_CUTOFFS_READ_DATABASE_URL
.venv/Scripts/python.exe -X utf8 -B -m uvicorn services.api.app.api.local_reference:create_local_reference_app --factory --host 127.0.0.1 --port 8004 --no-proxy-headers --no-access-log
# 前端新进程VITE_APP_MODE=reference，Vite5174，/reference代理8004
```

本批源hash和数值范围锁定；如果未来页面字节发生变化，即使同网址也不得冒用旧复核。需另做版本/人工核对，不能简单把新hash改成旧hash。数据库/密码/原HTML不随Git上传，换机器需要实际快照和专用PG权限，不能仅clone就宣称真实数据已入库。

## 实际验收与限制

实际完成：官方单页HTTP200及真实byte hash/表格/注释提取，独立空库迁移head0001_ref_cutoffs、导入3条candidate、用户绑定复核后approved_local、再次导入inserted=false。额外8项独立schema PG/HTTP检查：未审不读、完整批准、值不可变、撤回即时不读/重导和旧approve不复活、实际SELECT-only与DML拒绝、owner读账户拒绝、非法筛选/Origin/DEMO凭据拒绝。只删除本次新建随机验证schema，主批准批次仍可用。

实际Edge155.0.4283.45另8项页面检查：显式查询、三类型/数值、来源/hash/公布与复核/缺字段、2025不回填、其他省不造、港澳台不适用、艺术类不混、390px及page_errors=[]。桌面/移动截图已查看。完整命令/文件记录见[批次验收](acceptance/data_batches/BATCH_ZJ_2026_CUTOFF_01.md)。

未执行：其他全量Unit/Integration回归、Lint、TypeCheck、生产Build、CI/Docker、其他真实省份/资料类别和正式身份/公众发布；用户旧不用测试仅对这些未授权检查保留，本批只做必要来源/入库/查询闭环。无新包依赖，无录取概率、自动申请、学生数据处理或真实学校虚构要求。服务未设开机自动恢复，真实公开再分发责任/法规与运营目标仍待确认。
