"""读 engine.py 之前：用数字把「导数」和「链式法则」看一遍。

不做数学推导，只做两件事——把导数算出来看，把链式法则验证一遍。

运行：uv run python micrograd/01_derivative.py
"""


def f(x):
    """f(x) = 3x^2 - 4x + 5"""
    return 3 * x**2 - 4 * x + 5


def numerical_derivative(func, x, h=1e-6):
    """用中心差分近似导数：(f(x+h) - f(x-h)) / 2h。

    导数的定义是 lim(h->0) (f(x+h) - f(x)) / h，
    这里用中心差分（左右各取一点）比单边更准。
    """
    return (func(x + h) - func(x - h)) / (2 * h)


def show_derivative():
    print("=== 1. 导数是什么 ===")
    print("f(x) = 3x^2 - 4x + 5")
    print(f"{'x':>5} {'f(x)':>10} {'数值导数':>14} {'手推 6x-4':>16}")
    for x in [-2, -1, 0, 1, 2, 3]:
        print(f"{x:>5} {f(x):>10.3f} {numerical_derivative(f, x):>14.6f} {6 * x - 4:>16.1f}")
    print()
    print("两列应该几乎相同 —— 这就是「导数」，grad 存的就是它。")


def g(x):
    """内层函数"""
    return 3 * x**2 - 4 * x + 5


def h(u):
    """外层函数"""
    return u**3


def composed(x):
    """z = h(g(x))"""
    return h(g(x))


def show_chain_rule():
    print()
    print("=== 2. 链式法则 ===")
    print("z = h(g(x))，其中 h(u) = u^3，g(x) = 3x^2 - 4x + 5")
    print("链式法则说：dz/dx = h'(g(x)) * g'(x)")
    print()
    print(f"{'x':>5} {'g(x)':>10} {'z':>14} {'数值 dz/dx':>12} {'链式法则':>12}")
    for x in [-1, 0, 1, 2]:
        gx = g(x)
        chain = 3 * gx**2 * (6 * x - 4)     # h'(u)=3u^2, g'(x)=6x-4
        print(f"{x:>5} {gx:>10.3f} {composed(x):>14.3f} {numerical_derivative(composed, x):>12.3f} {chain:>12.3f}")
    print()
    print("两列同样应该相同 —— 复杂函数的导数，是「一层层乘起来」的。")


if __name__ == "__main__":
    show_derivative()
    show_chain_rule()
