# T52 省线候选

2026-10-12先固定ExamScope/Cutoff及一种candidate.1人工JSON格式，复用T50 load_candidates(payload,Cutoff)。该函数只返回不可发布的内存CandidateBatch；归一sha256用于候选重导识别，不是来源原文字节hash，也不证明DB事务幂等。原文hash没有bytes不填。fixture明确DEMO/合成，不是北京或任何真实省份分数线。

线种保留undergraduate_control/segment_first/segment_second/special_category/other与原始标签，不把一段当本科线；省年/科类/批次/轮次/改革及加分定义分开，港澳台高考scope拒绝，未知满分留空，不从经验填750。缺score必须missing_reason，已知score不附缺失原因；已知满分>0且score不超。所有数据pending/published=false，不产生资格规则。无PG新表/正式审核发布。上述案例/测试/类型/构建/导入调用全部未执行（用户要求）。
