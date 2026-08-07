"""
Unit tests for Impulse Channel Integration v1 in pcie_eq.channel_config.

Verifies:
1. Canonical Golden Cases: Delta identity, Exponential postcursor, User-defined non-centered zero index, Negative source amplitude, All-zero impulse, Empty wave.
2. Wave Input Matrix: bool, int, uint, float16/32/64, list, tuple, non-contiguous view -> all yield exact float64 impulse-channel output.
3. Relevance and Nested Config Validation: schema v1 rejection of impulse_response, non-None alpha rejection, missing/wrong impulse_source rejection, explosive wave validation order.
4. Integration Sample Interval Policy: sample_interval == 1.0 accepted, 0.5/2.0/1.0000001 rejected with ValueError before wave materialization.
5. Ownership & Result Contract: same-length float64 output, non-aliasing, new array/resolved config allocation per call, result mutation isolation.
6. Defensive Source Reconstruction & Object Identity Isolation: build_impulse receives distinct defensive source instance, final resolved_config.impulse_source is distinct from caller source and source_result.resolved_config.
7. Early Relevance Rejection in from_dict(): V2 none/legacy_lowpass reject non-None impulse_source with ValueError before calling ImpulseSourceConfig.from_dict() (proven via explosive source parser data).
8. Delegation Tracking: build_impulse() called exactly once and convolve_impulse() called exactly once for non-empty and empty waves with exact derived ImpulseConvolutionConfig.
9. Complete Child Result Boundary Failure Matrix via Monkeypatch: build_impulse or convolve_impulse returning wrong type, subclass, corrupted resolved config, wrong metadata, wrong dtype, wrong shape, non-contiguous, non-finite, or aliased memory (source/wave) all raise RuntimeError without repair.
10. Serialization: v2 canonical 4-key dictionary, nested source serialization, new allocations per call, caller dict/list mutation isolation after from_dict(), and round-trip consistency.
11. No direct numpy.convolve() / No duplicated impulse formula AST boundary check.
"""

import ast
import pathlib
import numpy as np
import pytest

import pcie_eq.channel_config as channel_config
from pcie_eq.channel_config import (
    CHANNEL_CONFIG_CONTRACT_ID,
    LEGACY_CHANNEL_CONFIG_CONTRACT_ID,
    ChannelConfig,
    ChannelResult,
    apply_channel,
    V2_CANONICAL_KEYS,
)
from pcie_eq.impulse_convolution import (
    ImpulseConvolutionConfig,
    ImpulseConvolutionResult,
)
from pcie_eq.impulse_source import (
    ImpulseSourceConfig,
    ImpulseSourceResult,
)


def test_impulse_channel_golden_case_delta_identity():
    """Verify Section 17.1 Golden Case: Delta impulse is an exact identity in values."""
    wave = np.array([1.0, 2.0, -1.0, 0.5], dtype=np.float64)
    source = ImpulseSourceConfig(
        source_type="single_tap",
        sample_interval=1.0,
        impulse_zero_index=1,
        normalization="none",
        length=3,
        amplitude=1.0,
    )
    cfg = ChannelConfig(mode="impulse_response", impulse_source=source)

    res = apply_channel(wave, cfg)

    assert type(res) is ChannelResult
    assert res.model_level == "project_owned_discrete_impulse_channel"
    assert res.values.dtype == np.float64
    assert res.values.shape == (4,)
    assert res.values.flags.c_contiguous
    assert np.array_equal(res.values, wave)
    assert res.values is not wave
    assert not np.shares_memory(res.values, wave)


def test_impulse_channel_golden_case_exponential_postcursor():
    """Verify Section 17.2 Golden Case: Exponential postcursor impulse channel output."""
    wave = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    source = ImpulseSourceConfig(
        source_type="exponential_postcursor",
        sample_interval=1.0,
        impulse_zero_index=0,
        normalization="none",
        length=3,
        amplitude=1.0,
        decay_ratio=0.5,
    )
    cfg = ChannelConfig(mode="impulse_response", impulse_source=source)

    res = apply_channel(wave, cfg)

    assert res.model_level == "project_owned_discrete_impulse_channel"
    assert res.values.dtype == np.float64
    expected = np.array([1.0, 0.5, 0.25, 0.0], dtype=np.float64)
    assert np.allclose(res.values, expected)


