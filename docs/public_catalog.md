# T20 公共目录与公开证据契约

2026-10-03代码前冻结。T02/T16/T19已验收并保存。只实现匿名、只读、当前已发布项目与明确可公开的证据片段；无管理页面、资格引擎、采集、真实发布或部署。T20是用户本批T08–T20最后一项，验收保存后停止。

## 数据契约

独立显式public_catalog应用profile，GET `/v2/config`、`/v2/offerings`、`/v2/evidence/{evidence_id}`。旧foundation/identity与M0入口/契约字节保持，基础工厂不自动连接数据库、迁移、装载身份或模型。reader未注入时配置business_available=false，业务503；无API密钥可读取配置。合成正例需test runtime、显式allow_test_fixture_read及demo数据集；production/verified正式路径仅formal非合成，真实准备开关默认false。

目录entry_year必填1..9999，country为两个大写字母，study_level本科可选；province/pathway/course_system/applicant_category精确匹配ScopeKey存储值known:ID或not_applicable，不把所在地推导为招生身份或套用高考。可选release_id、limit1..100默认20、长度有界cursor；重复/额外参数、非整数语法与坏游标拒绝，不默认为当前或其它年份。SQL有界读取distinct release/offering/pinned version，稳定引用排序；游标绑定全部过滤/limit及不可变ChangeEvent单调计数，发布/替代/撤回后409要求重新开始，不能凭游标获取权限。最多每release50个固定成员，不物化全国全部目录。

响应复用v2统一Envelope/Meta与安全错误和服务器request_id。Offering包含固定release/version/hash/年份、机构与项目标签、招生范围、当前已发布typed事实及单位/缺失/脚注；私有证据不发可访问ID。覆盖状态只no_published_records或partial、返回数量与未知总量；空游标页用有界存在性检查区分分页结束（partial/0）和范围没有记录，后者明确缺口，不宣称全国完整覆盖率。证据GET必填release_id，只接受同release固定public_evidence=true成员；公开有界quote、原文hash、byte/line定位、source出版者/声明的官方性、范围与版本，不返回file_id、private路径/key、owner、会话、完整附件或私有存储URL。所有响应Cache-Control:no-store；无自动通知消费者。T11候选dataset.visibility仍private；公开授权是T19当前release的有限投影，不将整库标public，也不提供原始候选读取。

## 权限与当前有效性

匿名公共许可独立于历史发布/审核人的登录会话，不能模拟Principal或假冒reviewer调用私有读取。使用同Engine/同Session直接核对当前release state/窗口、当前T18唯一选择及decision/revision/冲突快照、T17原字段/日期和T16范围/证据/文件绑定；固定release快照必须与当前证明完全一致。来源须当前version、启用且独立publication_permission=granted，有basis/ref/审核时间/复查期限；导入许可不替代公开许可。原文件必须精确ID/原byte hash/内部metadata指纹、quarantine、媒体/大小/合成模式及未过期，不能等字节copy续期。

先按dataset锁定再读取相关state/proof，避免与T19发布反向锁顺序。查询等待结束后重验状态，末次SQL后以同一fresh UTC检查所选release全部固定成员source/file/release窗口且不再SQL，防止第一成员在后续等待中过期。未发布候选、私有原附件/未获公开许可片段以及撤回/被替代版本不公开；证明失效保守拒绝，不回退历史或DEMO。每次读取验证捕获的元数据证明，不声称每次重新物理读取原附件或恢复验收。

## 修改范围

新增app/public_catalog五模块、api/public_catalog工厂及api/v2/public_catalog路由；契约public_catalog子目录及显式生成profile与该两产物LF checkout属性、TypeScript契约编译用例、纯/隔离PG/生成器测试；同步AGENTS、README、requirements、architecture、database、api、tasks、CHANGELOG、DECISIONS、本文件与独立验收记录。旧迁移和既有鉴权/导入/审核/发布代码冻结；无依赖更新。

## 测试用例

纯测试query严格类型/范围/坏cursor/过滤绑定/coverage及DTO防多余字段。隔离PostgreSQL经完整合成导入→证据→类型化→独立人工模拟审核→test_fixture发布：匿名分页/精确年份地区身份、private证据404、草稿/撤回/替代无公开、当前来源/许可/文件/范围/决策/冲突变化拒绝；真实SQL锁等待跨来源或文件期限；cursor发布变化409；历史审核/发布会话退出后公共授权独立。HTTP请求重复/extra参数、固定安全错误/request_id/no-store、无私有路径与None reader配置/503；production拒绝DEMO，不伪造真实学校数字/日期正例。运行相关回归、生成契约三profile检查、前端测试/类型/双构建；没有项目Lint/Python静态类型入口则明确未执行，浏览器页面未改不做无关UI验收。

正式责任、2026全国资料覆盖、法律/隐私/资料权利、真实来源负责人、实际数据库只读角色/GRANT/RLS、原附件清理备份恢复及部署均未验收，真实公开开关保持关闭。旧T15时效问题为任务外记录，不修改。

## 本地运行与离线检查

仅启动默认关闭的显式profile，不会创建读取器/数据库或获得正式公开授权。在项目根目录PowerShell配置本进程后运行：

```powershell
$env:V2_APP_ENVIRONMENT = "production"
$env:V2_DATA_MODE = "verified"
$env:V2_MODEL_MODE = "disabled"
$env:DEMO_MODE = "false"
.\.venv\Scripts\python.exe -m uvicorn services.api.app.api.public_catalog:create_public_catalog_app --factory --host 127.0.0.1 --port 8002
```

GET `http://127.0.0.1:8002/v2/config` 返回business_available=false；`/v2/offerings?entry_year=2026` 和绑定release的证据请求返回503。需由可信服务器组合已有服务/stores与显式CatalogReader才能注入读取能力，不能由请求参数启用。合成正例仅test/demo及allow_test_fixture_read；正式资料门槛未完成时保留None reader。source authority_claim是登记者声明，合成证据即使声明claimed_official也不是经核验的真实官方依据。

生成器：`.venv/Scripts/python.exe scripts/generate_contracts.py --profile public_catalog --check`。专项：`pytest tests/unit/public_catalog`、`pytest tests/contracts/test_t20_public_catalog_generation.py`；PG须先准备loopback PostgreSQL专库`study_t20_20261003`（测试账号须可建/删该库内随机schema），设置T20_TEST_POSTGRES_URL为其postgresql+psycopg连接串；测试使用随机schema，缺少环境直接fail，不能skip冒充通过，fixture独立迁移只用已冻结profiles。当前实现未给publicreader配置PostgreSQL角色/GRANT/RLS；SELECT FOR UPDATE用于一致性锁，不等于部署好的只读数据库账号。
