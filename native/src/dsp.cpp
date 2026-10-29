#include "vt_dsp/dsp.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace vt_dsp {

template <typename T>
std::vector<T> frame_rms(const T* x, std::size_t n, int frame_len, int hop) {
    if (frame_len <= 0 || hop <= 0) {
        throw std::invalid_argument("frame_len and hop must be positive");
    }
    const auto length = static_cast<std::size_t>(frame_len);
    const auto step = static_cast<std::size_t>(hop);
    const auto count = n < length ? 0 : 1 + (n - length) / step;
    std::vector<T> result(count);
    for (std::size_t f = 0; f < count; ++f) {
        T sum = 0;
        for (std::size_t j = 0; j < length; ++j) {
            const T value = x[f * step + j];
            sum += value * value;
        }
        result[f] = std::sqrt(sum / static_cast<T>(length) + static_cast<T>(1e-12));
    }
    return result;
}

template <typename T>
std::vector<T> normalize_peak(const T* x, std::size_t n, T target) {
    T peak = 0;
    for (std::size_t i = 0; i < n; ++i) {
        peak = std::max(peak, std::abs(x[i]));
    }
    std::vector<T> result(n);
    const T scale = peak < static_cast<T>(1e-8) ? T(1) : target / peak;
    for (std::size_t i = 0; i < n; ++i) {
        result[i] = x[i] * scale;
    }
    return result;
}

template <typename T>
std::pair<std::size_t, std::size_t> trim_bounds(
    const T* x, std::size_t n, int frame_len, int hop, T threshold_dbfs,
    int pad_samples) {
    if (pad_samples < 0) {
        throw std::invalid_argument("pad_samples must be nonnegative");
    }
    const auto rms = frame_rms(x, n, frame_len, hop);
    std::size_t first = rms.size();
    std::size_t last = 0;
    for (std::size_t f = 0; f < rms.size(); ++f) {
        if (T(20) * std::log10(rms[f]) >= threshold_dbfs) {
            first = std::min(first, f);
            last = f;
        }
    }
    if (first == rms.size()) {
        return {0, 0};
    }
    const auto pad = static_cast<std::size_t>(pad_samples);
    const auto begin = first * static_cast<std::size_t>(hop);
    const auto end = last * static_cast<std::size_t>(hop) + frame_len;
    return {begin > pad ? begin - pad : 0, end + std::min(pad, n - end)};
}

template std::vector<float> frame_rms(const float*, std::size_t, int, int);
template std::vector<double> frame_rms(const double*, std::size_t, int, int);
template std::vector<float> normalize_peak(const float*, std::size_t, float);
template std::vector<double> normalize_peak(const double*, std::size_t, double);
template std::pair<std::size_t, std::size_t> trim_bounds(
    const float*, std::size_t, int, int, float, int);
template std::pair<std::size_t, std::size_t> trim_bounds(
    const double*, std::size_t, int, int, double, int);

}  // namespace vt_dsp
