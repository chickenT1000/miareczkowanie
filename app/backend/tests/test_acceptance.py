"""
Acceptance tests for titration analysis.

These tests verify that the application meets key requirements:
1. ΔB step size accuracy within ±3% of true value
2. Fe peak detection before pH 6.5
"""
import pytest
import numpy as np
from peaks import detect_and_quantify_peaks


def create_synthetic_step_data(step_ph=3.5, step_size=0.01, noise_level=0.0002, ph_range=(2.0, 6.0), num_points=200):
    """
    Create synthetic pH and delta_b data with a step at specified pH.
    
    Args:
        step_ph: pH value where the step occurs
        step_size: Size of the step in delta_b (mol/L)
        noise_level: Standard deviation of Gaussian noise
        ph_range: Tuple of (min_ph, max_ph)
        num_points: Number of data points
        
    Returns:
        Tuple of (ph_array, delta_b_array)
    """
    # Create evenly spaced pH values
    ph = np.linspace(ph_range[0], ph_range[1], num_points)
    
    # Create delta_b with a step at step_ph
    delta_b = np.zeros_like(ph)
    step_idx = np.where(ph >= step_ph)[0][0]
    delta_b[step_idx:] = step_size
    
    # Add small random noise
    if noise_level > 0:
        np.random.seed(42)  # For reproducibility
        noise = np.random.normal(0, noise_level, len(ph))
        delta_b += noise
    
    return ph, delta_b


def test_delta_b_step_within_3_percent():
    """
    Test that detected ΔB step size is within ±3% of the true value.
    
    This is a key accuracy requirement for quantitative analysis.
    """
    # Create synthetic data with a known step size
    true_step_size = 0.01  # mol/L
    ph, delta_b = create_synthetic_step_data(step_ph=3.5, step_size=true_step_size, noise_level=0.0002)
    
    # Detect peaks
    peaks = detect_and_quantify_peaks(ph, delta_b)
    
    # There should be exactly one peak
    assert len(peaks) == 1, f"Expected 1 peak, found {len(peaks)}"
    
    # Get the detected step size
    detected_step = peaks[0]["delta_b_step"]
    
    # Calculate percentage error
    percent_error = abs(detected_step - true_step_size) / true_step_size * 100
    
    # Assert the error is within ±3%
    assert percent_error <= 3.0, f"Step size error {percent_error:.2f}% exceeds 3% tolerance"
    
    # Additional checks on peak properties
    assert abs(peaks[0]["ph_apex"] - 3.5) < 0.2, f"Peak apex pH {peaks[0]['ph_apex']} not near expected 3.5"


def test_fe_peak_detected_before_ph_6_5():
    """
    Test that Fe peak is detected before pH 6.5.
    
    Fe3+ typically precipitates around pH 3.2, well before the pH 6.5 cutoff.
    """
    # Create synthetic data with a step at pH 3.2 (representing Fe3+)
    fe_step_ph = 3.2
    ph, delta_b = create_synthetic_step_data(step_ph=fe_step_ph, step_size=0.015, noise_level=0.0003)
    
    # Add a second step after pH 6.5 (should be ignored with cutoff)
    second_step_idx = np.where(ph >= 5.8)[0][0]
    delta_b[second_step_idx:] += 0.02
    
    # Detect peaks with pH cutoff at 6.5
    peaks = detect_and_quantify_peaks(ph, delta_b, ph_cutoff=6.5)
    
    # There should be at least one peak
    assert len(peaks) >= 1, "No peaks detected"
    
    # The first peak should be the Fe peak
    fe_peak = peaks[0]
    
    # Assert the Fe peak is detected before pH 6.5
    assert fe_peak["ph_apex"] < 6.5, f"Fe peak detected at pH {fe_peak['ph_apex']}, should be < 6.5"
    
    # Assert the Fe peak is close to the expected pH
    assert abs(fe_peak["ph_apex"] - fe_step_ph) < 0.2, f"Fe peak at pH {fe_peak['ph_apex']}, expected near {fe_step_ph}"
    
    # Verify that without cutoff, we'd detect both peaks
    all_peaks = detect_and_quantify_peaks(ph, delta_b, ph_cutoff=None)
    assert len(all_peaks) >= 2, "Should detect at least 2 peaks without pH cutoff"


def test_multiple_peaks_with_accurate_steps():
    """
    Test detection of multiple peaks with accurate step sizes.
    
    This simulates a sample with multiple metals, each with its own step.
    """
    # Create pH array
    ph = np.linspace(2.0, 7.0, 250)
    delta_b = np.zeros_like(ph)
    
    # Add three steps at different pH values with known sizes
    steps = [
        {"ph": 3.2, "size": 0.015},  # Fe3+
        {"ph": 4.5, "size": 0.010},  # Al3+
        {"ph": 6.2, "size": 0.020},  # Another metal
    ]
    
    # Apply steps
    for step in steps:
        step_idx = np.where(ph >= step["ph"])[0][0]
        delta_b[step_idx:] += step["size"]
    
    # Add noise
    np.random.seed(42)
    noise = np.random.normal(0, 0.0002, len(ph))
    delta_b += noise
    
    # Detect peaks without cutoff to get all three
    peaks = detect_and_quantify_peaks(ph, delta_b, ph_cutoff=None)
    
    # Should detect three peaks
    assert len(peaks) == 3, f"Expected 3 peaks, found {len(peaks)}"
    
    # Check each peak's step size accuracy
    for i, step in enumerate(steps):
        detected_step = peaks[i]["delta_b_step"]
        true_step = step["size"]
        
        # Calculate percentage error
        percent_error = abs(detected_step - true_step) / true_step * 100
        
        # Assert the error is within ±3%
        assert percent_error <= 3.0, f"Step {i+1} error {percent_error:.2f}% exceeds 3% tolerance"
        
        # Check peak position
        assert abs(peaks[i]["ph_apex"] - step["ph"]) < 0.2, f"Peak {i+1} position error too large"
