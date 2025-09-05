"""
Tests for peak detection and quantification in peaks.py.
"""
import pytest
import numpy as np
from peaks import (
    smooth_data,
    compute_derivative,
    find_zero_crossings,
    find_peaks_in_derivative,
    calculate_peak_step,
    calculate_metal_concentration,
    detect_and_quantify_peaks,
)


def test_smooth_data():
    """Test Savitzky-Golay smoothing of data."""
    # Create noisy data
    x = np.linspace(0, 10, 100)
    y_true = np.sin(x)
    np.random.seed(42)  # For reproducibility
    noise = np.random.normal(0, 0.1, len(x))
    y_noisy = y_true + noise
    
    # Smooth the data
    y_smoothed = smooth_data(y_noisy)
    
    # Check that smoothing reduces noise
    error_noisy = np.mean((y_true - y_noisy) ** 2)
    error_smoothed = np.mean((y_true - y_smoothed) ** 2)
    assert error_smoothed < error_noisy
    
    # Test with small data (less than window length)
    small_data = [1.0, 2.0, 3.0]
    small_smoothed = smooth_data(small_data)
    assert len(small_smoothed) == len(small_data)
    
    # Test with even window length (should be converted to odd)
    even_window = smooth_data(y_noisy, window_length=8)
    assert len(even_window) == len(y_noisy)


def test_compute_derivative():
    """Test computation of derivative."""
    # Test with linear data (constant derivative)
    x = np.linspace(0, 10, 11)
    y = 2 * x + 1  # y = 2x + 1, derivative = 2
    dy_dx = compute_derivative(x, y)
    
    # Check that all derivatives are close to 2
    assert all(np.isclose(dy, 2.0) for dy in dy_dx)
    
    # Test with quadratic data
    x = np.linspace(0, 10, 11)
    y = x ** 2  # y = x^2, derivative = 2x
    dy_dx = compute_derivative(x, y)
    
    # Check that derivatives are close to 2x
    expected_derivatives = 2 * x
    assert np.allclose(dy_dx, expected_derivatives, rtol=0.1)
    
    # Test with empty data
    assert len(compute_derivative([], [])) == 0
    
    # Test with single point
    assert len(compute_derivative([1], [2])) == 1
    assert compute_derivative([1], [2])[0] == 0.0


def test_find_zero_crossings():
    """Test finding zero crossings in data."""
    # Test with simple sine wave (crosses zero at π, 2π, etc.)
    x = np.linspace(0, 2 * np.pi, 100)
    y = np.sin(x)
    
    zero_crossings = find_zero_crossings(x, y)
    
    # Should have two zero crossings (at π and 2π)
    assert len(zero_crossings) >= 2
    
    # Test with data that doesn't cross zero
    x = np.linspace(0, 10, 11)
    y = x + 1  # Always positive
    zero_crossings = find_zero_crossings(x, y)
    assert len(zero_crossings) == 0


def test_find_peaks_in_derivative():
    """Test finding peaks in derivative data."""
    # Create synthetic data with a peak
    x = np.linspace(2, 6, 100)
    y = np.zeros_like(x)
    
    # Add a peak in the derivative around x=4
    peak_idx = np.where(np.logical_and(x >= 3.9, x <= 4.1))[0]
    y[peak_idx] = 1.0
    
    # Find peaks
    peak_indices, peak_props = find_peaks_in_derivative(x, y)
    
    # Should find one peak
    assert len(peak_indices) == 1
    
    # Test with pH cutoff
    peak_indices_cutoff, _ = find_peaks_in_derivative(x, y, ph_cutoff=3.5)
    assert len(peak_indices_cutoff) == 1  # Peak is after cutoff
    
    peak_indices_cutoff, _ = find_peaks_in_derivative(x, y, ph_cutoff=3.0)
    assert len(peak_indices_cutoff) == 0  # No peaks before cutoff


def test_calculate_peak_step():
    """Test calculation of peak step size."""
    # Create synthetic data with a step
    ph = np.linspace(2, 6, 100)
    delta_b = np.zeros_like(ph)
    
    # Add a step around pH=4
    step_idx = np.where(ph >= 4.0)[0][0]
    delta_b[step_idx:] = 0.01  # Step of 0.01 mol/L
    
    # Calculate step size
    step_size = calculate_peak_step(ph, delta_b, step_idx - 10, step_idx + 10)
    
    # Should be close to 0.01
    assert step_size == pytest.approx(0.01, rel=1e-2)
    
    # Test with indices out of bounds
    step_size_oob = calculate_peak_step(ph, delta_b, -10, 200)
    assert isinstance(step_size_oob, float)  # Should still return a float


def test_calculate_metal_concentration():
    """Test calculation of metal concentration from step size."""
    # Test with various stoichiometries
    assert calculate_metal_concentration(0.03, 3) == 0.01  # Fe3+: 0.03/3 = 0.01 mol/L
    assert calculate_metal_concentration(0.02, 2) == 0.01  # Fe2+: 0.02/2 = 0.01 mol/L
    
    # Test with zero or negative stoichiometry
    assert calculate_metal_concentration(0.01, 0) == 0.0
    assert calculate_metal_concentration(0.01, -1) == 0.0


