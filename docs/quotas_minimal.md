# T55 人数与费用

2026-10-12先冻结PlanQuota与Fee，复用candidate.1本地导入。人数kind initial/executed/remaining/admitted/enrolled独立，原须知定义必填，未知人数为null+reason，不把执行计划当实际录取。费用保存entry_year/身份/校区/项目/币种/周期；未知周期unknown、币种null，不自动换汇或估完整学费/住宿，总成本恒未知。合成机构/专业/校区引用必须DEMO，真实候选不会与合成引用混用。

无新DB/PG事务/已发布事实/收费计算/HTTP。未来口径冲突需人工复核，当前pending保留，不覆盖其他候选。数值/缺因/年度/周期案例、测试/类型/构建和任何导入调用均未执行（用户要求）。
