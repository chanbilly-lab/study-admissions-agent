# T41 隐私与授权操作页面验收

2026-10-04源码及合成隔离验收完成；PRIVATE保存以后续实际Git核对为准，真实处理关闭。

## 基线与范围

PRIVATE 744e20aa6db241fff692239ad1e8af3692d08bb4/797tracked，codex/t41-privacy-rights-workspace；初工作区/索引为空。必读治理/原规格/docs01–05/相关模块已核，代码前冻结[契约](../privacy_workspace.md)。8旧路径允许、789其他tracked保护，旧head/原规格/M0/历史保持。

## 实际检查

- scoped Node24.19/pnpm11.19 `pnpm --dir apps/web exec vitest run tests/rights-client.test.ts tests/rights-state.test.ts tests/RightsPanel.test.ts`：首55 passed/3files/3.65s。随后`scripts/web.ps1 -Action typecheck`首exit1：新client闭包body.meta的unknown narrowing；仅改显式九字段校验后类型通过，不能把首轮称全通过。实际Meta按T40 ProfileMeta九字段/全null-private一致，没有改旧wire。

- `.cache\run-web-checks.ps1 -TaskId T41`实际`scripts/web.ps1 -Action test/typecheck`及scoped `VITE_APP_MODE=demo/auth pnpm --dir apps/web run build --outDir ../../.cache/t41-{demo,auth}-frontend-validation`：有界响应阶段802 passed/49files/25.51s/exit0，VueTypeCheck0；demo1.70/auth2.06s各139modules/exit0。该阶段59新专项全部包含在802内。首完整798/25.42s/demo1.50/auth2.22、界限补丁后800/25.25s/demo1.47/auth2.03也均exit0，是早轮重复节点；不累计重复测试。现auth563.79kB chunk warning/ignored外根outDir提示保持，没有无关拆包。PATH/VITE_APP_MODE由helper finally恢复。

- `.venv\Scripts\python.exe -X utf8 -B -m pytest tests/unit/privacy_rights tests/contracts/test_t40_rights_contract.py tests/contracts/test_privacy_contract.py tests/contracts/test_sharing_contract.py tests/security/test_mode_isolation.py -q --tb=short`：228 passed/10.10s/exit0/1旧Starlette warning，无skip；T40/隐私/共享wire和模式回归，后端源未改。

- `.venv\Scripts\python.exe -X utf8 -B .cache/check-profiles.py T41`：十二profile逐个实际`scripts/generate_contracts.py --profile <foundation/identity/public_catalog/admin/admin_review/profiles/assessments/plans/revisions/notifications/qa/rights> --check`均0；`scripts/verify_contract.py`M0一致0；`scripts/verify_originals.py`两原文UNCHANGED0。生成工件和旧迁移保护。

- `.cache\t23-postgres\run-tests.ps1 -PytestArguments @('tests/integration/privacy_ui/test_t41_browser.py','-q','--tb=short')`：初1failed/25.67s/exit1，实际Edge已读Cookie身份/告知/共享，但DELETE grant403；复核是深层管理员fixture使用另一个session_settings_factory，仍注册旧HTTPS回调。新fixture统一所有配置factory注册实际loopback origin并断言可信origin一致，业务规则及旧fixture不改。修后1 passed/34.23s；末有界响应/同步清理实际Build后复验1 passed/37.08s，均1旧warning/exit0，是同一distinct节点。最后仅harness等待相关隐私/共享面板完成读取，最终命令见下条。

- 实际Edge全程无mock API：预登记合成Cookie、真实Origin/即时CSRF、专用随机PG业务/独立ledger schema与Windows真实文件，十一检查点分别覆盖默认折叠零rights calls、键盘精确grant撤销、core撤回立即旧profile403、撤回仍可本人导出、他人真实受理UUID404、原bytes/SHA实际JSON下载、完成HTTP200交付延迟跨收起忽略、删除受理≠完成且立即关闭用途、实际文件失败/有限重试耗尽追踪、退出后专用worker继续完成清理、另一预登记同owner有效合成会话读completed责任/备份说明。该有效会话只是独立合成预登记session，不冒充真实IdP重新登录。无页面错误/外网/浏览器私有storage；十一检查点不是十一个pytest节点。最后截图人工查看排版、UTC与保留文案，没有原资料HTML渲染。

