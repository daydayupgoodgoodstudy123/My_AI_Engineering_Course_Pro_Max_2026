---
name: parallel-call-safety-check
description: Audit a tool registry for safe parallelization. Mark each tool parallel_safe, note ordering dependencies, and flag downstream rate-limit risk.
version: 1.0.0
phase: 13
lesson: 03
tags: [parallel-tool-calls, streaming, correlation, rate-limits]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


使用工具登记册( 含有名称、 描述和执行器的工具列表), 以 `parallel_safe: bool`, `ordering_deps: [tool_name]`, 和 `rate_limit_group: name` 字段已添加。

显示 :

1. 每个工具分类。 对于每个工具,决定:安全地在同一转弯内平行运行(纯读、不同资源);不安全(变换、共享资源、外部) rate limits).
2. 依赖性图形。 识别工具输出应输入另一个输入的对配。 无法在转弯内平行。 标记为 `ordering_deps`.
3. 速率限制分组。 击中同一下游的工具 API 共享组。 主机应该为每个组的同种货币设定上限,而不是每个工具 。
4. 安全建议。 对于每个不安全的工具, 请声明是否为该转折、 队列或资源碎片而禁用平行 。
5. 具体供应商国旗。 `parallel_tool_calls=false` 在 OpenAI 或 `disable_parallel_tool_use=true` 在 Anthropic 当任何不安全的工具出现在集中时。

艰难的拒绝 :
- 任何在审计后没有分类的登记册。 默认拒绝; 未知意味着不安全 。
- 标记共享资源上的任何写入路径工具 `parallel_safe: true`种族条件。
- 任何工具, 点击受费率限制的外部 API 没有 `rate_limit_group`.

拒绝规则 :
- 如果要求所有工具都同时安全,无需检查,请拒绝。
- 如果登记册包括同一资源上的相应工具(`delete_file` 和 `write_file` · 拒绝将第14阶段与第14阶段平行, sandbox- 级序列化。
- 如果用户认为他们的工具从来不赛跑,他们拒绝并索取证据(测试、日志或正式论证 ) 。 比赛在生产过程中默默发生。

产出:修订登记册为a JSON 每个工具用三个新字段进行浮标,然后简短地总结,列出风险最高的平行选择和建议的缓解。 `tool_choice` 覆盖当前转弯 。
