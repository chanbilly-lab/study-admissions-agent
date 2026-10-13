# T14 文件存储契约

2026-10-03，实施前冻结；T07/T08/T10/T13已验收，D06上限已确认。真实主体/告知/身份/来源责任与处理门槛保持；只合成文件和隔离实库验收，不部署、下载用户文件或自动解析。

## 数据契约

StorageBase独立单表storage_objects；独立storage_alembic_version/0001_storage_t14，显式先具备auth0006/catalog0003，保留旧链及metadata。FileData仅id(UUIDv4服务器生成)/namespace(student_private|source_quarantine)/is_synthetic/status(quarantined|delete_pending|deleted)/media_type/size_bytes/sha256/created_at/expires_at；不输出path/backend key/客户端文件名/owner。内部StorageObject额外保存服务器owner_user_id、private attachment owned_resource_id/resource_version，或source dataset_id/source_id/source_version；namespace耦合nullable、私有复合owner FK、来源确切版本与synthetic父FK。所有新文件quarantined，不表示可发布或安全扫描通过。

StoragePolicy严格冻结：enabled=false、real_storage_ready=false、source_retention_days=None默认；源隔离TTL显式1–730天，合成验收设1天，不是用户选择的真实原文保留期。真实启用须正式策略及责任配置，此轮不设置。私有expires_at为UTC最多24日历月，来源为显式TTL/24月/当前来源复查期限中最早者；到期立即拒用，不宣称已物理清理/备份传播。

Upload服务只收parent_kind(profile|plan)+parent_resource_id或source_id+expected_source_version，以及filename/content_type/bytes；owner/synthetic/UUID/hash/长度/时刻服务派生，不接受客户端owner/key/状态。upload_private在同TX验证owner根/core并创建exact attachment registry，版本1且与file UUID绑定；upload_source绑定最新来源许可及责任。FileData永不授权限。

## 替换接口与格式上限

StorageBackend Protocol：verify_ready()/write(namespace,object_id,bytes)->StoredBlob/read(namespace,object_id,expected_size,expected_sha256)->bytes/delete(namespace,object_id)->bool（True删除现存文件，False已不存在，错误抛固定异常）。StoredBlob只namespace/UUID/size/hash，无path。只服务端随机UUID作key，客户端filename仅校验不保存为key。依赖注入本地适配器，正式对象存储适配器未配置或验收；不签URL、不挂static或公开原文下载。

本地root显式绝对且已存在私有目录，两个固定namespace目录显式准备。拒root/ancestor/namespace/file的symlink/reparse、不覆盖旧UUID。Windows使用真实kernel句柄锚定目录并拒重解析/共享删除与写改向，最后路径/属性校验；POSIX使用dirfd+O_NOFOLLOW。服务私有目录ACL/恶意本机管理员属于部署边界；测试不足则不宣称竞态防护通过。

bytes严格非空且<=10485760；filename<=255，拒控制、separator/ADS、Windows设备/末尾空格点、伪后缀；MIME/扩展仅application/pdf/.pdf、text/csv/.csv、application/json/.json。PDF只受限版本头/EOF浅检，不解压或调用解析器。CSV严格UTF8、标准逗号reader、字段<=64KiB、列<=200、记录<=100000、总cells<=100000，不改csv.field_size_limit全局；CSV无唯一magic，拒明显PDF/ZIP/HTML等签名，余者不冒称语义或安全验证。JSON严格UTF8、对象/数组根、拒duplicatekey/nonfinite/depth>32/nodes>100000。解析不执行内容，不作招生事实审核。所有类型保留原始bytes/hash。

## 服务事务与访问

StorageService上传只自有TX；先鉴权再validate/write，metadata/attachment/audit同TX，IO后及auditflush后重验当前身份/角色/owner/core/expiry或签名MFA/current source责任/许可。来源须最新exact source_version、manual_import_permission granted+enabled/basis/ref/reviewed_at且未到期，publication许可或历史enabled不能代替；版本变化不自动套新许可覆盖旧asset。source service/store/metadata与auth同engine，所有实际mapper检查，不开持锁第二事务。

