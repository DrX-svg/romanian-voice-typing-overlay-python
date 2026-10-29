"""Offline recording DSP with a vectorized NumPy fallback."""

import logging
import operator

import numpy as np

try:
    import torch
    import vt_dsp_torch as _torch_ops
except ImportError:
    _torch_ops = None

_logger = logging.getLogger(__name__)


def backend() -> str:
    return "torch_cpp" if _torch_ops is not None else "numpy"


def _samples(x):
    x = np.asarray(x)
    if x.ndim != 1 or x.dtype not in (np.dtype("float32"), np.dtype("float64")):
        raise ValueError("Expected a 1-D float32 or float64 buffer")
    return np.ascontiguousarray(x)


def _frame_arguments(frame_len, hop):
    frame_len, hop = operator.index(frame_len), operator.index(hop)
    if frame_len <= 0 or hop <= 0:
        raise ValueError("frame_len and hop must be positive")
    return frame_len, hop


def frame_rms_numpy(x, frame_len, hop):
    x = _samples(x)
    frame_len, hop = _frame_arguments(frame_len, hop)
    if x.size < frame_len:
        return np.empty(0, dtype=x.dtype)
    windows = np.lib.stride_tricks.sliding_window_view(x, frame_len)[::hop]
    return np.sqrt(np.mean(windows * windows, axis=1) + x.dtype.type(1e-12))


def normalize_peak_numpy(x, target):
    x = _samples(x)
    peak = np.max(np.abs(x), initial=x.dtype.type(0))
    if peak < x.dtype.type(1e-8):
        return x.copy()
    return x * (x.dtype.type(target) / peak)


def trim_bounds_numpy(x, frame_len, hop, threshold_dbfs, pad_samples):
    x = _samples(x)
    pad_samples = operator.index(pad_samples)
    if pad_samples < 0:
        raise ValueError("pad_samples must be nonnegative")
    rms = frame_rms_numpy(x, frame_len, hop)
    voiced = np.flatnonzero(20 * np.log10(rms) >= x.dtype.type(threshold_dbfs))
    if not voiced.size:
        return 0, 0
    return (
        max(0, int(voiced[0]) * hop - pad_samples),
        min(x.size, int(voiced[-1]) * hop + frame_len + pad_samples),
    )


def frame_rms(x, frame_len, hop):
    if _torch_ops is None:
        return frame_rms_numpy(x, frame_len, hop)
    return _torch_ops.frame_rms(torch.from_numpy(_samples(x)), frame_len, hop).numpy()


def normalize_peak(x, target):
    if _torch_ops is None:
        return normalize_peak_numpy(x, target)
    return _torch_ops.normalize_peak(torch.from_numpy(_samples(x)), target).numpy()


def trim_bounds(x, frame_len, hop, threshold_dbfs, pad_samples):
    if _torch_ops is None:
        return trim_bounds_numpy(x, frame_len, hop, threshold_dbfs, pad_samples)
    return _torch_ops.trim_bounds(
        torch.from_numpy(_samples(x)), frame_len, hop, threshold_dbfs, pad_samples
    )


def preprocess_recording(audio_int16, sample_rate):
    if audio_int16.ndim not in (1, 2) or (
        audio_int16.ndim == 2 and audio_int16.shape[1] != 1
    ):
        _logger.warning("Skipping recording preprocessing: expected mono audio")
        return audio_int16
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    x = audio_int16.reshape(-1).astype(np.float32) / 32768
    frame_len = max(1, int(sample_rate * 0.025))
    hop = max(1, int(sample_rate * 0.010))
    start, end = trim_bounds(x, frame_len, hop, -45, int(sample_rate * 0.2))
    if end - start >= sample_rate * 0.25:
        x = x[start:end]
    x = normalize_peak(x, 0.9)
    result = np.clip(x * 32767, -32768, 32767).astype(np.int16)
    return result.reshape(-1, 1) if audio_int16.ndim == 2 else result
