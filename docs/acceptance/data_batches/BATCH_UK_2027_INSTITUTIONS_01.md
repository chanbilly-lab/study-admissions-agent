# BATCH-UK-2027-INSTITUTIONS-01 资料采集报告

- 日期：2026-10-13，Asia/Hong_Kong。
- 用户范围：剑桥大学、曼彻斯特大学；英国本科2027入学；具体专业未选。
- Git基线：codex/zj-2026-cutoffs，94e484a22b0c503f0eaa37049fbfa4069f40b480；工作区/索引开始无改动。新工作分支codex/uk-2027-sources。
- 完成范围：[事前数据契约与完成条件](../../uk_2027_sources.md)。只研究层候选来源，非正式数据库/页面闭环或招生事实验收。

## 实际操作与结果

| 操作/实际命令 | 结果 |
| --- | --- |
| 官方域名检索及web.open；实际官网和页面正文阅读 | 曼彻斯特目录可读；剑桥此前浏览工具403。搜索缓存只作来源发现，不当作原文字节。 |
| `.venv/Scripts/python.exe -X utf8 -B .cache/uk2027_capture.py` | exit0，固定8URL顺序普通HTTP获取，8个200 HTML。单页20秒/2MiB上限，最多3次固定官方主机内重定向，未重试/递归。实际HTML和元数据仅.cache。 |
| 原文/规范化文本人工源码阅读，针对2027、China、College、UCAS及Copyright段落 | 阅读实际捕获文本；专业和College差异、日期例外及复用许可限制记录为待审研究说明。国际页March2026是更新月份，不伪造确切发布日期。 |
| `.venv/Scripts/python.exe -X utf8 -B .cache/uk2027_register.py` | exit0；按实际捕获元数据与原文存在的短摘录生成研究JSON：2机构、8来源、8捕获、正式审核0/发布0。这属于采集/提取操作，不是应用测试或正式许可审查。 |
| `git ... status --short`、基线/remote检查及`gh repo view chanbilly-lab/study-admissions-agent --json visibility,nameWithOwner` | 基线干净，origin为已授权仓库、visibility=PRIVATE；仅当前Task文件审阅后普通提交推送。 |
| Unit/Integration/浏览器验收、Lint、TypeCheck、Build、校验脚本、CI、迁移/PG/API/页面查询 | **未执行**：用户原“不用测试”保持；本批仅采集研究文件，无应用/API/DB/前端实现。没有借用浙江或M0历史结果。 |

抓取UTC2026-10-12T17:23:12至17:23:20，对应本地2026-10-13。字符定位针对规范化HTML文本，不是HTML原字节偏移。

## 实际快照

| source id | bytes | 原HTML SHA256 |
| --- | ---: | --- |
| cam_study | 110424 | 69b9d639b0a5cb1ee40d3c9027429789f54515886bceb55d7ace79211b893b53 |
| cam_site | 77344 | c1fcff9116aefd74a5912e787bc83cd8f9c2a49192cdf27377728b6942b47db0 |
| cam_international | 178034 | 9f5c1a75aeefa6644796be8846a8e0dcdb207ab7cc1c5571c623061b89eafd9a |
| cam_entry | 90426 | 72d8feb9864844d6e10cbd428dfa25821e5d50c660b453a104204a83df9b6497 |
| cam_ucas | 87782 | 4249f76f279212bdd5832dee62aa7f9b4fd50a344ac9c01d946739972f04cfb5 |
| man_courses | 69200 | 059b52f5f759cff647c7c676028e8a6772e9fa0d357446aeee57191e2792f5b3 |
| man_international | 61000 | 9a34d2309e80e9308e986e60cd3317552ba4eb12eb3ac81cf97942471cad5c85 |
| man_china | 115900 | ebccab0691f2b8857e3e374982dc05e94202b00b273897fa74383ed9379fef69 |

这些是本机真实捕获版本hash，不代表正式审核、使用许可或未来页面不变。原文仅.cache；仓库只有小型候选元数据/短摘录。克隆源码不会取得原快照，正式审核前须取得可合法保存的适用版本及其原文。

## 修改文件

1. data/research/uk_2027_institutions_sources.json
2. docs/uk_2027_sources.md
3. docs/acceptance/data_batches/BATCH_UK_2027_INSTITUTIONS_01.md
4. AGENTS.md
5. README.md
6. docs/tasks.md
7. docs/CHANGELOG.md
8. docs/data_strategy.md
9. docs/requirements.md

未修改原始输入/旧研究文件/DECISIONS/架构/API/数据库/迁移/前端/依赖。当前做法遵循既有研究层及ADR-034目标，不构成新技术方案；无新增重要技术决策。

## 已知问题与停止边界

两校完整专业清单与选课未完成，所有专业的2027资格/费用/培养/就业覆盖未知；来源捕获8/8只指这8个指定端点，不是全校或全英国覆盖。曼彻斯特相关本科政策段年度未明确，不用其他段的2027替代。剑桥通用网站2027版本不保证所有课程一致。公开/商业复用及自动抓取未获许可，正式负责人/审核/发布未完成；研究候选不接资格或页面，不写正式SourceService、不伪造管理员/UCAS代码。

保留旧用户“不用测试”及M0/浙江运行状态；不运行额外检查，不启动全网采集/公众部署或其他任务。CHANGELOG/tasks本批同步完成后，仅当前9文件PRIVATE普通保存。
