# Romanian Voice Typing Overlay
# Copyright (C) 2026 DrX-svg
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import glob
import logging
import os
import site


def bootstrap_cuda_dll_paths(logger: logging.Logger | None = None) -> None:
    log = logger or logging.getLogger("voice_typing_ro")
    added = []
    seen = set()

    for site_dir in site.getsitepackages():
        pattern = site_dir + r"\nvidia\**\bin"
        for bin_dir in glob.glob(pattern, recursive=True):
            normalized = os.path.normcase(bin_dir)
            if normalized in seen:
                continue
            seen.add(normalized)
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
            added.append(bin_dir)

    log.info("CUDA DLL bootstrap complete. Added %d NVIDIA bin paths.", len(added))
