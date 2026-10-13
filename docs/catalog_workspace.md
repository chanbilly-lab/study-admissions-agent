# T29 项目比较与证据工作台

2026-10-03实施前冻结。基线PRIVATE T28 acb2b3cbe3e4f70c95f5156e41c9b9f67f0eec70，546tracked/工作区与索引空；仅T29，验收/同步/保存后才T30。无新依赖、后端/API/数据库/迁移/生成产物/M0变更；正式资料、未成年私有、live和部署关闭。

## 数据契约

两个可替换客户端复用固定生成DTO。CatalogApi匿名同源`/public/v2` config/offerings/evidence，credentials omit/no-store/redirect error；EligibilityApi同源`/api/v2` context/evaluate/get/replay，Cookie same-origin/no-store，每write即时CSRF，无Idempotency-Key。默认入口缺少reader/service时显示关闭，不调用v1或DEMO回退。只允许相对受控prefix，无外部传输/Token/local或sessionStorage；不显示自由错误正文。

公开查询entry_year明确输入、可选country及精确scope canonical filters，limit/cursor有界；筛选变化清cursor、选择、比较及评估，cursor409提示明确重读第一页而不静默改条件。year空白不取系统年；2026全国参考和2027英国暂定只是提示。跨页比较最多4个精确(release_id,offering_id,version)及完整scope/requirements绑定，显示年度/招生体系/项目和已发布状态，结果不排名。没有历史竞争、偏好和质量数据时各维unknown，不算分或概率。目标country从已读offering.scope.country取得；其他地域可浏览，个性化仅CN/GB适配，不套高考规则。

21字段EvidenceScope原样递归sort keys、UTF8 ensure_ascii=false/separators无空格后SHA256，不能删掉degree/course/campus/language等维度。画像、版本、release、目标、阶段与六个显式required-nullable附加范围由用户明确核对后confirmed=true提交；服务端重算为权威，前端不造AST/clock/owner/结论。不修改或转换实得/预测、未知/不适用，未知scope不能推known。每项目独立T28 POST，不宣称比较batch原子或幂等。

评估响应严格核实际profile metadata/profile hash、target scope SHA/release/requirements/stage等对应当前请求；保留不可变原结论与current_validity，withdrawn/replaced/needs_review/unavailable不当当前资格。历史读取/重放需要明确ID和replay确认，不自动复用当前选项。conditional显示必要事项及独立主补期限来源/精度，缺少期限无依据unknown，不能补23:59或通用学校条件。

公开证据只从实际该release/member公共evidence引用取得，显示publisher/官方性声明、年度范围、定位byte/line、原文/片段hash和release版本。原文用Vue文本插值，禁止v-html/执行HTML/Markdown/链接指令；DTO没有source URL不得补URL或声称已有原附件访问。合成机构/片段明确DEMO，即使claimed_official也不是真实官方依据。证据原quote UTF8 SHA/byte span与scope/target/release/requirements准确绑定；当前失效/撤回请求拒绝，不能用已缓存片段续读。

## 状态与权限

public/private/evidence独立generation/AbortController；actor变化（含同账号新会话）、核心用途读取中/失效、画像编辑/确认新版本、目标/阶段/范围变化及dispose立即清私人结果/历史/确认并取消请求。迟到的成功响应不能恢复旧actor或旧画像数据。403/401/关闭清私有，401向上通知会话失效，409明确核对不自动重写。公开目录可匿名使用；公开比较和私有结果生命周期分开，不能将管理员/共享角色视为本人授权。

旧ProfileView只追加最小profileSelected确认当前版事件及已有invalidated信号，AuthView保存当前只读版本/epoch并挂CatalogView；当前编辑/dirty/conflict/不确定/核心用途变化不得传有效画像。不修改旧useProfiles业务或旧M0组件wire。复用M0卡片排版、四态解释及原生dialog模式，新EvidencePanel使用当前v2 DTO。移动390px无横滚，fieldset/label/buttons/表格caption/对话框焦点恢复/Escape键与aria-live明确可用。

## 修改范围与验收

新features/catalog/eligibility/evidence的client/controller/DTO验证和组件、views/CatalogView.vue，AuthView/ProfileView最小接缝；Vitest、独立安全验收和实际PG/Edge桥接及新脚本；十个允许旧路径仅七治理文件+两Vue接缝+vite.config.ts。Vite开发代理增补/public→loopback8002并去/public前缀，复用T20独立入口；/api继续8000，未组合或部署正式服务。root同步README/requirements/architecture/tasks/CHANGELOG/ADR042、本契约及新验收，API/DB未变不改其文档或旧生成契约。

1. 查询明确年份、完整过滤/pagination/cursor409、跨页4项目比较及缺口；精确decimal/footnotes/日期精度/分母不混合。
2. 同源/无Token/即时CSRF/strict request和response metadata；跨目标/年/画像/范围/日期坏DTO拒绝，不从错误正文泄露。
3. 不确认不evaluate，当前画像dirty/新版本清结果；四态和必要后补义务可读，无期限unknown，非资格维明确unknown。
4. actor/core/profile/target/stage变化清私人状态，成功迟到请求无法复活，明确历史replay及失效标记。
5. 实际Edge→真实v2 ASGI→专库随机schema，经合成T19明确public_evidence=true发布，完成分页筛选比较→当前画像→evaluate四态/unknown→公开证据与HTML逃逸→移动/键盘→退出和延迟GET隔离；0外网/商业调用，无真实学校编数字/日期。
6. 专项/独立Vitest、完整前端Unit/Type Check/demo-auth Build；相关Python/生成/原文/M0/范围/文档/实际暂存diff及PRIVATEpushSHA。无Lint/Python静态入口标未执行；真实处理/领域/法律/生产权限/部署不执行。

冻结契约保留实施前范围；实际检查逐轮记录在[验收](acceptance/T29_catalog_workspace.md)，不能以契约代替通过结果。

## 本地入口与关闭状态

前端沿既有`VITE_APP_MODE=auth`和`scripts/web.ps1 -Action dev`运行；显式展开“项目与证据工作台”才建立目录请求。开发代理/public去前缀到loopback8002的既有T20 public_catalog factory，/api去前缀到8000的T28 assessments factory。各factory默认无reader/service，不连接数据库或装载学生资料，关闭时页面明确不可用；uvicorn运行方式沿对应模块文档，本Task不宣称部署或默认拼装了正式服务。测试组合仅ASGI隔离夹具，在同一随机schema把实际两个已验收工厂分别挂/v2和/public/v2，不改旧工厂协议。

本轮初始开发代理只有/api，已补必要/public接缝；两模式Build通过。实际页面验收使用静态构建+loopbackHTTP桥到真实ASGI/PG，未验证生产代理/HTTPS或Vite dev代理运行流量。
