---
name: skill-library
description: Generate a Voyager-shaped skill library with registration, retrieval by similarity, compositional execution, and failure-driven refinement.
version: 1.0.0
phase: 14
lesson: 10
tags: [voyager, skills, library, composition, refinement]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


制作一个技能库, 支持旅行者的三个组成部分:课程钩、可检索的技能存储、迭接改进。

显示 :

1. `Skill` 类型 `name`, `description`, `code`, `version`, `tags`, `depends_on`, `history`。每个写入记录前一个代码。
2. `SkillLibrary` 与 `register(skill, dedup=True)` (新版或版本的顶撞) `search(query, top_k, tag_filter)`, `get(name)`, `topo_order(name)` (分数), `execute(name, context)` (地形运行)。
3. 获取命令使用 embedding 相似或类似 BM25, 不 LLM 整个图书馆都得分了 LLM 允许重新排入最高级的短名单
4. 执行必须捕获每个技能的例外,然后将其表面显示到 trace 微调循环可以消耗
5. 精细钩: 失败后 `execute`,运行时间收集(任务、技能)_名称、 错误、 信封_传到模型上,然后打电话 `register` 重写技巧。 版本跳跃; 历史保存旧代码 。

艰难的拒绝 :

- 将技能作为编导字符串而不是代码的库。 技能可以执行。 Prose 属于 `description`.
- 深度 - 第一次没有周期检测 技能控制器中断
- 静态版本被覆盖。 每一次精细都得擦擦 `version` 将旧代码推到 `history` 供审计。

拒绝规则 :

- 如果目标运行时间没有 sandbox 用于技能执行,拒绝用于技能接触生产系统的领域。 sandbox (列森09原则) 船前。
- 如果用户要求“ 自动重新处理每个失败而不进行精细处理 ” , 请拒绝。 不精细修改的精密检查会放大错误; 他们不会修复它 。
- 如果图书馆使用平坦检索能力超过~ 200 个, 请拒绝将其命名为“ 制作就绪 。 ” 先添加标签过滤器和等级命名空间 。

输出: `skill.py`, `library.py`, `execute.py`, `refine.py`, 和一个 `README.md` 解释 didup 规则、 检索后端、 精细 prompt,并用版本策略。结尾使用“下一步读什么”表示 Claude Agent SDK 融合,第16课 OpenAI Agents SDK 工具翻译,或用于评估技能图书馆质量的30课。
