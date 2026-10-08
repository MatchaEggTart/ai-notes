"""环境自检：确认 PyTorch + CUDA 可用，并且真能在 GPU 上算。

在 code/ 目录里跑：uv run python env_check.py
"""

import numpy as np
import torch


def main() -> None:
    print("torch:", torch.__version__)
    print("numpy:", np.__version__)
    print("CUDA 可用:", torch.cuda.is_available())
    if not torch.cuda.is_available():
        raise SystemExit("CUDA 不可用：检查驱动，或装成了 CPU 版 torch")

    print("显卡:", torch.cuda.get_device_name(0))
    print("算力: sm_%d%d" % torch.cuda.get_device_capability(0))
    print("显存: %.1f GB" % (torch.cuda.get_device_properties(0).total_memory / 1024**3))

    # 真算一次：4096x4096 矩阵乘
    a = torch.randn(4096, 4096, device="cuda")
    b = torch.randn(4096, 4096, device="cuda")
    c = a @ b
    torch.cuda.synchronize()
    print("矩阵乘结果:", tuple(c.shape), c.device)


if __name__ == "__main__":
    main()