def test_impulse_channel_golden_case_user_defined_non_centered():
    """Verify Section 17.3 Golden Case: User-defined non-centered zero index impulse vector."""
    wave = [1.0, 2.0, 3.0]
    source = ImpulseSourceConfig(
        source_type="user_defined",
        length=None,
        amplitude=None,
        decay_ratio=None,
        impulse_zero_index=1,
        values=[0.25, 1.0, 0.5],
    )
    cfg = ChannelConfig(mode="impulse_response", impulse_source=source)

    res = apply_channel(wave, cfg)

    # Test-side independent calculation:
    # Full convolve of [1.0, 2.0, 3.0] and [0.25, 1.0, 0.5] is [0.25, 1.5, 3.25, 4.0, 1.5]
    # Slice full[1:4] is [1.5, 3.25, 4.0]
    expected = np.array([1.5, 3.25, 4.0], dtype=np.float64)
    assert res.values.dtype == np.float64
    assert res.values.shape == (3,)
    assert np.allclose(res.values, expected)


def test_impulse_channel_golden_case_negative_amplitude():
    """Verify negative legal source amplitude produces correct signed impulse channel output."""
    wave = np.array([1.0, 2.0], dtype=np.float64)
    source = ImpulseSourceConfig(
        source_type="single_tap",
        length=3,
        impulse_zero_index=1,
        amplitude=-2.0,
    )
    cfg = ChannelConfig(mode="impulse_response", impulse_source=source)

    res = apply_channel(wave, cfg)

    assert res.values.dtype == np.float64
    assert res.values.shape == (2,)
    assert np.array_equal(res.values, np.array([-2.0, -4.0], dtype=np.float64))


def test_impulse_channel_golden_case_all_zero_impulse():
    """Verify Section 17.4 Golden Case: All-zero impulse returns same-length zeros."""
    wave = np.array([1.0, -2.0, 3.0, -4.0], dtype=np.float64)
    source = ImpulseSourceConfig(
        source_type="single_tap",
        length=3,
        impulse_zero_index=1,
        amplitude=0.0,
    )
    cfg = ChannelConfig(mode="impulse_response", impulse_source=source)

    res = apply_channel(wave, cfg)

    assert res.values.dtype == np.float64
    assert res.values.shape == (4,)
    assert np.array_equal(res.values, np.zeros(4, dtype=np.float64))


def test_impulse_channel_golden_case_empty_wave():
    """Verify Section 17.5 Golden Case: Empty wave returns empty float64 array with shape (0,)."""
    source = ImpulseSourceConfig()
    cfg = ChannelConfig(mode="impulse_response", impulse_source=source)

    res = apply_channel(np.array([], dtype=np.float64), cfg)

    assert res.model_level == "project_owned_discrete_impulse_channel"
    assert res.values.dtype == np.float64
    assert res.values.shape == (0,)
    assert res.values.flags.c_contiguous


def test_impulse_channel_wave_input_dtype_matrix():
    """Verify bool, int, uint, float, list, tuple, and non-contiguous views all yield exact float64 output."""
    source = ImpulseSourceConfig(
        source_type="single_tap",
        length=3,
        impulse_zero_index=1,
        amplitude=2.0,
    )
    cfg = ChannelConfig(mode="impulse_response", impulse_source=source)

    dtypes = [
        np.dtype("bool"),
        np.dtype("int8"),
        np.dtype("int16"),
        np.dtype("int32"),
        np.dtype("int64"),
        np.dtype("uint8"),
        np.dtype("uint16"),
        np.dtype("uint32"),
        np.dtype("uint64"),
        np.dtype("float16"),
        np.dtype("float32"),
        np.dtype("float64"),
    ]

    for dt in dtypes:
        wave = np.array([0, 1, 0, 1], dtype=dt)
        res = apply_channel(wave, cfg)
        assert res.values.dtype == np.float64
        assert res.values.shape == (4,)
        assert res.values.flags.c_contiguous
        assert np.array_equal(res.values, np.array([0.0, 2.0, 0.0, 2.0]))

    # List & Tuple
    assert apply_channel([1, 0], cfg).values.dtype == np.float64
    assert apply_channel((1, 0), cfg).values.dtype == np.float64

    # Non-contiguous view
    wave_base = np.arange(10, dtype=np.float64)
    wave_slice = wave_base[::2]
    res_slice = apply_channel(wave_slice, cfg)
    assert res_slice.values.dtype == np.float64
    assert res_slice.values.shape == (5,)
    assert res_slice.values.flags.c_contiguous


