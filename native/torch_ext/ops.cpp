#include <ATen/ATen.h>
#include <torch/csrc/utils/pybind.h>
#include <pybind11/eval.h>
#include <pybind11/stl.h>

#include "vt_dsp/dsp.hpp"

#include <algorithm>

namespace py = pybind11;

at::Tensor samples(const at::Tensor& x) {
    TORCH_CHECK(x.device().is_cpu(), "Expected a CPU tensor");
    TORCH_CHECK(x.dim() == 1, "Expected a 1-D tensor");
    TORCH_CHECK(x.scalar_type() == at::kFloat || x.scalar_type() == at::kDouble,
                "Expected float32 or float64 tensor");
    TORCH_CHECK(x.layout() == at::kStrided, "Expected a strided tensor");
    return x.contiguous();
}

at::Tensor frame_forward(const at::Tensor& input, int frame_len, int hop) {
    const auto x = samples(input);
    at::Tensor output;
    AT_DISPATCH_FLOATING_TYPES(x.scalar_type(), "frame_rms", [&] {
        const auto values = vt_dsp::frame_rms(x.data_ptr<scalar_t>(), x.numel(), frame_len, hop);
        output = at::empty({static_cast<int64_t>(values.size())}, x.options().requires_grad(false));
        if (!values.empty()) {
            std::copy(values.begin(), values.end(), output.data_ptr<scalar_t>());
        }
    });
    return output;
}

at::Tensor frame_backward(const at::Tensor& input, const at::Tensor& rms_input,
                          const at::Tensor& grad_input, int frame_len, int hop) {
    const auto x = samples(input);
    const auto rms = samples(rms_input);
    const auto grad = samples(grad_input);
    TORCH_CHECK(frame_len > 0 && hop > 0, "frame_len and hop must be positive");
    const auto count = x.numel() < frame_len ? 0 : 1 + (x.numel() - frame_len) / hop;
    TORCH_CHECK(rms.numel() == count && grad.numel() == count,
                "RMS and gradient lengths must match the frame count");
    TORCH_CHECK(rms.scalar_type() == x.scalar_type() && grad.scalar_type() == x.scalar_type(),
                "RMS and gradient dtypes must match the input");
    auto result = at::zeros_like(x);
    AT_DISPATCH_FLOATING_TYPES(x.scalar_type(), "frame_rms_backward", [&] {
        const auto* data = x.data_ptr<scalar_t>();
        const auto* values = rms.data_ptr<scalar_t>();
        const auto* upstream = grad.data_ptr<scalar_t>();
        auto* dx = result.data_ptr<scalar_t>();
        for (int64_t f = 0; f < count; ++f) {
            const scalar_t scale = upstream[f] / (static_cast<scalar_t>(frame_len) * values[f]);
            for (int j = 0; j < frame_len; ++j) {
                const auto n = f * hop + j;
                dx[n] += scale * data[n];
            }
        }
    });
    return result;
}

at::Tensor normalize_peak(const at::Tensor& input, double target) {
    const auto x = samples(input);
    auto output = at::empty_like(x, x.options().requires_grad(false));
    AT_DISPATCH_FLOATING_TYPES(x.scalar_type(), "normalize_peak", [&] {
        const auto values = vt_dsp::normalize_peak(x.data_ptr<scalar_t>(), x.numel(), static_cast<scalar_t>(target));
        if (!values.empty()) {
            std::copy(values.begin(), values.end(), output.data_ptr<scalar_t>());
        }
    });
    return output;
}

std::pair<std::size_t, std::size_t> trim_bounds(
    const at::Tensor& input, int frame_len, int hop, double threshold_dbfs, int pad_samples) {
    const auto x = samples(input);
    std::pair<std::size_t, std::size_t> bounds;
    AT_DISPATCH_FLOATING_TYPES(x.scalar_type(), "trim_bounds", [&] {
        bounds = vt_dsp::trim_bounds(x.data_ptr<scalar_t>(), x.numel(), frame_len, hop,
                                    static_cast<scalar_t>(threshold_dbfs), pad_samples);
    });
    return bounds;
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("_frame_forward", &frame_forward);
    m.def("_frame_backward", &frame_backward);
    m.def("normalize_peak", &normalize_peak);
    m.def("trim_bounds", &trim_bounds);
    // Keep the Python autograd.Function in the extension module; all numeric work is C++.
    py::exec(R"(
import torch
from torch.autograd.function import once_differentiable

class FrameRms(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, frame_len, hop):
        rms = _frame_forward(x, frame_len, hop)
        ctx.save_for_backward(x, rms)
        ctx.frame_len, ctx.hop = frame_len, hop
        return rms

    @staticmethod
    @once_differentiable
    def backward(ctx, grad_out):
        x, rms = ctx.saved_tensors
        return _frame_backward(x, rms, grad_out, ctx.frame_len, ctx.hop), None, None

frame_rms = FrameRms.apply
)", m.attr("__dict__"));
}
