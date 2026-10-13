# T37 可替换模型接口与离线预算

2026-10-04代码前冻结，现源码与合成隔离验收完成；用户本批只授权接口和离线验证，D05实际供应商/地域/费用/数据流审查未完成，LIVE关闭。M0 providers.py与V2RuntimeSettings不改，不让当前启动接受live，不增加网络或依赖。

## 数据契约

新增app/model_gateway避免既有providers.py重名。冻结策略包含data_mode demo/verified、model_mode disabled/mock/live、environment development/test/production；verified+mock与production+demo拒绝，live调用在provider/预算/IO之前明确LIVE_UNAVAILABLE，不回退。disabled明确MODEL_DISABLED，无需key并不影响原确定性核心。

只读ModelRequest包含精确Scope(dataset_id/entry_year（2000–2100）/offering_id/offering_version)、有界question<=1000字符和最多20条EvidenceAtom；atom只有citation_id UUID/version>=1/kind text-number-date/value<=2000字符/is_synthetic，与scope逐条绑定，不传学生画像、owner/session/成绩、权限、URL或工具指令。输出有限StructuredAnswer：answered/unknown、最多20个Claim(citation_id、value)和最多3个固定AdviceCode；无资格结论、自由HTML/脚本或任意动作。ProviderResponse还有严格非负input/output usage整数及固定synthetic标志；再次校验构造/复制绕过。

ModelProvider可替换async complete(request) Protocol，OfflineMock仅demo明确合成。接口失败/超时/取消/坏结构/超额度有限代码，无原异常/prompt日志，不回退。输入输出与预算再次验证，T38后续才做证据引用语义校验。供应商不能得到DB/SQL/Shell/文件/学生服务。

BudgetPolicy限制请求次数、输入输出总token单位、每次输出、并发及超时和单调窗口；trusted BudgetKey由服务装配给出，不接客户端owner。进程内有界quota，先按输入UTF8字节的保守单位加max_output_tokens预留worst-case并计入调用次数，失败/timeout同样消耗预留，禁止虚报低usage逃额；实际usage仍记录且不得超单次输入/输出与预留。并发与超时可解释，取消释放并发；窗口/身份键容器有限防无界增长。时钟回退关闭。预算是离线产品限制，不是厂商token化/价格；正式跨进程持久预算与地域评审未实施，不允许生产模型调用。

## 修改范围

只新增model_gateway纯模块、必要离线async服务集成测试和独立安全专项；七治理文档及本契约/验收，无迁移、HTTP、前端业务、旧生成工件、供应商密钥或依赖变化。

## 可测试验收

严格模式/有限DTO/未知字段和恶意构造拒绝；disabled/live provider零调用；verified不可mock；真实async stub成功、timeout/并发/额度/取消/坏usage/结构失败及无fallback；quota窗口/键上限/保守扣量/时钟边界。原无密钥核心与相关模式/规则回归；全前端Tests/TypeCheck/两Build及原十profile检查。Lint/Python静态无入口标未执行；无实际供应商/live smoke或数据传输，不能把offline stub写成live通过。

结果见[验收](acceptance/T37_model_gateway.md)。

## 有限接口明细

ModelScope：canonical UUIDv4 dataset_id/offering_id、entry_year严格整数2000–2100、offering_version1..2147483647。EvidenceAtom同scope/citation UUIDv4/version、text-number-date、value1..2000字符；ModelRequest question1..1000/evidence最多20且citation唯一。StructuredAnswer answered必需非空claims、unknown空claims；Claim值平文本，不含尖括号，建议闭集REVIEW_SOURCE/CONFIRM_WITH_INSTITUTION/MISSING_EVIDENCE且不重复。ProviderResponse合成标识严格true；input/output_usage非负且不得超过预留。

离线默认每可信key每窗口10请求、100000输入UTF8字节单位、10000输出单位、并发2；全局100请求/1000000输入/100000输出/并发4；max_output_tokens512（保守answer规范JSON UTF8字节单位，正式vendor token化未配置）、timeout1000ms、window60秒、max_keys128、history256。最大边界由strict BudgetPolicy规定；整个provider请求的JSON字节作为输入保守量，整个answer规范JSON字节另核输出上限。失败/timeout/cancel均不退款；history只有固定reason及预留/实际usage，没有问题/证据/身份/私有数据。
