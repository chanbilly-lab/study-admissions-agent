# T38 范围检索与严格引用验证

2026-10-04代码前冻结，现源码与合成隔离验收完成；仅本Task，本批到T50。新增qa类型化只读端口，复用T20当前公开证明，模型live/真实资料仍关闭。无SQL/Shell/URL工具、向量库、爬虫、HTTP或前端，也不改旧数据库/迁移。

## 数据契约

RetrievalRequest只含release_id UUIDv4、offering_id UUIDv4/version>=1、entry_year严格2000..2100、scope:RequestScope、intent闭集requirements/materials/dates/fees/background、至多5个有界literal keywords；不含owner/session/profile/grades/tools。RequestScope为EvidenceScope去除dataset_id的20字段（institution/program/year/country/本科/省/pathway/course/applicant等），嵌套extra也拒绝。ScopeKey只在known/not_applicable时允许匹配；unknown范围保守unknown，不能放宽到全省/其它路径。数据集ID由服务器当前release派生，再构造完整21字段EvidenceScope，不接客户端伪dataset。请求内年份与entry_year、完整scope和精确release/target/version/year必须一致，关键词只对已经筛选的公开字段做文字匹配，不作SQL/regex/命令。

ScopedRetriever内部受信CatalogReader，冻结独立配置指纹，在其同Session事务先锁dataset再release/state/member；只当前published成员，逐条复用AnonymousProofVerifier当前T18审批/T16原文/来源/许可/文件/期限，不借旧publisher或学生Principal。选定项目后最多20个引用；数量或单项超过边界明确unknown/限额，不能偷偷截成完整答案。不给模型学生服务或原文件定位；原quote只能当数据，不能控制执行。

CitationData含服务器确定性有限projection UUIDv4 id/version=1、实际evidence_id、release_id/version/requirements_version、offering_id/version/year、完整scope、is_synthetic、field_key、原PublicFactData（原义/单位/满分/脚注/年份/分母/日期精度）、PublicEvidenceData（原quote/hash/locator/publisher/authority_claim）。projection ID由当前不可变公开内容与scope的canonical SHA产生固定版本4 UUID，不暴露私有import/candidate/学生ID；同一证据多个字段独立id，不冒称真实源证据ID。数字和日期用于回答的value由服务器公开typed fact生成，不转换日期到23:59，不把calculated_utc候选当official UTC，不混统计/历史最低分与当前硬门槛。

RetrievedBundle含精确request、服务器model_scope:ModelScope或null、release_version/requirements_version/content_sha256（无当前依据时null）、pin_sha256、有限citations/对应T37 EvidenceAtoms、unknown_reasons、retrieved_at和明确synthetic。时间与内部proof期限由服务器产生；公开wire不含authority grant或私有facts。ModelAtom citation_id为上述projection id/version1/kind text-number-date/value<=2000，完整ModelScope绑定；value为保留原义的PublicFactData canonical JSON，排除evidence/candidate/学生等身份字段。T39展示应映射Citation.fact类型化字段，不直接显示内部JSON。无依据/缺失/未公开quote/未知日期计算明确unknown，不由模型补值。官方source仅按原authority_claim展示，不把DEMO或claimed_official升级为真实官方核验。

validation.validate_answer(retriever,bundle,StructuredAnswer)只接服务端结果；必须重新获取当前同精确request证明以防模型等待期间替代/撤回/来源到期。Bundle自身hash、synthetic或reviewed标签都不是权限；比较完整当前公开pins/context/原子，不比较刷新后的retrieved_at值。逐条核ID唯一/存在/完整scope/version/source pins，Claim.value必须与该当前服务器atom完全一致（含数值/日期原义）；只有限固定通用建议，不能夹入自由数字/日期或资格结论。重复/错项目/错年/伪引用/坏值拒绝整个回答，不返回已通过部分。unknown无claim，参考来源失效也不能继续当当前事实。纯validate_claims(bundle,answer,current_bundle)用于固定离线金标准，调用者提供的current_bundle不能替代实际PG证明。

同TX最后必需SQL后用fresh now检查完整公开proof/source/file/release时间；无学生查询/写入，模型等待期间不持DB长事务。真实读取默认关闭，test+demo只显式已审批/发布合成夹具，query/validation纯金标准不能代替实际PG证明。

原始公开日期可作为忠实的类型化陈述引用；DATE_UNRESOLVED表示精确期限计算仍未知，不能把date-only推成日终，也不能把UTC计算候选当官方期限。historical_statistic/typical_offer只作background参考，不能进入requirements硬条件回答。

闭合DTO预检还限制累计原生UTF-8预算262144、12000节点、深度24；整体公开投影超过该安全预算只保留已证明版本pins并返回空引用/原子与LIMIT_EXCEEDED，不截取部分答案。损坏字段或证明错误仍拒绝，不能以限额降级掩盖。固定评测文件采用独立预期与SHA，仅检测夹具完整性，`.gitattributes`为该文件固定LF以保证Windows检出字节一致；SHA不证明当前权限或真实领域审核。

## 修改范围

新增 app/qa/{schemas,retrieval,validation}.py（按最小实现可拆），新unit/隔离PG专项；data/evals/qa小型手工固定合成金标准和离线校验脚本/测试。七治理文档及本契约/验收；旧T20原工厂、全部生成工件/M0/依赖/迁移保持。T39之后另Task再HTTP/UI。

## 可测试验收

纯strict范围/闭集工具/复制构造/未知/数量与值边界；人工固定合成金标准至少12个独立有意义案例（错年/项目/版本、数字/日期/未知、注入、单位/原义不变），报告真实样本/分母，不能冒真实领域审核。实际PG当前已审批发布positive、候选/替代/撤回/未知范围/无公开quote/来源过期拒绝；scope过滤先于关键词；匿名读取不查询学生/无任意SQL，旧业务物理不变。模型等待后引用重验失效以及末SQL等待过期。相关Python/原十profile、前端Tests/TypeCheck/双Build、原文/文档保护；无Lint/Python静态入口注明未执行，真实模型/资料审核/部署均不执行。

结果见[验收](acceptance/T38_qa_retrieval.md)。
