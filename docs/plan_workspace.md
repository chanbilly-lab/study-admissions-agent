# T33 计划与进度工作台

2026-10-04代码前冻结，现源码与合成隔离验收完成；T32 PRIVATE b90ad68/616tracked/空索引与工作区。仅当前T33前端和实际合成PG/Edge验收；九旧路径（七治理、AuthView/CatalogView）允许，607其他tracked包括所有backend/迁移/八生成profile/原文/docs01–05/M0/旧测试保护。无API/DB/依赖变化，无正式处理/模型/部署；保存验收后单独T34，本批T40停止。

## 数据契约与页面

复用T32 plans生成契约与八操作，新features/plans/{client,validation,form,usePlans,presentation}.ts、最少源选择/编辑/排程/任务/历史子组件和views/PlanView.vue；不强行拆tasks包或新增global store。当前actor/coreAllowed/确认profile/profileEpoch作为失效信号，服务器context及每次权限为权威；默认折叠，匿名或未准入无私有输入/探针，无M0回退。

CatalogView只在学生明确点击“加入准备目标”时交接已校验AssessmentData；AuthView持有最多四个同当前画像ID/version/hash/mode的选择。不能使用fixtureUUID、公开target或未读取结果代替实际评估。可使用当前以及当前画像匹配的历史/未知核验来源，后者明确标注只生成该来源核验安排，不把旧资格当当前资格；server create仍fresh重验。学生明确选择目标并确认创建，服务只收原assessment IDs、study_goals与估时字段；不传owner/AST/结论。

已有计划可在已登录且核心用途有效时明确读取，不要求先展开画像页；以服务器当前权限和返回的精确画像绑定为准。创建、编辑、确认和完成操作须有当前明确选择的确认画像，画像编辑/epoch失效后先重新选择确认版本，不能沿用旧CAS继续写。

创建目标确认、可用时段/留出休息确认、最终本人计划确认相互独立。估时及周工时均text＋decimal输入，空白null、0保留，最多六位；没有默认周小时/时段，不把未知估时补零。时段和内部目标明确UTC ISO原串（Z/+00:00、≤6小数）保留，指定IANA仅显示当地预览；不按机器时区猜datetime-local、不Date→ISOString丢微秒，不把日期-only/候选UTC或主补最小值冒充官方截止。官方未知恒提示，constraints_complete=false；容量blocked/partial/conflicts显示原原因/可选操作，不自动压缩休息/增加工时/平移时间。

当前execution、本地workspace draft、历史投影分开。历史GET按所选state_version精确显示且没有写动作，不拿历史CAS覆盖当前。最终确认须ready/known weekly、当前两SHA+expected_version、本人confirmed及独立ack未知期限；只有confirm传opaque随机key。确认后禁编辑；任务完成逐项本人声明、依赖服务端复核，包括0里程碑不自动完成。完成仅student_declared，不升级成绩或资格/学校结果。

## 并发、失败与私有擦除

同源credentials/cache:no-store/redirect:error；复用Cookie/CSRF短寿命局部值，仅confirm header，错误只固定status提示。响应验证verified/disabled及真实Meta/profile/plan/state/proposal/refs/hash/有限集合与正确重放绑定，bad200等敏感失败清空。响应/请求有界，不写浏览器持久存储、不执行v-html或任意URL。

409清confirm/ack并锁写到明确GET；保留未提交参数但不继续展示旧来源为可执行，重新读取后必须重新核对/确认，不自动覆盖。首次过去容量409不自动平移。create/workspace无T49，丢响应只明确读取服务端，不自动再写；confirm不确定只明确重试原冻结payload＋同key；complete不确定仅原CAS规范请求自然重试或读取，不能拿新CAS假重放。网络失败不显示成功，服务默认关闭明确显示边界。

actor变化（含同账号新会话）、core变化/撤回开始、退出开始、profile编辑/新版本/epoch变化、卸载同步清targets/current/localdraft/history/context/CAS/receipt/key并abort＋generation失效；忽略AbortSignal的迟到GET或POST200不能复活。401通知外层session。403/404/503/bad200清私有。来源已失效时T32拒绝仍是权威，不绕过历史读取；T34/T35处理后续历史核验及修订，本Task不提前实现。

## 修改范围与验收

前端实现代理拥有上述新modules/components及自有client/form/state/view测试、两旧Vue接缝。独立代理新增plans-workspace-safety测试，覆盖迟到响应/历史CAS/显式重试/0与null/UTC微秒/409；backend代理只新增tests/integration/plans_ui/{conftest,test_t33_browser}.py与scripts/plans_t33_browser_smoke.mjs，复用现T29真实Origin透明ASGI桥接、当前plans/private与public_catalog工厂，不改任何backend/API/迁移/生成工件。

实际专库study_t23_20261003/127.0.0.1:55438，plans_ui_t33_UUID自有随机schema；fixture只创建合成profile/发布资料/规则，不预创建plan/proposal/confirmation/completion；评估与计划从真实页面操作生成。实际Edge/Node24无外网/商业API，cookie仅stdin，DB/provider env剔除，owned端口/profile/截图.cache；不控制用户浏览器或部署。检验真实DOM创建/0null/µs容量/不足冲突/外部CAS/明确reload/未知期限ack/confirm/依赖自报完成/精确重放/只读历史、390px/键盘/转义、真实成功GET延迟跨actor/core/logout不复活；检查点属于实际PG用例，不重复当pytest数。

每Task实际Unit/相关Python/前端完整Vitest、Type Check/demo-auth Build、实库browser与截图人工检查、八生成profile/原文/M0/保护范围/66卡/历史/链接/实际暂存/PRIVATE SHA。Lint/Python静态无入口未执行；官方精确期限正例、真实身份/资料/法律/GRANT_RLS/代理HTTPS/部署/生产恢复未执行。实际结果见[验收](acceptance/T33_plan_workspace.md)。浏览器ICU与服务tzdata差异可能保守bad200；原PlanAssessmentRef未提供年度，页面明确显示缺失。草案expires_at取原来源评估记录期限最小值，不代替证据授权、规则或政策的当前期限，每次操作仍fresh重验。
