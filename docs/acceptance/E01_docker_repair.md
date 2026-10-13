# E01 · Docker Desktop 启动修复

> Privacy note (2026-10-14): private account/resource identifiers and personal home paths have been redacted for the public-release candidate. Historical outcomes are unchanged; placeholders are not live targets.

日期：2026-10-01，Asia/Hong_Kong。状态：已完成。用户新请求为修复 Docker；T01/T50A 历史验收不改写，不启动业务开发。

## 修复范围与验收

只修复本机 Docker Linux 引擎。先查找原磁盘及备份，保全配置/注册与仍存在的磁盘；涉及新建空数据环境时先明确说明并取得同意。不能注销 Ubuntu、清理未知文件、重置项目或自动提交。

Docker Server、`docker info`、实际隔离容器烟测、项目范围保护及任务/日志一致均已验证。当前Desktop4.93.0 / Client与Server29.8.1 / Linux引擎运行，新环境不是旧数据恢复。

## 修复前诊断

- Docker Desktop 4.22.0.117440，CLI 24.0.5；WSL 3.0.1.0 / kernel 6.18.40.1-1；Windows 11 Home Chinese 10.0.26200.9457；当前进程非管理员。
- 初始 `docker version --format '{{json .}}'` 退出1，Server 为 null，引擎管道不存在。初始Desktop UI 在运行，但 backend 已退出；之后已停止UI。`vmcompute` 与 `WslService` 运行，`com.docker.service` 停止/手动不能单独作为 Linux WSL 引擎故障依据。
- `wsl --list --verbose` 显示 Ubuntu、docker-desktop-data、docker-desktop 均为停止/WSL2。
- 对 Ubuntu 与 docker-desktop-data 执行 `/bin/true` 均退出4294967295，明确 `Wsl/Service/CreateInstance/MountDisk/ERROR_FILE_NOT_FOUND`，指向各自登记目录中的 `ext4.vhdx`。
- Docker 登记数据目录 `<USER_HOME>\AppData\Local\Docker\wsl\data` 与 Ubuntu 的 `LocalState` 目录存在但为空；Docker 仅现存 `wsl\distro\ext4.vhdx`（126,877,696 字节），这是引擎盘，不能称为镜像/容器/数据卷的完整备份。
- backend 日志本地10:25:01先报数据盘缺失，之后才出现 keepalive 与 `isocache` 网络名不存在；“网络名”是后续症状，不能简单作为 DNS 故障处理。
- 用户回复“没有移动过，或不确定”。回收站当前用户目录未找到疑似 VHD/Docker/WSL 条目；用户目录与 ProgramData 文件名搜索只命中引擎盘，搜索有拒绝访问目录（退出1），不表示全盘不存在备份。D盘 `电脑管家迁移文件/ProgramData/WpSystem/Temp` 有限扫描退出0：9,019目录、36,780文件，VHD/VHDX/TAR命中0、访问错误0；跳过指定游戏目录，不跟随重解析点，不是全盘搜索。

## 保全与限制

修改前保存85个项目文件哈希及 tasks/CHANGELOG 原文、Docker settings 副本到 `.cache/e01-docker-20261001-105443/`。`reg export HKCU\Software\Microsoft\Windows\CurrentVersion\Lxss ...` 退出0；现存126,877,696字节引擎盘复制前后SHA256一致（3BE8AE73463BCCCD48AF91D670438CBE3B90768C4082E5EA617F68BC918FF0C3），之后确认Desktop进程已退出。最初进程路径过滤未匹配到frontend实际位置，随后使用实际路径停止四个UI进程；backend/WSL此前已停止，磁盘校验保持一致。配置/注册/引擎盘副本不含缺失磁盘中的旧数据。

