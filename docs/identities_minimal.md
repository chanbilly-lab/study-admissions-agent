# T51 学院及年度代码候选

2026-10-12先冻结AcademicUnit/CodeCrosswalk，复用T50有界candidate.1 JSON导入接口。机构/校区/项目引用只为候选，合成统一DEMO前缀；同名无自动合并，校内学院与独立机构分开、年份范围独立，地方码包含生源scope/招生年度/目录版本，不当全国PK。组成员有界唯一，未审映射resolved_program恒None，不与正式事实join。

只有严格Pydantic/本地bytes模型，没有PG/官方映射审核或持久关系。既有T11身份不改。当前使用的公共候选导入补DecimalException固定拒绝，避免超长指数绕过错误契约。全部测试/Lint/TypeCheck/Build/校验未执行（用户要求）；名称重组/跨校区/年度复用/未审连接与导入错误案例均待执行，真实学校映射不能由模型猜造。
