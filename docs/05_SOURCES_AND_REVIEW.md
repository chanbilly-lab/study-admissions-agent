> 由原始开发方案对应章节提取；原文件保留。M0 范围以 M0_IMPLEMENTATION_PLAN.md 为准。

# 05 官方依据与风险审查
核查日期：2026-09-30。以下用于支撑开发方法与风险边界，不构成完整招生规则库。URL访问情况不等于抓取/商用授权；正式接入应重新读取并审查条款。来源随时间可能更新。

## 核查依据
[S1] OpenAI：Custom instructions with AGENTS.md。Codex读取仓库指导文件；可在其中放入工作方式、测试与审查约束。
`https://developers.openai.com/codex/guides/agents-md/`
核查时重定向至 `https://learn.chatgpt.com/docs/agent-configuration/agents-md`。

[S2] OpenAI：Prompting。将任务范围、验证步骤和测试输出写清楚。
`https://developers.openai.com/codex/prompting/`
核查时重定向至 `https://learn.chatgpt.com/docs/prompting`。

[S3] UCAS：Entry requirements for UK courses。课程要求因学校、课程和资格而异；国际资格须核实。
`https://www.ucas.com/international/international-students/applying-university-international-student/entry-requirements-uk-courses`

[S4] UCAS：Dates and deadlines for uni applications。区分入学年份、平等审理日期、最终申请等阶段，并保留英国本地时间。
`https://www.ucas.com/applying/applying-to-university/dates-and-deadlines-for-uni-applications`

[S5] 教育部2026全国高考专题。检索结果中有结合成绩位次、一分一段表与历年院校专业录取信息的说明；本次正文抓取超时，未完成该入口的自动采集验证。
`https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2026/2026_zt08/`
不得将此入口标记为已经成功接入的数据源。

[S6] OpenAI：Structured model outputs。结构化输出有助于schema一致性，但不保证事实正确。
`https://developers.openai.com/api/docs/guides/structured-outputs`

[S7] OWASP：LLM Prompt Injection Prevention Cheat Sheet。
`https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html`

[S8] RFC 9309：Robots Exclusion Protocol。robots规则不是访问授权，不替代条款及权利审查。
`https://www.rfc-editor.org/rfc/rfc9309.html`

[S9] FastAPI官方文档。
`https://fastapi.tiangolo.com/`

[S10] pgvector官方项目。
`https://github.com/pgvector/pgvector`

[S11] OWASP：Server Side Request Forgery Prevention Cheat Sheet。
`https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html`

[S12] OpenAI：Evaluation best practices。任务型评测、持续回归、人工校准与留出数据。
`https://developers.openai.com/api/docs/guides/evaluation-best-practices`
本方案使用自建离线评测，不依赖文档中可能处于迁移期的托管评测产品。

[S13] 国家网信办转载的《中华人民共和国个人信息保护法》。重点阅读最小必要、自动化决策、敏感信息、未成年人、跨境与数据主体权利条款。
`https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm`

[S14] 宁波诺丁汉大学2026年普通高校招生章程。可作为解析复杂条件的参考：省份/专业有条件差异、选科与投档规则分别表述、计划与上级政策有明确关系。单个学校示例不应泛化为所有学校的规则。
`https://www.nottingham.edu.cn/cn/study-with-us/undergraduate/entry-requirements/gaokao.aspx`

## 需求审查结论
P0 范围：全国+全球+所有学段过大；以招生路径适配器扩展，不以一个提示词覆盖。
P0 真相来源：RAG不能代替结构化事实与规则，尤其是分数、条件与期限。
P0 不确定性：unknown是正常业务状态；不能以“智能”之名补齐未公布内容。
P0 预测：不将历史录取线、成功案例或通用匹配度当成个人录取概率。
P0 个人信息：演示只用合成学生；上线前完成个人信息处理和供应商评审。
P0 执行权限：不自动代提交、付款或接受/拒绝offer；确认与审计不只是页面提示。
P1 学习效果：总分不足以支持知识诊断；计划需能力证据、工时与复盘。
P1 数据维护：采集规模必须与人工复核能力匹配；必须有撤回与错误纠正。
P1 体验：比较与任务是主界面，聊天为辅助；不同路线并列展示取舍。
P2 增强：更多国家、自动化题库、复杂优化、个体概率模型均在独立验证后再加。

## 个人信息特别说明
中国个人信息保护法对不满14周岁的个人信息和监护人同意有专门要求，也规定自动化决策的透明与说明、个人查阅更正删除及跨境提供等事项。[S13]

这是工程风险提示，不是具体业务已经合法的结论。建议在接入真实学生前由专业人员确认适用法律、年龄流程、各参与方职责、必要字段、保存期限、委托与跨境安排。14—17岁同样不能被当作无需保护的成人业务。

技术上准备字段最小化、细粒度授权、加密、日志脱敏、撤回/删除传播、备份到期处理与供应商选择机制。公共招生材料与学生私有资料分库/分区、分索引。仅删除姓名或关闭模型训练开关，不等于完成匿名化或所有合规要求。

## 尚未完成的工作
尚未选择首个生源省份和具体目标课程；未取得各站批量采集与再分发许可；未建立正式招生数据库；未由升学领域专家核验规则；未开发、部署或测试应用；未处理真实学生数据。本包把这些设为开发与发布门槛，而不是虚构为已完成。