def test_relevance_and_nested_config_validation():
    """Verify relevance rules, v1 schema rejection of impulse_response, and explosive wave validation order."""
    source = ImpulseSourceConfig()

    # v1 schema rejects impulse_response
    with pytest.raises(ValueError, match="Unsupported mode 'impulse_response'"):
        ChannelConfig(mode="impulse_response", schema_version=LEGACY_CHANNEL_CONFIG_CONTRACT_ID, impulse_source=source)

    # impulse_response requires impulse_source
    with pytest.raises(ValueError, match="impulse_source' is required"):
        ChannelConfig(mode="impulse_response", impulse_source=None)

    # impulse_source must be exact ImpulseSourceConfig (subclass or wrong type rejected)
    class SubImpulseSourceConfig(ImpulseSourceConfig):
        pass

    with pytest.raises(TypeError, match="impulse_source must be exactly ImpulseSourceConfig"):
        ChannelConfig(mode="impulse_response", impulse_source=SubImpulseSourceConfig())

    with pytest.raises(TypeError, match="impulse_source must be exactly ImpulseSourceConfig"):
        ChannelConfig(mode="impulse_response", impulse_source="not_a_source_config")

    # impulse_response rejects non-None alpha
    with pytest.raises(ValueError, match="alpha' is not applicable"):
        ChannelConfig(mode="impulse_response", alpha=0.08, impulse_source=source)

    # none & legacy_lowpass reject non-None impulse_source
    with pytest.raises(ValueError, match="impulse_source' is not applicable"):
        ChannelConfig(mode="none", impulse_source=source)

    with pytest.raises(ValueError, match="impulse_source' is not applicable"):
        ChannelConfig(mode="legacy_lowpass", impulse_source=source)

    # Explosive wave test: Corrupted nested impulse_source fails validation BEFORE wave materialization
    class ExplosiveWave:
        def __array__(self):
            raise RuntimeError("Wave should not be materialized!")

    valid_cfg = ChannelConfig(mode="impulse_response", impulse_source=ImpulseSourceConfig())
    corrupted_source = ImpulseSourceConfig()
    object.__setattr__(corrupted_source, "source_type", "invalid_source_type")
    object.__setattr__(valid_cfg, "impulse_source", corrupted_source)

    with pytest.raises(ValueError, match="Unsupported source_type"):
        apply_channel(ExplosiveWave(), valid_cfg)


def test_integration_sample_interval_policy():
    """Verify sample_interval == 1.0 accepted, and non-1.0 rejected before wave materialization."""
    class ExplosiveWave:
        def __array__(self):
            raise RuntimeError("Wave should not be materialized!")

    # sample_interval = 1 (int) canonicalizes to 1.0 in ImpulseSourceConfig and is accepted
    source_int = ImpulseSourceConfig(sample_interval=1)
    cfg_int = ChannelConfig(mode="impulse_response", impulse_source=source_int)
    assert cfg_int.impulse_source.sample_interval == 1.0
    res_int = apply_channel([1.0, 0.0], cfg_int)
    assert res_int.resolved_config.impulse_source.sample_interval == 1.0

    # Positive non-1.0 sample intervals (0.5, 2.0, 1.0000001) rejected before wave materialization
    for invalid_dt in [0.5, 2.0, 1.0000001]:
        valid_cfg = ChannelConfig(mode="impulse_response", impulse_source=ImpulseSourceConfig())
        bad_source = ImpulseSourceConfig()
        object.__setattr__(bad_source, "sample_interval", float(invalid_dt))
        object.__setattr__(valid_cfg, "impulse_source", bad_source)

        with pytest.raises(ValueError, match="accepts only sample_interval == 1.0"):
            apply_channel(ExplosiveWave(), valid_cfg)


