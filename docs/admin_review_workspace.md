# T22 审核与发布管理工作台契约

2026-10-03实施代码前冻结。T21 PRIVATE ed4defaf 已保存，425tracked/索引空；当前仅T22，codex/t22-review-release-admin，其他Task不启动。沿用既定模块化单体、依赖/旧迁移冻结；真实处理与公众发布默认关闭。

## 数据契约

新独立admin_review private profile复用T21全部原路径并增加以下显式接口（/v2前缀），旧T21/foundation/identity/public_catalog产物不改。

| 方法和路径 | 输入/输出与权限 |
| --- | --- |
| GET /admin/review-context | 服务器当前强data_admin及精确链策略能力 can_prepare/can_review/can_publish/can_withdraw/is_synthetic；不猜前端角色 |
| GET /admin/imports/{import_id}/rows | 负责导入账号、当前原批/源/file证明；limit<=20、cursor有界；ParsedRow+row UUID和精确原文件/来源/hash引用，不含owner/path/全文 |
| POST /admin/evidence/documents | 既有DocumentCreate+strict confirmed=true，DocumentData |
| POST /admin/evidence/versions | 既有VersionCreate+confirmed，VersionData，原hash/CAS保持 |
| POST /admin/evidence/snippets | 既有SnippetCreate+confirmed，SnippetData；明确UTF8半开byte定位<=4096，不猜PDF/字符offset |
| POST /admin/facts | 既有FactCreate+confirmed，TypedCandidate；显式九classification字段，未知仍draft，非审核/硬规则 |
| GET /admin/review-candidates | dataset_id/year显式、limit<=100/有界cursor，当前强审核者可发现最少候选引用；不借responsible账号读全文 |
| GET /admin/review-candidates/{fact_id} | TypedCandidate+ReviewCaseData+EvidenceScope+SnippetData或null+完整有界当前冲突和固定缺口；逐次当前证据及期限验证 |
| POST /admin/review-decisions | 既有ReviewRequest+confirmed，十固定checks均独立显式、全部当前冲突理由/return理由、expected_case_revision；独立审核者，返回服务器决定且不发布 |
| POST /admin/releases/precheck | 既有PublishRequest+confirmed，当前完整T19 proof/CAS诊断；status=precheck_passed/request_sha256/dataset_revision/member_count/checked_at/is_synthetic；不创建release或幂等receipt，不发永久permit |
| POST /admin/releases | 同PublishRequest+confirmed+单一bounded Idempotency-Key，当前T19重验及同TX发布；预检不代替当前检查 |
| GET /admin/releases/current | dataset_id/year明确，强管理员读取当前release最少状态/版本/hash/窗口/dataset CAS；不读取失效事实，允许发现减权撤回对象 |
| GET /admin/releases/{release_id} | 严格T19当前证明，ReleaseData；不回完整文件 |
| POST /admin/releases/{release_id}/withdraw | expected_state_revision/有限reason_code+confirmed，release_id仅取path，state CAS+有限原因；旧资料失效不阻挡有权撤回 |

所有unsafe操作复用会话Cookie/固定Origin/CSRF，bounded JSON body/重复keys和headers拒绝，服务即时强认证/角色/配置。UTC窗口HTTP只解析有offset严格RFC3339并转换native aware datetime，不放松原内部DTO，不接受epoch/naive；公开有效期不是招生截止日期。能力探针不是按记录永久授权，所有执行仍同事务当前证明。

新增create_admin_review_v2_app/private factory默认零DB/IO；parent create_admin_review_app单独挂/public/v2既有T20匿名读取。显式reader必须同engine/同release service、pipeline identity与runtime绑定；测试public runtime demo只能test/allow_test_fixture_read，production verified保持一致。匿名预览使用既有public_catalog契约/credentials omit、明确entry_year，显示真正当前release和覆盖缺口；不碰M0/v1DEMO页面或用管理DTO冒充公共事实。

## 修改范围

新增admin/review_http四模块与api/admin_review.py，backend unit/integration专项；复用T16–T19已验收service（仅明确必要局部修复须先记录范围），不建新表/迁移/框架/依赖。root生成器只显式增加admin_review profile/操作body/header/UUID白名单及新LF产物，旧四profile字节不变。新增frontend preparation/reviews/releases及ReviewReleaseView，旧AuthView仅最小挂载；新tests/browser脚本，不改旧tests。文档只当前Task/ADR/API/架构/需求/数据库现状及CHANGELOG/tasks。

## 可测试验收

1. 两个明确合成强管理员，经T21实际导入→候选行可发现→独立明确document/version/span/classification→有限原文/原字段并排→独立逐项审核；不用预知fixture factUUID冒充可达路径。
2. 缺证据/Scope/脚注/统计/日期缺口清楚可见；unknown与不可批准/未发布标识保留；自审/普通学生/operations/弱MFA/CSRF/Origin拒绝；来源URL和原文XSS不执行、不联网。
3. 当前完整冲突须逐一理由，不默认胜者；真实两审核者CAS争用只有一成功、历史保留；陈旧case/dataset/state和COMMIT失败不部分写入、不显示成功；相关服务专项回归。
4. 预检修改payload/账号/引用后清失效结果与confirmation；请求世代/abort阻止旧响应回填；同确认发布payload手工retry同key，其他写入不盲重试。
5. 发布→替代→撤回真实ASGI/PG，匿名公共页显示当前release/新version；过期或撤许可拒绝读取，但当前有权管理员仍可撤回metadata；失败不会重新启动旧版。
6. 十checks起始未选、独立确认/公示证据选择、明确UTC窗口与各CAS；390px/键盘、无浏览器token存储。
7. 纯/PG/组件/实际Edge专项及相关回归，TS Type Check/demo/auth Build、契约漂移/原文/治理检查。Lint/Python静态类型无入口需明确未执行，真实IdP/事实/法律/SQL权限/清理/部署不执行。

只合成离线验证，不代表真实人工事实审核或正式发布获授权。日期适配须既有T12已明确候选引用，未准备日期保持缺口；本Task不额外实现日期编辑、规则DSL或自动抽取。全部代码与文档验收、私有推送核对后才进入T23。
