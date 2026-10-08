# AI 学习路线

> **目标**:理解原理(**L2**),兴趣驱动,**自下而上**。
> **起点**:会 Java / TypeScript / React / SQL / Shell;数学学过但已遗忘(当年法语教学);
> Python 能读代码,缺的只是 numpy / 张量思维。
> **节奏**:每天约 4 小时。

## 0. 成功标准(L2)

学完应能做到:

1. 手写一个自动求导引擎 + 一个两层神经网络,并解释每一步梯度从哪来;
2. 手写 self-attention,讲清 Q / K / V、causal mask、位置编码;
3. 从零写出一个能训练的 mini-GPT,并在本机(RTX 5080 16G)上跑通;
4. 读懂 Transformer 原始论文,并复现一篇现代改进(RoPE / GQA / DPO 之一);
5. 讲清一条训练样本从 tokenizer → loss → 参数更新的完整链路。

**不做的**:不追求手推通用数学证明;不做产品级应用(属选修)。

## 1. 起点现实检查

| 维度 | 现状 | 影响 |
| --- | --- | --- |
| 编程 | Java / TS / React / SQL / Shell | Python 迁移成本极低 |
| Python 读码 | 已实测:导入 / 函数 / 类 / 调用都能读对 | 补一张 dunder 表即可 |
| 真正的新门槛 | numpy 广播 + 张量形状思维 | 阶段 1 末到阶段 2 集中补 |
| 数学 | 学过、遗忘,**且是法语教学** | 需要「概念唤醒 + 中英术语桥」 |
| 英语 | 待实战 | AI 资源以英文为主,但术语量不大 |

> 关于「辍学生」:这条路线不设学历门槛,唯一标准是能不能读懂、能不能实现。

## 2. 数学怎么补(AI 版最小集)

**不做系统数学课。** 只补阶段 1–2 会反复用到的四块:

- **链式法则** —— 反向传播的地基
- **矩阵乘法与形状** —— 张量运算
- **指数 / 对数 / softmax** —— 概率输出
- **期望 / 条件概率** —— 损失与采样的直觉

**补法**:

- 先花 **2–4 天**看 3Blue1Brown 的《Essence of Linear Algebra》与《Essence of Calculus》选集(开字幕,可 0.75x);
- 之后**完全按需**,卡住才补,不再专门安排数学时间;
- 法语遗忘不是障碍:概念还在,只是换了语言。用下面的术语桥把「法语概念」接回「英文术语」。

### 中 / 英 / 法 术语桥

| 中文 | English | Français |
| --- | --- | --- |
| 导数 / 求导 | derivative / differentiate | dérivée / dériver |
| 偏导数 | partial derivative | dérivée partielle |
| 链式法则 | chain rule | règle de dérivation en chaîne |
| 梯度 | gradient | gradient |
| 矩阵 | matrix | matrice |
| 矩阵乘法 | matrix multiplication | produit matriciel |
| 向量 | vector | vecteur |
| 点积 / 内积 | dot product / inner product | produit scalaire |
| 转置 | transpose | transposée |
| 指数函数 | exponential | exponentielle |
| 对数 | logarithm | logarithme |
| 求和 | summation | somme |
| 最大值 | maximum | maximum |
| 均值 | mean | moyenne |
| 方差 | variance | variance |
| 标准差 | standard deviation | écart-type |
| 概率 | probability | probabilité |
| 条件概率 | conditional probability | probabilité conditionnelle |
| 期望 | expectation | espérance |

> 这是一张**活表**:遇到新术语就往上加。

## 3. 阶段路线

| 阶段 | 时间 | 主线 | 验收标准 |
| --- | --- | --- | --- |
| 0. 适配 | ~1 周 | Python 迁移 + 环境 + 数学轻打底 | 能读懂并手改 numpy / torch 代码 |
| 1. 反向传播 | 2–4 周 | micrograd + makemore | 不看源码写出能跑的自动求导 + 两层 MLP |
| 2. Attention / Transformer | 5–8 周 | "Let's build GPT" | 手写 attention,讲清 Q/K/V,能读原论文 |
| 3. 2017 → 今天 | 9–12 周 | 现代组件 + 后训练 | 画出演进展图,说清每个改动解决什么 |
| 4. 结课 | 13–16 周 | mini-GPT + 复现一篇改进 | 能从原理讲到实现 |

### 阶段 0 —— 适配(约 1 周)

- **Python 迁移**:缩进、推导式、切片、`with`、`*args / **kwargs`、dunder 表;
- **环境**:`uv` + Python 3.12 / 3.13 的 venv + PyTorch (CUDA)
  - ⚠️ 本机 Python 是 3.14,ML 生态通常滞后,**大概率要另建 3.12 / 3.13 环境**,到时现验;
- **数学**:见上节,2–4 天。

### 阶段 1 —— 反向传播(2–4 周)

主线:*Karpathy《Neural Networks: Zero to Hero》* 前两章。

- **micrograd**:纯 Python 手写自动微分 + 一个 MLP;
- **makemore**:bigram → MLP → 训练循环 / loss / batch / 过拟合 / 正则 / 初始化。

### 阶段 2 —— Attention 与 Transformer(5–8 周)

主线:同系列 **"Let's build GPT"**。

- bigram → self-attention → multi-head → 完整 GPT;
- 在本机训练一个 char-level 模型(如 tinyshakespeare)。

### 阶段 3 —— 从 2017 到现在(9–12 周)

- 原始论文:*Attention Is All You Need*;
- 图解:*The Illustrated Transformer*;
- 现代组件:RoPE、RMSNorm、SwiGLU、KV cache、GQA、MoE、BPE;
- 后训练大图:SFT / RLHF / DPO;
- 对照实现:nanoGPT、LLaMA。

### 阶段 4 —— 结课(13–16 周)

- **必做**:mini-GPT 本机跑通;
- **L2 证明**:复现一篇现代改进(RoPE / GQA / DPO 之一);
- **选修**:QLoRA 微调小模型 / mini-RAG。

## 4. 节奏(每天 4h)

| 时长 | 内容 |
| --- | --- |
| 3h | 主线:跟课 + 写代码 + 调试 |
| 0.5h | 阅读(视频 / 文档 / 论文) |
| 0.5h | 笔记 |

## 5. 笔记规范

**原则**:可检索的知识不记;你的处境、卡点、决策、实验数字才记。

每条笔记至少包含:

- **卡点 / 误判**,例:「我以为 `__init__` 是私有方法 → 其实是构造函数」;
- **亲手跑出来的结果**(数字、loss 曲线);
- **用自己的话讲一遍**的概念(L2 的标准);
- **能跑的代码 + 一句「为什么这么写」**。

**检验**:一个月后回看,能否只看笔记重建理解 / 直接跑起来。

**格式**:自己手写用 `.org`;AI 生成 / 整理的用 `.md`(见 README)。