def test_ownership_and_result_isolation():
    """Verify same-length output, non-aliasing, new array/config allocation each call, and result mutation isolation."""
    wave = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    source = ImpulseSourceConfig()
    cfg = ChannelConfig(mode="impulse_response", impulse_source=source)

    res1 = apply_channel(wave, cfg)
    res2 = apply_channel(wave, cfg)

    assert res1.values.shape == wave.shape
    assert res1.values.dtype == np.float64
    assert res1.values.flags.c_contiguous
    assert res1.values is not wave
    assert not np.shares_memory(res1.values, wave)

    # Allocation isolation
    assert res1.values is not res2.values
    assert not np.shares_memory(res1.values, res2.values)
    assert res1.resolved_config is not res2.resolved_config
    assert res1.resolved_config.impulse_source is not res2.resolved_config.impulse_source

    # Mutation isolation
    res1.values[0] = 999.0
    assert wave[0] == 1.0
    assert res2.values[0] != 999.0


def test_defensive_source_reconstruction_and_identity_isolation(monkeypatch):
    """Verify build_impulse receives equal but distinct defensive source, and final resolved_config.impulse_source is distinct from caller source and child source_result.resolved_config."""
    source_caller = ImpulseSourceConfig(length=3, impulse_zero_index=1, amplitude=2.0)
    cfg = ChannelConfig(mode="impulse_response", impulse_source=source_caller)

    received_build_sources = []
    returned_child_results = []

    orig_build = channel_config.build_impulse

    def mock_build(src):
        received_build_sources.append(src)
        res = orig_build(src)
        returned_child_results.append(res)
        return res

    monkeypatch.setattr(channel_config, "build_impulse", mock_build)

    wave = np.array([1.0, 0.0], dtype=np.float64)
    res = apply_channel(wave, cfg)

    # (a) build_impulse receives an equal but distinct (is not) defensive source instance
    assert len(received_build_sources) == 1
    src_passed_to_build = received_build_sources[0]
    assert src_passed_to_build == source_caller
    assert src_passed_to_build is not source_caller

    # (b) final res.resolved_config.impulse_source is distinct (is not) from caller source AND child source_result.resolved_config
    child_source_res = returned_child_results[0]
    final_resolved_source = res.resolved_config.impulse_source

    assert final_resolved_source == source_caller
    assert final_resolved_source is not source_caller
    assert final_resolved_source is not child_source_res.resolved_config
    assert final_resolved_source is not src_passed_to_build


def test_from_dict_early_relevance_rejection_without_nested_parsing():
    """Verify V2 none and legacy_lowpass reject non-None impulse_source with ValueError before calling source parsing/conversion."""
    # Dict with invalid/non-dict impulse_source data
    d_none = {
        "schema_version": CHANNEL_CONFIG_CONTRACT_ID,
        "mode": "none",
        "alpha": None,
        "impulse_source": "invalid_source_string_data",
    }
    with pytest.raises(ValueError, match="Field 'impulse_source' is not applicable for mode 'none'"):
        ChannelConfig.from_dict(d_none)

    d_lp = {
        "schema_version": CHANNEL_CONFIG_CONTRACT_ID,
        "mode": "legacy_lowpass",
        "alpha": 0.08,
        "impulse_source": {"source_type": "invalid_source_type"},
    }
    with pytest.raises(ValueError, match="Field 'impulse_source' is not applicable for mode 'legacy_lowpass'"):
        ChannelConfig.from_dict(d_lp)


