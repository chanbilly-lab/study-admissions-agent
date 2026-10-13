# T09 明确范围的共享授权契约

日期：2026-10-03。用户已授权逐个实施 T08–T20；本次仅 T09。代码开始前先列契约、修改范围和验收，不开放真实处理。

## 产品与权限边界

共享授权与 T08 核心用途确认分别处理。本人只可授权具体对象、指定预登记受权人、固定字段、固定动作和明确到期时间；没有全会话、通配符、父对象继承、转授权或替学生确认功能。角色与监护同意均不会自动产生访问权。

本人逐项独立确认后先创建待接受授权；指定受权人须使用自己的当前会话和有效成年声明明确接受。未成年及年龄未知的私有功能继续关闭。受权人的接受不赋予 student、advisor、guardian 或管理角色。生产共享默认关闭；完整流程仅允许显式的合成 test 夹具，不使用真实学生资料。

## 持久与执行契约

实施采用认证链增量0005保存 owner 单调共享revision、精确grant及规范化字段/动作表。create 使用 expected_revision；create/revoke（含受权人拒绝/退出）后owner revision递增，旧正向输入不能在撤销后重放恢复权限。scope 与主体不可修改，变化须创建新授权；本人或指定受权人的撤销不受陈旧 revision、失效核心用途或未就绪告知阻挡。

授权绑定 owner 当前用途确认引用，创建时绑定受权人当前成年声明依据，接受时重验同一声明；用途撤回后重新确认、年龄失效后重新声明不得复活旧grant/accept。动作时使用当前时间、当前会话、当前角色、双方账户、政策和声明、对象与父状态及具体字段再验。

T07本人访问接口继续 owner-only，新增独立 shared seam。共享服务独立开启事务，先对全部相关账户按UUID排序锁定，再验证真实actor及被锁定owner的用途；不伪造owner Principal、不清除 T08 actor 绑定、不在已经锁住actor的本人事务里补锁另一账户。SQL先限制可见grant/对象，再做分页与计数，禁止事后过滤造成count泄漏。缓存只存最少引用，读取后再验；延迟执行使用同事务当前权限。外部文件副作用/真实worker仍待其所属Task。

## 修改范围

后端 auth/grants 模块、privacy 的受限subject/成年guard、0005增量迁移、identity装配与契约；前端 features/sharing 和 AuthView最小挂载；contracts/PG安全/前端/离线浏览器测试；当前Task文档及受影响API/数据库/架构/需求/README/AGENTS。无新增依赖；旧迁移、M0、原始规格、研究文件及旧验收保留。

## 可测试验收

1. 精确字段/action/对象/到期、独立确认与受权人接受；拒绝通配/对话/冒用owner/role/verified和自授。
2. 角色或监护关系不赋访问，accepted与当前effective分别展示；真实默认关闭，合成不能接入production。
3. 撤销、到期、禁用、用途/声明/政策变更后对象读取、SQL列表/计数、缓存及延迟执行均拒绝；旧grant与旧请求不恢复授权。
4. 隔离PostgreSQL迁移保留旧数据，SQL约束、并发/锁等待新时钟与回滚验证；启动只检查不DDL。
5. HTTP Cookie/CSRF/Origin/安全错误/无缓存，前端不乐观放行、不默认勾选、不注入owner、401/换账号/旧回复不恢复旧状态。
6. 实际专项与回归、Type Check/两Build/契约漂移、窄屏浏览器；无Lint/Python静态类型入口则明确未执行。

以下精确wire与服务接口在实施前冻结；本文件的验收结果将另记，不把冻结方案当已实现或正式法律告知。

## 冻结的数据契约与最小矩阵

当前没有真实画像/计划domain表。五类registry对象profile/plan/attachment/export/job，仅允许共享status/version两个metadata字段及read/list动作；禁止conversation、任意payload、通配、父对象继承、download/export/write/execute/confirm。实际领域字段与整文件权限由所属后续Task使用新的scope policy及重新明确授权，不冒称本Task已实现私有业务。延迟作业测试使用共享readonly执行seam，不建设真实worker。

独立合成共享告知为固定文本/版本/实际SHA256，最大授权时间2592000秒（30天，仅合成测试策略上限，不是正式部署决策）。SharingSettings.fixture_mode默认false，只test+synthetic+T08配置就绪可完整启用。

