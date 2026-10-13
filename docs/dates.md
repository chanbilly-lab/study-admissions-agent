# T12 日期事件契约

2026-10-03，代码前冻结；依赖T11已验收上传。只建候选日期结构与离线换算，不导入真实期限、读取网页或生成申请提醒。

## 数据契约

独立`admissions_catalog/date_schemas.py`、`dates.py`、`date_models.py`、`date_store.py`；DatesBase独立metadata，与CatalogBase共用catalog链增量`0002_catalog_dates_t12`。旧0001、M0/auth链冻结，T11历史迁移验收显式指定0001，不因新head改写旧DDL。

DateEventInput含UUID id/dataset_id/offering_id、严格正offering_version、显式entry_year、reference_key/is_synthetic、event_type、original_text、local_date/local_time/timezone、precision、source_alignment、可空evidence_reference。event_type固定application_open/application_deadline/equal_consideration/materials_deadline/language_supplement/score_supplement/offer_acceptance/scholarship_deadline/enrollment，事件不会互相替代；平等审理过期不自动断定不能申请。所有nullable字段必须显式提供，extra拒绝，复制构造重验。

precision=date/minute/second/unknown；date只允许日期，无补造时间，unknown不提供日期/时间/时区；minute/second须日期和无tzinfo/fold的本地时间，minute秒/微秒为0，second微秒为0。timezone只接受存在的IANA地区键或UTC，未知为NULL，不用服务器时区/原文地域猜选，不接受数值偏移或短缩写。已有hash锁定tzdata2026.4（via psycopg）提供Windows时区，不新增依赖。

source_alignment=pending/conflict：pending不表示已对照原文，conflict必须保守拒绝候选换算。original_text为有界原文；不做任意中英日期自动解析，T18实际人工核验原文。evidence_reference只是待解决标识，T16前evidence_state=unresolved，不能伪造Evidence FK或官方证据。

纯函数normalize_date_event对fold0/1分别往返UTC→地区本地，去重有效UTC：0个为nonexistent，2个为ambiguous，1个才unique。timezone缺失、date-only、unknown、source_conflict或overflow保持明确状态及NULL；不能默选fold或补23:59。只生成`calculated_utc_instant`计算候选；T12 `review_state=draft`且官方`utc_instant`固定NULL，审核尚未建立，T18核验后才可晋升。输入不能伪报UTC/已审核状态，持久读取重新计算并比对，时区库变化导致不一致需重核验而不是静默改值。

候选事件表`catalog_date_events`通过(dataset_id,offering_id,offering_version)复合FK引用T11确切版本，另机会synthetic复合FK防混接。entry_year为输入断言，由store同事务核对父机会，输出从父派生，表不重复存年以免SQL造成冗余错年。UUID/DEMO标记复用T11规则；条目唯一为(dataset_id,offering_id,offering_version,reference_key)，允许同版本多个不同事件，冲突原文保留独立候选。范围继承确切版本，不造实际省份或年度映射。

可信内部DateEventStore只同engine活动caller事务新增/读取，核对expected_dataset_revision并加锁递增；异常由调用者退出外层事务回滚，不自动commit/seed/DDL，不提供更新/删除或HTTP入口。当前及五个catalog mapper、date mapper均检查绑定；候选存储不代表管理员鉴权/事实发布。CatalogStore默认当前头0002，可显式required_head=0001作历史基线验收；migrate_catalog(engine,target='head')可显式target=0001，不默降级。DateEventStore就绪严格要求当前0002及日期列。

## 修改范围与验收

新增四模块、冻结0002、日期Unit/PG专项；必要改catalog store head/显式target、migration env combinedmetadata，以及两份T11历史测试固定0001 target。13个相关既有文件允许变更（9治理文档+上述4源码/测试），其余245tracked保护；公开wire/UI/依赖/原始两输入/旧迁移/研究不改。

测试覆盖严格精度/nullable/类型/名称空间、所有事件分开、2026合成伦敦冬夏时间、DST间隙/重叠、未知/日期-only/原文conflict、复制对象和UTC伪报；实际PostgreSQL验证确切版本FK/DEMO隔离、唯一键/原子回滚、无自动迁移、0001→0002升级保留旧数据及隔离恢复。相关Unit/Integration/原文/契约/Type Check/Build按实际运行记录；无Lint/Python静态类型入口时未执行。实测见[T12验收](acceptance/T12_date_events.md)。

工程联网核对仅[Python zoneinfo](https://docs.python.org/3/library/zoneinfo.html)与[datetime](https://docs.python.org/3/library/datetime.html)，测试不联网/不使用真实机构期限。正式审核、来源权限、真实证据/发布与生产恢复不在本Task通过声明内。

## 迁移恢复边界

复用T11显式CATALOG_DATABASE_URL与catalog_alembic.ini运行upgrade head，当前0002；启动不执行它。隔离测试实际0001→0002/重复升级及0002→0001→0002，逐行保留M0/auth/五张catalog历史与迁移头；DatesBase独立/复制合并metadata不污染原Base。降级仅在本批随机schema做，会删除新增日期表及其候选，不能当生产数据无损恢复；正式备份/隔离还原尚未执行。required_head/target只已知001/002或head，不能凭任意字符串伪造就绪，也不把旧库自动升级。
