# T08 年龄、告知与准入验收

日期：2026-10-03，Asia/Hong_Kong。当前状态：已完成源码/合成与隔离实库验收；真实处理与公众发布未开放。

## 开始前核对

已阅读 AGENTS、README、requirements、architecture、tasks、CHANGELOG、DECISIONS、API/数据库、两原始输入与对应规格，以及认证、对象授权和前端会话代码。开始 Git 干净、无暂存，HEAD `6a8d75d5b43db31d2b1bde1425d6b6a01095fac8`；新分支 `codex/t08-admission-privacy`。基线181个跟踪路径原字节哈希和索引保存在忽略的 `.cache/t08-baseline-20261003`。原始文件与旧迁移/验收不改。

## 数据契约、范围和人工产品复核

实施前契约、修改范围及矩阵已列入 [privacy](../privacy.md)。用户选择18+本人确认、14–17独立监护但首版不提供核验，未成年私有关闭；未知/under14公开。D06产品上限及具体开发告知草案由用户在本会话实际确认，正式处理主体/责任、渠道、真实告知和各地区法律复核仍为上线门槛。人工产品复核不标作专业法律审核。

本Task只实现准入基础，无画像/附件/计划业务、共享、后台清理、生产部署或真实资料收集。新迁移增量；启动不建表或导夹具；默认无密钥可读基础和公开政策就绪提示。合成离线验收与正式处理配置分开。

## 实际检查记录

准备：新 PostgreSQL16.15 仅loopback55438、专用 `privacy_t08_test` 和三个认证回归测试空库，随机schema；仅复用程序，未复用旧cluster/数据。凭据和数据库均忽略，不上传。首版忽略helper出现重复PowerShell哈希键解析失败，修复后新init/start成功；不是应用通过结果。

独立初次输入安全专项：`\.venv\Scripts\python.exe -m pytest tests/security/privacy/test_t08_adversarial.py -q --tb=short`（实际命令前缀为 `.\.venv`）结果59 passed、4 failed；数字1/1.0被两种Literal[True]确认输入接受，需局部严格布尔校验后复验，不能把本次算通过。前端新增会话失效初检63 passed（仍待最终新功能回归）。

输入确认局部修复后同命令实际63 passed；不能由此推定PG/全部安全矩阵通过。首次identity生成失败（旧生成器不支持JSON body/DELETE path），相关契约27 passed / 2 failed；限定实现当前两个必需JSON输入及UUID路径后，扩展拒绝非JSON/远程ref/重复path的契约矩阵，75 passed。

后端第一轮PG service/persistence：22 passed / 11 failed（2项新告知/政策重确认缺陷，9项新测试相对导入错误）；随后修复并复验，初轮未记作通过。

最终实际命令与结果如下（不是历史结果重用）：

| 检查 | 实际命令 | 结果 |
| --- | --- | --- |
| 完整Python回归 | `.cache/t08-postgres/run-tests.ps1 -PytestArguments @('tests','-q','--tb=short')` | 首轮1272 passed/2 failed旧精确路径断言；修正后同命令1274 passed、1既有warning，226.45s/exit0 |
| 实库数量核对 | `.\.venv\Scripts\python.exe -m pytest --collect-only -q -m postgres` | 277/1274；其余997，非执行代替 |
| 独立T08安全 | helper指定`test_t08_adversarial.py` | 最终102 passed（63纯输入/39PG及HTTP），exit0 |
| 前端 | `.\scripts\web.ps1 -Action test` | 最终116 passed/12files/exit0；中途112历史阶段另存 |
| TS类型 | `.\scripts\web.ps1 -Action typecheck` | 最终exit0，vue-tsc |
| Build | `.\scripts\web.ps1 -Action build`；进程`VITE_APP_MODE=auth`后同命令 | M0/auth均exit0；样式/状态最后修复后auth再次exit0 |
| 浏览器 | bundled `node.exe scripts/privacy_t08_browser_smoke.mjs` | 最终9 checks，Edge154.0.4258.48，无页面错误/外部请求，exit0 |
| 契约 | Python pytest指定identity/privacy/v2_generation三模块 | 最终75 passed/exit0 |
| 生成漂移 | `python scripts/generate_contracts.py --check`、`--profile identity --check` | 两profile match/exit0 |
| M0契约/原文 | `python scripts/verify_contract.py`、`python scripts/verify_originals.py` | 均exit0，M0一致，两原文原字节未改 |
| 范围保护 | `python .cache/t08-baseline-20261003/verify_protection.py` | 35冻结路径/其他66主Task卡保留；config/identity README是本Task相关运行文档更新，JSON配置未改 |
| 语法/空白 | Python内存compile相关源码、新browser `node --check`、`git diff --check` | 退出0；只有既有LF/CRLF提示 |

