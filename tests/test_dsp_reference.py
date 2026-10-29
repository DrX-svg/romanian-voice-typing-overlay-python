import numpy as np
import pytest

from voice_typing_ro import dsp


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_rms_hand_computed_and_edge_counts(dtype):
    x = np.array([3, 4, 0, 0, 2], dtype=dtype)
    np.testing.assert_allclose(dsp.frame_rms_numpy(x, 2, 2), np.sqrt([12.5 + 1e-12, 1e-12]), rtol=1e-6)
    assert dsp.frame_rms_numpy(x[:1], 2, 1).size == 0
    assert dsp.frame_rms_numpy(x[:2], 2, 1).size == 1
    assert dsp.frame_rms_numpy(x[:0], 2, 1).size == 0
    assert dsp.frame_rms_numpy(x, 2, 2).dtype == dtype


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_normalize_peak_hand_computed_and_tiny_copy(dtype):
    np.testing.assert_array_equal(dsp.normalize_peak_numpy(np.array([-2, 1], dtype=dtype), .5), [-.5, .25])
    for x in (np.zeros(4, dtype=dtype), np.array([1e-9], dtype=dtype), np.empty(0, dtype=dtype)):
        output = dsp.normalize_peak_numpy(x, .9)
        np.testing.assert_array_equal(output, x)
        assert not np.shares_memory(output, x)


def test_trim_bounds_hand_computed():
    x = np.array([0, 0, 1, 1, 1, 1, 0, 0], dtype=np.float64)
    assert dsp.trim_bounds_numpy(x, 2, 2, -20, 0) == (2, 6)
    assert dsp.trim_bounds_numpy(x, 2, 2, -20, 1) == (1, 7)
    assert dsp.trim_bounds_numpy(x, 2, 2, -20, 100) == (0, 8)
    assert dsp.trim_bounds_numpy(np.zeros(8), 2, 2, -45, 0) == (0, 0)
    assert dsp.trim_bounds_numpy(x[:1], 2, 2, -45, 0) == (0, 0)
    assert dsp.trim_bounds_numpy(np.ones(2), 2, 1, 0, 0) == (0, 2)


@pytest.mark.parametrize("frame_len,hop", [(0, 1), (-1, 1), (1, 0), (1, -1)])
def test_invalid_frame_arguments(frame_len, hop):
    with pytest.raises(ValueError, match="positive"):
        dsp.frame_rms_numpy(np.empty(0), frame_len, hop)
    with pytest.raises(ValueError, match="positive"):
        dsp.trim_bounds_numpy(np.empty(0), frame_len, hop, -45, 0)


def test_invalid_pad_and_buffers():
    with pytest.raises(ValueError, match="nonnegative"):
        dsp.trim_bounds_numpy(np.ones(4), 2, 1, -45, -1)
    for x in (np.ones((2, 2)), np.ones(4, dtype=np.int16)):
        with pytest.raises(ValueError, match="1-D float32 or float64"):
            dsp.frame_rms_numpy(x, 2, 1)


def test_backend_dispatch_and_numpy_fallback(monkeypatch):
    x = np.array([1, 0, 1, 0], dtype=np.float32)
    assert dsp.backend() in ("numpy", "torch_cpp")
    np.testing.assert_allclose(dsp.frame_rms(x, 2, 1), dsp.frame_rms_numpy(x, 2, 1), rtol=1e-5)
    np.testing.assert_allclose(dsp.normalize_peak(x, .9), dsp.normalize_peak_numpy(x, .9))
    assert dsp.trim_bounds(x, 2, 1, -45, 1) == dsp.trim_bounds_numpy(x, 2, 1, -45, 1)
    monkeypatch.setattr(dsp, "_torch_ops", None)
    assert dsp.backend() == "numpy"
    np.testing.assert_array_equal(dsp.frame_rms(x, 2, 1), dsp.frame_rms_numpy(x, 2, 1))


@pytest.mark.parametrize("column", [False, True])
def test_preprocess_trims_normalizes_and_restores_shape(monkeypatch, column):
    monkeypatch.setattr(dsp, "_torch_ops", None)
    x = np.zeros(32000, dtype=np.int16)
    x[12000:20000] = 1000
    output = dsp.preprocess_recording(x[:, None] if column else x, 16000)
    # First/last voiced frames start at 11680/19840, so padded bounds are 8480:23440.
    assert output.shape == ((14960, 1) if column else (14960,))
    assert output.dtype == np.int16
    assert output.max() == int(.9 * 32767)


def test_preprocess_retains_short_trim_and_silence(monkeypatch):
    monkeypatch.setattr(dsp, "_torch_ops", None)
    x = np.zeros(16000, dtype=np.int16)
    x[8000] = 1000
    # At 16 kHz the padding alone exceeds 0.25 s; use a short recording to exercise fallback.
    short = x[7900:8100]
    assert dsp.preprocess_recording(short, 16000).shape == short.shape
    silence = np.zeros((8000, 1), dtype=np.int16)
    np.testing.assert_array_equal(dsp.preprocess_recording(silence, 16000), silence)
    assert dsp.preprocess_recording(np.empty(0, dtype=np.int16), 16000).size == 0


def test_preprocess_stereo_unchanged_and_logged(caplog):
    stereo = np.ones((16, 2), dtype=np.int16)
    assert dsp.preprocess_recording(stereo, 16000) is stereo
    assert "mono" in caplog.text
