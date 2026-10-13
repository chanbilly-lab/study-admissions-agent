# T27 后补与期限验收

2026-10-03源码及合成离线验收完成，以下区分各轮实际检查和未执行项目。实施前[冻结契约](../deferrals.md)/ADR040；PRIVATE T26 a58a99306568f91c9aa0f8ac428e7d39a48024be、517tracked/空索引工作区。当前只纯政策/期限，不直接四态或真实审批。

实际命令、分轮失败及最终结果实施后记录。Lint/Python静态类型无入口，PG/browser无层变化及真实学生/政策审核/法律/生产权限/清理恢复/部署分别未执行；不宣称全部通过。

## 已执行的既有层检查

实现复核澄清requirements_version沿T26为必需非空Hash，只有ruleset_version可空；这是契约文字精确化，不放宽输入。实现者实际 `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/unit/deferrals/test_t27_input.py tests/unit/deferrals/test_t27_deadlines.py -q --tb=short` 首24 passed/1 failed：跨日夹具同时落主申请截止当天，主unknown优先于补expired；只将新夹具独立主截止置Oct20隔离该边界，随后25 passed/0.46s/exit0。首轮耗时未收到记录，不补造。

六次 `.venv/Scripts/python.exe -X utf8 -B scripts/generate_contracts.py --profile foundation|identity|public_catalog|admin|admin_review|profiles --check` 独立调用均exit0；同flags `scripts/verify_originals.py`两原规格UNCHANGED、`scripts/verify_contract.py`旧M0 PASS，各exit0。新专项尚未执行。

`.venv/Scripts/python.exe -X utf8 -B -m pytest tests/unit/dates tests/unit/evidence tests/unit/rules tests/unit/adapters tests/unit/catalog tests/unit/profiles tests/contracts tests/security/test_mode_isolation.py -q --tb=short`：1006 passed/45.91s/exit0，1既有Starlette弃用warning、无skip；最终范围保护仍须证明被测试的旧层原字节保持。

`.cache/run-web-checks.ps1 -TaskId T27`实际内部使用暂时Node24 PATH，执行`scripts/web.ps1 -Action test`、`-Action typecheck`及pnpm11.19 `--dir apps/web run build --outDir ../../.cache/t27-demo-frontend-validation`和auth对应目录，分别设置VITE_APP_MODE并恢复：348 passed/28files/15.79s，vue-tsc及两Build exit0、Vite1.21s/1.45s、73modules。缓存产物不提交；无前端源码变化。

## 最终专项与结论

独立评审者实际同Python flags的`pytest tests/unit/deferrals/test_t27_matrix.py tests/unit/deferrals/test_t27_safety.py -q --tb=short`：223 passed/7.19s/exit0、无warning/skip；这223加实现者25是248唯一集，root复跑不重复累计。独立测试先确认合法baseline允许再单独施加攻击。最后只读跨审无新增阻断，真实政策证明及必要项仍由后续受信服务负责。

root最终实际 `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/unit/deferrals -q --tb=short`：**248 passed/7.27s/exit0**，无warning/skip；实现者与独立两文件结果另列，不累加重复测试数。

纯事项许可完整绑定target/scope/year/stage/release/ruleset/政策/事项与证据，所有当前组重验/失效与冲突保守未知，回调后快照不允许改写。申请与补交独立；enrollment的申请不适用必须政策明确声明。日期精度、锁定来源日历、候选UTC和审核证明分开；日期当天/精确截止等于未知，不造23:59或服务器today，不执行custom tzinfo。只合成test/demo正例，无真实政策编译/审核或项目四态。T28必须重新核owner/确认、实际必需表达式与当前发布证明，不能复用纯DTO冒充授权。

治理检查实际输出另列收尾：14路径/7旧7新、510其他tracked/66其他卡/历史日志ADR保护、本地链接/5Python内存编译、密钥/产物检查。CHANGELOG/tasks同步已完成，API/数据库/迁移/生成/依赖/UI/旧M0保持；无对应变化不更新API/数据库文档。Lint/Python静态类型无入口未执行，PG/browser无层变化未重复；真实学生/政策领域审核/法律/SQL权限/清理恢复/部署未执行，不宣称全部通过。PRIVATE保存/SHAclean后才单独T28，批次到T40停止。

## 变更文件

实际 `.venv/Scripts/python.exe -X utf8 -B .cache/check_task.py T27`：exit0、14路径/7旧7新、510其他tracked/66其他Task卡保护、306本地文档链接、5Python内存编译、历史日志ADR和密钥/产物检查通过。不代替未执行的Lint、Python静态类型或真实政策发布验收。

- `AGENTS.md`
- `README.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/tasks.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/deferrals.md`
- `docs/acceptance/T27_deferrals.md`
- `services/api/app/rules/deferral.py`
- `tests/unit/deferrals/test_t27_input.py`
- `tests/unit/deferrals/test_t27_deadlines.py`
- `tests/unit/deferrals/test_t27_matrix.py`
- `tests/unit/deferrals/test_t27_safety.py`