浏览器有三次harness未完成：403 body等待被前端未消费，去除此等待并增加有界检查后复验；初次功能9通过但radio受全局input样式挤成竖排，组件scoped修复及16px尺寸断言后重新9通过。最终`.cache/t08-ui/2599837d-8207-4ba4-9aba-62dacbf7dff4`报告/桌面/390px图片已由root实际查看，正常排列；截图/证书/SQLite不上传。旧读取竞态由Vitest覆盖，不写成浏览器已测竞态。

无 Lint/Python静态类型入口时分别记录未执行；真实Keycloak、MFA/恢复、正式运营主体/法律复核和部署未执行。

## 变更文件

51路径（25既有修改/26新增），逐路径如下；仅这些审查内容上传：

- `AGENTS.md`
- `README.md`
- `config/identity/README.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/identity.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `docs/privacy.md`
- `docs/acceptance/T08_admission_privacy.md`
- `apps/web/src/features/auth/AuthView.vue`
- `apps/web/src/features/auth/useSession.ts`
- `apps/web/src/features/privacy/PrivacyPanel.vue`
- `apps/web/src/features/privacy/client.ts`
- `apps/web/src/features/privacy/useAdmission.ts`
- `apps/web/tests/PrivacyPanel.test.ts`
- `apps/web/tests/privacy-admission.test.ts`
- `apps/web/tests/privacy-client.test.ts`
- `apps/web/tests/privacy-session.test.ts`
- `apps/web/tests/privacyFixtures.ts`
- `packages/contracts/v2/identity/generated.ts`
- `packages/contracts/v2/identity/openapi.json`
- `scripts/generate_contracts.py`
- `scripts/privacy_t08_browser_smoke.mjs`
- `services/api/app/api/identity.py`
- `services/api/app/auth/store.py`
- `services/api/auth_migrations/env.py`
- `services/api/auth_migrations/versions/0004_privacy_t08.py`
- `services/api/app/privacy/__init__.py`
- `services/api/app/privacy/config.py`
- `services/api/app/privacy/errors.py`
- `services/api/app/privacy/models.py`
- `services/api/app/privacy/policy.py`
- `services/api/app/privacy/router.py`
- `services/api/app/privacy/schemas.py`
- `services/api/app/privacy/service.py`
- `tests/contracts/test_identity_contract.py`
- `tests/contracts/test_privacy_contract.py`
- `tests/integration/auth/test_persistence.py`
- `tests/integration/authorization/test_http_dependencies.py`
- `tests/security/auth/test_postgresql.py`
- `tests/security/authorization/test_http_postgresql.py`
- `tests/security/authorization/test_postgresql.py`
- `tests/security/privacy/conftest.py`
- `tests/security/privacy/test_persistence.py`
- `tests/security/privacy/test_service.py`
- `tests/security/privacy/test_t08_adversarial.py`
- `tests/e2e/privacy_t08_fixture.py`

## 已知问题与后续

正式主体、告知与法律/责任复核未完成，真实处理默认关闭。年龄本人声明不等于独立核验；监护核验首版不提供。D06清理、删除/恢复作业尚待后续Task，不把产品上限写成已执行删除。

T08实现验收已完成，CHANGELOG/tasks及受影响文档同步；随后按持续授权正常提交推送，再进入用户已授权且依赖满足的T09；不部署。T15/T19前需要独立T49，收据期限待用户回复。
