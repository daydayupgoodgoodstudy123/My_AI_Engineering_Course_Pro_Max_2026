---
name: tool-schema-linter
description: Audit a tool registry against production design rules for names, descriptions, parameters, and shape. Can run in CI on every tool-registry change.
version: 1.0.0
phase: 13
lesson: 05
tags: [tool-design, linter, selection-accuracy, naming]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定工具登记册( A)JSON 或 Python ),根据第13 . 05阶段的设计规则进行静态审计,并编制一份有碎片的固定清单。

显示 :

1. 姓名审计。 `snake_case`,动词名顺序,时态标记,嵌入参数,命名空间前缀一致性。
2. 说明审计:执行时限(40至1024个字符)、 `Use when X. Do not use for Y.` 模式,禁止常见的注射模式(`<SYSTEM>`, `ignore previous instructions`, URL 缩略语在行中) 。
3. 审计计划。 `required` 列表已存在, `additionalProperties: false` 对象,封闭的套件上钉,无 `type: any`,字符串字段的说明。
4. 形状审计。 旗帜单词 `action: string` 当 enum 超过 3 个值时, 工具会被移动。 建议原子分割 。
5. 一致性审计。 parameter 相关工具的名称; 相同的标识模式; 相同的单位常规 。

艰难的拒绝 :
- 任何工具名称 `snake_case`断开提供者的序列。
- 任何描述在 40 字符以下, 或者缺少“ 使用时” 模式。 选择精度罐 。
- 含有间接注射模式的任何描述。潜在的工具毒害矢量。
- 任何未输入的财产 。 Hallucination bait.

拒绝规则 :
- 如果登记册有超过64个工具,请警告 Anthropic / Gemini 13阶段 17 路线。
- 如果工具采纳了不信任的输入, 读取敏感数据, 并拥有相应的执行者, 拒绝并引用Meta的二法则 。
- 如果被要求批准一个工具, 将生产数据库包起来, 没有只读的守护符, 请拒绝 。

输出: 每条查找格式为 `[severity] path: message`,然后是摘要行和通过/失败的判断。严重性水平:区块(必须在船舶前修正)、警告(应该修正)、nix(样式)。结尾为单字母重写,这样可以最快地减少选择错误。
