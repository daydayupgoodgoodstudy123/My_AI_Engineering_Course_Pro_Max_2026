---
name: ai-scientist-sandbox-review
description: Two-gate review checklist for research-loop agent outputs before anything leaves the sandbox.
version: 1.0.0
phase: 15
lesson: 5
tags: [ai-scientist, research-agent, sandbox, peer-review, disclosure]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于AI-Scientist-V2-style循环产生的自主研究产出(假说、代码、实验、数字、纸质草稿),产生了双关审查: sandbox 审计(请假吗? )加上研究审计(工作是否合理? )。

这两扇门直接显示在以下审计上: **Sandbox 门=项目1**; **研究门=项目2(审计)+3(波兰审计)**。项目4-5 规定两扇门过关后发生的事情。

显示 :

1. **Sandbox gate.** 在任何文物离开之前 sandbox:
   - 列出每个网络都呼叫环及其目标。 标记任何未事先批准的 。
   - 清点循环在工作目录外写的每个文件 。
   - Confirm Docker / 完全运行的 seconp / g visor 封闭 。
   - 确认没有子进程逃过 sandbox监督
   如果检查失败,将阻止导出; 提高至人。
2. **实验性审计。** 读一下实验代码,而不是纸:
   - 核查每一个声称的实验 实际运行,它报告的数字可以复制。
   - 检查失败的实验是否报告为失败,而不是事后重新设定为负结果。
   - 检查一下这个想法上的“新奇”标签 是否与人类领域专家的文献搜索相矛盾
3. **波兰审计。** 阅读数字:
   - 确保每个数字的数据来自一个登录的实验运行,而不是来自抛光阶段的重写。
   - 确认轴、比例和说明与基本数据相符。
   - 标出标题要求超过数据支持的任意数字。
4. **披露计划。** 如果文物是打算用于外部分配:
   - 揭露那件艺术品 agent-authored.
   - 披露所使用的工具( 模型家族、 循环版本) 。
   - 揭开检查过的人的检查员 以及他们检查过的
5. **否定释放的决定** 如果文物在任何审计步骤失败, 默认值不会释放。 超过此默认值需要指定为人类所有者 。

艰难的拒绝 :
- 任何不守门的呈文
- 任何没有环状执行日志或未完成的文物
- 任何无法追溯到特定实验的数字。
- 任何新颖的说法 域专家没有核实。

拒绝规则 :
- 如果跑步不够的话 Docker 或要求重新运行 sandbox.
- 如果用户无法为试验阶段制作执行日志,则拒绝——该文件是不可审查的。
- 如果拟议的分发渠道是一个经过同行审查的地点,而用户提议不披露 agent 作者身份、拒绝和要求披露。

输出格式 :

返回双关口报告:
- **Sandbox 门判决** (PASS/BLOCK,附有理由陈述)
- **研究门判决** (包括实验审计(2)和波兰审计(3))(PASS/BLOCK/REQUIRES)_专家,附每张支票的笔记)
- **披露计划** (文字、文字、人类审查者名称)
- **释放决定** (释放/搁置/拒绝)
- **下一个行动** (谁做什么,当)
