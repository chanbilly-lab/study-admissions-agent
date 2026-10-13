# T26 范围适配验收

2026-10-03源码及合成离线验收完成，以下逐项区分实际检查与未执行项目。实施前[契约](../scope_adapters.md)/ADR-039冻结，基线PRIVATE T25 `3abed0cf4f3af77e337a06414247923d44c0940e`、506 tracked、空索引/工作区；本Task只纯范围和端口，真实规则关闭。

## 当前实际检查

实施前复核补充：具体TargetReference绑定完整原始scope_sha256；CN/GB之外country由DTO拒绝。英国规则省份明确不适用时允许学生省份三态，不推断学生招生身份；其他范围维度缺失仍未知。新专项将覆盖同一目标的规则冲突与顺序反转，不能被第一项匹配隐藏。全省配置仅输入识别，正式规则编译/审核/生产适配仍关闭。

`.venv/Scripts/python.exe -X utf8 -B -m pytest tests/unit/rules tests/unit/catalog tests/unit/profiles tests/contracts tests/security/test_mode_isolation.py -q --tb=short`：722 passed/45.91s/exit0，1既有Starlette弃用warning，无skip。此为旧代码相关回归，最终仍须范围保护证明其字节不变。

`.cache/run-web-checks.ps1 -TaskId T26`实际使用暂时Node24 PATH运行`scripts/web.ps1 -Action test`、`-Action typecheck`，以及pnpm11.19 `--dir apps/web run build --outDir ../../.cache/t26-demo-frontend-validation`和auth对应目录（每次明确VITE_APP_MODE后恢复）：348 passed/28files/16.36s；vue-tsc和两Build exit0、Vite1.21s/1.46s、73modules。忽略缓存保存产物，前端代码未改。

六个独立 `.venv/Scripts/python.exe -X utf8 -B scripts/generate_contracts.py --profile foundation|identity|public_catalog|admin|admin_review|profiles --check`均exit0；`scripts/verify_originals.py`与`scripts/verify_contract.py`同Python flags各exit0，两原规格与旧M0契约保持。

未执行Lint/Python静态类型（无项目入口），PG全回归/browser（纯内部模块无相应层变化），真实身份/学生/规则领域审核/法律/SQL权限/清理恢复/部署。本记录不是全国覆盖或正式规则审核通过的声明。

## 实施期间专项检查（不是最终轮）

实现者实际 `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/unit/adapters/test_t26_input.py tests/unit/adapters/test_t26_projection.py -q --tb=short` 首轮19 passed/4 failed：四个新夹具把已验证typed Expr dump中的无关null默认字段当原始T25 AST，已仅修测试保留typed Expr，旧T25未改。随后23 passed/0.71s/exit0。独立两文件同flags指定`test_t26_matrix.py test_t26_safety.py`：185 passed/1.83s/exit0；root全`tests/unit/adapters`：208 passed/1.91s/exit0，无warning/skip。静态复核又发现若干恶意Bundle测试有同类baseline问题，正在隔离每个tamper的真实原因并重新执行；以上两轮不冒称覆盖最后测试修正，不累加重复数量。

## 单列来源核查失败

只读界面预检者报告一次web search的两条官方域名query（`site.moe.gov.cn 2026 全国高考 专题 31 省 招生考试 兵团`与`site.gov.cn 省 自治区 直辖市 31 北京 天津 河北 山西 内蒙古 陕西`），随后同次open：[教育部候选通知](https://www.moe.gov.cn/srcsite/A15/moe_776/s3258/202601/t20260121_1427110.html)返回Timeout fetching，[政府候选地区页](https://www.gov.cn/home/2023-03/29/content_5748954.htm)返回403 Forbidden。正文未读成功，无原文哈希、规则审核或政策结论；不计离线测试通过。31内部代码依据现有ProfileForm识别配置，不冒充官方省码、全国规则覆盖或实际学校条件。

## 最终专项与实现结论

独立负向用例先证明原生/typed Expr有效baseline matched后才施加单一tamper，避免无关AST null字段造成假阳性；只改新测试。独立评审者最后同两文件命令185 passed/1.78s/exit0，无warning/skip；末次root全208覆盖该修正。首19/4失败、185/1.83s和208/1.91s中间结果均保留。

root最终实际 `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/unit/adapters -q --tb=short`：**208 passed/1.94s/exit0**；无warning/skip。实现者及独立评审者的分文件运行另列，不叠加为新的测试数。

纯模块按具体项目/完整15维scope原始哈希、年、阶段和半开有效窗口选择，唯一bachelor→undergraduate词汇映射。31内部省份与显式别名只在比较时使用；不改原画像/证据hash。英国暂定2027，规则省不适用可容纳学生省三态，其他维度没有wildcard。整组预验证、缺规则/期限/验证或同组冲突为unknown；所有回调后重验原快照，错误输出不含学生值或异常正文。provider只收到target/year/stage，无成绩/偏好/owner/session。

新配置仅可显式加载，import无文件/网络/数据库/模型/系统时钟IO；按需完整T23投影仍不读实例配置或做持久操作。实际适用/审核责任由受信服务负责；T26只有显式test/demo合成正例，真实ready固定false，facts-only发布不自动编DSL。此模块不调用T25评估、不产生eligible/ineligible/conditional、不代确认目标。

最终治理检查 `.venv/Scripts/python.exe -X utf8 -B .cache/check_task.py T26` 的实际输出另列收尾：18路径/7旧11新，499其他tracked、66其他Task卡、历史日志ADR、链接、8Python内存编译和密钥/产物检查。CHANGELOG/tasks已同步，旧API/DB/生成/迁移/依赖/UI/M0无变更，相应API/数据库文档不改。成功PRIVATE保存/远程SHAclean核对后才单独T27，完成T40后停止。

## 变更文件

收尾实际 `.venv/Scripts/python.exe -X utf8 -B .cache/check_task.py T26`：exit0，18路径/7旧11新、499其他tracked与66其他Task卡保护、299本地文档链接、8Python内存编译、历史日志ADR及密钥/产物检查通过。此治理检查不代替未执行的Lint、Python静态类型或真实发布验收。

- `AGENTS.md`
- `README.md`
- `config/scopes/undergraduate.json`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T26_scope_adapters.md`
- `docs/architecture.md`
- `docs/requirements.md`
- `docs/scope_adapters.md`
- `docs/tasks.md`
- `services/api/app/rules/adapters/__init__.py`
- `services/api/app/rules/adapters/schemas.py`
- `services/api/app/rules/adapters/scope.py`
- `services/api/app/rules/adapters/selector.py`
- `tests/unit/adapters/test_t26_input.py`
- `tests/unit/adapters/test_t26_matrix.py`
- `tests/unit/adapters/test_t26_projection.py`
- `tests/unit/adapters/test_t26_safety.py`
