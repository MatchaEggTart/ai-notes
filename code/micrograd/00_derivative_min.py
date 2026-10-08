"""读 micrograd 需要的最小微积分 —— 只有「斜率」一个概念，加五条规则。

不用记公式，看数字。

运行：uv run python micrograd/00_derivative_min.py
"""


def slope(func, x, h=0.001):
    """func 在 x 处的斜率：x 挪一丁点，func 跟着挪多少。"""
    return (func(x + h) - func(x - h)) / (2 * h)


def part1_slope():
    print("=== 1. 导数 = 斜率 ===")
    print("把 f(x) 想成一条山路：横轴是「往前走了多远」，纵轴是「海拔」。")
    print("斜率 = 此刻再往前走一小步，海拔涨多快。")
    print()
    print("f(x) = x^2")
    print(f"{'x':>4} {'f(x)':>7} {'斜率':>9}")
    for x in range(5):
        print(f"{x:>4} {x**2:>7} {slope(lambda t: t**2, x):>9.4f}")
    print()
    print("→ 盯住 x 和斜率两列：斜率永远是 2x。")
    print("  「x^2 的导数是 2x」就是这么来的，不是背书背来的。")


def part2_rules():
    print()
    print("=== 2. micrograd 只需要这五条规则 ===")

    def check(label, func, x, rule_value):
        print(f"  {label:<24} x={x}   数值 {slope(func, x):>9.4f}   规则 {rule_value:>9.4f}")

    check("常数 → 0", lambda t: 7, 3, 0)
    check("x → 1", lambda t: t, 3, 1)
    check("x^3 → 3x^2", lambda t: t**3, 2, 3 * 2**2)
    check("x^2 + 3x → 2x+3", lambda t: t**2 + 3 * t, 2, 2 * 2 + 3)
    check("x^2 * x^3 → 5x^4", lambda t: t**2 * t**3, 2, 5 * 2**4)
    print()
    print("  每行「数值」和「规则」都对得上 —— 规则不是规定，是观察出来的。")


def g(x):
    return 3 * x**2 - 4 * x + 5


def h(u):
    return u**3


def part3_chain():
    print()
    print("=== 3. 链式法则：函数套函数 ===")
    print("z = h(g(x))，其中 h(u) = u^3，g(x) = 3x^2 - 4x + 5")
    print("规则：dz/dx = h'(g(x)) * g'(x)    （外层的导数 × 内层的导数）")
    print()
    print(f"{'x':>4} {'数值 dz/dx':>12} {'规则算出来':>12}")
    for x in [-1, 0, 1, 2]:
        gx = g(x)
        print(f"{x:>4} {slope(lambda t: h(g(t)), x):>12.4f} {3 * gx**2 * (6 * x - 4):>12.4f}")
    print()
    print("  又是两列吻合。复杂函数也不可怕——一层层乘起来就行。")


def part4_map():
    print()
    print("=== 4. 这五条规则，就是 engine.py 的那几行 ===")
    print()
    print("  数学                          engine.py")
    print("  --------------------------    ----------------------------------------")
    print("  导数（斜率）                   self.grad")
    print("  (f + g)' = f' + g'            __add__ 里的 _backward")
    print("  (f * g)' = f'*g + f*g'        __mul__ 里的 _backward")
    print("  (x^n)' = n*x^(n-1)            __pow__ 里的 _backward")
    print("  ReLU 的导数（要么0要么1）       relu() 里的 _backward")
    print("  链式法则                       backward()：拓扑排序后逐个调 _backward")
    print()
    print("  就这些。94 行代码里没有别的数学。")


if __name__ == "__main__":
    part1_slope()
    part2_rules()
    part3_chain()
    part4_map()
