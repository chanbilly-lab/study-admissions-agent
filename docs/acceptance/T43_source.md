# T43 · 手动CI配置与契约门槛（源码记录，运行未验证）

2026-10-04：完成默认关闭的手动CI源码，推送不触发测试；固定契约、离线Python、独立PG/迁移及Vue四stage。状态：已完成。

## 基线和范围

PRIVATE T42 0c53313ff394ca937609d8e42f128ed5d3aee28a，分支codex/t43-manual-ci；开始空索引/工作区干净，先阅读必读治理/原规格和当前相关模块/源码。

- `.github/workflows/quality.yml`
- `AGENTS.md`
- `README.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/architecture.md`
- `docs/tasks.md`
- `docs/ci.md`
- `docs/acceptance/T43_source.md`
- `scripts/ci/__init__.py`
- `scripts/ci/offline_plugin.py`
- `scripts/ci/run_checks.py`

## 实际操作

读取源码/文档（Get-Content、rg）；必要Git状态/diff/提交内容人工审阅；`.cache/task_source_docs.py`只编辑文档，未运行验收检查。官方`gh api repos/actions/{checkout,setup-python,setup-node}/git/ref/tags/{v4.2.2,v5.6.0,v4.4.0}`分别返回固定SHA；只读来源登记，不是Actions运行验证。

## 未执行与已知问题

Unit/Integration/浏览器、Lint、TypeCheck、Build、校验脚本、容器/恢复/故障/容量/领域演练未执行（用户要求）；不能使用历史结果宣称本次通过。流水线/坏迁移/漂移/网络负例与分支门槛未验证；workflow仅工作分支、默认分支入口和branch protection未配置；旧Windows浏览器/pg_dump路径尚未接入，关键HTTP不能代替浏览器/完整恢复

## 文档及保存

tasks/CHANGELOG与受影响规范同步。保存范围仅上述明确文件；不纳入用户无关索引/秘密/.cache/产物，不强推、不部署。实际commit及远程核对见本轮最终报告。源码完成不消除原运行验收/真实发布门槛。
