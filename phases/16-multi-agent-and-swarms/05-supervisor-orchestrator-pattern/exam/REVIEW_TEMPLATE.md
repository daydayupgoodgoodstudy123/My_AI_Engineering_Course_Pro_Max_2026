# LeadSynth 复盘

日期/用时/实际命令：

|关|观察到的失败与根因|修改与证据|使用的提示|未完成|
|---|---|---|---|---|
|1窄artifact/cap/median||||
|2content与assignment||||
|3显式矛盾与来源||||
|4worker/lead领域块||||
|5scope/budget/provenance||||

复述：source id与worker id为何不同？预算耗尽的冲突还在哪里？P1完成后P3有哪些独立职责？GIVEN driver证明什么，候选实现什么？同一query重存后应保留哪些assignment？空summary与缺答如何区分？来源顺序与leaf原scope顺序是否保留？

这套题证明了什么，没证明什么：写出具体fixture证据；未观察写未观察。不能将本地结果写成真实LLM质量、研究收益或线程取消能力。

本机完整业务校准：11500个真实封口worker观察，完整输出核验在timer内。3慢3快双10.7855×/9.6082×、maxslow2.9441s；不外推真实worker执行或研究收益。
