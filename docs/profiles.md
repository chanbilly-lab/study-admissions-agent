# T23 画像根与不可变确认版本

2026-10-03代码前冻结。基线PRIVATE T22 `1054b8129ec9e94700a6f5158ea9f9b3f1f4d9a7`，457 tracked/索引与工作区空；当前`codex/t23-profile-versions`，只T23。先读取治理、原两份规格、API/数据库及授权/隐私/幂等和M0代码。T24 UI、规则与资格不在本Task；真实处理默认关闭。

## 数据契约

新ProfileSnapshot是完整替换快照，不作隐式PATCH：`study_level=bachelor`、显式`entry_year`（1..9999）、`residence_region/course_system/applicant_category/exam_province/pathway`五个独立ScopeKey、最多8个唯一subject标识、最多15项assessment、可空明确`weekly_hours`及可空`preferences`。ScopeKey复用T11的known/unknown/not_applicable和值耦合，所在地不推断生源省份、身份或课程；pathway只是本人声明的目标路线，仍需T26逐项目适用证明。没有姓名、生日、证件、联系方式或自动诊断字段。所有nullable字段必须显式出现；未知保持未知。

assessment使用同一闭集键字典；未提供的整项键可以省略，不表示零或后补。OpenAPI在该字段局部投影实际15个optional property及additionalProperties=false，运行时用同一闭集验证；不为此放宽全局生成器任意Record/未知schema。已提供Pair及其slot内nullable字段仍全部必需。明确意向代码为course_system=gaokao、applicant_category=cn_mainland及pathway=gaokao/uk_undergraduate；其他显式known或缺scope均不能套用该目标适配。

AssessmentPair逐项保存`achieved`和`predicted`两个必需独立slot。Slot的`status=provided/missing/pending/not_applicable`，`value/scale/unit`是必需nullable；provided要求严格有界非负十进制字符串、正scale、value<=scale和points/band，其他status三个值均null，不把pending当后补许可。数字固定`0|[1-9]整数`加可选1..6位小数、整数最多7位；拒float/NaN/Infinity/指数/负数/空字符串/前导零，不默认750/150/9、不换算不同单位或满分，不用预测替代实得。封闭15键：gaokao_total/chinese/math/gaokao_english/physics/chemistry/biology/politics/history/geography/ielts_overall/ielts_listening/ielts_reading/ielts_writing/ielts_speaking，重复JSON key或未知键拒绝；gaokao键仅points，ielts键仅band。可空weekly_hours使用明确十进制字符串0..40；0表示确实无容量，null表示未提供，旧M0语义保持。Preferences=`{preferred_fields:最多10个唯一有界文本,preferred_countries:唯一CN/GB至多2个,budget:{amount:同有界非负数字字符串,currency:CNY|GBP}|null}`；只是学生意愿，不是学校资格或诊断。

CreateInput=`{profile:ProfileSnapshot,confirmed:true}`；AppendInput=`{profile:ProfileSnapshot,expected_current_version:正严格整数,confirmed:true}`。拒绝owner/role/synthetic/verified/服务器proof ID及其他extra字段，confirmed=1或字符串拒绝。版本源只标student_declared，不冒充核验成绩。Response包含服务器root UUID、version UUID/递增序号、完整快照/hash、确认时间及声明源、24日历月内expires_at、is_synthetic和有限adaptation说明；不返回会话、内部存储路径或自由修改的owner副本。gaokao此时仍unknown/ADAPTER_NOT_IMPLEMENTED；明确其他课程或申请路径为unsupported，未知为unknown，绝不输出eligible或虚构已覆盖全国规则。未适配体系允许保存最少意向，但不得把其字段强制映射成高考资格；旧规划422拒绝路径不冒充当前新profile行为。

每版绑定服务器当前核心用途/告知/成年声明依据，原确认证明失效后历史payload与旧create receipt不能因重新同意而自动复活。本人可以明确提交新的完整payload、新确认和新CAS生成绑定新依据的版本，服务不能自动复制旧payload。T09的status/version metadata grant不授画像内容读写；管理员角色不授私人学生内容。

## 内部模型与事务

独立ProfilesBase与`student_profiles/student_profile_versions`，避开旧M0 `profile_versions`。root关联同事务T07唯一AuthOwnedResource归属依据，root current_version与registry version一致；version唯一(root,version)，固定root/确认者/模式/内容及原证据引用，hash由实际canonical字节计算。root指针/版本归属须有数据库约束，不能跨root。禁止版本UPDATE；本Task无DELETE入口，未来T40可信删除流程可删除私有历史，不创建永久不可删除数据。24日历月按实际收集时间逐版计算，到期立即拒读/replay；物理清理/备份传播留T40/T44，不宣称已实施。

创建仅用既有T49 `profile.create`+Idempotency-Key，receipt只root UUID/version；同key同payload回放原确认版本，不能把旧receipt变成最新版本，也不能跨用户。追加仅严格CAS，不改T49 operation闭集/旧头；相同旧CAS重试409，网络丢响应后重新读取当前版本核对，不能自动覆盖或冒充已确认。所有registry/root/version/receipt/必需审计同Session/TX；ownTX成功COMMIT后才响应，callerTX异常整笔回滚。锁账户→会话/角色/用途→receipt→registry/root/版本，按现有服务顺序复用；输入/构造copy绕过及错mapper同engine校验在业务IO前拒绝。

