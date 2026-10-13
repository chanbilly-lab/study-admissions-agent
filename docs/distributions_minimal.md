# T53 一种分布格式

先冻结descending_inclusive降序、score/count/cumulative与人群/加分/总分/总人数定义，再实现纯候选。分数必须严格降序且唯一，count正整数，累计至少包含各段人数；完整表每段等于前累计+人数、最终等于total_people。未完整或关键定义缺失返回unknown，不把缺段插值成个人位次。完整且有定义的同分score仅返回该报告人群的cumulative-count+1至cumulative，不决定并列内部排序、不跨省/年/改革/加分套用。

复用candidate.1接口，pending/published=false。现有格式只处理有界1000行，其他统计格式应另写明确适配器，不能猜累计方向。2026-10-12代码/负例/导入/PG/测试/构建均未运行（用户要求），无真实分布、当前资格或录取概率，所有结果只是候选报告的确定性检查。
