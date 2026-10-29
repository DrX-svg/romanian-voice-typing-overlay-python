"""Compare CPU C++ tensor operators with vectorized NumPy on 30 seconds of audio."""

import platform
from pathlib import Path
import statistics
import sys
import time

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import vt_dsp_torch as ops
from voice_typing_ro import dsp


def median_ms(operation):
    for _ in range(5):
        operation()
    samples = []
    for _ in range(50):
        start = time.perf_counter_ns()
        operation()
        samples.append((time.perf_counter_ns() - start) / 1e6)
    return statistics.median(samples)


def cpu_name():
    if sys.platform.startswith("linux"):
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    if sys.platform == "win32":
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    return platform.processor() or platform.machine()


def main():
    x = np.random.default_rng(42).normal(0, .1, 30 * 16000).astype(np.float32)
    x[:16000] = 0
    x[-16000:] = 0
    tensor = torch.from_numpy(x)
    operations = [
        ("frame_rms", lambda: dsp.frame_rms_numpy(x, 400, 160), lambda: ops.frame_rms(tensor, 400, 160)),
        ("trim_bounds", lambda: dsp.trim_bounds_numpy(x, 400, 160, -45, 3200), lambda: ops.trim_bounds(tensor, 400, 160, -45, 3200)),
        ("normalize_peak", lambda: dsp.normalize_peak_numpy(x, .9), lambda: ops.normalize_peak(tensor, .9)),
    ]

    def numpy_pipeline():
        rms = dsp.frame_rms_numpy(x, 400, 160)
        start, end = dsp.trim_bounds_numpy(x, 400, 160, -45, 3200)
        return rms, dsp.normalize_peak_numpy(x[start:end], .9)

    def cpp_pipeline():
        rms = ops.frame_rms(tensor, 400, 160)
        start, end = ops.trim_bounds(tensor, 400, 160, -45, 3200)
        return rms, ops.normalize_peak(tensor[start:end], .9)

    operations.append(("pipeline", numpy_pipeline, cpp_pipeline))
    print(f"CPU: {cpu_name()}")
    print(f"Platform: {platform.platform()}")
    print(f"Python: {platform.python_version()} | NumPy: {np.__version__} | Torch: {torch.__version__}")
    print("Input: 30 s, 16000 Hz, float32 | frame=400, hop=160 | warm-up=5, runs=50, median")
    print("Tensor views are prepared before timing; Python/C++ dispatch and output allocation are included.")
    print("| Operation | NumPy ms | C++ ms | NumPy/C++ |")
    print("| --- | ---: | ---: | ---: |")
    for name, numpy_op, cpp_op in operations:
        numpy_ms = median_ms(numpy_op)
        cpp_ms = median_ms(cpp_op)
        print(f"| {name} | {numpy_ms:.9f} | {cpp_ms:.9f} | {numpy_ms / cpp_ms:.9f} |")


if __name__ == "__main__":
    main()
