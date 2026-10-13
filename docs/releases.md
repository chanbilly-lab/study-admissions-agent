# T19 不可变发布与撤回契约

2026-10-03代码前冻结。T18/T49已验收保存；本Task内部发布接口、迁移/离线测试，无HTTP/UI/影响分析/通知消费/正式事实发布。T25规则尚未实现，因此facts-only release的ruleset_version显式null，requirements_version为服务器事实成员快照hash；不伪造已编译规则或可执行资格。真实数据门槛保持关闭。

## 数据与范围
app/releases/{init,schemas,validation,models,store,service}，独立ReleasesBase五表/profile0001_releases_t19：catalog_releases（不可变release ID/version1、dataset/entry_year、kind、UTC适用半开区间、内容hash/requirements_version、ruleset_version=null）、catalog_release_members（不可变指定fact+T18决策/revision、原事实/范围/证据/source/file快照指纹与显式public_evidence）、catalog_release_states（published|withdrawn|replaced及revision，每dataset/year仅一个published，partial UNIQUE）、catalog_change_events（不可变published/withdrawn/replaced责任轨迹）、catalog_outbox（event唯一、pending无消费者）。冻结旧profile/head，无新依赖，不更新T17/T18历史。审计actor/audit ID是责任trace而非阻挡D06清理的永久FK。
PublishRequest：dataset_id/expected_dataset_revision/entry_year/kind=formal|test_fixture/valid_from/valid_until（UTC、半开、不推断年份）、members（1..50，fact_id/expected_case_revision/expected_decision_id/public_evidence全显式）、replaces_release_id及expected_replaced_state_revision成对nullable；每fact和logicalkey唯一，成员按UUID规范排序。idempotency key为SecretStr单独输入，不存原key。file_sha256指原字节SHA256，内部file_metadata_sha256另保存FileData指纹（不输出到公共DTO）；文件ID精确绑定原import，不用相同字节copy续期。所有派生hash/角色/发布时间来自服务器。WithdrawalRequest：release_id/expected_state_revision/有限reason_code（INCORRECT_FACT、RIGHTS_REVOKED、SOURCE_UNAVAILABLE、ADMIN_REQUEST），没有自由文本或模型操作。
发布DTO仅bounded metadata+member IDs/指纹/状态，内部不可视为公共查询；不得返回Storage路径/key/fullbytes。ReleasePolicy enabled/real_releases_ready/allow_test_releases默认false。formal永不接受synthetic/DEMO；正向离线原子测试只能test_fixture且is_synthetic=true、runtime=test，不能伪造真实学校数据或进入production/正式verified数据集/正式公开渠道；runtime=test/data_mode=verified配合demo dataset的既有合成身份fixture不改变。

## 发布与撤回
首版仅在valid_from<=当前UTC<valid_until的已生效窗口发布，不支持预定发布；周期与资料期限分别检查。发布重验当前强catalog.publish及T18同TX当前批准（包括独立审核者、完整冲突快照、原值/范围/证据/当前文件期限）；来源publication_permission独立granted且有basis/ref/审核日期/复查期限，manual import许可不等于public许可。所有成员同dataset/year/mode、指定Offering版本，member保存有界TypedCandidate+SnippetData原DTO及精确source/file绑定指纹（不重复存完整许可文本/路径/owner）；引用和快照明确固定，不因未来新子记录扩充release。未知/未审/过期/未解决冲突不能发布；明确处理并通过T18的冲突仍保留历史边，不将历史边非空误判为未解决。
T49 catalog.publish同Session包裹本事务，重新校验receipt资源和当前权限；内容自然去重独立于receipt TTL，重发不重复release/事件；撤回或替代不能由重复发布重启旧release。成功发布/替代/撤回使CatalogDataset.revision+1（替代整笔只+1），自然去重/receipt重放不增加；发布需expected dataset CAS，替代同时需旧state CAS，撤回需state CAS。发布、members/state、成功audit、ChangeEvent/outbox及receipt一起COMMIT或全部rollback。最后SQL/审计后再重验所有proof并在无后续SQL处重验source/file/MFA/适用窗口，caller异常同EngineactiveTX整笔rollback。
每dataset/year只一个当前published；不同新内容必须显式替代，不能静默抢占。替代只能同dataset/year已发布旧版、expected state revision一致；原版状态变replaced、新版发布及两事件/outbox同事务。撤回是减权操作：当前strong catalog.withdraw/mode/config与精确state CAS，旧source/file/approval已失效仍可撤回metadata，不要求失效事实再通过；保留不可变release/members/事件历史。没有消费者，不声称通知/影响分析已运行。

## 测试用例与限制
纯测试严格DTO、kind/时间/范围/重复/版本/显式引用。隔离PG：DEMO→formal拒绝、未审/缺证据/失效冲突/跨dataset/year/未授权来源拒绝，成功test_fixture固定成员及源、重复key/新key/TTL去重，audit/outbox/deferredCOMMIT失败全部回滚，实际SQL锁等待跨file/source/MFA期限，两主体并发/expectedrevision、撤回失效旧proof、替代原子性/历史不可变及独立迁移往返保留。
真实正向发布、正式身份/法律/资料权利/SQLGRANT/RLS/清理备份/部署不执行，必须明确未执行；test_fixture不是正式release验收资料。公共HTTP/筛选/证据权限由T20单独实现。
