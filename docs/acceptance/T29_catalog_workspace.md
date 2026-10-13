# T29 项目比较与证据工作台验收

2026-10-03开始；2026-10-04本地合成验收完成。源码保存按后续Git核对，公众处理仍关闭。

## 基线与契约

T28 PRIVATE提交`acb2b3cbe3e4f70c95f5156e41c9b9f67f0eec70`，远程SHA已核对/工作区索引空；新分支`codex/t29-catalog-evidence-workspace`。546tracked，初始9个允许旧路径（七治理+AuthView/ProfileView），读代码后增补必要vite.config.ts公共开发代理，共10允许/536其他旧tracked保护；必读治理、两原文及目录/画像/评估/API/数据库相关代码文档先核对，再冻结[工作台契约](../catalog_workspace.md)和ADR042。只有T29，无API/迁移/依赖/旧M0变更；正式处理/领域审核/未成年私有/live/部署关闭。开始日期2026-10-03，继续检查时项目时区已为2026-10-04，实际完成记录另记。

只读查找曾误用不存在的`apps/web/src/views/AuthView.vue`，已通过rg纠正到features/auth/AuthView.vue；不是应用测试失败或通过。

## 实际检查（逐轮追加）

本轮根实际：`.venv/Scripts/python.exe -X utf8 -B -m pytest tests/contracts tests/security/test_mode_isolation.py tests/unit/eligibility -q --tb=short`：529 passed/42.49s/exit0，1既有Starlette弃用warning，无skip；不是历史T28结果重写。

同Python flags分别执行`generate_contracts.py --profile foundation|identity|public_catalog|admin|admin_review|profiles|assessments --check`：七项exit0；`verify_originals.py`两原文UNCHANGED、`verify_contract.py`旧M0 PASS，各exit0。package.json核实无Lint或Python静态入口。查找独立vitest.config.ts不存在，实际沿vite.config.ts配置，不当作测试通过。

2026-10-04独立实库准备实际命令：`& '.\.cache\t23-postgres\run-tests.ps1' -PytestArguments @('tests/integration/catalog_ui/test_t29_browser.py::test_t29_public_pipeline_requires_actual_publication_and_serves_conditional','-q','--tb=short')`：1 passed/71.01s/exit0，1既有Starlette warning、无skip。旧T28私有证据release经过真实T19替代成public_evidence=true及第二offering发布，公开分页/证据quote、真实T28 conditional HTTP通过；不把此准备项冒称浏览器验收。两个新增Python模块内存编译exit0。

## 前端逐轮检查

2026-10-04前端实现者实际检查：使用进程内Node24/Pnpm执行`pnpm.cmd --dir apps/web exec vitest run tests/catalog-client.test.ts tests/admissions-workspace.test.ts`，首轮47 passed/3 failed（11.24s），缺失旧session响应必需meta的测试夹具修正后，增补历史ID取消用例，最终51 passed/3.86s。不是51项新旧轮次相加。初次直接pnpm因全局Node16不满足运行条件退出1，类型编译未执行；随后Node24的类型编译首次报2处新Trace收窄、2处新mock call类型、2处新Vue模板问题（编译exit2，外层PowerShell误未传递exit而显示0，不计为通过），正在修正并等待根最终检查。

组件实现者实际`pnpm.cmd --dir apps/web exec vitest run tests/catalog-workspace-view.test.ts`：首轮27项全部setup失败（jsdom无showModal）；第二26 passed/1 failed（新测试误认为旧discardDraft退出editing）；夹具和断言修正，保留dirty/editing时不能选中画像的要求，追加精确历史证据绑定，最终30 passed/6.75s/exit0。原生dialog的测试替身不作为真实浏览器验收。

根首轮`& .\.cache\run-web-checks.ps1 -TaskId T29`：444 passed/18 failed、32文件（37.92s/exit1），失败全部来自独立Safety新helper默认未注入公共CatalogApi，目标准备未建立；此次组合命令随失败停止，Type Check/demo/auth Build未执行。独立单文件同轮15 passed/18 failed（33.10s），默认两个接口均注入闭合夹具并增加ready前提后33 passed/2.97s/exit0；没有弱化安全断言。

另行根`& .\.cache\t29-types-build.ps1`：vue-tsc及demo/auth两Build退出0，Vite1.25/1.60s，outDir在.cache的已有提示，未使用emptyOutDir；这是文本guard/私有meta补强前的中间构建，不冒称最终源码验收。实现者修正后的单独Type Check也exit0（6.64s）。

实际身份配置复核后补强：私有响应固定verified/disabled（包含合成主体）；公开Fact context文本拒C1和纯空白，但有限原quote保持原字节。owned两文件专项最终57 passed/3.52s。独立Safety追加模式六例后红测35 passed/4 failed（2.94s/exit1），修复后新进程最终39 passed/2.94s/exit0；无skip/warning。

