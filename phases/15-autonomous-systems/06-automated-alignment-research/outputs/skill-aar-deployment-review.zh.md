---
name: aar-deployment-review
description: Pre-deployment review of an automated-alignment-research pipeline, including sandbox isolation and log integrity.
version: 1.0.0
phase: 15
lesson: 6
tags: [aar, alignment-research, sandbox, log-integrity, rsp]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于拟议中的自动Alignment- 研究部署(模型, sandbox将进行部署前审查,由边防实验室安全小组签署。

显示 :

1. **Sandbox isolation.** 校验每个 AAR 实例的文件系统、 网络和处理限制。 确认任何 AAR 无法读取或修改另一个 AAR 的 sandbox. 确认任何AAR都无法直接到达论坛的书写端点(所有职位都通过单独的服务)。
2. **论坛日志完整性。** 论坛必须只附加且显示篡改。 请指定存储( 如用对象锁定的 S3 、不可更改的分类账、 仅附加的 WAL) 。 请指定校验间隔和检测到篡改时的反应 。
3. **任务分配政策。** 描述任务分配方式:谁写、谁批准、AARs是否可以提出自己的后续任务,以及条件如何。 自由分解在业绩上胜出;规定的工作流程在可审计性上胜出。 明确记录权衡。
4. **人类审查大门** 在任何 AAR 输出影响实际研究方向、 训练数据或已出版的工作之前, 指定的人审查员必须签名。 请指定审查清单: 实验可复制性、 日志完整性、 索赔- 证据映射 。
5. **门槛监测。** 跟踪信号显示,AAR系统接近RSP v3.0 AI 研发-4区域:任务复杂三角洲、自主的子任务产卵、跨任务信息传输。

艰难的拒绝 :
- 任何AAR部署,没有篡改 显而易见,出...sandbox logs.
- AARs的产出直接纳入训练数据或生产政策而不进行人类审查的任何管道。
- 任何单一的AAR具有足够资格影响多个下游系统的管道。

拒绝规则 :
- 如果 sandbox 隔离未指明或依赖于单层(Docker 拒绝 要求深入防御
- 如果任何人(甚至操作员)都可以编辑日志存储,则拒绝并需要写入一个介质。
- 如果部署的目的是使部分能力管道自动化——不仅仅是 alignment 研究——拒绝并升级为区域支助方案审查。

输出格式 :

以下列方式返回审查备忘录:
- **管道摘要** (一款)
- **隔离得分** (每组: fs, net, proc, 对等)
- **日志完整性评分** (附有核查计划)
- **任务分配决定** (固定/自由/混合,附有理由陈述)
- **人类审查大门** (审查者姓名,核对表)
- **阈值监视器** (信号清单、阈值、响应)
- **部署决定** (走/ 坚持/ 不走)