读取自有TX有界完整buffer，校验size/hash，required审计与最终重验且commit成功后才返回bytes。另提供get_source_file_in_transaction(session,principal,file_id,expected_dataset_id/expected_source_id/expected_source_version)给后续导入/证据的metadata/current授权复核，不I/O；expected可不提供用于内部复核，任一提供须三项完整并匹配确切file元数据；后续consumer须明确传三项防A来源文件错归B；不是公众读取或绕过文件校验的授权缓存。T15/T16应先读取有界bytes再解析，在业务事务提交前重新核此metadata与当前许可。

新增Authorizer.check_owned_in_transaction(session,principal,kind,id,action)复用现有owner/root规则；closed catalog.storage.write/read能力，POLICY_VERSION=T14_owner_v3，旧接口/HTTP不变。private只本人；T09的status/version metadata grant不能取得文件bytes，未扩共享字段/动作。上传/私有读复用attachment固定审计动作，来源复用administrator.action空对象，审计无filename/path/content/hash。

上传audit/commit失败尽力delete刚写blob；delete失败无可读metadata，orphan不被自动登记或恢复。进程崩溃可留未登记orphan，生产有界清理/恢复后删除传播仍待后续验收，不宣称FS与DB两阶段原子。显式private逻辑删除不以撤回core阻挡本人减权：当前本人身份/owner核对，墓碑与registry deleted及audit先提交立即拒读，再尝试物理删除；失败保持delete_pending，不冒称30天内全部副本已清理。完整权利请求/定时清理/备份属于T40/T44。

## 修改范围与验收

新增storage协议/格式/本地适配器/schema/models/store/service、独立migration profile与Unit/security PG专项；只必要Authorizer同事务增量及受影响文档。原始两规格/docs01–05、旧迁移/M0/catalog/auth/HTTP/前端/生成契约/依赖/研究不改。无新依赖。

验收：路径/文件名/reparse/伪MIME/大小/深度及签名；owner与metadata grant隔离、core/年龄/角色/session/notice变化逐次拒绝；source current许可/责任/版本/期限；错mapper零连接；写/审计/真实commit失败补偿和孤儿不可读；读后与真实audit锁时效不返回bytes；篡改hash/长度failclosed；独立迁移重复/降级恢复保留旧五域。实际Unit/Integration/前端Type Check/双Build及wire/原文/文档检查记录[T14验收](acceptance/T14_file_storage.md)，无入口Lint明确未执行。

本轮Windows接口依据：[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)、[GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)。目录句柄分享限制在关闭前生效；OPEN_REPARSE_POINT不替代所有父目录检查。实际race保证以专项结果与部署目录权限为限。

## 显式本地运行与检查

旧auth/catalog依次显式迁移至0006/0003后，给独立storage CLI设置专用STORAGE_DATABASE_URL并运行`.\.venv\Scripts\python.exe -m alembic -c services/api/storage_alembic.ini upgrade head`。应用启动不执行此命令。调用者手工准备独立私有root及两个固定namespace目录，再显式注入LocalStorageBackend；不要置于web静态目录或提交Git。新接口不挂现有factory，真实配置及正式适配器未验收。

离线格式/文件检查：`.\.venv\Scripts\python.exe -B -m pytest tests/unit/storage -q`；专用T14_TEST_POSTGRES_URL后执行`pytest tests/security/storage -q --tb=short`，只用合成随机schema/临时目录。权限不具备的平台变体与未执行分支必须单列。

## T40 私有文件与导出工件清理

复用固定StorageBackend/opaque UUID，准确捕获size/SHA，先实际读取核验再删除；缺失404可幂等完成、其他故障不标全部清理完成。范围包含本人附件和已存在导出工件，source_quarantine及他人文件保持。私有文件显式delete在guard装配时追加最小file_deleted外台账，旧备份恢复重放。

导出附件只已核验本人原bytes/base64，整个UTF8 JSON≤10MiB；超限固定失败无截断。默认1小时/最多1天工件下载TTL，过期拒下载；物理工件/备份定期清理与生产存储ACL为后续运维验收。实际A备份/B删除/pg_restore A/外台账B重放同时恢复并擦除合成原文件，不声称生产备份恢复。
