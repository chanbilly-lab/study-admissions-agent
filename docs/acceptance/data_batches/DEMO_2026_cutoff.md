# T67 单批最小清单：DEMO省线

2026-10-13；这是一个合成候选清单，不是真实审核/发布结果。对应DEMO_cutoff_2026.json一条假记录；地区只是资料范围，不能当北京真实省线。预期全量分母null、真实published=0，原文字节hash、使用权、责任人、原文抽查与质量报告均缺失，结论blocked。

实施前冻结BatchManifest（≤200候选/≤10distinct源引用与hash对）、assess_batch纯报告和合成清单；它不执行导入/审核/发布/撤回，不相信调用者自报通过作为授权，全部字段齐备也只needs_trusted_review_pipeline且real_publication_authorized=false。归一候选hash不能填成原文hash；没有bytes不编hash。未知分母不算覆盖率，首批不等于全国采齐。每次真实批次仍需独立BATCH范围、许可/原文/审核人和所选类型的PG发布/撤回及人工抽查。

本Task也修复当前人口候选观察窗口的日期边界：只date对象/明确YYYY-MM-DD，不从时间戳或datetime猜日历日期。培养版本teaching_year不自动继承到未标教学年的模块；未来性只能在模块实际教学年已知时判断，未知模块排程不当已确定未来课表。所有模型/清单/日期/发布负例、测试、Lint、TypeCheck、Build、校验、真实资料或演练均未执行（用户要求），没有‘严重错误为0’或真实资料已审结论。