根最终同`& .\.cache\run-web-checks.ps1 -TaskId T29`：474 passed/32文件/17.58s，vue-tsc --noEmit exit0，demo/auth Vite1.28/1.62s各exit0，组合结果四项均0。包含57owned客户端/控制器、30组件、39独立安全共126新前端用例及348旧回归，不与此前重复轮次相加。auth构建包含最终guard/mode补强，供实际浏览器读取；构建工件仅在.cache。

## 实际浏览器与范围

`& '.\.cache\t23-postgres\run-tests.ps1' -PytestArguments @('tests/integration/catalog_ui/test_t29_browser.py::test_t29_actual_browser_catalog_evidence_and_private_isolation','-q','--tb=short','-s')`：1 passed/92.10s/exit0，1既有Starlette warning、无skip。真实Edge154.0.4258.53，13检查点包含于此一个PG用例，不能另加13 pytest。实际静态auth构建→loopback HTTP透明桥→真实v2 ASGI→专用PG随机schema，API结果没有route mock；公开每次cookie=0、page_errors=0、blocked外网=0。四态/后补/当前确认画像/明确历史重放/字节定位/文本转义/390px移动无横滚/键盘Escape与焦点恢复、真实跨owner403/撤用途/退出通过；三个真实成功GET200先完成再延迟送达，主体切换/撤回/退出后均不能复活私有结果。

fixture创建并清理本Task随机schema，使用此前专用loopback study_t23_20261003，不连接生产库。截图与报告仅.cache/t29-ui/6d8856b3-82c3-44f8-813f-60cbca7bff0f，不纳入源码。准备1项+浏览器1项是两个不同PG测试节点，不重复相加。本Task未改业务数据库或迁移，不重跑无关全体PG套件。

根`node.exe --check scripts/catalog_t29_browser_smoke.mjs`、`git diff --check`退出0；原哈希检查保留536其他tracked。gh repo view确为PRIVATE、origin精确目标且当前codex/t29-catalog-evidence-workspace，无远程替换/全局配置。最终治理与暂存blob/实际diff/SHA保存随后按持续授权核对，不将预定push冒称已成功。

独立实际view_image查看1280桌面和390移动截图，内容无横滚/遮挡，原文HTML按文本、当前unknown和历史ineligible分开。专库只读清理检查exit0：catalog_ui_t29_* schema=0、其他backend session=0；首次PowerShell quoting ParserError未执行SQL，改here-string后执行，不能计作SQL失败或通过。专用PG保持供已授权下一Task使用，不停止其他进程。

根文档辅助首次退出1为README既有状态文字与helper匹配不同，四个当前说明已写后停止；依据实际文字修正并明确恢复，最终`.venv/Scripts/python.exe -X utf8 -B .cache/finalize_t29.py`及`.cache/check_task.py T29`退出0。检查32路径（10旧/22新）、536范围外tracked、66其他任务卡/历史日志及ADR保护、318本地链接、两个Python模块内存编译/JSON/秘密形态和禁止工件通过；CHANGELOG/tasks/ADR042及影响文档一致。原始两份输入、docs01–05、旧API/迁移/生成/依赖保持。

## 未执行与限制

Lint/Python静态类型没有配置入口，标未执行；真实身份/学生、领域规则/资料权利与法律、SQL GRANT/RLS/生产清理恢复/部署未执行。实际浏览器正例须明确DEMO合成且public_evidence=true真实发布，不能以旧私有fixture代替公开链。


## 修改文件

- `AGENTS.md`
- `README.md`
- `apps/web/src/features/auth/AuthView.vue`
- `apps/web/src/views/ProfileView.vue`
- `apps/web/vite.config.ts`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/architecture.md`
- `docs/requirements.md`
- `docs/tasks.md`
- `apps/web/src/features/catalog/CatalogFilters.vue`
- `apps/web/src/features/catalog/OfferingCard.vue`
- `apps/web/src/features/catalog/client.ts`
- `apps/web/src/features/catalog/presentation.ts`
- `apps/web/src/features/catalog/useAdmissionsWorkspace.ts`
- `apps/web/src/features/catalog/validation.ts`
- `apps/web/src/features/eligibility/AssessmentResult.vue`
- `apps/web/src/features/eligibility/client.ts`
- `apps/web/src/features/eligibility/validation.ts`
- `apps/web/src/features/evidence/PublicEvidenceDialog.vue`
- `apps/web/src/views/CatalogView.vue`
- `apps/web/tests/admissions-workspace.test.ts`
- `apps/web/tests/catalog-client.test.ts`
- `apps/web/tests/catalog-workspace-view.test.ts`
- `apps/web/tests/catalogFixtures.ts`
- `apps/web/tests/catalogUiFixtures.ts`
- `apps/web/tests/catalogWorkspaceSafety.test.ts`
- `docs/acceptance/T29_catalog_workspace.md`
- `docs/catalog_workspace.md`
- `scripts/catalog_t29_browser_smoke.mjs`
- `tests/integration/catalog_ui/conftest.py`
- `tests/integration/catalog_ui/test_t29_browser.py`
