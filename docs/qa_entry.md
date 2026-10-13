# T39 有限证据问答入口

2026-10-04代码前冻结，现源码与合成隔离验收完成；仅本Task，本批T50停止。T38已PRIVATE保存；真实live/资料/公众部署仍关闭，无新依赖/迁移、不给模型私有服务。既有十profile/M0保持。

## 数据契约

独立api/qa create_qa_v2_app/create_qa_app仅继承T20公共目录三个只读操作，新增GET /qa/context与POST /qa/answers；mount /v2，默认verified+disabled无key/DB/provider初始化，capfalse且MODEL_DISABLED。production/demo/mock/live拒用原V2模式边界，live仍不接受启动；错误不回退DEMO或既有M0。明确test/demo/合成mock注入才允许有限调用。/config/offerings/evidence沿用T20原形状，不改变旧公共工厂。

QAContextData冻结schema_version v2.t39、can_ask、model_mode disabled/mock、live_available=false、real_processing_enabled=false、allow_test_fixture_read、demo_banner明确合成或null、disabled_reason有限代码或null、budget_unit=conservative_utf8_bytes。context只配置检查，不能当某项目已公开证明；不读取Student/Auth表或预算clock。

POST body仅复用RetrievalRequest（release/target/version/year、无dataset的20完整RequestScope、requirements/materials/dates/fees/background、最多5 literal keywords）；不收自由聊天、画像/成绩/owner/工具/确认。UTF8 JSON先按16KiB上限流读，拒重复keys、NaN、额外字段/query、坏content-type/idempotency-key，错误无原输入/SQL/供应商prompt。未启用或disabled在DB/provider/配额IO前拒绝。提问文本由服务器根据意图固定生成；keywords只文字检索，不交模型作指令。

沿T38原默认契约，keywords可省略并规范为[]；null与额外字段不接受。前端冻结明确body后比较服务器规范化request。模型选择unknown且不引用任何事实时，已核验发布范围可保留，未提供检索原因不编造新的原因。

QAService先T38同期精确retrieve→无atom或范围未知时直接unknown（不虚构模型答/不消耗模型预算）；有已证atom才经T37 async gateway，等待不持DB TX，最后再T38实际current proof整答核验。可信BudgetKey为服务固定实例键，客户端不能控制或每请求新建逃额；共享全局/匿名应用预算，offline输出max4096 JSON UTF8单位，不是供应商token/计费。timeout/failure/budget/坏引用固定错误；旧核心服务与无key读取不被模型阻断。pipeline/settings/gateway引用与独立配置指纹每次重验。

QAAnswerData冻结schema_version v2.t39/status answered|unknown/request/model_scope可null/release_version可null/requirements_version可null/content_sha256可null、最多20 CitationData、最多3固定advice_codes、有限unknown_reasons、is_synthetic可null、model_mode mock、live_available=false、generated_at UTC。只返回实际通过Claim引用的typed CitationData；不传内部atom JSON或自由模型文本。Citation.fact按原值/单位/脚注/统计分母与真实届/原日期精度显示，Citation.evidence原quote/hash/locator/publisher/authority_claim只作纯文本引用。原数字不经JS Number丢精度；日期calculated UTC标候选/official UTC未知；claimed_official只来源声明，DEMO不冒真官方。模型通用建议只固定标签；不改资格、画像、事实、权限、计划或申请。

错误复用v2标准ErrorEnvelope与status，details仅固定qa代码（MODEL_DISABLED/LIVE_UNAVAILABLE/MODEL_TIMEOUT/BUDGET_EXHAUSTED/CONCURRENCY_LIMIT/KEY_LIMIT/BUDGET_UNAVAILABLE/INVALID_PROVIDER_RESPONSE/PROVIDER_FAILURE/CITATION_CONFLICT/QA_UNAVAILABLE等），不扩旧共享错误枚举；timeout/provider坏响应安全503，quota429，坏引用409。旧服务/生成文件的行为保持。

## 前端与修改范围

新features/qa client/严格response校验/状态/折叠面板；CatalogView传明确所选公开项目，AuthView仅optional qaApi透传，无学生数据传入。默认折叠无额外QA请求；用户明确打开/检查入口/选择意图/提问。展示model disabled/unknown/timeout/quota/坏引用，源版本与适用范围、原文展开、固定一般建议分开。更换target/intent/重新检查/收起卸载清空旧状态，Abort＋generation拒迟到200/跨范围回复；不以客户端checkbox打开服务。v-html/任意链接/HTML执行禁止，不自动重试贵调用。网络credentials omit/cache no-store/redirect error，同源/qa prefix（dev loopback8003）。

只当前13旧路径（治理7/API/.gitattributes/契约生成器/Vite/AuthView/CatalogView）与新qa HTTP/service/wire、独立qa生成profile/前端及新专项；旧T37/T38四源、旧生成20工件、后端旧业务/数据库/迁移/依赖/M0/原文不改。OpenAPI/TS同步生成并固定LF，无any兜底。

## 可测试验收

默认无key context/answer明确关闭且零DB/provider/预算IO；strict JSON/闭合输入/模式漂移；实际async成功、unknown/timeout/额度/坏引用不fallback；实际专用PG-HTTP公开positive/完整scope/等待期间替代撤回/匿名无StudentSQL与旧业务不写；两owner/私有字段不能进入请求或读取。前端DOM纯文本注入、日期/数字原义、disabled/unknown/失败、明确目标与迟到200/changed scope拒绝；实际PG+浏览器有限闭环，绝不把route stub当实际证明。全相关Python/前端Tests/TypeCheck/demo-auth Build、十一profile及M0/原文检查，Lint/Python静态无入口标未执行；真实供应商/资料/身份/法律/部署未执行。

结果见[验收](acceptance/T39_qa_entry.md)。
