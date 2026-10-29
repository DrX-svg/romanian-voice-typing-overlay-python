#include "vt_dsp/dsp.hpp"

#include <gtest/gtest.h>
#include <cmath>
#include <stdexcept>
#include <vector>

template <typename T>
class DspTest : public testing::Test {};
using SampleTypes = testing::Types<float, double>;
TYPED_TEST_SUITE(DspTest, SampleTypes);

TYPED_TEST(DspTest, FrameCountsAndConstantRms) {
    const std::vector<TypeParam> x(8, TypeParam(0.5));
    EXPECT_TRUE(vt_dsp::frame_rms(x.data(), 0, 4, 2).empty());
    EXPECT_TRUE(vt_dsp::frame_rms(x.data(), 3, 4, 2).empty());
    EXPECT_EQ(vt_dsp::frame_rms(x.data(), 4, 4, 2).size(), 1);
    const auto rms = vt_dsp::frame_rms(x.data(), x.size(), 4, 2);
    ASSERT_EQ(rms.size(), 3);
    for (auto value : rms) {
        EXPECT_NEAR(value, std::sqrt(0.25 + 1e-12), 1e-7);
    }
}

TYPED_TEST(DspTest, SilenceAndPeakNormalization) {
    const std::vector<TypeParam> silence(8, 0);
    const auto rms = vt_dsp::frame_rms(silence.data(), silence.size(), 4, 2);
    for (auto value : rms) {
        EXPECT_NEAR(value, 1e-6, 1e-12);
    }
    EXPECT_EQ(vt_dsp::normalize_peak(silence.data(), silence.size(), TypeParam(0.9)), silence);
    const std::vector<TypeParam> x = {-2, 1};
    const auto normalized = vt_dsp::normalize_peak(x.data(), x.size(), TypeParam(0.5));
    EXPECT_EQ(normalized[0], TypeParam(-0.5));
    EXPECT_EQ(normalized[1], TypeParam(0.25));
    EXPECT_TRUE(vt_dsp::normalize_peak(x.data(), 0, TypeParam(0.9)).empty());
}

TYPED_TEST(DspTest, TrimSilenceAndPadding) {
    const std::vector<TypeParam> x = {0, 0, 1, 1, 1, 1, 0, 0};
    EXPECT_EQ((vt_dsp::trim_bounds(x.data(), x.size(), 2, 2, TypeParam(-20), 0)), std::make_pair(std::size_t(2), std::size_t(6)));
    EXPECT_EQ((vt_dsp::trim_bounds(x.data(), x.size(), 2, 2, TypeParam(-20), 1)), std::make_pair(std::size_t(1), std::size_t(7)));
    EXPECT_EQ((vt_dsp::trim_bounds(x.data(), x.size(), 2, 2, TypeParam(-20), 20)), std::make_pair(std::size_t(0), x.size()));
    const std::vector<TypeParam> silence(8, 0);
    EXPECT_EQ((vt_dsp::trim_bounds(silence.data(), silence.size(), 2, 2, TypeParam(-45), 2)), std::make_pair(std::size_t(0), std::size_t(0)));
    EXPECT_EQ((vt_dsp::trim_bounds(x.data(), 1, 2, 2, TypeParam(-45), 0)), std::make_pair(std::size_t(0), std::size_t(0)));
}

TYPED_TEST(DspTest, InvalidArguments) {
    TypeParam x = 0;
    EXPECT_THROW(vt_dsp::frame_rms(&x, 1, 0, 1), std::invalid_argument);
    EXPECT_THROW(vt_dsp::frame_rms(&x, 1, 1, -1), std::invalid_argument);
    EXPECT_THROW(vt_dsp::trim_bounds(&x, 1, 0, 1, TypeParam(-45), 0), std::invalid_argument);
    EXPECT_THROW(vt_dsp::trim_bounds(&x, 1, 1, 0, TypeParam(-45), 0), std::invalid_argument);
    EXPECT_THROW(vt_dsp::trim_bounds(&x, 1, 1, 1, TypeParam(-45), -1), std::invalid_argument);
}
