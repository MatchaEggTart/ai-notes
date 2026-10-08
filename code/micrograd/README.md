# micrograd

Karpathy 的 [micrograd](https://github.com/karpathy/micrograd)（MIT License）——
一个一百多行的纯 Python 自动求导引擎，可以看作 PyTorch `autograd` 的「儿童版」。
PyTorch 的心脏是什么样，这里就是缩小版。

本目录的用途：**读懂它，然后自己重写一遍。**

## 文件

| 文件 | 是什么 |
| --- | --- |
| `engine.py` | 原件。核心，94 行，逐段读的就是它 |
| `nn.py` | 原件。在 engine 上搭出来的 MLP（阶段 1 后半段读） |
| `test_engine.py` | 原件。官方自测，最终用来验收自己重写的版本 |
| `01_derivative.py` | 练习。数值求导 + 链式法则——**读 engine 之前先跑这个** |

`engine.py` / `nn.py` / `test_engine.py` 是**照抄不改**的原作，方便对照视频；
自己写的代码另起文件名。

> 原件里 `from micrograd.engine import Value` 这种导入依赖完整包结构，直接跑会报错；
> 那是给自己重写版本做验收时才要处理的事，先不用管。

## 三步读法

1. **读**：逐段过 `engine.py`，把自己猜错的、看不懂的记下来（卡点）；
2. **重写**：合上原件，自己写一份能跑通的版本；
3. **验收**：用 `test_engine.py` 跑自己写的那份。

## 跑

```bash
cd ~/Workspace/Notes/ai-notes/code
uv run python micrograd/01_derivative.py
```
