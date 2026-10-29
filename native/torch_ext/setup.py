from pathlib import Path
import sys

from setuptools import setup
from torch.utils.cpp_extension import BuildExtension, CppExtension

HERE = Path(__file__).resolve().parent

setup(
    name="vt_dsp_torch",
    version="0.1.0",
    ext_modules=[CppExtension(
        "vt_dsp_torch",
        sources=[str(HERE / "ops.cpp"), str(HERE.parent / "src/dsp.cpp")],
        include_dirs=[str(HERE.parent / "include")],
        extra_compile_args=["/O2", "/std:c++17"] if sys.platform == "win32" else ["-O3", "-std=c++17"],
    )],
    cmdclass={"build_ext": BuildExtension},
)
