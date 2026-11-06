---
name: primitive-mapper
description: Map any multi-agent framework or codebase to the four primitive axes (agent, handoff, shared state, orchestrator).
version: 1.0.0
phase: 16
lesson: 04
tags: [multi-agent, primitives, framework-comparison, architecture]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


假设一个多...agent 框架(或使用一个代码库)产生四种原始绘图,使读者能够在一个段落中理解该框架。

显示 :

1. **Agent definition.** 怎么样 agent 已经建好? parameters哪个州,确切的等级或工厂
2. **Handoff mechanism.** 三个中哪一个 handoff 模式是否使用函数返回、图形边缘或扬声器选择?如果混合,哪个是主词?显示触发最小代码 handoff.
3. **共享国家模型。** 完整的信息库或预测视图? 模拟还是耐久( 选中) ? 是否对同时撰写的作者安全? 谁能调解冲突 ?
4. **螺丝型** Static, LLM-selected, handoff- 驱动还是排驱动? LLM- 选择, 默认是哪个模型? 如果静态, 是图形周期还是 DAG ?
5. **交叉轴交换** 每一句:确定性、可缩放性上限、调试性、典型的失败模式。

艰难的拒绝 :

- 任何声称抽象的绘图都是“新”的, 但没有显示它不会倒塌到四个原始的状态中。 如果您不能缩小它, 请准确指出差距, 而不是发明第五个原始状态 。
- 框架比较只引用营销文档。 总是引用框架存储处或官方烹饪手册中的具体代码示例 。
- 类似“框架X 比较适合 agents" 但没有具体说明框架的原始性。

拒绝规则 :

- 如果框架是封闭源码,公众文件不披露 agent-handoff- 状态-切除器表面, 表示没有内部设备无法绘制地图 。
- 如果用户提供代码库但没有框架( 手动滚动) agents),绘制自定义执行图,并标出原始设计不足的标志。
- 如果框架年长于2024年(原AutoGen v0.2, pre-)Swarm不再保留,包括一个单行说明,说明其继承者是否保存了制图。

输出: 一页框架摘要。 从单句摘要开始 (“ Framework X fixes”) handoff 以图边和通过减小显示共享状态。” ),然后上面的五个部分, 然后一个结尾段落命名哪个生产项目最适合这个框架的原始部分。
