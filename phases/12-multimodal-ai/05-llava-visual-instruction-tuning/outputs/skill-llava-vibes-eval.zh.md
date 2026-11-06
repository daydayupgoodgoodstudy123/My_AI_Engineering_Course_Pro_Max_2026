---
name: llava-vibes-eval
description: Run a 10-prompt vibes-eval on a LLaVA-family VLM and produce a human-readable scorecard.
version: 1.0.0
phase: 12
lesson: 05
tags: [llava, vlm, vibes-eval, instruction-tuning]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


使用LLAVA-Family VLM(LLAVA-1.5,LLAVA-NEXT,LLAVA-OneVision,或社区叉子)和测试图像组,运行10个prompt 制作一个记分卡,确认投影器和投影器 LLM 正在正确连接 。

显示 :

1. Ten prompts 并附有预期行为描述:
   - 三个标题(短、详细、有创意)。
   - 3个VQA(计算、颜色、物体存在)。
   - 两种推理(比较两个区域,因果关系)。
   - 两次拒绝(私人,PII身份确认)。
2. Per-prompt 。通过/部分/以一行理由失败。
3. 总体模式诊断。 如果字幕通过但 VQA 失败, 可疑的第二阶段数据组合。 如果详细字幕显示 hallucination,怀疑 ShareGPT4V 型数据不足。如果拒绝失败,则显示安全数据缺口。
4. 分辨率检查。运行一个 OCR 要求 prompt ,在336x336 基点,并在 AnyRes 中再次;注意三角洲。预计低频失败;高频失败意味着 AnyRes 配置错误。
5. 建议的后续行动。如果特定类别失败, 呼叫者可以使用三个具体的培训数据 。

艰难的拒绝 :
- 将 VLM 定位在基准数上, 而不同时运行感官套件。 基准可以被游戏; 感官会显示实际部署准备状态 。
- Conflating hallucination 具有文体动词。 具体指哪些物体是被发明的, 或只是被详细描述。
- 要求获得推理 prompts 而不是最后的答案

拒绝规则 :
- 如果打电话者要求感应器 - eval 一个专有的 VLM (VLM) (N)Gemini, Claude, GPT-5V)无 API 进入、拒绝——测试需要实际 inference.
- 如果目标使用案例是医学诊断或法律咨询,则拒绝——感觉-反常不是证明,不得用于高接触领域。
- 如果不提供图像,则拒绝——测试是按定义以图像为依据的。

产出:一个计分卡,有10行(prompt,图像,预期的,实际的,通过/部分/失败的,总体模式诊断,以及三项目后续列表。结尾处有一个“阅读下一步”段落,指向与分辨率有关的故障的12.06课(任何反射)或用于数据混合调控的12.07课(校正)。
