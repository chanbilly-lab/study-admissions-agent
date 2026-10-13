# P04 · GitHub仓库与验收后提交推送规则

日期：2026-10-01，Asia/Hong_Kong。状态：已完成。实施前计划保留，实际结果后补；本轮只做P04。

## 实施前计划与范围

用户授权创建仓库并在每个Task成功完成后上传，随后明确确认私有仓库`chanbilly-lab/study-admissions-agent`。Git源代码上传属于本次及后续成功Task的持续授权，公众部署/真实学生数据/招生事实发布仍须各自验收及授权；不开发T03。

当前本地已有.git，无commit/remote，工作区99个项目文件未跟踪，GitHub CLI已登录目标个人账号。保留Git目录和所有文件；拟将初始未提交分支master改名main，不创建无关工作分支，后续新工作分支用codex/前缀。复用既有Git身份，不改全局safe.directory或认证设置。初次上传是现状基线，不编造过去Task的独立commit。

不修改应用数据契约。仅修改AGENTS、README、.gitignore、tasks、CHANGELOG、DECISIONS共6份；新增.gitattributes及本记录共2份。快照/诊断存ignored `.cache/p04-git-20261001/`。原输入/docs01–05、全部运行代码/锁/迁移/夹具/研究/旧验收保持。

实施顺序：清单/秘密与ignore核对 → 同步持续授权及ADR → 私有仓库创建与remote连接 → 仅暂存审查清单、验证blob与原文 → 创建首个基线commit并正常push → 读取远程可见性/refs验证 → 完成记录随治理Task提交及推送 → 核对最终refs/工作区并停止。若推送失败，保留本地commit和用户改动、准确记录失败；不强推或reset，不称上传成功。

验收：远程私有/owner/name准确且无意外共享；本地/远程main HEAD相同；真实凭据/.env/cache/备份/私有学生资料未暂存；两个原输入的Git blob与原始SHA一致，生成schema/TS保持LF并通过--check；所有范围外文件/历史Task/日志/ADR不变；同步CHANGELOG/tasks，区分历史测试与本轮检查。

未来每Task：先读基线/已有暂存内容，验收和必需文档全部完成后才stage当前Task必要文件或hunks；不得用git add -A/.批量带走无关用户变更，不覆写/回滚/强推，不存token到remote/脚本。commit message带Task ID，普通push当前明确仓库/分支；最终报告给出commit/分支及上传结果。工作尚未验收不自动上传，失败任务不以commit代替完成。

## 实际结果

已创建私有仓库并设置本地main/origin，初始基线已提交并上传。随后repo view确认isPrivate=true、nameWithOwner准确及defaultBranchRef=main。Git初始log退出1因无commit，初repo view退出1因仓库不存在，是记录的初始状态；无创建/提交/推送失败。

### 实际命令与结果

均在`D:\Projects\study`执行，以下为本轮新检查，不引用T02历史测试。

