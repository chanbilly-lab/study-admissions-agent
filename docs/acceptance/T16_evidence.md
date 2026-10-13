# T16 不可变文档与证据验收

2026-10-03，源码、合成抽查与隔离实库验收完成。下述待答/阻塞段保留历史，当前已解除。独立codex/t16-immutable-evidence，基线3cc5357c155937f083fccf4d3e02d1ce0da7fcd6；327tracked、开始Git/index干净。读取必读、原规格与相关catalog/source/storage/imports后冻结[evidence](../evidence.md)。专用loopback evidence_t16_test、不打印凭据；合成资料人工抽查与最终检查尚待完成。


已实际执行（不替代T16专项或人工抽查）：

- .cache/t16-postgres/run-tests.ps1 -PytestArguments @('tests/unit/ingestion','tests/integration/imports','tests/unit/storage','tests/security/storage','tests/integration/sources','-q','--tb=short')：143 passed/1 skipped123.58s exit0。skip真实Windows symlink1314。
- .venv/Scripts/python.exe -m pytest tests/contracts tests/security/test_mode_isolation.py -q --tb=short：333 passed/1既有warning18.78s exit0。
- .cache/run-web-checks.ps1 -TaskId T16：170 passed/15files8.86s、Type Check/demo+auth Build exit0。
- scripts/generate_contracts.py --check及--profile identity --check、scripts/verify_contract.py、-X utf8 scripts/verify_originals.py：全部exit0。

Lint/Python静态Type Check无入口；UI browser（无UI改动）、全体PG、POSIX/真实身份/正式资料/PDF解析/OCR/清理备份/部署未执行。前端Type Check已执行；两Build常规outDir warning，产物仅忽略缓存。

- .venv/Scripts/python.exe -B -m pytest tests/unit/evidence -q：root32 passed1.26s exit0（最后物理行DTO补强之前；随后最终纯测试另记）。
- 首轮 .cache/t16-postgres/run-tests.ps1 -PytestArguments @('tests/integration/evidence','-q','--tb=short')：19 passed66.14s exit0。进程在最后future timestamp/最后查询时效补丁前加载，不冒称已测此补丁；最终重跑待记录。
- root独立Python stdin读取365原字节，检查原hash、A/B/C三区间及4/5/7行/片段hash：exit0。这是程序验证，用户人工仍待答。

只读交叉复核补正：初始INSERT的span须<=原版本size；同hash副本不renew旧文件；current scope的hash指纹拒父范围变化；last query后source/file到期和document/version/snippet未来时刻检查；纯locator增加可证物理行范围。无已发布事实、旧代码或依赖改变。证据getter验证metadata/创建时captured hash，不每次读取磁盘原bytes；不声称物理恢复/外部维护篡改检测已验收。

最终pure .venv/Scripts/python.exe -B -m pytest tests/unit/evidence -q：33 passed1.25s exit0；三pure模块内存compile exit0。最后backend时间守卫后8模块内存compile/Service import/3表metadata exit0（2.40s）。32为历史首轮，33覆盖物理行可达性copy/construct否定；最后PG尚待完成。


最终自动验收：
- 最后 .cache/t16-postgres/run-tests.ps1 -PytestArguments @('tests/integration/evidence','-q','--tb=short')：19 passed70.44s exit0。覆盖冻结版future timestamp/final source-file时效/locator可达性；中间第二轮19 passed69.14s也是实际通过，但未加载最后两补丁。三轮同19项，不累加为57项。
- 最后8模块内存compile/Service import/3-table metadata：exit0，2.42s。命令：.venv/Scripts/python.exe -B -c "from pathlib import Path; paths = list(Path('services/api/app/evidence').glob('*.py')) + list(Path('services/api/evidence_migrations').rglob('*.py')); [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in paths]; from services.api.app.evidence.service import EvidenceService; from services.api.app.evidence.models import EvidenceBase; assert len(EvidenceBase.metadata.tables) == 3; print(f'{len(paths)} modules compiled; service import and 3-table metadata passed')"
- git diff --check：exit0；本TaskSQL每行去尾空格，无T15格式错误重演。
- .cache/check_task.py T16 --blocked：只检查变更范围/历史/状态/链接/编译与凭据，不把阻塞Task宣称通过；数量由实际输出记录。

19项PG含真实JSON/CSV定位、相同hash去重/新hash追加、旧original不借副本续期、两immutable DB trigger、current offering范围指纹/原size/span、角色MFA/session、source最新许可/expiry/删除、强reviewer只衍生片段（无fullbytes或伪owner）、sameEngine/当前callerTX、audit失败/真正deferred COMMIT失败回滚/重试、实际等待锁后时效、并发版本锁和独立迁移旧域保留。专用test/verified合成与真实PG/本地文件，不是正式招生事实验收。

人工原文抽查：已在2026-10-03向本会话用户请求对照原文4/5/7行及DEMO边界；未收到回答。材料有程序核对，不填人工姓名/时间或确认。该项未执行完成，Task保持阻塞；其他66卡不变，T17–T20未启动。没有提交/推送本Task；本地源码和用户文件保留。解除条件是实际确认一致或修正材料并重新验收。

完整变更清单：
- `AGENTS.md`
- `README.md`
- `docs/tasks.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`
- `docs/api.md`
- `docs/database.md`
- `docs/architecture.md`
- `docs/requirements.md`
- `.gitattributes`
- `docs/evidence.md`
- `docs/acceptance/T16_evidence.md`
- `docs/acceptance/T16_manual_review.md`
- `data/fixtures/evidence/DEMO_T16_original.json`
- `services/api/app/evidence/__init__.py`
- `services/api/app/evidence/schemas.py`
- `services/api/app/evidence/locators.py`
- `services/api/app/evidence/models.py`
- `services/api/app/evidence/store.py`
- `services/api/app/evidence/service.py`
- `services/api/evidence_alembic.ini`
- `services/api/evidence_migrations/env.py`
- `services/api/evidence_migrations/versions/0001_evidence_t16.py`
- `tests/unit/evidence/test_t16_locators.py`
- `tests/integration/evidence/conftest.py`
- `tests/integration/evidence/test_t16_evidence.py`

实际阻塞状态QA：26路径（10旧/16新）、317保护tracked、66其他任务卡、274本地链接、11Python内存编译与历史/凭据形状检查通过（blocked_check_only=true，非Task完成）。Git基线无暂存，当前仍无暂存；未提交/未推送T16。

## 2026-10-03恢复验收

用户直接回复“确认，继续执行 T16”，对上轮合成抽查材料确认，人工项已完成；先前阻塞过程保留为历史，不代表当前仍阻塞。重新读必读/原规格和11个相关Python文件并内存编译、核对空index/HEAD与26路径。缓存保存本次恢复时hash，不覆盖用户改动。新的专项命令与结果待当前实际执行完成后记录；前述170前端等是同T16之前实际结果，本轮源码未改变不重跑，不写成新通过。真实门槛不解除，随后按既有批次逐个T17–T20，T21不启动。

本次恢复专项实际命令 .cache/t16-postgres/run-tests.ps1 -PytestArguments @(\'tests/unit/evidence\',\'tests/integration/evidence\',\'-q\',\'--tb=short\')：52 passed68.10s exit0（33pure/19PG）。恢复时及保存前hash比对源码/ini/原json不变，未重跑前端/全体PG，历史结果不标为新执行。用户人工确认日期2026-10-03，直接回复已记抽查材料；当前Task完成，保存后单独T17–T20。完整26路径清单沿用，其他66卡不改。
