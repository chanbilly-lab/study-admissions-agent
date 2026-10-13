# T16 合成证据人工抽查材料

日期：2026-10-03。**状态：用户已于2026-10-03确认合成原文抽查。** 以下哈希和坐标是程序从实际文件读取的结果；本会话用户对A/B/C文本、原文行号及DEMO边界的人工确认已记录，不替代真实招生事实的责任审核。

## 原文与坐标约定

原文：[DEMO_T16_original.json](../../data/fixtures/evidence/DEMO_T16_original.json)，仅包含 `DEMO_` 合成机构与测试文本，`is_synthetic=true`。无真实学校、真实分数或日期，不接入 M0、已发布目录或资格规则。文件采用 UTF-8、LF，共 **365 bytes**；原始字节 SHA-256：

```text
5edf7f71fc75d7ded528d25811520c8ef378b3f0bbead3aaf0f33f01408f298c
```

字节从 0 开始，区间为 `[byte_start, byte_end)`；行号从 1 开始，按实际原文字节计算，非 CSV 逻辑记录号。CRLF 为一次换行，单独 CR/LF 也换行；换行字节属于上一行。以下均为 `location_kind=utf8_byte_lines`，`page=null`、`section=null`，没有伪造 PDF 页码或文档节。片段保持原文字节，不裁空白、不翻译、不执行 HTML。

## 三个具体抽查项

| 项 | 原文件行 | 半开 byte 区间 | 字节数 | 原文位置 |
| --- | --- | --- | --- | --- |
| A | 4–4 | `[81,146)` | 65 | `summary` 的字符串内容，不含 JSON 引号 |
| B | 5–5 | `[165,241)` | 76 | `condition` 的字符串内容，不含 JSON 引号 |
| C | 7–7 | `[323,361)` | 38 | `markup` 的字符串内容，不含 JSON 引号 |

A 的精确片段：

```text
DEMO_合成证据：仅测试定位，不是真实招生要求。
```

片段 SHA-256：`f2b076ddea78e9c1cca22ffd8db0adf0b2453fcf498734a8ea1cc156b08dd271`。

B 的精确片段：

```text
DEMO_缺少成绩且没有已审核后补政策时，结果保持 unknown。
```

片段 SHA-256：`9a7dc68ecf2bdd30f8638d39cf29e495710bc075b9e475f860cdab52b79745b2`。

C 的精确片段：

```text
DEMO_<script>do_not_execute()</script>
```

片段 SHA-256：`7d0522c0152475ced9cb9f1df5cb708a2a2fc657397ec4abc92d35f4c31c384c`。此内容仅为字符串；程序不加载页面、不执行 script。

## 人工确认记录

- [x] 用户确认 A/B/C 的文本与实际第 4/5/7 行一致。
- [x] root 独立程序核对原字节区间、字节数、行号与片段哈希（exit 0）；这是程序验证，不是用户人工确认，不把UTF-8字节数当中文字符数。
- [x] 用户确认 DEMO 标签、无真实招生事实、无 PDF 页码/节号及未审核/未发布边界。

确认人：本会话用户（未收集真实姓名）。确认日期：2026-10-03，Asia/Hong_Kong；未获得精确小时/分钟，不补造。原始回复：“确认，继续执行 T16”。确认范围：上轮请求的A/B/C文本与原文件第4/5/7行一致，以及合成、未审核/未发布边界。字节和哈希由程序校验，不冒称用户手工计算。 用户对本合成材料的抽查不表示 T18 事实审核或 T19 发布已完成。

## 程序生成记录

实际执行：Python stdin 通过 `Path.read_bytes()` 读取原文件，`hashlib.sha256` 计算原文哈希；调用 `app.evidence.locators.extract_snippet` 分别定位三个精确 UTF-8 片段。执行命令形式为 `@'…'@ | .\.venv\Scripts\python.exe -B -X utf8 -`，exit 0；输出为上面的实际大小、哈希和定位数据。该记录是程序校验，不是人工确认。
