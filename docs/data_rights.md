# T40 资料权利、删除与独立恢复台账

2026-10-04代码前冻结，现源码与合成隔离验收完成；仅本Task，本批T50停止。T39已PRIVATE保存，正式处理/法律责任/真实用户/部署关闭；本轮只合成离线和专用PG，不改原规格/M0/旧迁移，不新增依赖。

## 数据契约

新增privacy/rights有限模块与独立增量迁移，不把T36 cleanup_probe改成任意删除handler。业务库存权利请求/作业、有限尝试、备份到期登记、恢复水位及匿名影响删除计数；删除/撤权最小台账独立于业务备份保存，独立PG迁移/实例或隔离schema。最新完整性锚点位于业务备份外，验证单调水位、闭合事件、顺序/hash与受信签名；缺失、损坏、落后、引用/配置漂移fail closed，不能从旧业务备份自认证最新台账。

RightsPolicy默认disabled/真实ready=false；只有显式test+合成可装配执行。有限export|deletion作业queued/running/failed/completed/cancelled；持久自然去重、lease/generation/token fencing、有限重试和错误码，执行/attempt/ack同事务；固定处理器，不接SQL/Shell/URL/自定义handler。不能以已接收或仅墓碑显示全部已删除。

独立api/rights profile继承T36；六操作GET /privacy/rights/context、POST /privacy/exports、GET /privacy/exports/{request_id}、GET /privacy/exports/{request_id}/content、POST /privacy/deletions、GET /privacy/deletions/{request_id}。默认关闭无DB/worker初始化；显式Cookie认证、当前本人及对象归属逐次重验、写固定Origin/CSRF、16KiB闭合JSON/no query/owner/private options，no-store/requestID/有限错误。create body只明确owner_confirmed=true；源owner/范围与水位来自服务器，不能传待删除IDs或路径。规范化请求和作业元数据有界，重复删除回同一本人受理，不创建第二份授权。

权利访问独立于核心咨询同意；已撤回core的有效本人仍可请求本人查阅/删除，不能以监护共享或管理员角色取得他人资料。未知/未成年私有仍关闭，正式依法受理流程/责任未落实前不处理真实资料。导出读取只限本人已存在数据；排除session/cookie/CSRF/hash密钥/私钥/他人payload及受版权约束的公共原文件。包含画像各版、评估/计划与进度/修订历史、本人附件及权利/共享元数据；JSON UTF8工件≤10MiB，原数字/日期/版本/历史含义保持。附件使用已核验原bytes和hash，有限base64；超限明确失败可追踪，不截断伪称完整。下载返回有限JSON文本/byte size/SHA/短期expiry，下载及产生效应最后身份/当前删除/lease/TTL重验，core撤回不冒充无权查阅本人旧资料；退出或当前身份失效不交付私有导出。

删除受理在本人账户锁下捕获精确资源/root/version/mode、private文件UUID与真实hash/size、已存在导出/用户作业范围和截止30天，立即阻止相应用途、新采集及历史私有读取；独立台账先持久，业务/文件失败保守关闭，明确可重试。最小权利/审计/授权记录保留上限24月，备份登记35天上限及到期；不是法定期限。接受删除的专用worker不依赖旧session/core继续有效，退出不阻断清理；不得扩大owner/捕获epoch/路径，文件仅现有StorageBackend opaque UUID，删除前实际定位核验，失败不标完成。

按FK顺序清除本人通知/偏好/私有作业及attempt、导出工件/附件、共享私有缓存/索引及私有幂等摘要、修订/替代、完成/确认/排程、计划sources/tasks/versions/root、私有影响、评估/画像版本/root。AuthOwnedResource只可保留最少已删除墓碑/审计引用，不保学生payload。既有公共发布/来源文件、他人资料、旧M0不删除；数据库索引随行删除，未配置的外部cache/vector不编造清理完成。T34不可变公共事件回执保持原计数；只增无owner/学生payload的匿名已擦除数量，用live+erased核原计数，后续事件不能重新生成已受理主体的私有影响。

已装配guard的现有认证/隐私/授权/存储/变化服务重验最新台账和业务恢复水位；生产有效身份服务缺guard拒用，默认关闭旧入口不受新DDL影响。当前配置引用/engine/clock/ledger/锚点须固定重验；不能删guard或换合法DTO绕过。现有会话退出、角色撤销、core撤回、grant撤销、私有文件删除在配置guard时登记最小撤权/资源台账；原业务语义、权限/减权与期限不放宽。本人terminal删除不因再声明/同意、重新登录、旧幂等响应或restore复活。

业务备份A不得包含独立最新台账/锚点；B受理删除/撤权后恢复A，先验证业务头和最新独立水位，重放B的准确减权/删除，完成持久水位才开放对应流量。missing/stale/corrupt ledger/anchor或未重放时旧factory/direct service同样关闭；台账本身的业务失败恢复不得自动猜最新。Task40实际验证专用PG pg_dump/pg_restore和本地合成文件，不把复制内存对象叫恢复；T44另验加密/恢复RPO/RTO与正式操作方案。

## 修改范围与验收

仅治理/受影响identity/privacy/storage/sharing/API/DB文档、.gitattributes/有限生成器、既有AuthService/AuthStore/PrivacyService/GrantService/StorageService/ChangesService/Store必要guard与匿名计数接缝；其余现有源/生成工件/迁移/原文保护。新rights模块/factory/两独立增量迁移及rights生成工件、新pure/PG/HTTP/恢复测试。无前端功能实施，T41另行做页面。

先列上述契约及范围再实现。pure：严格DTO/模式/限额/UTC/lease/fencing/锚点与构造绕过/禁用零IO。实际PG：增量幂等保留16旧head、两用户全历史导出/删除与附件真实bytes/私有幂等/通知/影响覆盖、越权/退出/核心撤回、接受后logout继续cleanup、失败重试/并发/迟到lease/audit回滚、其他用户/公共目录保持。HTTP：Cookie/CSRF/Origin/body/query/no-store与错误/受理≠完成。实际A→B→restoreA+独立B重放含core/grant/session减权，missing/stale/corrupt/未重放拒traffic、合法他人/当前公共数据可读；备份到期与文件原bytes/hash证明。相关Python、前端回归/TypeCheck/demo-authBuild、12profile/M0/原文检查；Lint/Python静态无入口标未执行，真实处理/供应商/正式法律/部署仍关闭。

结果见[验收](acceptance/T40_data_rights.md)。
