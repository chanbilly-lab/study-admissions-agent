# T57 逐指标实际毕业人群

2026-10-12先冻结report→metric→population三层。每metric各自保存真实统计层级/对象、毕业届、学位/学习方式、观察窗口、方法、样本定义/受邀数/回应数、分母定义；publication_year不改graduation_cohort，不反算未报告受邀人数。学校/学科的subject_ref不当某专业值。working/further_study/destination_confirmed/salary定义独立，落实不是纯就业。percent≤100、人数非负整数，抑制值不暴露；缺值留null+reason，薪资币种/周期/税前后未知不标月薪年薪或换汇。

复用candidate.1本地bytes，不新增PG/真实报告抓取/发布或模型补值。source元数据没有原文字节不填hash，证据不足仍pending。将来单位/抑制/同页不同届/缺分母/专业只有学科案例及测试/校验/类型/构建全部未执行（用户要求）；人口口径和真实审核仍待完成。