def create_synthetic_step_data(step_ph=3.5, step_size=0.01):
    """Create synthetic pH and delta_b data with a step at specified pH."""
    ph = np.linspace(2.0, 6.0, 200)
    delta_b = np.zeros_like(ph)
    
    # Add a step at step_ph
    step_idx = np.where(ph >= step_ph)[0][0]
    delta_b[step_idx:] = step_size
    
    # Add some noise
    np.random.seed(42)
    noise = np.random.normal(0, 0.0005, len(ph))
    delta_b += noise
    
    return ph, delta_b


def test_detect_and_quantify_peaks_synthetic():
    """Test peak detection with synthetic data having a step around pH=3.5."""
    # Create synthetic data with a step at pH=3.5
    ph, delta_b = create_synthetic_step_data(step_ph=3.5, step_size=0.01)
    
    # Calculate derivative (for visualization/debugging)
    derivative = compute_derivative(ph, delta_b)
    
    # Detect peaks
    peaks = detect_and_quantify_peaks(ph, delta_b, derivative)
    
    # Should detect one peak
    assert len(peaks) == 1
    
    # The peak should be around pH=3.5
    assert peaks[0]["ph_apex"] == pytest.approx(3.5, abs=0.1)
    
    # The step size should be close to 0.01
    assert peaks[0]["delta_b_step"] == pytest.approx(0.01, rel=0.1)


def test_detect_and_quantify_peaks_multiple():
    """Test peak detection with multiple steps."""
    # Create pH array
    ph = np.linspace(2.0, 6.0, 200)
    delta_b = np.zeros_like(ph)
    
    # Add multiple steps
    steps = [(3.0, 0.005), (4.0, 0.01), (5.0, 0.015)]
    
    for step_ph, step_size in steps:
        step_idx = np.where(ph >= step_ph)[0][0]
        delta_b[step_idx:] += step_size
    
    # Add noise
    np.random.seed(42)
    noise = np.random.normal(0, 0.0005, len(ph))
    delta_b += noise
    
    # Detect peaks
    peaks = detect_and_quantify_peaks(ph, delta_b)
    
    # Should detect three peaks
    assert len(peaks) == 3
    
    # Check peak positions and step sizes
    for i, (step_ph, step_size) in enumerate(steps):
        assert any(abs(peak["ph_apex"] - step_ph) < 0.2 for peak in peaks)
        assert any(abs(peak["delta_b_step"] - step_size) < 0.002 for peak in peaks)


def test_ph_cutoff():
    """Test that pH cutoff removes peaks beyond the cutoff."""
    # Create synthetic data with steps at various pH values
    ph = np.linspace(2.0, 8.0, 300)
    delta_b = np.zeros_like(ph)
    
    # Add steps at pH 3.0, 5.0, and 7.0
    steps = [(3.0, 0.01), (5.0, 0.02), (7.0, 0.03)]
    
    for step_ph, step_size in steps:
        step_idx = np.where(ph >= step_ph)[0][0]
        delta_b[step_idx:] += step_size
    
    # Add noise
    np.random.seed(42)
    noise = np.random.normal(0, 0.0005, len(ph))
    delta_b += noise
    
    # Detect peaks with different cutoffs
    peaks_no_cutoff = detect_and_quantify_peaks(ph, delta_b, ph_cutoff=None)
    peaks_cutoff_4 = detect_and_quantify_peaks(ph, delta_b, ph_cutoff=4.0)
    peaks_cutoff_6 = detect_and_quantify_peaks(ph, delta_b, ph_cutoff=6.0)
    
    # Without cutoff, should detect all three peaks
    assert len(peaks_no_cutoff) == 3
    
    # With cutoff at pH 4.0, should only detect the first peak (pH 3.0)
    assert len(peaks_cutoff_4) == 1
    assert peaks_cutoff_4[0]["ph_apex"] == pytest.approx(3.0, abs=0.2)
    
    # With cutoff at pH 6.0, should detect the first two peaks (pH 3.0 and 5.0)
    assert len(peaks_cutoff_6) == 2
    assert any(abs(peak["ph_apex"] - 3.0) < 0.2 for peak in peaks_cutoff_6)
    assert any(abs(peak["ph_apex"] - 5.0) < 0.2 for peak in peaks_cutoff_6)


def test_peak_properties():
    """Test that detected peaks have all required properties."""
    # Create synthetic data
    ph, delta_b = create_synthetic_step_data()
    
    # Detect peaks
    peaks = detect_and_quantify_peaks(ph, delta_b)
    
    # Check that each peak has all required properties
    required_properties = ["peak_id", "ph_start", "ph_apex", "ph_end", "delta_b_step"]
    
    for peak in peaks:
        for prop in required_properties:
            assert prop in peak
        
        # Check value types
        assert isinstance(peak["peak_id"], int)
        assert isinstance(peak["ph_start"], float)
        assert isinstance(peak["ph_apex"], float)
        assert isinstance(peak["ph_end"], float)
        assert isinstance(peak["delta_b_step"], float)
        
        # Check value ranges
        assert 2.0 <= peak["ph_start"] <= 6.0
        assert 2.0 <= peak["ph_apex"] <= 6.0
        assert 2.0 <= peak["ph_end"] <= 6.0
        assert peak["ph_start"] <= peak["ph_apex"] <= peak["ph_end"]
