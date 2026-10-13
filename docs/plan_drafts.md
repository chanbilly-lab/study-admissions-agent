# T30 差距到草案任务

2026-10-04实施前冻结；T29 PRIVATE 4ef4e9e1fb849ee28bf10b1ab6b5c1b17234989e，568tracked/索引和工作区空。仅T30，验收/文档/PRIVATE保存后才T31；无HTTP/UI/排程/确认/进度/worker/模型，真实处理关闭。

## 数据契约

M0 app/planning.py 已占模块，保留原字节，新app/plans/隔离，复用现Python/Pydantic/SQLAlchemy/Alembic/PostgreSQL。纯build_plan_draft只接服务端当前读取且hash正确的≤4个T28 AssessmentData、同一本人确认profile/version/hash/模式，目标选择confirmed=true与有界可选自主学习目标及估时；不向HTTP接受客户端owner/成绩/结论/AST/时钟。模型不参与。生成器/T30 schema版本固定，source assessment/release/target/scope/阶段/result hash与规则/证据引用保存；草案status=draft、confirmed=false，选择目标确认不能变成计划确认。

内部 `PlanCreateInput` 仅允许准确assessment_ids、目标confirmed、可选学习目标和估时调整；`DraftBuildInput` 的generated_at必须是服务端明确UTC时刻，不读环境时钟。纯构建另接最多4个实际RuleBundle与60个实际DeferralBundle快照，精确核验原规则引用/表达式SHA/target/scope/release/阶段；单位、量表或招生周期缺失时不跨目标合并任务。估时调整最多64项；持久服务不得让客户端提交快照、身份或时钟。纯结果使用稳定task_key；持久身份由服务端UUID另行分配。

unknown仅优先verification；ineligible复核不满足项与替代目标，不产生已满足资格/申请成功断言；eligible只一般材料准备/再次核对，不执行申请；conditional只采用原完整表达式实际必要obligations，取得对应实得记录及重新检查任务，不处理未选any分支、不预测转实得。可选study来自学生明确自主目标，通用练习/测评记录，不推知识弱点、提分或录取效果。需要学习诊断的资料没有时未知。

期限refs按每目标/政策/阶段/主申请与后补分别保留；纯输入可附从同Session当前已核T28 policy snapshot取得的确切DeadlineBinding，不解析quote，不把T12 calculatedUTC升级official。核绑定eventID/type/evidence/范围/政策，保持date/minute/second/unknown、原local/date/timezone、计算候选/官方未核定分开；没确切日期snapshot则未知/NULL，不补23:59。学生目标日期与内部安排不混入官方固定期限，本Task不排程。

估时strict 0–1000小时十进制字符串（最多6位小数）或null，editable=true、来源template/user_adjusted/unknown；这是输入资源上限，不是学习效果预测。默认可为空，不从weekly_hours截断或保证效果。override按准确task_key，未知key/float/bool/负数/超界拒绝。共用任务只按动作/验收/成绩basis/key及兼容单位/量表/周期范围等语义键合并；不能仅同标题或成绩字段合并。每目标不同阈值、policy、主补deadline引用独立不丢；目标级复核依赖必要共用动作，同版依赖不得指其他版/目标。

current_validity current可使用原四态；unavailable规则缺失仍可核验；needs_review/replaced/withdrawn只verification-only并保留原历史状态和原因，不能把旧eligible/conditional当当前动作。过期评估或画像不能生成新私有草案；正式规则缺失unknown不被拒掉或升为conditional。

自动生成的未知/历史核验动作优先展示，SHA仅用作同优先级稳定排序。明确自主学习目标独立保留，不将其冒充未知资料的后补许可。T30的内部get_draft返回不可变原快照：当前来源有效性与原refs不同则409，不返回可能被当作当前许可的旧准备动作。新建历史核验草案仍允许。安全历史展示及修订投影在后续任务验收，本Task不提前实现。

## 持久与权限

独立PlansBase及plans_alembic_version/0001_plans_t30，最小根/不可变草案版/任务/来源评估关联/同版依赖关系；绑定server owner/registry/current确认profile与source assessments。旧T28 assessment只有ID唯一，新refs用确切assessmentID FK及同TX归属/版本/hash验证，不ALTER旧表/迁移；新表父子scope用复合FK/有界JSON/唯一语义键/正版本/UTC期限、不可变内容UPDATE拒绝。可信DELETE为后续T40保留，审计引用无强FK以兼容审计独立留存。TTL≤所有源画像/评估及24月上限。

内部PlansService默认关闭且real_plans_ready=false，显式合成测试才启用，不挂HTTP。复用T28 EligibilityService/T23画像当前owner/student/core/原用途证明，同Session读取并锁精确source；注册T07 plan ownership、草案/任务/审计同事务，不借T49 plan.confirm。ownTX提交后输出，callerTX不得隐藏commit；禁止错engine/mapper/非活动Session。全部写/审计flush后再次检查当前身份/原用途/当前画像/assessment/发布及来源期限，失败整体rollback。只允许本人读取，不因管理员或grant授私有写；旧历史来源只能核验说明，撤回再同意不复活旧证明。

迁移只显式PLANS_DATABASE_URL/PostgreSQL或已绑定专库connection，检查现十一迁移头；应用导入/启动不DDL/seed。空schema通过所有必要旧链后升级本链；降级/升级仅本Task随机schema，不宣称生产恢复。

## 修改范围与验收

新app/plans/纯DTO/drafts、models/store/internalservice与独立Alembic链；owned unit/PG及独立金标准/安全测试，新契约与验收。仅八旧治理文档允许修改（含数据库），560其他tracked/旧M0/原规格/docs01–05/旧迁移/API/生成/依赖/前端保护。

1. 四态金标准、实际必要obligations/无期限/unknown/历史失效、原SHA与复制构造重验、无模型/外网/DB纯import。
2. 共用任务兼容/不兼容量表、独立主补refs、同版依赖/去重、估时可改/未知key/有界输入。
3. 实际PG两owner/管理员/grant拒绝、当前profile/用途/TTL、同TXaudit/registry回滚/COMMIT失败/等待跨期/错mapper零IO。
4. 显式迁移空库upgrade/current/downgrade/upgrade、旧heads/数据保持、不可变UPDATE/可信DELETE和FK/CHECK。
5. 相关Python/PG、完整前端Unit/Type Check/demo-auth Build、七profile/原文/M0/范围/历史/治理/实际暂存diff及PRIVATEpushSHA；无Lint/Python静态入口标未执行。真实领域/身份/法律/SQL权限/清理备份/部署不执行。

实施前冻结与实际检查分开；2026-10-04本地合成验收完成，命令及限制见[验收](acceptance/T30_plan_drafts.md)。单个版本JSONB上限524288B、任务JSONB上限131072B；极端合法DTO组合可能超过版本上限，数据库拒写并整笔回滚，目前返回固定503。这一组合的PG检查未执行，不宣称全部合法组合可保存。
