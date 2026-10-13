# T15 人工结构化导入契约

2026-10-03实施前冻结，仅合成离线候选基础，不OCR/爬取/后台Task或公开事实，不改变既有架构/依赖/HTTP/旧迁移。

## 数据契约

ImportRequest严格额外字段拒绝：dataset_id/source_id/source_version/file_id/file_sha256/format(json|csv)。身份由当前Principal，is_synthetic由服务器dataset/source/file推导，不收owner/role/reviewed/published。每行closed fields：offering_id/offering_version/entry_year、source_record_reference、fact_type(requirement|score|fee|material|date|statistic)、field_key ASCII、value_kind(text|decimal)、value_text|null、unit|null、missing_reason|null、footnote_state(present|none|unknown)、footnote_text|null、locator|null；字段必须显式给齐。decimal仅≤64字符十进制词法字符串，不转float、不猜单位/最低门槛或当前年。缺value需明确原因，脚注未知与无脚注分开，定位null保持unresolved，T17再类型化/冲突建模。合成record reference须DEMO_，真实不能使用DEMO。

JSON根array，只exact封闭字段/原生类型，无重复key/nonfinite/nested injection；CSV按上述13字段固定次序的精确唯一完整header，整数严格词法后有界转换，nullable用显式\N，不trim/NA/空串推断null。≤1MiB/200记录/单字段UTF8≤4KiB，拒超界不启动后台任务。JSON行号从1，CSV逻辑记录号首数据2；多行quoted CSV不得假装物理行号。

ParsedImport rows/errors/total_rows；只要任一行错误，整批rejected且零candidate写，durableerrors仅行号/封闭field/code，不保存原行/错误值/自由异常。无法计算总量的结构错误total_rows=null、row_number=0；空array总量0但rejected。ImportResult仅id/status/counts/errors/replayed，不能把rejected显示为已导入事实。

## 事务、权限与范围

Storage.read_source进行有界bytes/hash验证，在业务TX外解析；之后T49catalog.import同TX perform与verify必须调用get_source_file_in_transaction(expected_dataset_id/source_id/source_version全部三项)，核对server hash/size/media、当前强data_admin/MFA/来源责任/manual_import许可/期限。管理主体按现有T13强管理员配置，不从student core推导或冒称年龄核验。ImportsPolicy默认enabled/real_imports_ready=false。T49/Source/Storage真实门槛同样保留。

每行offering/version精确同dataset/synthetic且entry_year等于服务器机会，不按名字注册机构、不覆盖当前/历史/发布资料。ImportBatch与CandidateRow/RowError三独立表，profile显式迁移。候选固定draft/evidence_unresolved，所有值是待审核管理员输入，不成为硬规则。row_count未知保持null。

自然唯一键(dataset,source,source_version,file_hash,format,parser_schema_version=T15_v1)，跨key/receiptTTL不重复写，回执与T49/审计同TX。自然键不含file_id时旧batch绑定的original file亦重验，不能借newcopy续期；deleted/expired旧资产不能自动复活。原文件修改不同hash创建新batch而不清旧版。request与oldbatch both scope verified；操作与重放、最终审计后再核。不支持外部副作用或第二数据库连接持锁。

## 修改范围与测试

新增 app/admin/imports/、app/ingestion/、独立imports profile/0001、pure与PG专项、当前契约/验收及治理文档；旧head、原文件、wire/UI/依赖保持。重复/不同key/并发/TTL、坏数字/脚注缺失/字段注入/结构/限额、跨dataset/offering/version/year/source/file、proof到期/当前撤许可、trueCOMMIT/audit回滚、错mapper/动态DTO、防原始错误值持久、迁移重复/降级保留旧域。受影响T14/T49、契约模式、前端Test/Type/两Build及保护/生成检查；Lint无入口和未执行单列。T16真实原文与人工审核、正式数据/部署不在本Task验收。

同步文件上限小于T14上传上限：Storage可隔离10MiB文件，但ImportService对>1MiB或不匹配format/MIME拒绝开始批次（fixed422），不借数据库CHECK报原始错误；纯parser的limit code用于工具结果。尺寸内结构/表头错误可持久rejected(total_rows=null)，不猜总行数。同原始source_record_reference可以携带多个字段候选，只有(import,row_number)唯一，不用未约定的引用去重丢字段。
