"""Conservative segment-level repairs for known technical MT mistranslations.

``refine(source_prepared_segment, translated_segment, phase='')`` uses visible,
explicit English triggers. It never decodes a protected placeholder, guesses
what a placeholder means, or edits a document as a whole. This is a limited
post-edit dictionary, not a claim that the resulting translation was reviewed.
"""

from __future__ import annotations

from collections import Counter
import re


_KEEP_RE = re.compile(r"ZXKEEP\d+QXZ")
_HEADINGS = {
    "Learning Objectives": "学习目标",
    "The Problem": "问题",
    "The Concept": "概念",
    "Build It": "动手实现",
    "Use It": "使用现有工具",
    "Verify It": "验证",
    "Practice Lab": "练习实验",
    "Interactive Lab": "交互式实验",
    "Shipped Artifact": "交付成果",
    "Key Terms": "关键术语",
    "Common Mistakes": "常见错误",
    "Code Walkthrough": "代码讲解",
    "Run It": "运行示例",
    "Capstone Connection": "与综合项目的联系",
}


def _phase_number(phase: str) -> int | None:
    match = re.search(r"(?:^|[/\\])(?:phase[-_ ]*)?(\d{1,2})(?:[-_/\\]|$)", str(phase), re.I)
    return int(match.group(1)) if match else None


def _replace_visible(text: str, replacements: dict[str, str]) -> str:
    """Apply known Chinese repairs only between untouched placeholder tokens."""
    if not replacements:
        return text
    pattern = re.compile("|".join(re.escape(key) for key in sorted(replacements, key=len, reverse=True)))
    output: list[str] = []
    last = 0
    for match in _KEEP_RE.finditer(text):
        output.append(pattern.sub(lambda found: replacements[found.group()], text[last:match.start()]))
        output.append(match.group())
        last = match.end()
    output.append(pattern.sub(lambda found: replacements[found.group()], text[last:]))
    return "".join(output)


def _model_repair(source: str, target: str, name: str, wrong: tuple[str, ...]) -> str:
    """Repair a model name beside a provider/version, or in a short name cell."""
    if not re.search(r"\b" + re.escape(name) + r"\b", source):
        return target
    pattern = "(?:" + "|".join(re.escape(word) for word in wrong) + ")"
    prefix = r"(?:ZXKEEP\d+QXZ|Claude|GPT(?:[- .\w]*)?|Gemini|Qwen[\w.-]*|克劳德)"
    # Captured provider placeholders are emitted byte-for-byte, never edited.
    target = re.sub(
        r"(" + prefix + r"[ \t\d.-]*)" + pattern,
        lambda match: match.group(1).rstrip() + " " + name,
        target,
    )
    target = re.sub(pattern + r"[ \t]*(?=\d+(?:\.\d+)?)", name + " ", target)
    target = re.sub(re.escape(name) + r"(?=\d)", name + " ", target)
    visible = _KEEP_RE.sub("", source).strip(" \t-0123456789.")
    if visible == name:
        target = _replace_visible(target, {word: name for word in wrong})
    return target