当前账户/会话/student/owner、核心用途、原notice/consent/declaration、版本期限在读取/写入/replay与审计之后重验。T49 verifier后还有身份SQL，故create使用外层同TX并在其返回后再做最终检查；最后SQL之后用一个fresh now聚合会话/角色/成年声明/版本期限、创建收据expires_at和冻结配置，不在检查后再做业务SQL或审计。等待导致失效时无payload返回、无部分写入。列表SQL先按当前owner/type/active及版本有效证明过滤，再有界keyset分页，不先全量读后Python过滤。

## 最小HTTP

独立`profiles` profile继承现identity16个path，旧五profile/M0不变，默认factory不连接DB/seed/IdP，业务503。所有私有路由复用当前Cookie/no-store/安全错误，unsafe须固定Origin+CSRF；不相信客户端owner。

下表为6个操作/5个新path item。所有成功为200 Envelope；新局部ProfileMeta/ProfileEnvelope在具体版本读取/写入填实际profile_version_id和synthetic/real，list/context为null，旧identity的Meta钉null不改。本人引用列表是有界`{items,next_cursor}`小范围DTO，cursor最长2048；此处不冒称通用PageInfo协议。静态private factory的`/openapi.json`沿继承行为200，parent的根schema/docs路由404，均无需数据库；schema公开不代表业务开放。

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| GET | /profiles/context | 服务器当前能力/关闭原因，不等同永久授权；不加载成绩；创建能力另受T49冻结开关限制 |
| GET | /profiles | 本人有限root/version引用列表，limit<=20、actor/当前窗口绑定cursor |
| POST | /profiles | 明确确认新root首版；唯一有界Idempotency-Key |
| GET | /profiles/{profile_id} | 当前确认版本；foreign/missing/deleted一致404 |
| GET | /profiles/{profile_id}/versions/{version_id} | 明确UUID历史版本，同root与当前证明；不读取他人版本 |
| POST | /profiles/{profile_id}/versions | 明确完整新版本，strict expected_current_version CAS |

## 修改范围与可测试验收

新增app/profiles/schema/model/store/service/router/默认关闭factory、独立迁移ini/env/0001、纯/PG专项；生成器只显式profiles路径/body/UUID/header白名单及新OpenAPI/TS/LF产物和契约/类型测试。T23不修改前端UI、旧模型/服务/迁移/生成产物/依赖。root更新当前文档、ADR036、CHANGELOG/tasks和验收记录。

1. 双用户所有列表/当前/历史/写/replay隔离，伪owner/role/verified/confirmed拒绝；管理员及metadata-only grant不读payload。
2. null/零/实得预测同时保存、有限精确数值/单位/满分；课程/路径unsupported与省份/所在地/身份独立，未知不造事实。
3. 缺成年/core/坏告知/撤回拒绝；撤回再确认不复活历史或收据，仅明确完整新版本重绑定。所有读取、回放与更新即时重验。
4. 两Session相同expected版本只有一个追加，首版并发samekey一资源；旧版hash/内容不可UPDATE，root指针/owner/mode跨域FK负例；真实deferred COMMIT失败registry/root/version/receipt/audit整体回滚。
5. 实际PostgreSQL锁等待后session/role/age/version到期拒绝；same-engine逐mapper、冻结配置及构造绕过；失败固定安全错误、不泄露请求内容。
6. 显式增量迁移重复升级/降级、父域/M0保持；启动无DDL。专项/相关回归、契约漂移/原文/治理、TS Type Check/demo-auth Build；Lint/Python静态类型无入口明确未执行。真实用户/供应商/法律/SQL权限/清理备份/部署不执行。

完成验收、文档同步及PRIVATE源码推送核对后，按批次授权进入T24，不自动开放真实业务。

## 显式本地运行与关闭边界

无密钥可构造静态契约与关闭状态：`.venv/Scripts/python.exe -m uvicorn services.api.app.api.profiles:create_profiles_app --factory --host 127.0.0.1 --port 8000`。业务默认503、无数据库/身份供应商I/O，这条为运行说明，本次未另起浏览器服务器。现无真实开启环境变量或自动fixture入口。要实际开发联调须自行提供同engine的Auth/Privacy/Idempotency/ProfileService依赖；只能在明确隔离测试环境用合成身份与已确认核心用途，不能使用真实学生。

迁移仅显式管理员开发动作，先完成auth `0006_audit_t10` 与idempotency `0001_idempotency_t49`，再设置未提交的`PROFILES_DATABASE_URL`执行 `.venv/Scripts/python.exe -m alembic -c services/api/profiles_alembic.ini upgrade head`。独立版本表为`profiles_alembic_version`，head=`0001_profiles_t23`；同一数据库各profile相互保留。应用启动只读校验，不自动建表。验收实际在各case隔离schema中以Alembic Python API升级/重复升级/降级，不把此说明命令冒称已另外执行。

纯离线契约及单元可执行`.venv/Scripts/python.exe -m pytest tests/unit/profiles tests/contracts/test_t23_profiles_generation.py -q`；集成需显式`T23_TEST_POSTGRES_URL`及本地隔离PostgreSQL，缺配置须显示跳过，不能算通过。合成正例只是开发验收，没有已核验成绩、已审全国规则或正式隐私处理许可。
