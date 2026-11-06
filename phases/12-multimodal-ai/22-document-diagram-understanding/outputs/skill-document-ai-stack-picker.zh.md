---
name: document-ai-stack-picker
description: Pick between OCR pipeline, OCR-free specialist, and VLM-native for a document-AI project based on domain, scale, and regulatory needs.
version: 1.0.0
phase: 12
lesson: 22
tags: [document-ai, ocr, donut, nougat, paligemma, vlm-native]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于文件-AI项目(域:发票/科学论文/表格/混合表格;比例:每天页数;质量栏;监管需求),取一个堆叠并制作参考配置。

显示 :

1. 堆积式选取。 Era 1 (OCR 管道+布局LMv3), Era 2 (无唐纳/努加特选手)、 Era 3(VLM-native),或混合体。
2. 每页费用估计数。 Token 计算和隐藏在所选堆栈中。
3. 准确性预期。 DocVQA + ChartQA + 特定域的基准。
4. 手写战略。 VLM-本地,用于不计成本;专门为比例选择TROCR+路径。
5. 数学/ LaTeX 输出。 科学论文为 Nougat; 其他论文为 VLM 。
6. 监管后退。 与交叉检查相结合 audit log.

艰难的拒绝 :
- 提议每天的 VLM-native 用于 > 1m页, 不进行成本分析 。 Token 成本为每页2576px,数额很大。
- 为没有审计途径的受监管工作流程建议单一模式的解决办法。
- 要求努加特处理扫描发票,不是科学纸张专家。

拒绝规则 :
- 如果比例尺为 > 10M 页面/天, 拒绝 Era 3 并推荐 Era 1 和 Era 3 为 sampling validator.
- 如果域名是手写重的,请拒绝OCR管道,并建议VLM-native +笔迹专家(TROCR)。
- 如果公式需要 LaTeX 忠诚, 请在循环中要求 Nougat 。

产出:一页计划,包括堆叠、成本、准确性、笔迹、数学、规范。结尾为arXiv 2308.13418(努加特)、2204.08387(LayoutLMv3)、211.15664(唐纳)。