def refine(source_prepared_segment: str, translated_segment: str, phase: str = "") -> str:
    """Repair established mistranslations with segment-scoped English evidence.

    ``phase`` may be ``'09'``, a phase directory name, or a repository path. RL
    policy/state rules apply in Phase 09; Phases 10/11 additionally require a
    visible reinforcement-learning cue. Placeholder contents are never used.
    """
    if not isinstance(source_prepared_segment, str) or not isinstance(translated_segment, str):
        raise TypeError("refine requires source and translated strings")
    source = source_prepared_segment
    target = translated_segment
    tokens_before = Counter(_KEEP_RE.findall(target))
    # Fully visible, exact headings only. No token-bearing heading is guessed.
    if source.strip() in _HEADINGS and not _KEEP_RE.search(source):
        leading = re.match(r"\s*", target).group()
        trailing = re.search(r"\s*$", target).group()
        target = leading + _HEADINGS[source.strip()] + trailing
    visible = _KEEP_RE.sub(" ", source)
    phase_number = _phase_number(phase)

    def has(pattern: str, flags: int = re.I) -> bool:
        return bool(re.search(pattern, visible, flags))

    repairs: dict[str, str] = {}
    # Terminal tools: exact English words, never a phrase inferred from a token.
    if has(r"\bterminals?\b"):
        repairs.update({"终点站": "终端", "端子": "终端"})
    if has(r"\bshells?\b"):
        repairs.update({"壳牌": "Shell", "外壳": "Shell"})
    if has(r"\b(?:pipes?|piping)\b"):
        repairs["管材"] = "管道"
    if has(r"\btmux\b"):
        repairs["多路复用器"] = "tmux"
    if has(r"\bnohup\b"):
        repairs["诺哈普"] = "nohup"

    # Explicit ML collocations distinguish technical training from training
    # employees, and statistical bias from social prejudice.
    if has(r"\btraining\s+(?:data|datasets?|pipelines?|loops?|runs?|jobs?|steps?|sets?|loss|samples?|examples?|batches|epochs?)\b|\bmodels?\s+(?:are\s+|is\s+)?trained\b"):
        repairs["培训"] = "训练"
    if has(r"\b(?:notebook|kernel|Jupyter|ghost\s+cell|code\s+cell|markdown\s+cell)\b") and has(r"\bcells?\b"):
        repairs["电池"] = "单元格"
    if has(r"\bopen[- ]weights?\b"):
        repairs.update({"开放重量": "开放权重", "开源重量": "开放权重"})
    if has(r"\bweight\s+decay\b"):
        repairs["重量"] = "权重"
    if has(r"\bcheckpoints?\b"):
        repairs["检查站"] = "检查点"
    if has(r"\bepochs?\b") and (phase_number is not None and 2 <= phase_number <= 11):
        repairs.update({"纪元": "epoch", "时代": "epoch"})
    if has(r"\bloss(?:es)?\b") and (
        phase_number is not None and 2 <= phase_number <= 11
        or has(r"\b(?:training|validation|test)\s+loss\b|\bloss\s+(?:function|gradient|value)\b")
    ):
        repairs["亏损"] = "损失"
    if has(r"\bmargin\b") and (
        has(r"\b(?:decision\s+boundary|classifier|support\s+vector|SVM)\b")
        or phase_number == 3 and has(r"\b(?:narrow|wide|wider|large|small|maximum)\s+margin\b")
    ):
        repairs.update({"利润率": "间隔", "利润": "间隔", "边距": "间隔", "余量": "间隔"})
        if has(r"\bviolations?\b"):
            repairs["违法行为"] = "违反约束"
    if has(r"\bbias\b") and has(r"\bvariance\b|\bbias\s+(?:dominates|term|parameter)|\b(?:high|low)\s+bias\b"):
        repairs["偏见"] = "偏差"
    if has(r"\bindividual\s+variances\b"):
        repairs["个体差异"] = "个体方差"
    metric_context = has(r"\bprecision\s*[,/]\s*recall\b|\brecall\s*[,/]\s*precision\b|\bF1\b|\bconfusion\s+matrix\b")
    if metric_context and has(r"\bprecision\b"):
        repairs["精度"] = "精确率"
    if metric_context and has(r"\brecall\b"):
        repairs["回忆"] = "召回率"
    if has(r"\bregularization\b"):
        repairs["正规化"] = "正则化"
    if has(r"\bTensorBoard\b", 0):
        repairs["张量板"] = "TensorBoard"
    if has(r"\blog[- ]derivative\b"):
        repairs["日志导数"] = "对数导数"
    if has(r"\blog\s+loss\b"):
        repairs["日志损失"] = "对数损失"
    if has(r"\bgradient\s+(?:descent|norm|clipping|update)\b"):
        repairs["坡度"] = "梯度"
    if has(r"\bno\s+fitting\b"):
        repairs["没有合适的"] = "无需拟合"
    if has(r"\bremote\s+(?:machine|server|host)\b|\bgit\s+remote\b"):
        repairs["遥控器"] = "远程"

    # Observed acronym/brand mistranslations. Explicit expansions and mixed
    # ordinary meanings make the segment ambiguous, so those stay untouched.
    whisper_brand = has(r"\bWhisper\b", 0)
    ordinary_whisper = has(r"\bwhisper\b", 0) or has(
        r"\bWhisper\s+(?:quietly|softly|to\b|a\s+secret|in\s+(?:my|your|their)\s+ear)"
    )
    if whisper_brand and not ordinary_whisper:
        repairs["耳语"] = "Whisper"
    if has(r"\bMTP\b", 0) and not has(r"\b(?:medium|mid)[- ]term\s+plans?\b"):
        repairs["中期计划"] = "MTP"
    agency_context = has(
        r"\bNational\s+Security\s+Agency\b|\b(?:government|surveillance|intelligence\s+agency|classified\s+documents)\b"
    )
    if has(r"\bNSA\b", 0) and not agency_context:
        repairs.update({"国家安全局": "NSA", "国安局": "NSA"})
    if has(r"\bGQA\b", 0) and not has(r"\bglobal\s+quality\s+assessment\b"):
        repairs["全球质量评估"] = "GQA"
    gas_context = has(r"\bgas[- ]phase\b|\bgaseous\b|\bgas\s+chromatography\b")
    if has(r"\bschemas?\b") and not gas_context:
        repairs.update({"气相图": "Schema", "气相": "Schema"})
    if has(r"\bFlash[- ]Attention\b"):
        repairs.update({"闪存注意力": "Flash Attention", "闪光注意力": "Flash Attention"})
    if has(r"\bretrieval[- ]augmented[- ]generation\b"):
        repairs["回收提款一代"] = "Retrieval-Augmented Generation"
    if has(r"\bcapstones?\b") and not has(r"\b(?:vertex|vertices|apex|apices)\b"):
        repairs.update({"顶点项目": "综合项目", "顶点": "综合项目"})
    ordinary_norm = has(r"\b(?:social|cultural|ethical|societal)\s+norms?\b")
    if (phase_number == 1 and has(r"\bnorms?\b")
            and not has(r"\bstandard\w*\b") and not ordinary_norm):
        repairs["标准"] = "范数"
    keyboard_context = has(
        r"\b(?:keyboard|keybindings?|key[- ]bindings?|shortcuts?|keystrokes?|hotkeys?|arrow|press|Ctrl|Alt|Cmd|Option)\b"
    )
    dictionary_context = has(r"\b(?:dictionar\w*|mappings?|hash\s+maps?|JSON|object\s+keys)\b")
    credential_keys = has(
        r"\b(?:SSH|API|public|private|secret|encryption|cryptographic|signing|authentication|credential|access)\s+(?:[\w-]+\s+)?keys\b"
        r"|\bkeys\s+(?:for\s+)?(?:SSH|encryption|authentication)\b"
    )
    if phase_number == 0 and has(r"\bkeys\b") and keyboard_context and not dictionary_context and not credential_keys:
        repairs.update({
            "方向钥匙": "方向键", "方向密钥": "方向键",
            "快捷钥匙": "快捷键", "快捷密钥": "快捷键",
            "钥匙": "按键", "密钥": "按键",
        })

    # Phase-limited RL repairs avoid administrative policies and U.S. states.
    rl_cue = has(r"\b(?:reinforcement|RLHF|PPO|DPO|REINFORCE|Markov|Bellman|reward|rewards|environment|trajectory|trajectories|actor|critic)\b|\b(?:policy\s+gradient|state\s+value|on-policy|off-policy)\b")
    rl_context = phase_number == 9 or phase_number in {10, 11} and rl_cue
    if rl_context:
        if has(r"\bstates?\b"):
            repairs["国家"] = "状态"
        admin_policy = has(r"\b(?:privacy|security|organizational|company|access|content|data|retention|approval|governance)\s+polic(?:y|ies)\b")
        if has(r"\bpolic(?:y|ies)\b") and not admin_policy:
            repairs["政策"] = "策略"
        if has(r"\bcritics?\b"):
            repairs.update({"批评家": "critic", "评论家": "critic"})
        if has(r"\brewards?\b"):
            repairs.update({"报酬": "奖励", "酬劳": "奖励"})

    # A few demonstrated idioms have unambiguous technical English triggers.
    if has(r"\bspecific\s+beats\s+vague\b"):
        repairs.update({"特定节拍模糊": "具体优于模糊", "具体节拍模糊": "具体优于模糊"})
    if has(r"\btable\s+stakes\b"):
        repairs["赌注"] = "基本要求"
    if has(r"\bstill\s+off\b"):
        repairs["仍然关闭"] = "仍然不够准确"
    if has(r"\bdiscipline\s+of\b|\blarger\s+discipline\b|\bengineering\s+discipline\b"):
        repairs["纪律"] = "学科"
    if has(r"\bunder\s+the\s+hood\b"):
        repairs["引擎盖下"] = "底层"
    target = _replace_visible(target, repairs)

    # Capitalization is intentional: the common words opus/sonnet/flash do not
    # establish a model name. Provider/version adjacency handles model cells.
    for name, wrong in (
        ("Opus", ("作品",)),
        ("Sonnet", ("十四行诗",)),
        ("Flash", ("闪存", "闪光")),
    ):
        target = _model_repair(source, target, name, wrong)
    # mini and Max need extra model evidence; Max entropy/Max norm stay intact.
    model_prefix = r"(?:ZXKEEP\d+QXZ|GPT[\w.-]*|Claude|Gemini|Qwen[\w.-]*|o[1-9][\w.-]*)"
    ordinary_mini = has(r"\bmini[- ](?:batch(?:es)?|projects?|examples?|demos?|courses?|benchmarks?|tutorials?|exercises?)\b")
    ordinary_max = has(r"\bMax\s+(?:entropy|norm|pool(?:ing)?|length|tokens?|iterations?|steps?|values?|size|depth|retries|count|memory|output|context|capacity|workers?|threads?|limit|utilization|concurrent|temperature|score|probability|range|heap|flow|sum)\b")
    if not ordinary_mini and re.search(model_prefix + r"[ \t\d.-]*\bmini\b", source):
        target = _model_repair(source, target, "mini", ("迷你",))
    if not ordinary_max and re.search(model_prefix + r"[ \t\d.-]*\bMax\b", source):
        target = _model_repair(source, target, "Max", ("最大",))
    if Counter(_KEEP_RE.findall(target)) != tokens_before:
        raise ValueError("Post-edit unexpectedly changed protected placeholders")
    return target