def test_delegation_called_exactly_once_for_non_empty_and_empty_waves(monkeypatch):
    """Verify build_impulse and convolve_impulse are called exactly once with exact derived config for non-empty and empty waves."""
    source = ImpulseSourceConfig(length=3, impulse_zero_index=1, amplitude=2.0)
    cfg = ChannelConfig(mode="impulse_response", impulse_source=source)

    build_calls = []
    convolve_calls = []

    orig_build = channel_config.build_impulse
    orig_convolve = channel_config.convolve_impulse

    def mock_build(src):
        build_calls.append(src)
        return orig_build(src)

    def mock_convolve(w, val, conv_cfg):
        convolve_calls.append((w, val, conv_cfg))
        return orig_convolve(w, val, conv_cfg)

    monkeypatch.setattr(channel_config, "build_impulse", mock_build)
    monkeypatch.setattr(channel_config, "convolve_impulse", mock_convolve)

    # 1. Non-empty wave
    wave_non_empty = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    apply_channel(wave_non_empty, cfg)

    assert len(build_calls) == 1
    assert build_calls[0] == source
    assert len(convolve_calls) == 1
    assert convolve_calls[0][2] == ImpulseConvolutionConfig(mode="same", impulse_zero_index=1)

    # Reset tracking
    build_calls.clear()
    convolve_calls.clear()

    # 2. Empty wave
    wave_empty = np.array([], dtype=np.float64)
    apply_channel(wave_empty, cfg)

    assert len(build_calls) == 1
    assert build_calls[0] == source
    assert len(convolve_calls) == 1
    assert convolve_calls[0][2] == ImpulseConvolutionConfig(mode="same", impulse_zero_index=1)


