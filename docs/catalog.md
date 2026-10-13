# T11 招生机会关系契约

日期：2026-10-03。代码前冻结；T11依赖T01–T03已完成。本轮只建立候选关系模型，T12日期、T13来源、T15导入、T19发布和T20公开查询各自实施。研究文件不导入，真实省份/英国周期/审核与使用权待决不猜选。

## 数据契约

采用`app/admissions_catalog`、独立CatalogBase、`catalog_`表前缀和`catalog_alembic_version`，与M0的`catalog.py`/七表及auth0006并存。五张表：dataset、institution、program、offering根、offering_versions。UUID用于内部主键；`reference_key`为有界显式标识，合成标识及机构/项目展示名称必须`DEMO_`前缀、`is_synthetic=true`。verified只表示真实候选命名空间，不代表已审核；本Task所有dataset visibility固定private。

dataset记录mode demo/verified、synthetic、正revision；mode与synthetic一致。Institution独立身份、名称和country，不以名称自动合并。Program明确institution、学位、课程/校区/授课语言及衔接路径；Offering明确program及entry_year、intake、application_cycle、channel、course_system、pathway、applicant_category、province、exam_system、subject_scope、batch_group。country是机构地域，province是生源范围，不能互相推断。entry_year为显式严格整数，测试2026只是合成范围，不提供真实省份默认值。

缺失范围采用显式ScopeKey：`status=known/unknown/not_applicable`及可空value；known须有非空有界值，其他状态必须无value。持久化为非空`known:<value>`、`unknown`、`not_applicable`规范键。未知、不适用与实际值不同，不用NULL参与防重，也不推断英国的province。存储按精确大小写，不自动以同名/代码合并。

known.value/reference_key是ASCII标识而非原文显示标签：1–100字符、首字符字母/数字，后续允许字母、数字及`_.:+-`；规范键最多106字节。PG按字节检查此上界，完整多字段唯一键保持有界，不改为哈希防重。中文或其他原文标签保留到显示名/后续证据，不未经审核转换成范围码。合成名字必须精确DEMO_前缀，真实候选拒绝大小写变体的DEMO前缀。

父子关系用包含dataset和synthetic标记的复合FK约束；引用父级同dataset，禁止混接DEMO/真实候选。Program的规范键区分机构、明确项目标识及校区/学位/课程/语言/衔接；Offering业务唯一键含dataset、program及全部上述招生范围，禁止省份/渠道/申请周期遗漏。相同scope重复拒绝；改变年度、校区或渠道可并存。版本正整数，确切引用为`(dataset_id, offering_id, version)`；后续release成员在T19以复合FK引用此版本，不用任意release字符串充当发布证明。

候选登记/追加版本是可信内部维护接口，仅接受同engine的显式活动Session事务，不自动提交/建表/seed；未来HTTP入口须按T07/T10当前管理员权限及审核流程装配，底层store不是授权端点。追加版本锁dataset/offering、核对expected revision/version，旧版本不覆盖；调用者必须让维护异常退出外层事务并回滚，store不自行commit/rollback。没有任意编辑/删除父身份或旧版本的store接口，FK不级联删除历史；不能声称已配置生产GRANT/RLS或恶意本地SQL沙箱。

## 修改范围

仅新增admissions_catalog schema/models/store、独立catalog Alembic profile/0001、合成夹具和Unit/PG专项，相关九份既有治理文档同步。全部既有应用代码、M0/DEMO夹具、旧迁移、旧验收、生成HTTP契约、前端、依赖、原始输入和研究数据冻结。模块路径替代仅为避免Python同名包遮蔽，不改变技术栈/模块化单体。

## 验收矩阵

1. 严格年份/版本/布尔、额外字段和复制构造对象重验；DEMO命名、模式与缺失键；同名机构不同UUID可并存。
2. 真实PostgreSQL验证同机构不同年/校区/渠道/省/身份可并存，完全重复与并发重复拒绝；NULL不绕过unique。
3. 原始SQL验证同dataset/synthetic复合FK及CHECK、孤儿/错父/DEMO混接拒绝；父删除不级联丢历史。
4. 同事务登记/追加版本、乐观冲突和回滚；旧版本保留，未来确切版本FK目标存在。
5. 空库显式升级、重复升级、仅隔离测试schema降级再恢复；保留M0七表/夹具和auth0006数据，不对用户或正式库降级。
6. 默认/production/identity factory仍无catalog DB/DDL或自动导入，公开目录保持基础空行为。无API密钥、无联网测试；相关Unit/Integration、Type Check/Build/前端、契约/原文/范围与文档验收，Lint/Python静态类型无入口时说明未执行。

工程核对使用既有锁定SQLAlchemy2.0.41/Pydantic2.11.7/Alembic1.16.2，无新依赖。实现前查阅[SQLAlchemy复合约束](https://docs.sqlalchemy.org/en/20/core/constraints.html#defining-foreign-keys)与[Pydantic严格字段](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/)，复合FK用ForeignKeyConstraint，年份/版本/标记使用严格字段；联网文档核对与离线测试分别记录。

实际结果另记[T11验收](acceptance/T11_admissions_catalog.md)，本文件不是实现通过声明。

## 显式迁移与恢复

只在已备份、已核对目标的 PostgreSQL 上显式设置当前进程 `CATALOG_DATABASE_URL`，运行 `.\.venv\Scripts\python.exe -m alembic -c services/api/catalog_alembic.ini upgrade head`，用后恢复或移除变量。profile不读取M0 dotenv/auth设置，不安装日志handlers，不输出连接URL；禁止把凭据写入仓库。`migrate_catalog(engine)`提供隔离测试的既有Connection入口；重复升级不重导夹具。

T11头为 `0001_catalog_t11`，五张业务表加catalog版本表。恢复实测只对本批专用随机schema执行downgrade base→upgrade head，同时逐行比对M0七表/夹具和auth用户/会话/迁移头不变。降级会删除候选五表，不能当正式库无损恢复；正式数据损坏需先停写、备份和隔离还原验收，生产备份/还原尚未执行。应用启动仅既有入口行为，没有自动catalog建表、导入或seed。
