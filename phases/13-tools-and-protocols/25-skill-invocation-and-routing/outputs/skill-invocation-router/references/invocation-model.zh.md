<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="invocation-model"></a>

# 援引模式

| 频道 | Initiator | Selection | 典型用途 |
|---|---|---|---|
| 人 体 | User | 确切发现的名称 | 故意选择工作流程 |
| 隐含型号或 agent | 型号或自主 agent | 说明相关性加主机政策 | 环境敏感路线 |
| 方案应用 | 产品运行时间 | 精确配置的名称和目标允许列表 | 决定性产品工作流程 |
| 技能构成 | 另一种技能或 subagent | 精确目标、呼叫者身份和深度政策 | 受外线影响的工作流量 |
| Programmatic harness | Evaluation runtime | 精确配置的名称和目标允许列表 | Deterministic evaluation |

人类和模型激活形成 2x2: 既不是人类, 也只是模型, 或两者兼有。 应用程序、 构成, 以及 harness 启动是各自有目标、呼叫和深度政策的单独渠道。

用于隐含路线 actor 和主机扩展资格,然后进行相关排序。 被阻断的高分技能不是赢家; 将其从选择组中删除并评估其余的合格候选人。 保留如果符合资格的集合是空的或者其最佳得分低于门槛值的话。

字段,例如 `user-invocable` 或 `disable-model-invocation` 适应器可以强制执行,但可移动的文档不能声称每次运行时都承认相同的字段或值。
