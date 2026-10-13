# T16 不可变文档与证据契约

2026-10-03实施前冻结；只DEMO合成和隔离库，无真实事实/自动采集/模型/OCR/新依赖。

## 数据与版本
EvidencePolicy默认enabled/real_evidence_ready=false。DocumentCreate：dataset_id/source_id/source_version/document_reference/language；VersionCreate：document_id/expected_current_version/file_id/file_sha256。文件必须exact三source refs、当前责任人/强data_admin/manual许可/期限。document_reference封闭ASCII/合成DEMO，language显式zh-Hans|zh-Hant|en|und，不猜语言。Document根及DocumentVersion、EvidenceSnippet三表独立EvidenceBase/evidence profile0001，前置auth006/catalog003/storage001；root只递增版本指针，版本与片段UPDATE/DELETE由DB trigger拒绝，可信维护/恢复须另授权。相同bytes/hash不得因副本重建同版本；不同hash新版本，expected_current_version旧值409。无文件原文则无hash。

SnippetCreate：document_id/document_version/offering_id/offering_version/entry_year（断言）/byte_start/byte_end。当前限定<=1MiB UTF8 JSON/CSV原文，片段精确半开byte范围，UTF8边界/非空<=4KiB；行号由实际原字节推导，不是CSV逻辑记录号。输出locator携带byte/line_start/end、page=null、section=null、location_kind=utf8_byte_lines；PDF页面/OCR及结构化节适配尚未实现，PDF明确拒绝，不伪页码。片段原text及hash落不可变记录；无trim/转写，HTML仅字符串无执行。项目/年/身份/路径等适用范围由exact offering版本及服务器root派生，不能由输入换scope或推断；所有scope key（包括unknown）保留。

SnippetData最少id/document/version/offering/version/entry_year、language、hash、text、locator、synthetic、created_at；不返回file_id/path/backendkey/owner。创建不代表已审/已发布，T18/T19另行验收。

## 事务与检查
原bytes由Storage.read_source ownTX实际核hash；I/O在业务TX外。随后同Session创建/检查依赖exact Source/File/current offering+mode，audit后重新核角色/MFA/source许可与到期再COMMIT。创建重复同docVersion/offeringVersion/span返回同片段；不共享到跨scope。get_snippet与verify_in_transaction每次重验当前文件metadata存在/exact hash/quarantine/到期及source当前版本/手动许可，expired/deleted/revised不能成为依据。verify_in_transaction须输入expected offering/year/version，任何不匹配409；只返回经过严格DTO重建的有限片段，供后续受信领域使用，不调用模型或形成规则。

管理员内部审核读允许当前catalog.review强认证主体读取同dataset的有界已生成衍生片段（非全文件权限）；SourceService current policy与current responsible配置须通过、文件metadata exact refs/hash/status/expiry，auth/source/storage/evidence全部同Engine。该内部衍生读不提供Storage full bytes，不涉及student_private，不给前端owner/角色权。T18仍应实施职责限制；公开读T20另加published release及public permission，不允许拿此管理接口公开。

## 修改与验收
新增evidence模块/独立迁移/pure locator测试/隔离PG测试/合成manual-review原文与报告及治理文档。旧模型/迁移/heads/HTTP/wire/UI不改。pure hash/UTF8/边界/行号/unsupportedPDF/复制DTO；PG 新版/旧版追溯/不可变trigger/错项目年身份版本/mode/许可失效/当前角色MFA/commit审计失败/sameMapper/并发与重复迁移。人工抽查合成原文片段另待用户确认；真实原文行业审核不由此代替。相关imports/storage、契约模式、前端Test/Type/双Build、原文生成/范围；未执行项分别记录。

合成抽查原文件通过.gitattributes -text保留原字节，避免Windows checkout换行导致hash/位置变化；scope_sha256固定服务器派生完整EvidenceScope，用于拒绝维护SQL改变父scope后继续复用旧证据。

有界衍生getter不读完整原bytes：hash对比为Storage metadata与创建时实际验过的不可变文档hash；不宣称每次重新核磁盘blob存在/外部维护修改。实际version/snippet创建才经Storage read核真实bytes/hash。物理文件恢复/清理、生产ACL及可信维护后恢复验证另待验收。

2026-10-03收尾：合成定位材料已由用户直接确认，T16完整验收完成；仅确认A/B/C原文抽查，不代表T18招生事实审核、T19正式发布或上线门槛解除。