用户已明确回复“允许升级并重建空 Docker 环境”。官方固定版本4.93.0/build240920（627,791,792字节）下载最终退出0，SHA256与官方校验文件一致：`c139124c9cf71477dc565c3c0ea5a18f90b93d68ebe9aaa848a065960416c0bc`；Authenticode为Valid，签名主体Docker Inc，FileVersion4.93.0.240920。[发布记录](https://docs.docker.com/desktop/release-notes/#4930)、[固定安装包](https://desktop.docker.com/win/main/amd64/240920/Docker%20Desktop%20Installer.exe)、[官方校验](https://desktop.docker.com/win/main/amd64/240920/checksums.txt)。

随后再次核对docker-desktop-data唯一注册、BasePath为预期Docker目录且目录仍空，`wsl.exe --unregister docker-desktop-data` 退出0（操作成功完成）；只注销该缺失数据盘的登记，没有注销Ubuntu或docker-desktop。注册表快照保留全部三个发行版的原值。

Docker旧settings仅将`enableIntegrationWithDefaultWslDistro`从true改为false，避免尝试集成磁盘缺失的Ubuntu；写前与备份字节一致、显式集成列表为空，其他配置值保留。Ubuntu文件/注册不更改。

11:02:35通过`Start-Process -FilePath 'D:\Projects\study\.cache\e01-docker-20261001-105443\Docker Desktop Installer-4.93.0-native.exe' -ArgumentList @('install','--backend=wsl-2','--quiet') -Verb RunAs -WindowStyle Hidden -PassThru`启动升级（PID37144）；11:03:10安装退出0，安装日志标明Installation succeeded，Program Files中FileVersion4.93.0.240920。保留原all-users安装模式，没有使用`--user`迁移，没有自动接受协议参数。11:03:33通过`Start-Process -FilePath 'C:\Program Files\Docker\Docker\Docker Desktop.exe' -WindowStyle Hidden -PassThru`启动Desktop。项目技术栈及部署方案未变，不新增ADR。

下载准备：首个Anaconda路径curl下载未完成，停止本次下载进程后命令退出1（Installer download failed）；改用Windows系统curl，设置连接/总时限和低速超时，最终下载及校验成功；不把下载命令当离线应用测试。

官方说明：[Docker 备份与恢复](https://docs.docker.com/desktop/settings-and-maintenance/backup-and-restore/)、[WSL 后端](https://docs.docker.com/desktop/features/wsl/)、[Docker 故障处理](https://docs.docker.com/desktop/troubleshoot-and-support/troubleshoot/)、[WSL 注销风险](https://learn.microsoft.com/en-us/windows/wsl/basic-commands#unregister-or-uninstall-a-linux-distribution)。旧版本兼容性可能是另一问题，尚不能代替磁盘缺失的直接证据。

## 实际检查

以下`docker`均为实际执行的`C:\Program Files\Docker\Docker\resources\bin\docker.exe`；命令及标准输出/退出码保存在本任务忽略缓存。表内结果是本次实际检查。

| 命令 / 检查 | 结果 |
| --- | --- |
| `wsl.exe --unregister docker-desktop-data`（再次核对唯一登记、预期目录、无文件、已保全） | 退出0，只移除失效Docker data登记 |
| 固定包系统curl下载、`Get-FileHash -Algorithm SHA256`、`Get-AuthenticodeSignature` | 退出0，627,791,792字节、官方哈希一致、Valid/Docker Inc |
| 上述安装命令，原安装模式 | 退出0，4.93.0.240920，日志Installation succeeded |
| `docker --version` | 退出0，29.8.1 |
| `docker version --format '{{json .}}'` | 退出0，Client29.8.1 / Server29.8.1 / Linux |
| `docker info --format '{{json .}}'` | 退出0，overlay2，初始容器/镜像0，无warnings |
| `docker context show` | 退出0，desktop-linux（Desktop启动后当前上下文） |
| `docker run --rm --name study-e01-smoke-20261001 --network none --label study.task=E01 hello-world:latest` | 退出0，实际Hello from Docker；官方library/hello-world镜像下载成功，容器自动删除 |
| `docker ps -a --format '{{json .}}'` / `docker volume ls --format '{{json .}}'` | 均退出0、为空，未遗留测试容器/卷；hello-world镜像保留 |
| `docker compose version --short` | 退出0，5.5.1 |
| `wsl.exe --list --verbose` | 退出0；docker-desktop运行，Ubuntu仍为默认/停止/WSL2；新实现不再登记docker-desktop-data |
| Ubuntu注册原值及Docker集成配置核对 | 退出0，Ubuntu整项注册与前快照一致，默认集成false；新settings-store的属性名为PascalCase |
| `.\.venv\Scripts\python.exe -X utf8 scripts/verify_originals.py` | 退出0，两份原输入不变 |
| `.\.venv\Scripts\python.exe -X utf8 .cache/e01-docker-20261001-105443/verify_scope.py` | 退出0，2旧文档修改+1验收新增、83范围外文件与全部历史内容不变、18本地链接、Task/日志/报告状态字段一致 |

镜像摘要为`sha256:5e23090353324d887c48ad5e5c56d294eab81588df9605b07d1afe895f9cc8f8`。镜像拉取与安装下载明确为联网操作，测试容器自身网络关闭；未调用商业API或处理学生资料。

新持久磁盘为`<USER_HOME>\AppData\Local\Docker\wsl\disk\docker_data.vhdx`，引擎为`wsl\main\ext4.vhdx`；此处是新环境，不是找到旧data磁盘。`com.docker.service`仍停止/手动，但Linux引擎和容器已实际运行，不将该服务状态单独标故障。

## 失败、修正与未执行项

- 初始故障命令与缺盘错误见诊断部分，修复前Docker不可用没有掩盖。
- 首次下载未完成，停止本次Anaconda curl进程后该命令退出1；系统curl重试最终退出0，完整哈希及签名验证成功。首次未完成的部分下载文件（287,698,944字节）保留在缓存，没有拿来安装。
- 后验收辅助代码首次因raw字符串末尾反斜线导致SyntaxError；外层后续PowerShell检查继续运行并退出0，该返回不能算Python校验通过。修正语法后辅助检查退出1：把新settings-store的`EnableIntegrationWithDefaultWslDistro`按小写首字母读取，误判为重新启用。实际字段为false、Ubuntu停止；按实际属性归一大小写后最终辅助校验退出0。两次均为检查代码问题，无再次安装/重置，未把失败隐藏为通过。
- 应用Unit/Integration/Lint/Type Check/Build、项目Compose数据库启动/迁移/PG基线、公众部署、主机重启后的自动启动及旧数据恢复均未执行：本任务不改应用，只验收本地Docker启动与容器执行；不能由本次烟测声称这些检查已通过。

## 变更与剩余问题

项目仅修改`docs/tasks.md`、`docs/CHANGELOG.md`，新增本文件；83范围外文件哈希保持，历史T01/T50A记录保留，没有提交。本地升级Docker并重建已授权的空数据环境、关闭失效Ubuntu集成；注册/配置/日志与旧引擎盘备份保存在忽略缓存，原数据盘不存在，备份不含旧容器/卷。

旧Docker镜像/容器/数据卷未恢复。Ubuntu缺盘仍未修复，注册与目录保留。Docker保持运行，E01结束，不自动进入业务开发或Ubuntu重建。
