---
name: skill-release-gate
description: Evaluate an Agent Skill bundle for structural integrity, trigger quality, artifact improvement, script correctness, safety, installed-tree integrity, and target-host portability before release.
license: MIT
metadata:
  lesson: "27"
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="skill-release-gate"></a>

# 技能释放门

使用此技能后发布或发行 Agent Skill 目录捆绑 。

<a id="workflow"></a>

## Workflow

1. Resolve `SKILL_ROOT` 至包含此安装的绝对目录
   `SKILL.md`。不要假设进程 cwd 是已安装的捆绑。
2. Resolve `TARGET_ROOT` 工作目录和
   将用户提供的候选人确定为绝对候选人 `TARGET_BUNDLE`.
3. Read `references/eval-contract.md` 来自 `SKILL_ROOT`.
4. 调查在
   `evals/cases.json` under `TARGET_BUNDLE`.
5. 调查共同基线和技能主张
   `evals/artifacts.json` under `TARGET_BUNDLE`.
6. 检查明确的脚本和安全结果
   `evals/evidence.json` under `TARGET_BUNDLE`.
7. 检查申报运行时间能力
   `assets/hosts.json` under `TARGET_BUNDLE` 并核实目标文件 hashes
   反对其《公约》 `assets/manifest.json`.
8. 生产时,代替决定性预测, 艺术品,证据,
   和拥有所捕捉结果的东道主能力; 设置所有四种所捕捉的模式;
   并绑定所有原始触发观察, 两种工艺品, 完整的
   以及非空主机矩阵,用于非空源和
   匹配 SHA-256 源代码摘要。 这些本地检查可以设置
   `localEvidenceReady`,但当地可比较的大麻不会被捕获。
9. 获取外部 JSON 证明 `evidenceRoot` 和报告吻合
   加上其精确的SHA-256字节,来自单独的可信赖政策或
   释放频道。 证明必须是目标外的常规文件
   bundle.
10. 执行前,请显示准确解析的 Argv。 已安装的评价器是
    `scripts/evaluate_skill.py` under `SKILL_ROOT`。为了上载的课程
    固定, 创建 argv 来源于 `python3`绝对评价者路径
    `--fixture-demo`,以及绝对 `TARGET_BUNDLE`生产时使用
    相同的已安装脚本 `--attestation`,
    `--trusted-attestation-sha256`,以及绝对 `TARGET_BUNDLE`, 不使用
    `--fixture-demo`.
11. 返回 `checksPassed`, `fixturePassed`, `localEvidenceReady`,
    `trustAnchorValid`, `productionReady`, 和 `passed` 与证据根,
    evaluation 模式、失败的检查、精确度、回溯、每个原始触发器
    观察,每个案例重复运行率, 工艺品比较,脚本和
    安全证据、安装的树木核查和可移动性矩阵。
    包含已解决的脚本路径、 已解决的目标路径、 cwd、 准确的argv,
    标记未核实的未完成的观察。

<a id="output-contract"></a>

## 产出合同

将完整数据还给您 JSON evaluation 保存每一层特定的检查及其证据,这样经过的总数无法隐藏路径、工艺品、脚本、安全性、安装树木或可移动性故障。 `fixturePassed` 说这是个成功的教学方案 `localEvidenceReady` 只报告本地的文摘完整性。 `passed` 只有在 `productionReady` 还有一个有效的无赖托管锚。

<a id="failure-behavior"></a>

## 失败行为

如果配置无效, 来源不存在或不匹配, 信任的证明丢失或无效, 文件散列不同, 缺少所需的能力, 或者任何生产门失败, 以非零结果停止并报告失败的层 。 明确 `--fixture-demo` 路径只有在 `fixturePassed` 这样的假设是真实的,它从来不会要求释放。 永远不要公布、安装到其他地方、修复证据、创建信任决定或自动削弱门槛。

不要仅仅因为 SKILL. md 的剖析或一个正值而发布捆绑 prompt 激活。当目标击落所需的同伴文件或忽略所需的运行时间扩展时,不要给软件包贴上可移植的标签。
