<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="evaluation-contract"></a>

# Evaluation contract

只有在所有必要的表面通过时,才通过候选人的解职:

- 结构 : 在读取配置之前, 物理树前飞行会拒绝连接的根、 父或条目, 缺少所需的常规文件以及特殊文件。 然后目录名称匹配前事项名称, 需要的元数据存在, 运行时扩展被明确宣布, 直接引用解析, 软件包大小和类型限制, 没有明显的秘密模式, 存在输出和失败合同, 没有未引用的文件容器 。
- 触发: 正 prompts 激活和几乎没有的负数仍然不活动。 报告混乱计数、精确度、回溯和每次原始运行预测。 局部完整性将完整的观测序列和路径固定与源代码和 SHA-256 消化器捆绑在一起,不仅运行零速率或总速率。
- 稳定:反复处理每个案件,报告每个案件通过率。
- 人工制品:对基准和技能输出应用同样的说法。 技能输出必须经过并显示改进。 生产要求将捕获的字符串与源代码和 SHA-256 文摘联系在一起。
- 脚本: 需要从确定性脚本测试中明确获得通过/ 失败的证据, 包括重复执行。 制作证据将完整的脚本和安全检查套装与捕获的源和 SHA-256 文摘捆绑在一起 。
- 安全性: 要求每个已宣布的当局边界案件通过。 平均无法隐藏一次逃跑 。
- 已安装树: 在激活前, 对照已记录的文件列表验证已安装的干净副本 。 需要 `manifestVersion: 1` 和 `algorithm: "sha256"`。 `assets/manifest.json` 将之作为保留元数据,并自有 `files` 地图; 验证通过信任的外部释放或登记频道显示的列表。
- 便捷性: 说明每个目标主机是本地的, 需要适配器还是没有支持 。 列出缺少的能力 。 需要至少一个主机和正本地主机阈值 。 本地完整性将所捕捉的要求和主机矩阵与探测源和 SHA-256 文摘联系起来 。

将路线的 Eval 与确定性分开 harness 激活。 前者测量可发现性;后者分离工作流程和人工制品行为。

发运 JSON 值是学习大门的决定性固定装置。 它们可以设置 `fixturePassed` 却从未 `productionReady` 或 `passed`。对于真正的释放,设置 `evaluationMode` 以 `captured-observations`, `artifactMode` 以 `captured-artifacts`, `evidenceMode` 以 `captured-results`, 和 `hostMode` 以 `captured-capabilities`;记录每运行一次布尔值预测,并将完整观测集与源和SHA-256摘要捆绑在一起;用从同一任务和环境捕获的文物取代基线和技能字符串;记录非空白捕获源并匹配SHA-256人工文摘;用捕获的测试结果取代每一项证据判断;将全部证据绑在源和SHA-256摘要中;用捕获的主机探测结果替换模拟能力矩阵并将其与源和消化结果捆绑起来;重建舱单;安装到一个干净的目的地。

本地的支票可以设置 `localEvidenceReady`。它们不证明捕获,因为捆绑的作者可以重新标签固定装置并重新计算每个摘要。因此,评价员拥有完整的五种配置证据根,需要外部 `attestationVersion: 1` JSON 对象。从包件外提供证明,并通过 `--trusted-attestation-sha256`,来源于一个带外信任的政策。只有六层门加上当地完整性加上这个信任锚才能设置 `productionReady` 和 `passed`.