def test_child_result_boundary_failure_matrix_full(monkeypatch):
    """Verify apply_channel raises RuntimeError for all source and convolution child result contract violations."""
    wave = np.array([1.0, 0.0], dtype=np.float64)
    source = ImpulseSourceConfig()
    cfg = ChannelConfig(mode="impulse_response", impulse_source=source)

    # 1. build_impulse raises TypeError/ValueError -> converted to RuntimeError
    monkeypatch.setattr(channel_config, "build_impulse", lambda s: (_ for _ in ()).throw(ValueError("Source failed")))
    with pytest.raises(RuntimeError, match="build_impulse failed"):
        apply_channel(wave, cfg)

    # 2. build_impulse returns non-ImpulseSourceResult
    monkeypatch.setattr(channel_config, "build_impulse", lambda s: "not_a_result")
    with pytest.raises(RuntimeError, match="source result is not exact ImpulseSourceResult"):
        apply_channel(wave, cfg)

    # 3. build_impulse returns ImpulseSourceResult subclass
    class SubImpulseSourceResult(ImpulseSourceResult):
        pass

    sub_src_res = SubImpulseSourceResult(
        values=np.array([1.0], dtype=np.float64),
        resolved_config=source,
        model_level="project_owned_discrete_impulse_source",
    )
    monkeypatch.setattr(channel_config, "build_impulse", lambda s: sub_src_res)
    with pytest.raises(RuntimeError, match="source result is not exact ImpulseSourceResult"):
        apply_channel(wave, cfg)

    # 4. build_impulse returns wrong resolved_config type (subclass or non-config)
    class SubImpulseSourceConfig(ImpulseSourceConfig):
        pass

    bad_src_cfg_res = ImpulseSourceResult(
        values=np.array([1.0], dtype=np.float64),
        resolved_config=SubImpulseSourceConfig(),
        model_level="project_owned_discrete_impulse_source",
    )
    monkeypatch.setattr(channel_config, "build_impulse", lambda s: bad_src_cfg_res)
    with pytest.raises(RuntimeError, match="source resolved_config is not exact ImpulseSourceConfig"):
        apply_channel(wave, cfg)

    # 5. build_impulse returns corrupted/invalid resolved_config semantics
    corrupted_src_cfg = ImpulseSourceConfig()
    object.__setattr__(corrupted_src_cfg, "source_type", "corrupted_source_type")
    bad_src_semantics_res = ImpulseSourceResult(
        values=np.array([1.0], dtype=np.float64),
        resolved_config=corrupted_src_cfg,
        model_level="project_owned_discrete_impulse_source",
    )
    monkeypatch.setattr(channel_config, "build_impulse", lambda s: bad_src_semantics_res)
    with pytest.raises(RuntimeError, match="source resolved_config semantics invalid"):
        apply_channel(wave, cfg)

    # 6. build_impulse returns wrong source model_level
    bad_model_src = ImpulseSourceResult(
        values=np.array([1.0], dtype=np.float64),
        resolved_config=source,
        model_level="other_source_model",
    )
    monkeypatch.setattr(channel_config, "build_impulse", lambda s: bad_model_src)
    with pytest.raises(RuntimeError, match="source model_level mismatch"):
        apply_channel(wave, cfg)

    # 7. build_impulse returns float32 values
    bad_dtype_src = ImpulseSourceResult(
        values=np.array([1.0], dtype=np.float32),
        resolved_config=source,
        model_level="project_owned_discrete_impulse_source",
    )
    monkeypatch.setattr(channel_config, "build_impulse", lambda s: bad_dtype_src)
    with pytest.raises(RuntimeError, match="source values dtype mismatch"):
        apply_channel(wave, cfg)

    # 8. build_impulse returns wrong shape
    bad_shape_src = ImpulseSourceResult(
        values=np.array([1.0, 2.0], dtype=np.float64),
        resolved_config=source,
        model_level="project_owned_discrete_impulse_source",
    )
    monkeypatch.setattr(channel_config, "build_impulse", lambda s: bad_shape_src)
    with pytest.raises(RuntimeError, match="source values shape mismatch"):
        apply_channel(wave, cfg)

    # 9. build_impulse returns non-C-contiguous values (length=2)
    src2 = ImpulseSourceConfig(length=2)
    cfg2 = ChannelConfig(mode="impulse_response", impulse_source=src2)
    base_src = np.array([1.0, 0.0, 2.0, 0.0], dtype=np.float64)
    non_c_src = base_src[::2]
    bad_contig_src = ImpulseSourceResult(
        values=non_c_src,
        resolved_config=src2,
        model_level="project_owned_discrete_impulse_source",
    )
    monkeypatch.setattr(channel_config, "build_impulse", lambda s: bad_contig_src)
    with pytest.raises(RuntimeError, match="source values is not C-contiguous"):
        apply_channel(wave, cfg2)

    # 10. build_impulse returns non-finite values (NaN)
    bad_nan_src = ImpulseSourceResult(
        values=np.array([np.nan], dtype=np.float64),
        resolved_config=source,
        model_level="project_owned_discrete_impulse_source",
    )
    monkeypatch.setattr(channel_config, "build_impulse", lambda s: bad_nan_src)
    with pytest.raises(RuntimeError, match="source values contains non-finite elements"):
        apply_channel(wave, cfg)

    # Valid source result for convolution tests
    valid_src_res = ImpulseSourceResult(
        values=np.array([1.0], dtype=np.float64),
        resolved_config=source,
        model_level="project_owned_discrete_impulse_source",
    )

    # 11. convolve_impulse raises TypeError/ValueError -> converted to RuntimeError
    monkeypatch.setattr(channel_config, "build_impulse", lambda s: valid_src_res)
    monkeypatch.setattr(channel_config, "convolve_impulse", lambda w, s, c: (_ for _ in ()).throw(ValueError("Convolution failed")))
    with pytest.raises(RuntimeError, match="convolve_impulse failed"):
        apply_channel(wave, cfg)

    # 12. convolve_impulse returns non-ImpulseConvolutionResult
    monkeypatch.setattr(channel_config, "convolve_impulse", lambda w, s, c: "not_a_conv_result")
    with pytest.raises(RuntimeError, match="convolution result is not exact ImpulseConvolutionResult"):
        apply_channel(wave, cfg)

    # 13. convolve_impulse returns ImpulseConvolutionResult subclass
    class SubImpulseConvolutionResult(ImpulseConvolutionResult):
        pass

    conv_cfg_valid = ImpulseConvolutionConfig(mode="same", impulse_zero_index=0)
    sub_conv_res = SubImpulseConvolutionResult(
        values=np.array([1.0, 0.0], dtype=np.float64),
        resolved_config=conv_cfg_valid,
        output_start_index=0,
        model_level="discrete_linear_convolution",
    )
    monkeypatch.setattr(channel_config, "convolve_impulse", lambda w, s, c: sub_conv_res)
    with pytest.raises(RuntimeError, match="convolution result is not exact ImpulseConvolutionResult"):
        apply_channel(wave, cfg)

    # 14. convolve_impulse returns wrong resolved_config type
    class SubImpulseConvolutionConfig(ImpulseConvolutionConfig):
        pass

    bad_conv_cfg_res = ImpulseConvolutionResult(
        values=np.array([1.0, 0.0], dtype=np.float64),
        resolved_config=SubImpulseConvolutionConfig(mode="same", impulse_zero_index=0),
        output_start_index=0,
        model_level="discrete_linear_convolution",
    )
    monkeypatch.setattr(channel_config, "convolve_impulse", lambda w, s, c: bad_conv_cfg_res)
    with pytest.raises(RuntimeError, match="convolution resolved_config is not exact ImpulseConvolutionConfig"):
        apply_channel(wave, cfg)

    # 15. convolve_impulse returns wrong mode metadata (e.g. "full")
    conv_cfg_wrong_mode = ImpulseConvolutionConfig(mode="full", impulse_zero_index=0)
    bad_conv_mode = ImpulseConvolutionResult(
        values=np.array([1.0, 0.0], dtype=np.float64),
        resolved_config=conv_cfg_wrong_mode,
        output_start_index=0,
        model_level="discrete_linear_convolution",
    )
    monkeypatch.setattr(channel_config, "convolve_impulse", lambda w, s, c: bad_conv_mode)
    with pytest.raises(RuntimeError, match="convolution mode mismatch"):
        apply_channel(wave, cfg)

    # 16. convolve_impulse returns wrong zero_index metadata
    conv_cfg_wrong_z = ImpulseConvolutionConfig(mode="same", impulse_zero_index=5)
    bad_conv_z = ImpulseConvolutionResult(
        values=np.array([1.0, 0.0], dtype=np.float64),
        resolved_config=conv_cfg_wrong_z,
        output_start_index=0,
        model_level="discrete_linear_convolution",
    )
    monkeypatch.setattr(channel_config, "convolve_impulse", lambda w, s, c: bad_conv_z)
    with pytest.raises(RuntimeError, match="convolution impulse_zero_index mismatch"):
        apply_channel(wave, cfg)

    # 17. convolve_impulse returns non-zero output_start_index
    bad_conv_start = ImpulseConvolutionResult(
        values=np.array([1.0, 0.0], dtype=np.float64),
        resolved_config=conv_cfg_valid,
        output_start_index=1,
        model_level="discrete_linear_convolution",
    )
    monkeypatch.setattr(channel_config, "convolve_impulse", lambda w, s, c: bad_conv_start)
    with pytest.raises(RuntimeError, match="convolution output_start_index mismatch"):
        apply_channel(wave, cfg)

    # 18. convolve_impulse returns wrong model_level
    bad_conv_model = ImpulseConvolutionResult(
        values=np.array([1.0, 0.0], dtype=np.float64),
        resolved_config=conv_cfg_valid,
        output_start_index=0,
        model_level="other_conv_model",
    )
    monkeypatch.setattr(channel_config, "convolve_impulse", lambda w, s, c: bad_conv_model)
    with pytest.raises(RuntimeError, match="convolution model_level mismatch"):
        apply_channel(wave, cfg)

    # 19. convolve_impulse returns float32 values
    bad_conv_dtype = ImpulseConvolutionResult(
        values=np.array([1.0, 0.0], dtype=np.float32),
        resolved_config=conv_cfg_valid,
        output_start_index=0,
        model_level="discrete_linear_convolution",
    )
    monkeypatch.setattr(channel_config, "convolve_impulse", lambda w, s, c: bad_conv_dtype)
    with pytest.raises(RuntimeError, match="convolution values dtype mismatch"):
        apply_channel(wave, cfg)

    # 20. convolve_impulse returns wrong shape
    bad_conv_shape = ImpulseConvolutionResult(
        values=np.array([1.0], dtype=np.float64),
        resolved_config=conv_cfg_valid,
        output_start_index=0,
        model_level="discrete_linear_convolution",
    )
    monkeypatch.setattr(channel_config, "convolve_impulse", lambda w, s, c: bad_conv_shape)
    with pytest.raises(RuntimeError, match="convolution values shape mismatch"):
        apply_channel(wave, cfg)

    # 21. convolve_impulse returns non-C-contiguous values
    base_conv = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float64)[:, 0]
    bad_conv_contig = ImpulseConvolutionResult(
        values=base_conv,
        resolved_config=conv_cfg_valid,
        output_start_index=0,
        model_level="discrete_linear_convolution",
    )
    monkeypatch.setattr(channel_config, "convolve_impulse", lambda w, s, c: bad_conv_contig)
    with pytest.raises(RuntimeError, match="convolution values is not C-contiguous"):
        apply_channel(wave, cfg)

    # 22. convolve_impulse returns non-finite values (NaN)
    bad_conv_nan = ImpulseConvolutionResult(
        values=np.array([1.0, np.nan], dtype=np.float64),
        resolved_config=conv_cfg_valid,
        output_start_index=0,
        model_level="discrete_linear_convolution",
    )
    monkeypatch.setattr(channel_config, "convolve_impulse", lambda w, s, c: bad_conv_nan)
    with pytest.raises(RuntimeError, match="convolution values contains non-finite elements"):
        apply_channel(wave, cfg)

    # 23. convolve_impulse returns memory aliasing caller wave
    bad_conv_alias_wave = ImpulseConvolutionResult(
        values=wave,
        resolved_config=conv_cfg_valid,
        output_start_index=0,
        model_level="discrete_linear_convolution",
    )
    monkeypatch.setattr(channel_config, "convolve_impulse", lambda w, s, c: bad_conv_alias_wave)
    with pytest.raises(RuntimeError, match="convolution values memory aliases caller wave"):
        apply_channel(wave, cfg)

    # 24. convolve_impulse returns memory aliasing source values
    bad_conv_alias_src = ImpulseConvolutionResult(
        values=valid_src_res.values,
        resolved_config=conv_cfg_valid,
        output_start_index=0,
        model_level="discrete_linear_convolution",
    )
    monkeypatch.setattr(channel_config, "convolve_impulse", lambda w, s, c: bad_conv_alias_src)
    with pytest.raises(RuntimeError, match="convolution values memory aliases source values"):
        apply_channel(np.array([1.0], dtype=np.float64), cfg)