| 实际命令 | 结果 |
| --- | --- |
| `gh auth status`；`gh api user --jq '{login: .login, id: .id}'` | 退出0，已登录chanbilly-lab；认证复用本机keyring，token不写仓库 |
| `gh repo create chanbilly-lab/study-admissions-agent --private --description '升学咨询智能体：Vue3 + FastAPI，M0演示与已验收的v2基础契约'` | 退出0，创建目标私有仓库 |
| `gh repo view chanbilly-lab/study-admissions-agent --json nameWithOwner,isPrivate,url,defaultBranchRef` | 退出0，owner/name/private/main均正确 |
| `git -c safe.directory=D:/Projects/study branch -m main` | 退出0，保留.git，将无历史master改名main |
| `git -c safe.directory=D:/Projects/study remote add origin https://github.com/chanbilly-lab/study-admissions-agent.git` | 退出0，无token remote；原先无remote，不替换用户配置 |
| `.\.venv\Scripts\python.exe -X utf8 .cache/p04_validate_20261001.py --prepare` | 退出0，空索引/候选/范围/忽略/文档/字节属性检查后生成101份显式清单 |
| `git -c safe.directory=D:/Projects/study -c core.quotepath=false add --pathspec-from-file=.cache/p04-git-20261001/reviewed-paths.nul --pathspec-file-nul` | 退出0，仅纳入已审查清单；原core.autocrlf产生普通换行warning，未关闭/修改全局配置 |
| `.\.venv\Scripts\python.exe -X utf8 .cache/p04_validate_20261001.py --stage` | 退出0，101份index清单正确；原输入和生成文件blob字节等于工作区 |
| `git -c safe.directory=D:/Projects/study commit -m 'P04: establish reviewed project baseline through T02'` | 退出0，首个现状基线`819e5cb3e1640249b6d0ddb8155f5f825ee567b8`，101文件；不造历史Task commits |
| `git -c safe.directory=D:/Projects/study -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin main` | 退出0，main→main、上游origin/main已建立；credential helper只当前命令，不改全局凭据设置 |
| `git -c safe.directory=D:/Projects/study -c credential.helper= -c 'credential.helper=!gh auth git-credential' ls-remote origin refs/heads/main` | 退出0，首次推送后远程SHA与本地819e5cb全值一致；完成记录推送后再次核对最终HEAD |
| `gh api 'repos/chanbilly-lab/study-admissions-agent/git/trees/main?recursive=1' --jq '{file_count: ([.tree[] \| select(.type == "blob")] \| length), truncated: .truncated}'` | 退出0，file_count101、truncated=false |
| `.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py` | 退出0，两份原始输入SHA未变 |
| `.\.venv\Scripts\python.exe -X utf8 scripts/verify_contract.py` | 退出0，M0 TS/OpenAPI语义一致 |
| `.\.venv\Scripts\python.exe -X utf8 scripts/generate_contracts.py --check` | 退出0，v2两个产物未漂移 |
| `.\.venv\Scripts\python.exe -X utf8 .cache/p04_validate_20261001.py --stage --final` | 最终退出0，完成字段、Task/日志/ADR及上传规则一致 |
| `git -c safe.directory=D:/Projects/study diff --cached --check -- AGENTS.md README.md docs/tasks.md docs/CHANGELOG.md docs/DECISIONS.md docs/acceptance/P04_git_repository.md` | 退出0，本轮完成记录暂存diff无空白错误 |

完成记录随后仅暂存AGENTS、README、tasks、CHANGELOG、DECISIONS和本验收6份文件，使用`git -c safe.directory=D:/Projects/study commit -m 'P04: record private repository and verified task upload policy'`及同一credential helper的普通`push origin main`。这些元数据不改已上传运行代码；最终提交SHA以Git、远程refs及本次完成报告为准，避免在commit内循环填写自己的SHA。

`.\.venv\Scripts\python.exe -X utf8 .cache/p04_validate_20261001.py --prepare`退出0：6份旧规则/文档改、2份新增、93文件哈希保护；101项目候选UTF-8且无高置信真实token/私钥形态；22个私有运行路径check-ignore通过，必要源码可纳入；旧Task/日志/ADR内容保留，6文档86本地链接及P04字段检查；两个原规格-text、生成文件LF属性正确。核对空索引/无已有tracked文件后，生成显式NUL路径清单，不自动纳入未知内容。`.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py`与`... scripts/generate_contracts.py --check`退出0。

候选只含固定DEMO凭据与合成URL拒绝用例；历史验收含本机路径，按用户确认保持仓库私有，未改写旧记录。.cache内配置/注册/数据库/磁盘备份均被排除，未上传其内容。没有添加协作者、发布服务或改变现有Git身份/全局设置。

原项目99文件中6份规则/文档改、2份新增，共101份已核对候选；93份范围外原文件哈希不变，旧Task卡/P00记录/CHANGELOG和ADR-001–012保留。修改文件为AGENTS、README、.gitignore、tasks、CHANGELOG、DECISIONS；新增.gitattributes及本验收。没有改应用/配置/依赖/迁移/DEMO或研究数据，未新增协作者或公开访问。初次push后Git状态干净，完成记录再次提交推送后核对最终状态。

应用Unit/Integration/Lint/Type Check/Build、PostgreSQL/浏览器/监听服务/部署本轮未执行：仓库治理不改运行代码，不引用T02历史通过为本次结果。clone/重新安装及CI未执行：本Task验证暂存blob、属性和真实远程上传，不宣称新机器完整运行或自动测试CI已建立。

无P04阻断问题。Git上传与业务部署/真实招生事实发布分别授权；后续按AGENTS持续规则，每Task验收完成及文档同步后提交/推送审查差异，保留用户既有改动和索引。Task/CHANGELOG状态已同步，本轮停止；T03仅推荐，不开始。