def self_test() -> None:
    token = "ZXKEEP00000012QXZ"
    fixtures = [
        ("Learning Objectives", "学习目的", "", "学习目标"),
        ("Use It", "使用它", "", "使用现有工具"),
        ("Open the terminal", "打开端子", "00", "打开终端"),
        ("shell piping", "外壳管材", "00", "Shell管道"),
        ("Use tmux and nohup", "使用多路复用器和诺哈普", "00", "使用tmux和nohup"),
        (token + " Opus 4.7", token + " 作品 4.7", "11", token + " Opus 4.7"),
        (token + " Sonnet 4.6", token + "十四行诗4.6", "11", token + " Sonnet 4.6"),
        (token + " 3 Flash", token + " 3闪存", "11", token + " 3 Flash"),
        (token + "-5 mini", token + "-5迷你", "11", token + "-5 mini"),
        ("Qwen3 Max", "Qwen3最大", "11", "Qwen3 Max"),
        ("Max entropy", "最大熵", "03", "最大熵"),
        (token + "Max norm" + token, token + "最大范数" + token, "03", token + "最大范数" + token),
        ("A mini batch", "一个迷你批次", "05", "一个迷你批次"),
        (token + "mini batch" + token, token + "迷你批次" + token, "05", token + "迷你批次" + token),
        ("State values use a reward policy and critic", "国家价值使用报酬政策和批评家", "09-reinforcement-learning", "状态价值使用奖励策略和critic"),
        ("states and policy", "国家与政策", "11", "国家与政策"),
        ("reward policy", "报酬政策", "phases/11-llm-engineering/docs/en.md", "奖励策略"),
        ("security policy", "安全政策", "09", "安全政策"),
        ("The country's states", "这个国家的州", "12", "这个国家的州"),
        ("training pipelines", "培训管道", "00", "训练管道"),
        ("employee training", "员工培训", "18", "员工培训"),
        ("a notebook ghost cell", "笔记本幽灵电池", "00", "笔记本幽灵单元格"),
        ("weight" + token + "decay", "重量" + token + "衰减", "03", "权重" + token + "衰减"),
        ("Loss explodes", "亏损爆炸", "03", "损失爆炸"),
        ("A financial loss", "财务亏损", "18", "财务亏损"),
        ("bias dominates", "偏见占主导", "03", "偏差占主导"),
        ("gender bias", "性别偏见", "03", "性别偏见"),
        ("precision, recall, F1", "精度、回忆、F1", "03", "精确率、召回率、F1"),
        ("half precision", "半精度", "05", "半精度"),
        ("regularization", "正规化", "03", "正则化"),
        ("Specific Beats Vague", "特定节拍模糊", "11", "具体优于模糊"),
        ("It became table stakes", "它变成了赌注", "11", "它变成了基本要求"),
        ("Whisper's input", "耳语的输入", "06", "Whisper的输入"),
        ("ASR (Whisper, Parakeet)", "ASR（耳语、Parakeet）", "06", "ASR（Whisper、Parakeet）"),
        ("Please whisper quietly", "请轻声耳语", "06", "请轻声耳语"),
        ("Whisper softly to a friend", "对朋友轻声耳语", "06", "对朋友轻声耳语"),
        ("Whisper transcribes a whisper", "Whisper转录耳语", "06", "Whisper转录耳语"),
        ("MTP prediction heads", "中期计划预测头", "05", "MTP预测头"),
        ("Medium-term plan (MTP)", "中期计划（MTP）", "18", "中期计划（MTP）"),
        ("NSA uses sparse attention", "国安局使用稀疏注意力", "05", "NSA使用稀疏注意力"),
        ("NSA kernels", "国家安全局内核", "05", "NSA内核"),
        ("National Security Agency (NSA)", "国家安全局（NSA）", "18", "国家安全局（NSA）"),
        ("NSA surveillance documents", "国安局的监控文件", "18", "国安局的监控文件"),
        ("GQA groups", "全球质量评估组", "07", "GQA组"),
        ("Global Quality Assessment (GQA)", "全球质量评估（GQA）", "18", "全球质量评估（GQA）"),
        ("Schema Validation", "气相校验", "13", "Schema校验"),
        ("Name and schema input payload", "名称和气相图输入载荷", "13", "名称和Schema输入载荷"),
        ("schema for a gas-phase reaction", "气相反应的schema", "01", "气相反应的schema"),
        ("Flash Attention", "闪存注意力", "07", "Flash Attention"),
        ("Flash-Attention", "闪光注意力", "07", "Flash Attention"),
        ("Flash storage requires attention", "闪存需要注意力", "00", "闪存需要注意力"),
        ("retrieval-augmented generation", "回收提款一代", "11", "Retrieval-Augmented Generation"),
        ("retrieval augmented generation", "回收提款一代", "11", "Retrieval-Augmented Generation"),
        ("A capstone project", "一个顶点项目", "19", "一个综合项目"),
        ("The capstone connects graph vertices", "顶点项目连接图顶点", "19", "顶点项目连接图顶点"),
        ("A capstone near the apex", "顶点接近最高点", "19", "顶点接近最高点"),
        ("Compute vector norms", "计算向量标准", "01", "计算向量范数"),
        ("norm and standard deviation", "范数和标准差", "01", "范数和标准差"),
        ("standardize the norm", "标准化范数", "01", "标准化范数"),
        ("Compute vector norms", "计算向量标准", "02", "计算向量标准"),
        ("social norms", "社会标准", "01", "社会标准"),
        ("Press the arrow keys", "按方向钥匙", "00", "按方向键"),
        ("Keyboard shortcut keys", "键盘快捷密钥", "00", "键盘快捷键"),
        ("Press keys to inspect a dictionary", "按键检查字典密钥", "00", "按键检查字典密钥"),
        ("Press keys to create SSH keys", "按键创建SSH密钥", "00", "按键创建SSH密钥"),
        ("API keys", "API密钥", "00", "API密钥"),
        ("private keys for authentication", "用于认证的私钥与密钥", "00", "用于认证的私钥与密钥"),
        ("Press the arrow keys", "按方向钥匙", "01", "按方向钥匙"),
        ("MTP " + token + " NSA", "中期计划" + token + "国家安全局", "05", "MTP" + token + "NSA"),
    ]
    for source, target, phase, expected in fixtures:
        result = refine(source, target, phase)
        assert result == expected, (source, target, result, expected)
        assert Counter(_KEEP_RE.findall(result)) == Counter(_KEEP_RE.findall(target))
        assert refine(source, result, phase) == result, ("not idempotent", source)
    print(f"local_zh_postedit: {len(fixtures)} self-tests passed")


if __name__ == "__main__":
    self_test()
