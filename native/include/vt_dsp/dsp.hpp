#pragma once

#include <cstddef>
#include <utility>
#include <vector>

namespace vt_dsp {

template <typename T>
std::vector<T> frame_rms(const T* x, std::size_t n, int frame_len, int hop);

template <typename T>
std::vector<T> normalize_peak(const T* x, std::size_t n, T target);

template <typename T>
std::pair<std::size_t, std::size_t> trim_bounds(
    const T* x, std::size_t n, int frame_len, int hop, T threshold_dbfs,
    int pad_samples);

}  // namespace vt_dsp
