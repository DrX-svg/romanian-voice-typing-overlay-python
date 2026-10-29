import numpy as np
import pytest

torch = pytest.importorskip("torch")
ops = pytest.importorskip("vt_dsp_torch")

from voice_typing_ro import dsp


@pytest.mark.parametrize("dtype,rtol", [(np.float32, 1e-5), (np.float64, 1e-10)])
@pytest.mark.parametrize("n,frame_len,hop", [(0, 4, 2), (3, 4, 2), (4, 4, 2), (31, 7, 3), (51, 4, 9), (16000, 400, 160)])
def test_ops_match_numpy(dtype, rtol, n, frame_len, hop):
    x = np.random.default_rng(42).normal(size=n).astype(dtype)
    tensor = torch.from_numpy(x)
    np.testing.assert_allclose(ops.frame_rms(tensor, frame_len, hop).numpy(), dsp.frame_rms_numpy(x, frame_len, hop), rtol=rtol, atol=0)
    np.testing.assert_allclose(ops.normalize_peak(tensor, .9).numpy(), dsp.normalize_peak_numpy(x, .9), rtol=rtol, atol=0)
    assert ops.trim_bounds(tensor, frame_len, hop, -10, 3) == dsp.trim_bounds_numpy(x, frame_len, hop, -10, 3)


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_silence_tiny_and_trim_boundaries(dtype):
    for x in (torch.zeros(8, dtype=dtype), torch.full((8,), 1e-9, dtype=dtype)):
        torch.testing.assert_close(ops.normalize_peak(x, .9), x, rtol=0, atol=0)
        assert ops.normalize_peak(x, .9).data_ptr() != x.data_ptr()
        assert ops.trim_bounds(x, 2, 2, -45, 2) == (0, 0)
    x = torch.tensor([0, 0, 1, 1, 1, 1, 0, 0], dtype=dtype)
    assert ops.trim_bounds(x, 2, 2, -20, 1) == (1, 7)


@pytest.mark.parametrize("frame_len,hop", [(4, 2), (4, 7), (20, 1)])
def test_frame_rms_gradcheck(frame_len, hop):
    x = torch.linspace(-.9, 1.2, 13, dtype=torch.float64, requires_grad=True)
    assert torch.autograd.gradcheck(lambda t: ops.frame_rms(t, frame_len, hop), (x,))


def test_noncontiguous_input_and_overlapping_backward():
    base = torch.linspace(-1, 1, 18, dtype=torch.float64, requires_grad=True)
    x = base[::2]
    output = ops.frame_rms(x, 4, 2)
    expected = (x.unfold(0, 4, 2).square().mean(1) + 1e-12).sqrt()
    torch.testing.assert_close(output, expected)
    weights = torch.tensor([1., -2., 3.], dtype=torch.float64)
    grad = torch.autograd.grad(output, base, weights)[0]
    expected_grad = torch.autograd.grad(expected, base, weights)[0]
    torch.testing.assert_close(grad, expected_grad)
    torch.testing.assert_close(ops.normalize_peak(x, .9), x.detach() * (.9 / x.detach().abs().max()))
    assert ops.trim_bounds(x, 4, 2, -45, 0) == (0, 8)


@pytest.mark.parametrize("x,message", [(torch.ones(2, 2), "1-D"), (torch.ones(3, dtype=torch.int16), "float32 or float64"), (torch.empty(3, device="meta"), "CPU")])
def test_reject_invalid_tensors(x, message):
    for call in (lambda: ops.frame_rms(x, 2, 1), lambda: ops.normalize_peak(x, .9), lambda: ops.trim_bounds(x, 2, 1, -45, 0)):
        with pytest.raises(RuntimeError, match=message):
            call()


@pytest.mark.parametrize("frame_len,hop", [(0, 1), (1, 0), (-1, 2), (2, -1)])
def test_reject_invalid_frame_arguments(frame_len, hop):
    x = torch.ones(4)
    with pytest.raises((RuntimeError, ValueError), match="positive"):
        ops.frame_rms(x, frame_len, hop)
    with pytest.raises((RuntimeError, ValueError), match="positive"):
        ops.trim_bounds(x, frame_len, hop, -45, 0)


def test_negative_padding_and_forward_only_normalize():
    x = torch.ones(4, requires_grad=True)
    with pytest.raises((RuntimeError, ValueError), match="nonnegative"):
        ops.trim_bounds(x, 2, 1, -45, -1)
    assert not ops.normalize_peak(x, .9).requires_grad
    assert issubclass(ops.FrameRms, torch.autograd.Function)
