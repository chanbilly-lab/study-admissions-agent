# T24 画像编辑与本人确认工作台

2026-10-03实施前冻结。T23已PRIVATE上传`f901ab2e406d42e93fec23f28df6a814fb6d6765`、481tracked/工作区和索引空；当前只T24、`codex/t24-profile-confirmation-ui`。本Task无后端业务/API/数据库/生成契约/新依赖改变，使用已验收T23六操作；T25及后续尚不开发，真实处理保持关闭。

## 数据与状态契约

ProfileApi复用生成的profiles DTO，与会话同源相对URL、Cookie/no-store/redirect=error；不传owner/role/模式、secret/token/query proof，写入前读当前CSRF，由浏览器提供Origin。运行时严格验证当前能力、完整version/scope/grade/null/decimal/meta引用；拒绝坏响应或多余敏感字段，不将后端错误正文/自由HTML显示给用户。初建使用唯一安全Idempotency-Key，只对完全相同的明确payload重试同key；编辑或账户/授权变化清除key。追加仅expected_current_version/CAS，不发送幂等key、不自动重新提交409；网络写响应丢失显示未确认并要求重新读取当前版，不宣称成功。

本人上下文探针决定create/read/append能力，客户端角色或成年勾选不是授权。AuthView仅挂载ProfileView，未知/未登录不显示学生输入；PrivacyPanel通过最小admissionChanged事件通知当前核心用途是否有效，读取中/错误/撤回及任何age/core/withdraw操作开始立即置false。ProfileView据当前actor和此信号清空私人数据、取消请求并递增generation；同一账号重新登录也重新读取。服务端仍每次重新核验，不以页面探针永久授权。无local/sessionStorage/URL画像或第三方传输。

表单完整对应T23ProfileSnapshot。首次所有成绩/满分/每周小时/偏好预算空白；入学年须本人明确，2027仅暂定目标提示。五个scope各自明确known/unknown/not_applicable，不从所在地推出省/身份/课程。省份为学生选择的意向，列出的地区不代表规则已覆盖。课程/路线unknown或unsupported不渲染普通高考成绩输入；只有明确known gaokao课程、known cn_mainland申请身份以及known gaokao/英国本科路线才显示新的普通高考成绩与语言询问；身份未知或未适配先保留最少意向。已存完整版本先只读，用户明确进入编辑后保留所有原字段；只有实际切换范围才清不支持的草稿字段并提示，不因隐藏自动丢弃。用户切换到未适配体系，草稿不提交高考字段；说明草稿清除及旧确认版本保留，最后完整确认后才写入。gaokao也是待适配，不生成资格判断或学校通用条件。

复用M0空字符串/数字v-model处理经验及合适的固定字段标识；不复用DEMO姓名、默认满分/科目/8小时或旧Number输出，避免改动M0 wire。T23精确decimal字符串保持用户值；''保持missing/null或省略整项、零保留0；满分/单位明确、不用预测填实得。实得/预测独立，pending不能显示后补许可，preferences/budget只是意愿。本Task不收姓名/证件/生日/附件，不做诊断或录取概率。

编辑草稿与已确认版本分开。任何修改撤销本地confirmed勾选、标记草稿未确认并发出可复用profileInvalidated事件；后续评估必须绑定新确认版，不复用旧结果。没有T28时只提示尚无可用资格结果，不能假装已作评估。新建/追加都由用户重新勾选明确确认；生成建议/历史读取不能代确认。读取本人有限root引用及必要明确版本，显示当前UUID/序号/确认时间/合成标签/适配未知；历史只读，不能把历史版号作为当前CAS。

409保留本人当前草稿供核对、撤销确认，并提供明确读取当前版/放弃草稿选择；不静默覆盖。权限403、会话401、撤回、关闭或账户切换清空私人状态并取消迟到响应。能力关闭显示原因和DEMO/正式未开放，不能回退M0或合成账号。日期按服务器值展示，不造官方日期。

## 修改范围与用例

新增前端features/profiles/{client,form,state,components}及views/ProfileView.vue、对应Vitest和实际browser smoke/pytest loopback桥接；AuthView最小挂载、PrivacyPanel最小用途状态事件。root同步README/requirements/architecture/ADR037/任务/日志与新验收。无旧M0/后端/迁移/依赖/生成产物修改；原规格和历史保护。

1. DOM数字v-model实际编辑、清空非零、实得预测与满分/单位、每周0和unknown、偏好；精确有界数字拒绝NaN/指数/不合法单位，创建不带owner。
2. 不确认不写入、每次编辑重新确认；新版本保留旧版；普通高考/UK询问及unknown/unsupported隐藏高考字段；地区身份独立。
3. 当前能力关闭不收私有输入；成年人声明与core独立；401/403/withdraw/账户切换/unmount取消和清空，迟到响应无法恢复旧私人数据。
4. API同源/CSRF/安全错误/Meta与payload匹配；初建同payload重试、变更key及append仅CAS；409无自动写、失败不冒充成功。
5. 实际Edge+ASGI/PostgreSQL隔离合成流程完成准入→创建→编辑确认→读取历史，缺失/预测与DB一致；并发外部版本变更触发UI409/重新核对；移动390px无横滚、键盘确认、退出/撤回隔离，0外网/商业请求与页面错误。所有正例DEMO，不在生产创建账号或处理真实资料。
6. 相关T23/契约模式回归、完整Vitest/Type Check/demo-auth Build、生成/原文/治理检查。无Lint/Python静态类型入口时明确未执行；真实用户/供应商/法律/生产权限/部署不执行。

成功验收、文档同步及PRIVATE普通保存核对后才进入T25；完成T40后停止。
