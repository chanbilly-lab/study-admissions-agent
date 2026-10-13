# T37 可替换模型接口与离线预算验收

2026-10-04源码及合成隔离验收完成；PRIVATE保存以后续实际Git核对为准，真实处理关闭。

## 基线与范围

PRIVATE 6182aa9142c3227bfbb0fcc5d37b6b922ecb0b6d/721tracked，codex/t37-model-boundary；初工作区/索引为空。必读治理/原规格/docs01–05/相关模块已核，代码前冻结[契约](../model_gateway.md)。7旧路径允许、714其他tracked保护，旧head/原规格/M0/历史保持。

## 实际检查

- `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/contracts tests/unit/rules tests/unit/eligibility tests/unit/auth/test_provider_boundary.py -q --tb=short`：651 passed/60.51s/exit0，1现有Starlette warning。

- `.cache\run-web-checks.ps1 -TaskId T37`：684 passed/43files/24.28s；Vue Type Check exit0；demo Build1.63s/auth1.98s/125modules均exit0。auth522.75kB体积与cache outDir提示保留。

- `pytest tests/security/test_mode_isolation.py tests/backend/test_api.py::test_mock_complete_flow_and_evidence tests/backend/test_api.py::test_live_mode_explicitly_unavailable_without_fallback -q --tb=short`（同.venv Python -X utf8 -B）：143 passed/4.10s/exit0，1现有Starlette warning。

- 十profile逐个 `scripts/generate_contracts.py --profile <profile> --check` 全部exit0；`scripts/verify_contract.py` M0 TS/OpenAPI一致，exit0。旧20生成工件无改。

- 新owned `pytest tests/unit/model_gateway/test_t37_gateway.py tests/integration/model_gateway/test_t37_service.py -q --tb=short`（同.venv Python）首24 passed/0.68s；新增合法原地配置漂移两负例后26 passed/0.42s；坏async签名补既有failure节点，单节点1 passed/0.31s；无warnings/skip。

- 根首次新全专项 `pytest tests/unit/model_gateway tests/integration/model_gateway -q --tb=short`（同.venv Python）75 passed/12 failed/1.39s/exit1：独立成功夹具额度32低于最小合法answer JSON，改合法256且源码输出限制保持；新增128中文大answer且usage0仍拒/不退款。独立64 passed/0.43s。

- 实际只读发现初始policy/quota共享引用允许合法原地漂移，改独立验证副本；独立stdin probe错async签名原TypeError/inflight1，无usage记录，构建catch/close/charge/release最小修后固定PROVIDER_FAILURE/inflight0/charged1/history1。probe不是额外pytest。最终64独立再passed/0.43s。

- 最终全部源/fixture：`.venv\Scripts\python.exe -X utf8 -B -m pytest tests/unit/model_gateway tests/integration/model_gateway -q --tb=short`：90 passed/0.59s/exit0（26owned/64独立），无warning/skip。真实async offline stub/不合作取消硬超时/全局配额，不是商业模型、live smoke或PG；不累计重复复验。

- `.venv\Scripts\python.exe -X utf8 -B .cache/check_task.py T37`：exit0；17路径（7旧/10新）、714其他tracked、66卡、393文档链接及8新Python内存compile/历史/凭据检查通过。

## 未执行与已知问题

Lint/Python静态Type Check：项目无配置入口，未执行；Vue Type Check实际执行。Task37无数据库/HTTP/新增UI或迁移，不执行新PG/浏览器检查；真实live smoke、供应商调用/购买/数据传输、法律/正式身份/部署/SQL权限/生产备份恢复未执行。

D05实际供应商/处理地域/token费用与数据流评审未完成；真实模型关闭。预算只进程内离线限制，不是正式跨进程计费控制；mock仅明确合成。auth主包522.75kB的Vite体积提示和既有Starlette警告保留。

## 修改文件

- `AGENTS.md`
- `README.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T37_model_gateway.md`
- `docs/architecture.md`
- `docs/model_gateway.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `services/api/app/model_gateway/__init__.py`
- `services/api/app/model_gateway/budget.py`
- `services/api/app/model_gateway/gateway.py`
- `services/api/app/model_gateway/provider.py`
- `services/api/app/model_gateway/schemas.py`
- `tests/integration/model_gateway/test_t37_service.py`
- `tests/unit/model_gateway/test_t37_gateway.py`
- `tests/unit/model_gateway/test_t37_safety.py`
