# PRIVACY-PUBLISH-01 源码公开前隐私审阅

日期：2026-10-14，Asia/Hong_Kong。状态：用户明确确认方案后，干净源码已公开。

用户要求审阅两个Git项目的个人隐私／信息，修复后公开。本Task只涉及源码与Git发布边界，不恢复应用测试、真实学生处理、模型调用、数据发布、部署或后续开发。

## 本次实际审阅

- 完整原远程镜像：49个分支、78个可达提交、1,685个blob，实际读取43,574,037字节；所有历史tree建立路径映射，并审阅提交作者／提交者与message。不是仅检查最新HEAD。
- Gitleaks 8.30.1使用默认规则、空忽略文件、`--ignore-gitleaks-allow`、`--log-opts='--all --full-history --root -m --no-renames'`、`--redact=100`、JSON本地报告扫描原镜像；exit1、18项候选。逐条读取对应原提交后确认均非真实凭据：业务batch/record键、SQL范围约束、None清理赋值或明确合成的测试输入。不为消除误报修改应用代码或添加宽泛豁免。
- 当前源码4份文档的8处个人home前缀已脱敏，保留相对工具路径；旧原件与历史完整保留在本地私有镜像。旧验收结果保持原有含义，新增隐私注释说明这些是脱敏后的命令记录。
- 原提交历史含私人邮箱（作者／提交者共156处）；它不会被复制到新的公开提交历史。新提交使用GitHub noreply邮箱。
- 所有原历史blob均为可读取文本，没有二进制或LFS。DEMO画像、测试账号／样例邮箱、幂等标识及官方公开来源与真实个人资料分开。依赖锁中的公开维护者联系信息和合成工时数字不作你的隐私处理。
- 原GitHub远端没有PR、Issue、Release、Tag、Actions运行、Artifact、Cache、Deployment、Environment或Repository variables需要迁移／清理；平台Secret值不能经API读出，未尝试读取或验证凭据。
- 脱敏候选再次逐文件审阅后，在所查真实信息类别中候选为0。应用、测试、数据库迁移、锁文件、类型契约、DEMO与有限公开来源研究字节保持原样。完整明细、literal映射与原镜像只本地保留，不上传。

## 已批准发布方式与实际交接

用户明确确认保留私有历史、公开同名干净版本。改名前实际49条远程分支与已审镜像完全一致。原仓库ID1400234431改名study-admissions-agent-private-archive，保持PRIVATE并只读归档；78个原提交及原工作保留。原D:/Projects/study和原镜像origin现在指向此备份，不指向新公库。

新公开仓库https://github.com/chanbilly-lab/study-admissions-agent，ID1418914840，默认codex/privacy-release；公开工作目录D:/Projects/study-public。初始干净根ab0da1f90ee396f9e10da30cd00fc6d650212298，969个tracked文件／1个提交，远端SHA、tree、唯一分支与noreply作者／提交者已核对。先私有上传与核对，再改PUBLIC；只普通push，没有强推或删除原refs。应用CI运行0，手动默认关闭的质量工作流保留但未执行。

匿名请求新仓库metadata／页面均200，私有归档页面404；原HEAD在新公库Git对象接口404。旧提交REST接口实际422且明确No commit found for SHA；首轮预期404的检查因此中止，读取实际信息及Git对象接口后已核对。此为代表性原HEAD探测，不宣称逐一检查全部外部缓存；新Repo ID／干净refs不继承原历史。

最终干净根Gitleaks实际exit1／同18项已复核误报，fsck exit0／无不可达对象。源码、契约、迁移、锁、DEMO及有限研究资料字节保持；本Task新增变更仅隐私／治理文档与ignore。新公开提交使用GitHub noreply，只从干净副本创建，不能合并或推入旧私有历史。本次授权替代历史“源码必须私有”的受众规则，不改变应用发布门槛。

源码公开不等于咨询服务公众上线，不授权真实学生数据或事实自动发布。原D01–D08、真实目录／模型／生产门槛保留。

## 检查限制

本轮明确授权的安全扫描与静态审阅实际执行，不是应用Unit／Integration／浏览器回归。Lint／TypeCheck／Build／生成／导入／部署／数据库／真实凭据验证均未执行。检查有规则与编码边界，不宣称绝对无未知泄露；历史测试通过记录不作为新的公开候选运行证据。