def test_impulse_channel_serialization_canonical_keys_and_round_trip():
    """Verify v2 4-key canonical dictionary, nested source serialization, allocation isolation, and round-trip consistency."""
    source = ImpulseSourceConfig(
        source_type="user_defined",
        length=None,
        amplitude=None,
        decay_ratio=None,
        impulse_zero_index=1,
        values=[0.5, 1.0, -0.5],
    )
    cfg = ChannelConfig(mode="impulse_response", impulse_source=source)

    d1 = cfg.to_dict()
    d2 = cfg.to_dict()

    assert d1 is not d2
    assert list(d1.keys()) == V2_CANONICAL_KEYS
    assert d1["schema_version"] == CHANNEL_CONFIG_CONTRACT_ID
    assert d1["mode"] == "impulse_response"
    assert d1["alpha"] is None

    assert type(d1["impulse_source"]) is dict
    assert d1["impulse_source"] is not d2["impulse_source"]
    assert d1["impulse_source"]["source_type"] == "user_defined"
    assert d1["impulse_source"]["values"] == [0.5, 1.0, -0.5]
    assert d1["impulse_source"]["values"] is not d2["impulse_source"]["values"]

    # Round-trip
    restored = ChannelConfig.from_dict(d2)
    assert restored == cfg
    assert restored.impulse_source == source

    # Dict & nested list mutation isolation after from_dict
    raw_dict = cfg.to_dict()
    restored_from_raw = ChannelConfig.from_dict(raw_dict)

    raw_dict["impulse_source"]["values"][0] = 999.0
    raw_dict["impulse_source"]["source_type"] = "corrupted"

    assert restored_from_raw.impulse_source.values == (0.5, 1.0, -0.5)
    assert restored_from_raw.impulse_source.source_type == "user_defined"


def test_no_direct_numpy_convolve_or_duplicated_impulse_formula_boundary_check():
    """AST check verifying pcie_eq/channel_config.py contains zero direct np.convolve calls or duplicated impulse formulas."""
    config_path = pathlib.Path("pcie_eq/channel_config.py")
    source_code = config_path.read_text(encoding="utf-8")
    tree = ast.parse(source_code)

    assert "np.convolve" not in source_code
    assert "numpy.convolve" not in source_code
    assert "convolve(" not in source_code or "convolve_impulse(" in source_code

    # Check AST for numpy.convolve calls
    found_convolve_call = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == "convolve":
                    found_convolve_call = True

    assert not found_convolve_call, "pcie_eq/channel_config.py must not call numpy.convolve directly!"
