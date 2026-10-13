# T25 类型化规则验收

2026-10-03源码及合成离线验收完成。以下保留实施期间分轮结果，末尾是最终结论。代码前[冻结契约](../rules.md)。起点PRIVATE T24 `e3c74f956280cd0bc381581ac0da1bcc57be589b`，497tracked/工作区索引空，当前`codex/t25-typed-rule-expressions`，只有7个治理旧路径允许变化，490其他tracked保护。

只纯规则AST/解释器与离线测试，无HTTP/数据库/前端/依赖/旧M0改变；T17/T23已完成，T26适配/T27后补/T28四态未开始。纯解释器不证明已审事实/适用规则或画像本人授权；所有真实启用门槛保持。

## 实施期间实际检查

`.venv/Scripts/python.exe -B -m pytest tests/unit/facts tests/unit/profiles tests/backend/test_rules.py tests/contracts tests/security/test_mode_isolation.py -q --tb=short`：539 passed、1既有Starlettewarning、38.12s、exit0，无skip。此为当前T25相关旧行为回归，不代替尚在编写的新规则专项。

`.cache/run-web-checks.ps1 -TaskId T25` 实际顺序调用 `scripts/web.ps1 -Action test`（348 passed/28 files/15.30s）、`scripts/web.ps1 -Action typecheck`（exit0）、临时`VITE_APP_MODE=demo/auth pnpm --dir apps/web run build --outDir ../../.cache/t25-<mode>-frontend-validation`（均含vue-tsc，exit0/73modules/Vite1.22s与1.50s）；Node PATH及mode恢复。无前端源码变更，无新前端case，不把历史T24结果当本轮。

`.venv/Scripts/python.exe -B scripts/verify_originals.py` 与 `scripts/verify_contract.py` 两项exit0，原两规格和M0契约保持。Lint/Python静态类型无配置入口未执行；T25无持久模块/入口或UI变化，PG/实际browser不作为本Task新增检查，真实事实/身份/学生/法律/生产权限/清理恢复/部署未执行。

六个独立实际命令 `.venv/Scripts/python.exe -X utf8 -B scripts/generate_contracts.py --profile <foundation/identity/public_catalog/admin/admin_review/profiles> --check` 全部exit0，旧生成产物保持。

新独立规则专项首轮 `pytest tests/unit/rules/test_t25_semantics.py tests/unit/rules/test_t25_safety.py -q --tb=short` 实际145 passed/3 failed/2.08s/exit1：一项新纯模块顶层T23导入触及被禁止的app.settings应用依赖，已改为仅显式画像投影时加载既有严格类型；两项新测试前提不符冻结语义（将text绑定integer字段、将opaque calendar域当成IANA核验），修正前提，不放宽字段类型或日期精度。

实现同时固定FieldRef实际类型/高考与IELTS单位，避免错误字段类型和错误literal“互相配合”返回true；StringSet在Pydantic前检查原生str，raw结构预JSON序列化共享预算拒过大字节/数字与自定义对象；仅known可有值，predicted永不代实得。第二轮独立两文件156 passed/1.39s/exit0；尚未包括后续实现者专项及最终源码冻结，不提前计最终完成。

## 最终验收

独立评审者实际 `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/unit/rules/test_t25_semantics.py tests/unit/rules/test_t25_safety.py -q --tb=short`：156 passed/1.36s/exit0，无warning/skip。实现者两文件首次21 passed/0.72s，中间不是最终；最后只增加datetime内嵌自定义tzinfo的必要guard，在任何offset/format前限制exact timezone/ZoneInfo，证明恶意回调0次，正常明确时区保留。最终owned同命令指定`test_t25_expression.py test_t25_projection.py`：22 passed/0.73s/exit0。

root加载所有最终源码实际 `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/unit/rules -q --tb=short`：**178 passed、1.55s、exit0，无warning/skip**，包含独立156及实现者22，不能把重复运行相加。这是最终完整专项结果，覆盖首轮问题与最后时区guard；无新增源码变化。

实现与冻结契约一致：整树预验证/256nodes/16depth/32children与members/64KiB预算，raw结构先共享字节预算再序列化；固定FieldRef kind/单位，精确64字符数字、实得与预测分离；全合法分支trace与Kleene，未知不因not变true。Context最多40唯一fields；dates显式域/precision，valid_at半开。parse/evaluate纯导入不加载旧应用/数据库/模型/环境时钟；只有明确`context_from_profile`调用按需加载既有T23严格schema（可能导入既有应用类型定义，但不读取配置实例/数据库/模型），全画像重验，不创建表或账号。Trace不含实际私人值；纯模块不负责owner/consent/审核证据，后续HTTP必须由已验收服务重新核验。

| 最终实际命令/检查 | 结果 |
| --- | --- |
| `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/unit/rules -q --tb=short` | 178 passed/1.55s，无warning/skip |
| `.venv/Scripts/python.exe -B -m pytest tests/unit/facts tests/unit/profiles tests/backend/test_rules.py tests/contracts tests/security/test_mode_isolation.py -q --tb=short` | 539 passed/38.12s/1既有warning，无skip；旧行为最终原字节保护 |
| `.cache/run-web-checks.ps1 -TaskId T25`，实际内部命令见前文 | 348 passed/15.30s；vue-tsc、demo/auth含Type Check两Build exit0（Vite1.22s/1.50s）；前端原字节保持 |
| `.venv/Scripts/python.exe -X utf8 -B scripts/generate_contracts.py --profile <六profile> --check`，六个独立调用 | 六项exit0，生成未改 |
| `.venv/Scripts/python.exe -B scripts/verify_originals.py` / `scripts/verify_contract.py` | 两项exit0，原两规格/旧M0契约保持 |
| `.venv/Scripts/python.exe -X utf8 -B .cache/check_task.py T25` | 保护490tracked、66其他Task卡/历史日志ADR、16paths/本地链接/7Python内存编译、无密钥或产物；exit0见收尾实际输出 |

首145passed/3failed/2.08s如实保留，后续156/1.39s与156/1.36s为加载时的中间结果，不冒称最后时区修补已覆盖。Lint/Python静态Type Check无配置入口，**未执行**；本Task无持久/HTTP/UI行为变化，不执行PG全回归或重复实际browser，相关M0/类型/契约已检。真实身份/学生/事实领域审核/法律/生产权限/物理清理备份恢复/部署**未执行**。不宣称全部检查通过或全国已覆盖。

## 修改文件与结论

16路径（7旧/9新）、490其他tracked保持；无API/数据库/迁移/生成/依赖/前端变化，API/数据库文档无需修改。CHANGELOG/tasks同步、T25已完成；普通PRIVATE保存/远程SHA核对后才下一T26，完成T40后停止。

- `AGENTS.md`
- `README.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T25_typed_rules.md`
- `docs/architecture.md`
- `docs/requirements.md`
- `docs/rules.md`
- `docs/tasks.md`
- `services/api/app/rules/__init__.py`
- `services/api/app/rules/evaluator.py`
- `services/api/app/rules/expression.py`
- `tests/unit/rules/test_t25_expression.py`
- `tests/unit/rules/test_t25_projection.py`
- `tests/unit/rules/test_t25_safety.py`
- `tests/unit/rules/test_t25_semantics.py`
