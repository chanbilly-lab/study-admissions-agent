# T34 发布变更影响契约

2026-10-04代码前冻结，现源码与合成隔离验收完成；本Task为内部服务、关系索引及合成隔离验收，不增加HTTP/UI/worker，不消费或修改旧T19 pending outbox。真实处理关闭。

## 数据契约

只处理数据库已存不可变T19 ChangeEvent及其release/members，调用方仅传精确event UUID，不接受事实、owner、needs_review、时刻或比较结论。published首次发布无旧引用；replaced比较同dataset/year/mode的旧/新固定快照；withdrawn对原release确切引用保留原因与before/after。不同年度的新发布不得使旧年度成为新规则。

纯比较使用已发布TypedCandidate及SnippetData的有界固定快照，严格检验fact/offering/version/year/mode/fullscope与指纹。稳定分组offering身份、fact_type、field_key；同组多minimum/typical成员按完整规范业务投影multiset比较，不任意配对或只取首条。版本/来源/事实ID与内容hash本身不代替业务比较。规范decimal、要求原文、分类/单位/口径/分母/届别/脚注/缺失原因、完整范围、日期事件/精度/时区/当地组成及候选状态、适用窗口与公开引用许可分别比较。日期计算候选仍不是官方UTC。文本保守比较，不推理自然语言同义或删除脚注。差异最多100组，每侧最多50发布成员；参考IDs/版本/证据指纹单独trace。原引用变化单独保留trace；哈希、文件排版、物理定位或审核责任元数据变化不自动改变业务结论；semantic_business_changed=false不新增业务needs_review，但REFERENCE_REPLACED轨迹保留，T28/T32的旧引用失效证明仍严格适用，不自动换绑。

独立ChangesBase及增量profile：事件处理回执、评估影响、计划影响；event/对象引用自然唯一，有界不可变before/after/原因JSON与完整性hash，needs_review是sidecar，不UPDATE旧评估/画像/计划/执行/完成。用精确release+目标引用索引筛选评估，再通过PlanSourceAssessment找到计划；不得扫描或解释画像replay_snapshot。未相关offering、不同年/province/课程scope不误标；撤回即使hash相同仍追踪。

处理同一事务锁定已存且与root/state/relation一致的事件，比较与影响/回执一起COMMIT，重复事件不重复影响；索引传播不能LIMIT后提前完成而遗漏对象，事件后新建历史核验计划由原assessment关联动态继承既有影响。失败整笔回滚。入口默认disabled，合成仅显式test/DEMO边界，真实门槛恒关闭。系统内部最小来源完整性标记不重算学生资格、不读私有成绩、不创建修订/通知。owner查询仍即时session/student/core/original notice与对象owner/生命周期证明，撤回旧来源不得阻止查看有限变更轨迹；不得因此返回失效事实为当前或重新授权旧行动。返回只当前owner对象的trace，审计最少引用与固定错误。

## 修改范围

新app/changes纯DTO/比较、三表store/service、独立显式migration及Unit/真实PG专项；旧治理文档仅AGENTS、README、requirements、architecture、database、tasks、CHANGELOG、DECISIONS，新增本契约/验收。无新增依赖，无旧head/API/generated/前端/M0/原规格/旧验收改写；应用启动不建表。

## 可测试验收

1. 条件值/类别/单位/脚注/统计口径、date-only与候选时间/精度/IANA、年度/范围、有效窗口与withdrawal矩阵；同业务而只ID/hash/locator/排版改变不误标，规范小数数值不丢精度。
2. 实际T19审核发布→实际T28评估→T30/T32计划确认/完成→替代或撤回→exact assessment/plan needs_review；不相关目标保留；原快照/hash/state_version/完成数量完全不变。
3. event重复、真实并发、失败/COMMIT回滚、withdrawal trace、关系FK/immutable/JSON预算/索引及新migration down/up保留旧十三head；另owner/跨用户/撤权/失效绑定/错误engine/mapper/disabled零IO。
4. 相关Python/契约回归、完整frontend、Type Check、demo/auth Build、八生成profile/原文/M0/保护hash/历史/文档同步；无Lint/Python静态入口标未执行，不伪称生产法律/角色RLS/Keycloak/真实事实/部署通过。

结果见[验收](acceptance/T34_changes.md)。T35修订与T36后台提醒各自另行实施，本批T40停止。

## 实施中范围澄清

2026-10-04复核发现并修正首版影响筛选：不能只遍历旧rule_refs，也不能用整个offering混合范围的差异直接标学生。`target_member_diffs`先证明原offering/version/fullscope存在，再对该范围的before与after业务投影重比；after可以是同完整范围的新版本，新增关键字段不能漏，原scope删除须复核，其他省份的新scope同时保留原scope不误标。完整projection multiset决定业务变化，单字段分布相同而组合不同记association；不是逐字段边缘分布替代业务关系。

持久receipt只保存前后release、原成员引用/hash、变化字段与固定理由，业务before/after由不可变发布快照重建，不重复保存原文或学生输入。REFERENCE_REPLACED作为独立trace可有sidecar，needs_review=false；不升级旧来源current_validity。本人trace超过100条明确409，不截断冒充全部，后续分页未实现。系统传播无LIMIT，在所有现存精确引用写入后才完成回执；晚建历史核验计划由原assessment影响动态继承。

新关闭入口在审计包装前核验配置/提供的事务绑定，默认disabled包括失败审计在内零数据库IO；已启用的权限失败沿用最小诊断。T40物理删除须协调当前immutable receipt的历史计数和impact清理，不能为保计数永久保留私有对象；本Task尚无删除服务，不提前实现。
