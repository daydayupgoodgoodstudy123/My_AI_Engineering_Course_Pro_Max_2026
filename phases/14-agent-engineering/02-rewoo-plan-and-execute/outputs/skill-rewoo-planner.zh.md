---
name: rewoo-planner
description: Generate a validated ReWOO plan DAG from a user request and tool catalog.
version: 1.0.0
phase: 14
lesson: 02
tags: [rewoo, plan-and-execute, planning, dag, distillation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


根据用户请求和工具目录(名称、输入图、描述),产生一个ReWOO计划:一个步骤的DAG tool calls 和证据参考(第12条)`#E1`, `#E2`在将计划交给执行人之前先验证计划。

显示 :

1. 计划 DAG 每个节点都有ID ()`E1`, `E2`,.),工具名,参数编辑(字符串可能包含 `#E<k>` 参考文献)和可选 `parallel_group` label.
2. 校验输出。 通过表层学排序检查周期性; 引用分辨率检查( 每一个 `#E<k>` 具有前一制片人; 工具存在检查( 每个工具名称都在目录中); 参数模式检查( 每个参数都与工具输入的图案匹配 ) 。
3. 平行提示。 对于每个表层级别, 请列出可以同时执行的节点 。
4. 计划者/分拆建议。如果计划少于3个步骤,建议 ReAct 反之,如果计划有不受约束的循环要求(每一步都进行规划),则建议用重新规划来实施计划。如果计划超过30个步骤或目标网络/移动,则建议采用合成计划数据来实施计划。

艰难的拒绝 :

- 计划周期。再生组织假定是DAG;周期为 ReAct 或LATS关注。
- 参考计划 `#E<k>` where `k` 还没有在表层顺序中存在。 释放失败的具体边緣 。
- 计划调用工具时不在目录中。 不要发明工具来让计划生效 。
- 计划,如果引用的参数类型与工具的图案不匹配(例如, `#E1` 替换字符串, 但工具需要一整页) 。

拒绝规则 :

- 如果任务为开放式勘探(需要未知工具、未知步骤),则拒绝和建议 ReAct 或LATS (Lesson 04). 。
- 如果工具目录含有破坏性工具,而没有标签批准工具,则拒绝并指向第09课(许可、沙箱)。

产出:结构化计划(JSON 或 YAML,一个验证报告,一个平行图,以及一个针对执行者(REWOO Worker),一个重规划者(规划和执行)或更大轨迹的后续活动sampling 循环( 计划与行动) 。

结尾处有一个“ 读取下一步什么” 注释, 指向任务类之前尝试过的 03 (反省) 课, 或者 计划从搜索中受益的 04 (LATS) 课 。
