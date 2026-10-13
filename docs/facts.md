# T17 类型化候选事实契约

2026-10-03代码前冻结；只合成离线候选，不自动事实判断、爬取、规则执行或发布。

## 数据
独立app/facts/与FactsBase/profile 0001_facts_t17，保留M0 catalog.py和所有旧Base/heads。两张表fact_candidates、fact_conflicts；JSONB payload防护上限262144 bytes，仅容纳严格限定字段的转义与日期/规范值副本，不改变原文件1MiB/原字段4KiB输入界限；候选内容/冲突发现不可变（UPDATE/DELETE触发器），无published=true或可执行DSL。FactCreate：import_id/import_row_id、classification、evidence_id|null；value/单位原文/缺失/脚注/项目年版本等均从T15原行取得，不能输入覆盖。绑定同dataset/source/version/原file hash，T16 evidence若给出须exact offering/year/version且DocumentVersion.file_id/hash与原batch一致。

Classification所有字段显式：claim_kind unknown|minimum_requirement|typical_offer|historical_statistic|information；unit_code unknown|points|percent|fraction|CNY|GBP|item|people|text|ISO_DATE；period unknown|not_applicable|academic_year|program|one_time|survey_period；statistics_basis unknown|not_applicable|admission|employment|other；statistic_population|null、statistic_denominator|null、cohort_year|null、survey_period|null、date_event_id|null。有限文本<=512 bytes/时间上下文<=100 bytes。未知字段保留null/unknown，不从2026目标年/field名称补造学年、毕业届、分母或事实类别。

原fact_type六类保持；score/requirement可以minimum/typical/info；fee为info，material/date可以minimum/info；historical仅score/statistic且需要统计口径；statistic不变最低要求。字段与claim/unit组合不匹配固定422。Decimal字符串只严格词法（<=64）且无float/指数/NaN，规范等价数字用精确字串算法或无舍入Decimal相等，不normalize导致28位截断；percent[0,100]、fraction[0,1]、金额/分数/人数非负，人数/项数整数；不猜分制上限。原unit文本与明确normalized unit分别留存。闭合兼容矩阵：score=decimal+points/percent/fraction/unknown；fee=decimal+CNY/GBP/unknown；material=text+text/unknown或decimal+item/unknown；date=text+ISO_DATE/unknown；requirement=text+text/unknown或decimal+points/percent/fraction/item/unknown；statistic=decimal+points/percent/fraction/people/unknown。unknown unit只保留draft，statistic与historical的basis/population/denominator/cohort/survey不完整时draft，0值不是缺失。日期引用复用T12原精度/timezone候选，必须sameoffering/version/original_text，未知/歧义不能冒充正式UTC；official_utc不补写。

TypedCandidate输出：id/version=1、import/row引用、dataset/offering/year/version、rawrow的限定字段、classification、normalized_value|null、evidence_id|null、state draft|review_required|conflicted、is_synthetic/created_at、conflicting_ids、hard_rule=false/publication_eligible=false。仅允许有界字段，没有path/fullfile/owner/自由异常。日期附带服务端完整DateEventData身份字段（reference_key/is_synthetic/evidence_reference）的有限resolution快照，官方UTC仍null；缺原value/证据、unknown claim/unit/period必要口径、未知脚注或未定日期为draft，完整仍只review_required。

## 冲突与范围
sameLogicalKey=(dataset,offering/version,field_key,fact_type,claim_kind,规范unit/period/统计口径/date context)比较不同有效值或缺失状态；最低/典型/历史属于不同语义，不能自动合并。同键不同值、原value_kind、缺失状态、原单位或脚注内容追加冲突边，保留所有候选；无取最高/最新覆盖。单节点冲突邻接最大200，新增将超限则固定409整事务回滚，既有边不截断。候选自然key(import_row_id,classification_hash,evidence_id归入fingerprint)防重复；数字规范等价不误判不同值。冲突发现是历史不可变记录，T18用新review/resolution记录处理，不清T17历史状态或直接写发布。

## 权限与事务
FactPolicy enabled/real_facts_ready默认false。创建要求T13当前强data_admin、来源责任人、最新manual许可/原file存在metadata及期限，调用T15同Session当前batch/candidate重验，不持锁开第二连接。读取/verify_in_transaction允许当前catalog.review强管理员读取有界候选衍生字段：最新SourcePolicy/configured责任人及Storage metadata exact source/hash/quarantine/期限/模式重验，原fullbytes权限仍T14，不假owner，不读取student_private。若有evidence使用T16同TX有限审核读并核其原file绑定；均同Auth/Source/Storage/Imports/Evidence引擎。成功audit同TX，审计/锁等待后角色/MFA/source/file/当前offering scope/日期fingerprint再验，COMMIT后响应；callerTX结果为暂定；verify异常自动rollback本模块同Engine的active callerTX，错Engine不触碰，不掩盖原固定错误。派生hash拒父范围/原row/日期可信维护变化；无实际磁盘重读保证，沿用T16边界。

## 修改与验收
新增facts六模块（schema/纯typing/model/store/service/init）、独立profile/冻结0001、pure与隔离PG测试及当前文档；旧heads/HTTP/前端/依赖不改。测试最低/典型/历史隔离、Decimal精度/单位/缺失/脚注/date、重复/冲突保留、同source/项目/年/身份/版本/合成scope、未审核发布排除、即时授权/到期/错mapper、audit与真实COMMIT rollback、两会话并发/独立迁移及旧域保护。T18才决定审核，T19才正式release；没有真实事实或资格规则。

## 显式运行
模块没有公开端点，默认FactPolicy关闭，不在启动时建表。开发者仅在隔离测试库设置FACTS_DATABASE_URL，先验auth006/catalog003/storage001/imports001/evidence001，再显式运行`.venv/Scripts/python.exe -m alembic -c services/api/facts_alembic.ini upgrade head`；本轮用迁移函数/random schema，不向正式库运行该命令。只降级本Task隔离schema用于恢复验证，不能替代正式备份授权。
纯测试：`.venv/Scripts/python.exe -B -m pytest tests/unit/facts -q`。实库：配置专用loopback facts_t17_test的T17_TEST_POSTGRES_URL后运行`pytest tests/integration/facts -q`；没有设置时必需检查失败，不能写成通过。离线禁外部网络，合成学生/DEMO来源，无模型密钥可运行。完整实际结果见[T17验收](acceptance/T17_typed_facts.md)。