| 方法/路径（identity子应用，外层/v2） | 契约 |
| --- | --- |
| GET /sharing/policy | 公开固定文本、实际text_sha256/version、sharing_available、disabled/synthetic_test_ready、scope_matrix、30天上限、guardian_verification_available=false/private_business_available=false |
| GET /access-grants | direction=issued/received，limit1–100默认20，after_id UUID；当前本人revision/actor_declaration_id/owner_consent_id、就绪、items/total/PageInfo；无owner请求参数 |
| POST /access-grants | CreateGrantInput，严格独立confirmed=true；成功200统一Envelope[GrantMutationData] |
| POST /access-grants/{grant_id}/accept | 当前指定受权人，严格独立confirmed=true/current grant version/policy version/hash；200同统一envelope |
| DELETE /access-grants/{grant_id} | owner撤销或指定受权人拒绝/退出共享、body/query为空；不需expected_revision或仍有效用途/告知；200同统一envelope |

CreateGrantInput：resource_type（五kind）、resource_id UUID、expected_resource_version strict int>=1、grantee_user_id UUID、fields唯一数组(status/version，1–2)、actions唯一数组(read/list，1–2)、expires_at带明确UTC offset的日期时间、confirmed严格bool true、expected_revision strict int>=0、owner_consent_id UUID、sharing_policy_version字符串、sharing_policy_hash64小写hex。额外字段一律拒绝，不接client owner/roles/verified。

AcceptGrantInput：confirmed严格bool true、expected_version strict int>=1、sharing_policy_version/hash。受权人身份来自当前会话；不能指定另一user。创建capture的受权人成年声明必须仍current，且尚未接受时才能transition；重复相同已有效接受不改变scope或绑定，不恢复撤销/过期/变更。

GrantData：id、resource_id/type、resource_version、owner_user_id、grantee_user_id、fields/actions、created_at/expires_at、accepted_at/revoked_at可空、state=pending/accepted/revoked、version、sharing_policy_version、is_synthetic、access_active。owner consent和grantee declaration引用只存服务端，不跨主体暴露于grant DTO。GrantMutationData为user_id/revision/grant。GrantListData为user_id/revision/actor_declaration_id/owner_consent_id（仅当前本人引用）/sharing_available/total/items/page。accepted表示历史接受，access_active表示当前有效，两者不得混为一谈。

精确resource_version绑定，registry版本touch后旧grant失效；不自动授权根对象未来版本。新grant需新revision/独立确认。四张表为auth_sharing_states、auth_access_grants、grant_fields、grant_actions；增量head0005_shared_grants_t09，旧迁移冻结。复合FK约束对象owner、owner确认与recipient年龄依据同主体；期限/版本/状态采用明确非空CHECK。应用scope不可变，不声称有DB immutable trigger/RLS。

内部SharingService：get_policy、list_grants、create_grant、accept_grant、revoke_grant；require_shared/list_shared/execute_shared/cache_key/cached_value实时重验。SharedProjection只含resource_id/type/is_synthetic/requested_fields/status|null/version|null，不返回owner/parent/payload；SharedPage为items/total/next_cursor。可信本地operation接收同Session/current actor/受限projection，不是任意代码沙箱或事务化外部I/O。

Privacy新增当前actor成年proof及registry导出owner的受限subject用途proof；不能用owner假Principal。owner须active+student+current core，receiver须active+current成年声明+specificgrant accept，不能从关系推导权限。对双方账户锁后读取当前notice/声明/role/consent，等待后刷新时钟与版本。

受权人可直接拒绝待接受邀请或退出已接受共享，使用同一DELETE减少权限；第三人不可撤销。无有效core/成年/告知仍可退出，不强迫通过改年龄间接停用共享。修改同一grant为revoked，owner sharing_revision递增；MutationData.user_id/revision始终为当前actor自己的状态，不跨主体暴露owner revision。

## T40 共享撤权与恢复

已装配guard的本人撤销写外部精确grant/owner引用后业务撤权；恢复旧备份必须重放最新grant_revoked，不能以旧accepted状态复活访问。删除清理本人授出字段/动作/授权和私有缓存；保留的最小审计/责任记录不是共享资料访问权。已有接收者资料与公共事实不删；他人导出/删除始终404。