- 最后同实际PG-browser命令：1 passed/39.6s/exit0/1既有warning；Edge 154.0.4258.53、十一检查点完成，当前告知/共享读取结束后保留截图，scope仅合成隔离。


- 提交前审查补充静置到期保护：仅新增本地session/artifact定时器，分段防浏览器2^31溢出，dispose取消计时；三个专项覆盖工件到期无poll、会话到期abort且成功迟到不接收、旧actor计时取消/长期计时不误到期。再次`.cache\run-web-checks.ps1 -TaskId T41`：最终805 passed/49files/25.46s，62新专项（38client/17state/7panel）全部包含其中；VueTypeCheck exit0；demo1.48/auth2.10s各139modules/exit0，auth563.79kB warning保留。此前802是早轮结果，不累计同节点。

- 本地到期补丁后的实际同PG/HTTP/Edge命令：最终1 passed/39.85s/exit0/1旧warning，十一检查点再次完成；没有新增pytest节点。最后截图人工查看，隐私/共享读完，无排版重叠。此前39.60s是同节点早轮。

- 提交准备辅助检查：补丁后再次调用`.cache/save-task.py T41 stage`首exit1，原因是该辅助脚本仍假定初次空索引，而本Task之前已暂存21个准确路径；没有撤销或重置索引。核对暂存仍仅本Task manifest，逐路径重新add同21路径，`.cache/check_task.py T41 --staged`与cached diff检查exit0（789其他tracked/66卡/历史/428链接保护）。这是辅助脚本前提问题，不计作应用测试。

## 未执行与已知问题

Lint/Python静态TypeCheck：无配置入口，未执行；VueTypeCheck实际执行。T41无API/DB/依赖变更，无新DDL检查；旧head/生成工件已保护。真实Keycloak/MFA/学生/监管法律/生产SQL权限/TLS/供应商采购/公众部署未执行，Edge仅专用loopback合成装配。Docker镜像与生产平台适配未执行：本Task无部署源码，T42另验且D01未定/daemon未连。

真实资料/身份供应商/正式权利渠道/法律与部署仍关闭；不自动轮询，刷新页面需本人受理UUID重新追踪，页面不持久保存标识/原内容。10MiB原内容上限与T40有限重试/最小责任记录、备份到期物理清理局限保持。D01用户明确待定；D07旧提案不采用且替代目标未定；D08只确认T50首批34地区×2026登记，真实审核发布负责人未定。auth563.79kB及ignored cache outDir提示、旧Starlette warning保留。T42前read-only docker version：CLI29.8.1但Docker Linux Engine管道不存在，实际镜像/容器检查尚不可执行；不顺带重装或重建数据环境。

## 修改文件

- `AGENTS.md`
- `README.md`
- `apps/web/src/features/auth/AuthView.vue`
- `apps/web/src/features/privacy/rights/RightsPanel.vue`
- `apps/web/src/features/privacy/rights/client.ts`
- `apps/web/src/features/privacy/rights/useRights.ts`
- `apps/web/src/views/SettingsView.vue`
- `apps/web/tests/RightsPanel.test.ts`
- `apps/web/tests/rights-client.test.ts`
- `apps/web/tests/rights-state.test.ts`
- `apps/web/tests/rightsFixtures.ts`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/acceptance/T41_privacy_workspace.md`
- `docs/architecture.md`
- `docs/privacy_workspace.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `scripts/privacy_t41_browser_smoke.mjs`
- `tests/integration/privacy_ui/conftest.py`
- `tests/integration/privacy_ui/test_t41_browser.py`
