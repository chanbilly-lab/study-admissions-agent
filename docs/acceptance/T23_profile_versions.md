# T23 画像根与纵向版本验收

2026-10-03源码及合成离线/隔离实库验收完成。实施前范围、数据契约及用例见[profiles](../profiles.md)。

Git基线PRIVATE T22 `1054b8129ec9e94700a6f5158ea9f9b3f1f4d9a7`，457 tracked/索引空/工作区干净；新分支`codex/t23-profile-versions`。已读取必读治理、原始两份规格、相关API/数据库/隐私/授权/幂等与M0；原文和其他任务历史冻结。只T23，不实施T24页面或资格引擎。

复用自有PG16.15/127.0.0.1:55438，检查确属本任务现有隔离cluster；显式检查不存在后创建`study_t23_20261003`，保留旧库。URL秘密保留ignored `.cache/t23-postgres/environment.json`，helper临时设置T23及旧专项env并退出恢复，未输出/提交凭据；应用默认不自动迁移/seed。

冻结选择：新独立表名避开M0；首建仅T49 profile.create、追加strictCAS且不改旧闭集/头；历史禁UPDATE、无本TaskDELETE入口但未来可信删除可清私有记录；本人完整新payload+确认才绑定新core proof。assessment同runtime闭集15键局部schema投影，不放开生成器任意开放字典。

## 检查记录

已实际执行相关旧服务回归：`.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/unit/idempotency','tests/integration/idempotency','tests/security/privacy','tests/integration/authorization','tests/security/authorization','-q','--tb=short')`：401 passed，1条既有Starlette warning，162.94s，exit0，无skip；这些服务保持原字节，新模块末端行为仍须T23专项验证。

新生成专项首轮24 passed/3 failed，继承identity数字Literal被新测试误交旧M0 parser；不改旧验收器，新测试限定真实profiles组件及递归依赖，完整产物由TS编译。第二轮26 passed/1 failed，因新测试假定private factory静态schema404，而冻结契约仅限制业务/noIO；明确保留继承schema200、parent根schema404，修正新断言。生成器初改的旧T22生成专项15 passed、5.56s，是相关中间结果；不计为T23新专项。初TS Type Check exit0、5.43s；最终新Meta/产物将另验。


## 最终实际结果

