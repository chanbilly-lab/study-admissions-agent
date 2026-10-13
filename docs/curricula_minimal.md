# T56 培养版本候选

2026-10-12先冻结CurriculumVersion与Module，再复用candidate.1导入。program/institution/campus保持候选命名空间；entry_cohort/teaching_year/observed_year与document_version独立，不将教学年推入学届。课程≤200/代码唯一，必选修/实践/未知保留；credits缺失必须ambiguity/not_reported原因，hours可未知；未来教学模块必须provisional。学分和学时不同字段，不从错位表格猜数值。

有界毕业要求摘要不复制整PDF，培养目标不当就业统计。按入学届独立版本，不覆盖其他届；暂无实际PG版本库、专业映射审核、发布或对外查询。未来跨届/歧义/课程/未来状态案例及测试/校验/类型/构建、导入调用全部未执行（用户要求）。
