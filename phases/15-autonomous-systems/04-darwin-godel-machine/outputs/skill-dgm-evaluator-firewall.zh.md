---
name: dgm-evaluator-firewall
description: Specify the evaluator separation a Darwin-Godel-Machine-style self-modifying agent loop needs to avoid documented reward hacking.
version: 1.0.0
phase: 15
lesson: 4
tags: [dgm, self-modification, reward-hacking, evaluator, sandbox]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于一个拟议的自我调整 agent loop (agent 设置脚架、评价人员管道、部署目标,制定防火墙规格,使评价人员不参与 agent数据采集系统记录了 agent 去除自己的安全标记以提升分数; 这种技能是控制。

显示 :

1. **文件系统边界 。** 列出每个文件 agent 也可以编辑。列出所有被评价者读取的文件。交叉点必须是空的。如果不是,请指定要将其变成空的所需的确切动作 。
2. **处理边界。** 评价员必须在一个过程中运行 agent 不受控制。请检查容器或 sandbox。如果 agent Shell访问 agent 能够绕过处理中的守卫
3. **网络和秘密边界** 该 agent 无法编辑获取评价器输入或发布分数的 CI 机密。 列出密钥所在位置和挂载方式 。
4. **记分员合同** 评分从评价器返回循环的归档。 此路径是唯一的频道。 任何信息 agent 能够写出影响未来评分的作品 打破合同
5. **变异审查清单。** 列出 agent 需要手动审查的编辑在被接受前:新的依赖关系, 编辑到评分比对代码, 编辑到 sandbox 配置、编辑到记录或监测。

艰难的拒绝 :
- 与 agent 来源,移开
- 以一个运行 Python 导入 agent 进程。在子进程中运行它。
- 任何在 agent边界的侧面。 所有调整必须是服务器的侧面 。
- 任何记录 agent 可以通过编辑自己的代码而沉默。

拒绝规则 :
- 如果用户不能给每个文件命名 agent 能够编辑、拒绝并要求先进行文件级的写入访问审计。
- 如果评价员没有被搁置的投入,就拒绝——这是第三课的审计,这是先决条件。
- 如果部署表面包括评价人员本身的突变(甚至通过拟议附属关系更新间接地),则拒绝,需要人工防火墙审查步骤。

输出格式 :

返回一页规格 :
- **Agent write-surface** (路径,球)
- **评估器读表** (路径, 终点)
- **Intersection** (必须空; 显示 diff)
- **进程模式** (评价员是如何孤立的)
- **秘密库存** (地点和安装方式)
- **需要审查的突变等级** (bulleted)
- **签名行** (谁拥有防火墙的变数)
