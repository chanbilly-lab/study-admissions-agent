# T49 持久幂等契约

2026-10-03实施前冻结，现源码/隔离验收完成。仅后续内部业务事务基础，HTTP/前端/部署不变。正式receipt期限待用户决定，默认enabled=false/ttl_seconds=null，只有合成离线fixture显式24h，不能写成正式产品选择。

## 数据契约

actor由当前服务器Principal获取；operation使用有限白名单；opaque ASCII key有界并持久摘要；规范请求只存SHA256，不缓存body/私有内容/旧响应。规范化根dict/list、exact JSON字符串/布尔/null及安全53bit整数，sorted对象key与原数组顺序，UTF-8不trim/NFC，深度32/nodes100000/1MiB，拒float/Decimal/UUID/subclass/cycle/surrogate；类型化调用者先显式dump成约定字符串，文件请求只引用UUID/hash/size参数。

同actor+operation+key唯一；processing与业务操作在同一活动PostgreSQL Session/TX，完成时只记录有限kind+UUID+version，资源本身经当前授权查询。当前AuthService同engine重新核验身份/会话/角色；创建与重放均有强制业务当前权限/用途/资源有效性检查，等待/业务/审计后再验。相同payload有效回执返回same引用并标replayed=true；不同payload409 IDEMPOTENCY_CONFLICT；actor不共享；expires_at<=now不再保证重放，续期不能删除旧业务资源。

## 范围与验收

新增独立幂等profile/表与api/v2内部模块，复用Auth/Privacy/Audit，不修改旧迁移/已有HTTP wire/原规格，不新增依赖。真实准入与正式TTL门槛不解除。具体内部接口如下，在编码前冻结。

PostgreSQL必须实际验证双Session同key竞争commit/rollback、不同actor/operation/hash、回滚/真实COMMIT失败、exact expiry、撤会话/角色/core/notice/资源删除后重放拒绝、等待后过期、mandatory audit与错mapper零业务IO，重复迁移/降级及旧域保留。纯canonical边界与Copy/construct绕过；相关权限/隐私/审计、契约模式、前端测试/类型/双Build。无Lint入口及未执行检查单列，不以历史结果代替。

## 内部接口与事务

IdempotencyPolicy(enabled=false,real_idempotency_ready=false,ttl_seconds=null)，显式strict整数1..730天秒值，再以24日历月截断。IdempotencyService(auth_service,privacy_service,store,policy).execute(principal,operation,key:SecretStr,payload,*,perform,verify_resource,session=None)。固定operation为catalog.import/catalog.publish/profile.create/plan.confirm，对应kind import/catalog_release/profile/plan。SecretStr key仅ASCII `[A-Za-z0-9._:-]{1,128}`，数据库唯一是actor/operation/key SHA256摘要。ResourceReceipt只有kind/resource_id UUID/version，IdempotencyResult只有resource/replayed/expires_at；不保存或重放任意body、状态权限或学生事实。

当前支持的是组合基础，import/release/画像/确认的领域行为仍由后续Task实现；合成测试callback不冒充已有正式业务。perform(session,current)返回严格最少ResourceReceipt；verify_resource(session,current,receipt)必须显式配置且返回exact True，检查当前所属资源、删除/撤回、grant/用途等领域条件。闭集管理员能力或student+T08core由通用层执行，身份/资源/时效在业务或replay及必要审计之后重复检查；业务回调是可信应用代码，不是恶意Python沙箱。

IdempotencyBase/独立0001版本表，仅依赖auth0006；one table含processing/completed、摘要/最少引用/服务器UTC与有限期限。先当前account/session/roles锁，再receipt，再domain；新业务必须在domain锁前领取receipt。INSERT ON CONFLICT DO NOTHING真实唯一竞争与FOR UPDATE，不开启第二事务；deferred constraint trigger在COMMIT检查当前row必须completed，未完成业务回滚，不能持久processing阻挡后续重试。过期重新claim只替换回执，不删除旧业务；过期后新的创建可能新建资源，由领域自然键与明确接口语义控制。

ownTX模式仅成功COMMIT后返回；caller Session模式结果尚未提交，调用者不得提前发送响应，并必须在任何异常时rollback整个事务，不得捕获后继续提交部分业务。所有default/Auth/Privacy/Audit/Idempotency mapper需同engine，进行操作前检查；suppliedSession下不另连接。没有通知worker/租约、网络外部副作用或HTTP中间件。业务不得在perform内COMMIT或执行不可回滚外部操作；此接口只保证同一个PostgreSQL事务内的修改。

## 运行与限制

先显式升级Auth至0006；同一已核验PostgreSQL连接赋予IDEMPOTENCY_DATABASE_URL后执行`.\.venv\Scripts\python.exe -m alembic -c services/api/idempotency_alembic.ini upgrade head`。迁移检查前置，启动/导入不DDL。源码构造注入明确policy，环境值不自动开启TTL/真实处理。离线纯测试 `python -B -m pytest tests/unit/idempotency -q`；专用loopback idempotency_t49_test连接放T49_TEST_POSTGRES_URL后执行`pytest tests/integration/idempotency -q`。无API密钥可测试，所有主体/事实是合成。

等待、perform和最终审计之后重复SHA256，payload改变409回滚；resource verifier不得动态改变receipt，结果从持久行重建。回执只控制重放窗口：没有后台/物理清理工具，未请求过期最少摘要行仍需未来T40/T44或独立维护验收，不宣称留存合规。适配器配置/正式TTL、真实身份/准入、运营责任/法律、备份恢复与部署仍未验收。实际命令与保存记录见[T49验收](acceptance/T49_persistent_idempotency.md)。
