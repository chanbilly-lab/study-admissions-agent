# T18 人工审核决定契约

2026-10-03代码前冻结；内部显式人类操作接口，测试仅模拟DEMO审核主体，不是对真实招生事实的人工审核。T17候选和冲突历史不修改，无模型/自动审核/发布/HTTP/UI/新依赖。

## 数据与修改范围
独立app/reviews/六模块（init/schemas/validation/models/store/service），ReviewsBase三表review_cases（每logical_key_hash唯一的版本锁/当前选择）、review_decisions（不可变逐次判断）、review_conflict_resolutions（不可变被选候选与其他冲突候选的处理）。独立0001_reviews_t18/profile，旧heads/Base冻结；两个历史表UPDATE/DELETE拒绝，case仅版本递增，不直接写事实或release。
ReviewRequest：fact_id/expected_fact_version=1/expected_case_revision（0表示尚无case）、action=approve|return、checks（全部固定关键字段逐项accepted|rejected|not_applicable）、conflict_resolutions（明确其他候选ID+有限reason_code）、return_reason（有限reason|null）。所有字段显式，服务器派生reviewer/时间/事实/证据/原文件/范围指纹；客户端不能传角色、审核时间或改value。
固定checks：original_value、claim_kind、unit、period、scope、evidence_location、missingness、footnote、statistics_context、date_context。每项恰好一次；approve不得rejected，前8项必须accepted；statistics/date未适用时才允许not_applicable，适用时必须accepted。return须明确有限原因且conflict_resolutions为空，不假造选择/处理或完整性。return_reason有限码为INVALID_VALUE/MISSING_EVIDENCE/SCOPE_MISMATCH/UNIT_MISMATCH/PERIOD_UNCLEAR/MISSING_CONTEXT/FOOTNOTE_UNRESOLVED/SOURCE_UNAVAILABLE/CONFLICT_UNRESOLVED/UNSUPPORTED_LITERAL；冲突处理码为SELECTED_SUPPORTED/INCORRECT_VALUE/WRONG_CONTEXT/DUPLICATE_OR_EQUIVALENT。
DTO输出审核case_revision、decision_id、fact_id、action、检查/处理记录、server reviewer UUID/UTC、is_synthetic和current approval状态，不含原文件路径/fullbytes/异常；不是公开目录DTO。ReviewPolicy enabled/real_reviews_ready默认false。

## 批准条件与冲突
批准要重验T17当前bounded候选、精确T16证据（原文件与项目/年度/版本绑定）、全部15个ScopeKey不得unknown、必要原value/claim/unit/period/脚注/统计口径和日期完整；用type_candidate重新检查基础state=review_required，即使历史state=conflicted也不能跳过draft检查。定位由T16byte/line/hash提供；原值、原unit（若有）、present脚注必须能在所引有界原片段内对照。十进制原literal要求完整token，防60从600或-60匹配；文本/原unit避免单词前缀误对照，中文元不能从万元或分从分数取得；只字面边界、不分词/猜比例。仅做文字对照防错引用，语义由显式逐字段人类判断，不宣称程序完成真实性或法律审核。复杂转义/分散脚注不能对照时canonical422 INVALID_REVIEW_INPUT保守拒绝；UNSUPPORTED_LITERAL仅为人类可显式选择的退回原因，不自动造决定，后续适配另Task。
审核者必须当前强data_admin/catalog.review，且与ImportBatch.actor_user_id不同（按服务器账户UUID隔离职责，不声称已核验自然人多账号）；来源责任不因此转移，审核者不获全原文件权限。真实运营责任/身份/来源门槛保留。
每logicalkey只一个当前被批准候选。审批者明确选择当前fact，必须逐一处理当前所有conflicting_ids（有界200、固定理由）；缺/多/陈旧IDs一律409，不能默认取最高/最新。保留T17边不变；独立case胜者投影限制不会出现两个矛盾值同时批准。新冲突出现后原处理快照不匹配，当前批准失效直到重新审核。return清空该case当前批准，但全部决策与已发布历史仍保留。

## 权限与事务
ReviewService(fact_service,store,policy)提供decide/get_case/approval_in_transaction；get_case在当前强catalog.review/policy/mode验证后只给有界case引用，已绑定case的当前事实/来源/file proof409时current_approved=false供历史追溯，不给原值/片段、不吞401/403/503；原文件过期/删除若T16返回404则get_case也拒绝，未知对象404不转换；decide与approval始终严格拒绝失效proof。ownTX COMMIT后返回，callerTX仅暂定，异常同Engine active TX整笔rollback，错Engine不触碰。当前capability/签名强认证/来源许可/旧原文件状态与期限/当前Scope/原row/date/evidence指纹复用T17/T16同Session。case INSERT ON CONFLICT再FOR UPDATE，expected_revision防丢决策；冲突snapshots、追加判断/处理、case指针及catalog.review成功审计同TX。最后锁/审计/授权边界后重验并本地时效检查；审核成功不发布、不改T17hard_rule/publication_eligible。
approval_in_transaction供后续T19显式消费，必须当前caller强权限、case所选决策与请求revision匹配、当前事实指纹/冲突集合/证据/期限仍有效。旧decision不能独自当当前授权。不要在锁内调用get_fact自有第二TX。

## 验收
纯测试固定checks/原因/批准对照/必要上下文/namespace/copy-construct；隔离PG实际通过/退回/完整冲突解决/旧历史保护、缺证据/必要Scope/draft、自己审核/角色/MFA、expected revision与新冲突、真实两主体并发case争用、审计及deferredCOMMIT回滚/重试、file/source expiry等待、同Engine/caller rollback/独立迁移重复与降级恢复。无真实资料/模型/外网；全量原文件的physical恢复不属于本模块。
