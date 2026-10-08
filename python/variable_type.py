# Python 的四种基本类型：int / float / str / bool
# 运行：python3 variable_type.py

# --- int：任意精度整数，四种进制字面量 ---
print("0b100 =", 0b100)      # 二进制 → 4
print("0o100 =", 0o100)      # 八进制 → 64
print("100   =", 100)        # 十进制
print("0x100 =", 0x100)      # 十六进制 → 256
print("2**100 =", 2 ** 100)  # 没有上限

# --- float：小数，支持科学计数法 ---
print("123.456   =", 123.456)
print("1.23456e2 =", 1.23456e2)  # = 123.456
print("0.1+0.2   =", 0.1 + 0.2)  # 不精确 → 0.30000000000000004

# --- str：单/双引号包裹的文本，两者等价 ---
print("hello", 'hello')

# --- bool：只有 True / False，但它其实是 int 的子类 ---
print(True, False, True + True)

# --- 查类型：type(x) 问的是对象，不是名字 ---
for v in (45, 123.456, "hello", True):
    print(v, "->", type(v).__name__)