| 实际命令 | 结果 |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest tests/unit/profiles -q --tb=short` | 最终48 passed、1既有Starlette warning、2.26s、exit0，无skip |
| `.cache/t23-postgres/run-tests.ps1 -PytestArguments @('tests/integration/profiles','-q','--tb=short')` | 最终51 passed、1既有warning、72.11s、exit0，无skip/deselect |
| `.venv/Scripts/python.exe -B -m pytest tests/contracts/test_t23_profiles_generation.py -q` | 最终28 passed、1既有warning、6.27s、exit0 |
| `.venv/Scripts/python.exe -B -m pytest tests/contracts tests/security/test_mode_isolation.py -q --tb=short` | 411 passed、1既有warning、30.34s、exit0；包含28新专项，不重复计数 |
| `.cache/run-web-checks.ps1 -TaskId T23` | 24文件/279 tests、13.77s；vue-tsc、demo及auth vite Build全部exit0 |
| `.venv/Scripts/python.exe -X utf8 scripts/generate_contracts.py --profile <foundation/identity/public_catalog/admin/admin_review/profiles> --check` | 六条实际独立命令均exit0、产物一致；旧五profile原字节未变、新两产物LF |
| `.venv/Scripts/python.exe -X utf8 scripts/verify_originals.py` | exit0，两份原始输入未变 |
| `.venv/Scripts/python.exe -X utf8 scripts/verify_contract.py` | exit0，旧M0 TS与OpenAPI required/null/literals/types/arrays/records一致 |

PG实际覆盖两用户及管理员/metadata grant不读payload、缺确认/未成年/core撤回与新确认绑定、旧receipt仍原版、满分/单位/实得预测、SQL分页cursor、Origin/CSRF/no-store/固定安全错误、immutable UPDATE/FK/root归属及真双SessionCAS、samekey并发commit/rollback、真实deferredCOMMIT与审计失败整笔回滚、重复迁移与降级。六次实际SQL末端期限等待使用pg_blocking_pids确认阻塞；包含T49两verifier之后第三次outer_final的1秒收据TTL，其他证明仍有效时新registry/root/version/receipt/success-audit全部回滚。另有必要审计SQL等待，成年声明到期不返回内容。

首PG集成命令exit1、4 collection ImportErrors、1.07s，是新folder缺__init__，没有PG case执行；加本Task包标记后第二轮16 failed/32 passed、67.06s，原因全部为新safe(response)错误假设error有meta，旧ErrorEnvelope仅error.request_id。修正新辅助，旧wire不改；加入并发/receipt等待后最终51全过，不将中间32计为最终。root最初误写 `tests/unit/test_mode_isolation.py` 的整套契约命令exit1、no tests ran，纠正为现有security路径后取得表中411；两个辅助只读文件路径不存在、一次apply_patch行定位失败均未改文件，也不当测试通过。

无新依赖/旧服务/旧迁移/M0/前端UI修改。所有正例明确合成，默认factory无DB/IdP/seed且私有业务503，已验context创建能力受T49开关限制；静态private schema200/parent404。具体版本响应meta实际UUID及模式，列表/context空；bounded Page DTO为明确局部协议。

## 未执行与剩余门槛

Lint与Python静态类型无配置入口，未执行；前端Type Check实际执行。未另做浏览器交互测试，T23无UI改动，实际HTTP/PG已覆盖；T24将验页面。未执行全项目所有PG测试、真实Keycloak/管理员MFA恢复、正式主体/告知/法律核验、真实用户或全国事实、PostgreSQL生产GRANT/RLS、物理删除/备份恢复/部署。D06期限访问控制已实施，物理清理与传播留T40/T44；真实TTL/真实处理仍关闭。候选路径未实现规则适配，不能宣称全国及英国2027/学校专业已覆盖。

## 修改清单与保护

35路径（11旧/24新），原457tracked中446范围外保持原字节；66其他主Task卡、历史CHANGELOG及ADR前缀保留。最终 `.venv/Scripts/python.exe -X utf8 .cache/check_task.py T23` exit0：35路径/11旧24新、446保护tracked、66其他Task不变、337本地链接/19Python内存编译、历史/JSON/秘密形态一致；`git -c safe.directory=D:/Projects/study diff --check` exit0。首治理检查将3处test:test/127.0.0.1:1/unreachable的零IO伪连接误当秘密，核对只用于无连接mapper测试后在ignored检查器精确限制该路径与完整literal，重跑通过；没有放宽实际凭据规则或改测试。旧autocrlf换行warning保留，生成profile两文件实际LF。确切路径如下：

- `.gitattributes`
- `AGENTS.md`
- `README.md`
- `apps/web/tests/profiles-contract-types.ts`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T23_profile_versions.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/profiles.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `packages/contracts/v2/profiles/generated.ts`
- `packages/contracts/v2/profiles/openapi.json`
- `scripts/generate_contracts.py`
- `services/api/app/api/profiles.py`
- `services/api/app/profiles/__init__.py`
- `services/api/app/profiles/models.py`
- `services/api/app/profiles/router.py`
- `services/api/app/profiles/schemas.py`
- `services/api/app/profiles/service.py`
- `services/api/app/profiles/store.py`
- `services/api/profiles_alembic.ini`
- `services/api/profiles_migrations/env.py`
- `services/api/profiles_migrations/versions/0001_profiles_t23.py`
- `tests/contracts/test_t23_profiles_generation.py`
- `tests/integration/profiles/__init__.py`
- `tests/integration/profiles/conftest.py`
- `tests/integration/profiles/test_t23_http.py`
- `tests/integration/profiles/test_t23_migrations.py`
- `tests/integration/profiles/test_t23_service.py`
- `tests/integration/profiles/test_t23_waits.py`
- `tests/unit/profiles/test_t23_contracts.py`
- `tests/unit/profiles/test_t23_guards.py`
