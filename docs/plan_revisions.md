# T35 明确修订与只读历史契约

2026-10-04代码前冻结，现源码与合成隔离验收完成；仅本Task。先复用T23当前本人确认画像、T29新评估、T33学生显式创建的新草案；再请求修订提案、展示差异与原完成历史、由学生独立接受或拒绝。不会自动改事实/画像/资格，不调用模型，不新增完成信用。

## 数据契约

新plan_revisions模块、独立Base与增量迁移。ProposeInput固定old_plan_id/new_plan_id、两侧expected_state_version、student_confirmed=true；旧计划必须本人已确认，新计划必须同owner/mode/profile根的不同draft。学生在已有工作台明确选择新成绩/证据对应评估并创建新草案，修订复用该草案，不创建影子画像/评估、不自动生成或确认准备目标。输入不含owner/diff/成绩/旧完成结论/时间。

服务端核旧根/原快照hash与精确来源关联、当前新plan完整T32 profile/source/原notice/core证明，在单事务锁两侧state并派生有界差异：profile确认版本、task业务语义/估时/依赖、原期限字段及容量/安排、来源引用分别列项；不把新ID、生成时刻、hash噪声当成绩改变或官方截止日改变。原任务最多60/100沿旧契约，不推自然语言同义。proposal固定两侧plan/proposal/state/hash/profile版本、精确旧confirmation/completion引用及<=24个月且不超过任一原私有TTL的到期时间；无原画像/成绩/证据原文副本。无实际可审阅变化时明确409，不虚构变化。

接受/拒绝有expected_revision_version、student_confirmed=true以及固定action（accept/reject）枚举。同pair与相同pins重复生成返回原proposal；决定自然去重，原请求明确重试仍重新核权限和私有生命周期，accept/reject相反或陈旧revision CAS409。accept前锁old/new状态并重新核两侧pins，生成后完成/编辑变化要求重新审阅，不能吞新增旧完成；新草案必须仍current且draft，追加唯一old→new建议替代关系，绝不UPDATE旧plan/registry/确认/完成，不能代替T32单独本人排程和最终确认。reject只核当前owner/core/原profile用途与TTL、revision CAS，不因新来源/画像变化或计划编辑失效阻止拒绝，旧历史仍可读。无T49新action，一old最多一个accepted successor、一new最多一个accepted predecessor，不形成循环/跨owner关系。关系表示学生接受新的替代草案；未停用旧T32写端口，原来源/授权/CAS仍有效时旧完成可继续追加并在历史显示，不能宣称旧执行全局关闭。

历史读取为新的有限owner端口；旧T32 current-source失效仍严格409，不改变旧实现。即时session/student/core/原notice和原profile版本TTL必验，但允许profile.current指针变化及原release替代/撤回。重建完整旧持久数据与hash、精确PlanSourceAssessment集合/resultSHA/profile与原assessment元数据关联后只输出计划历史任务、原确认/完成引用及可识别原安排/来源版本，不输出成绩、私有replay或证据quote，current_actions恒false，明确历史不代表当前资格。原完成仅历史引用，title或同名任务不等于新任务完成，无自动credit或伪新completion。拒绝/接受后均可读取原历史；private过期/原用途撤回则拒绝，不以再同意复活旧授权。年度/目标变化必须明确展示原引用的entry_year/target metadata，无法对齐则拒绝，不能把其他届/课程规则当成绩变化。

独立显式factory extends plans profile，默认服务关闭/test合成显式启用，real_revisions_ready恒false。HTTP仅5类：GET /plan-revisions/context、GET /plan-revisions/history/{plan_id}、POST /plan-revisions、GET /plan-revisions/{revision_id}、POST /plan-revisions/{revision_id}/decision。固定UUID/strict JSON/有界body/query/content-type、稳定CSRF+Origin、当前session、no-store/有限错误与最小审计。构造关闭零IO，SQL/审计/实际COMMIT任一失败整TX回滚；最后SQL后一个fresh时刻校所有身份/purpose/profile/plan/proposal TTL，accept还须完整新当前证据/规则/日期证明。

## 修改范围

新app/plan_revisions/domain/schema/service/store/router、api/revisions factory、独立迁移/ini与Unit/PG/HTTP/浏览器专项；新packages/contracts/v2/revisions LF工件。旧路径仅治理8文档+docs/api.md、.gitattributes、scripts/generate_contracts.py、apps/web/src/views/PlanView.vue。原8profile工件保持，generator只增加有限新profile、不放宽原schema。前端仅PlanView子组件接缝与features/plans/revisions新client/validator/controller/panel/专项；旧M0/head/T23–34业务/完成状态/依赖/原文/旧验收不变，无新依赖。

## 可测试验收

1. pure受限输入/差异/历史DTO/无假credit/时刻/hash预算；同标题异scope/单位/尺度不承接完成，引用噪声单列、unknown与日期精度保留。
2. 实际PG合成画像新版/新评估/新draft→proposal→accept或reject，旧确认/完成/registry全不变，reject旧history可读，新draft未确认/未完成；替代与withdraw当前源不能accept。
3. 真实两Session accept/reject/重复accept、旧完成CAS、新编辑CAS、rollback/deferred COMMIT、权限/原purpose/notice/私有TTL最后时间、mapper零IO、跨owner/admin/grant、migration down/up不改十四旧head。
4. 真实HTTP与Edge端到端接受/拒绝、差异/旧完成历史、手机/键盘、迟到200清理；新前端专项及完整Unit/Type Check/demo-auth Build；相关Python/契约/9profile生成/原文/保护与文档同步。无Lint/Python静态入口明确未执行，正式模型/资料/法律/部署关闭。

T40未来删除先清revision/decision/关系/历史completion引用，不能为FK永久保留私有对象。本Task不实施worker/通知/删除。结果见[验收](acceptance/T35_plan_revisions.md)，本批T40停止。

## 最终一致性补强

get/decision及重复提案重建两侧原pin的不可变proposal/截至state完成与完整历史映射，再核原diff；自洽SHA不能授权伪历史。原创建时刻须包住原隐藏proposal/完成/assessment/profile/source期限；来源impact只按创建时刻及精确owner/plan/version/source/hash/receipt集合验证，后来的事件不改变旧拒绝依据。unknown日期精度的原local_date/local_time/timezone全null，参考日历独立保留；官方UTC不补造。实际末版命令与复验加载范围见验收。
