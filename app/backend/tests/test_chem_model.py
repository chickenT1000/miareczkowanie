"""
Tests for the chemical model and calculations in chem.py.
"""
import pytest
import numpy as np
from chem import (
    compute_h_from_ph,
    compute_oh,
    compute_sulfate_fraction,
    time_to_base_volume,
    compute_base_moles,
    compute_normalized_base,
    compute_sodium_with_dilution,
    compute_h2so4_model,
    convert_na_to_normalized_base,
    convert_normalized_base_to_na,
    estimate_c_a,
    process_row,
    process_titration_data,
)
from models import K_A2, K_W


def test_compute_h_from_ph():
    """Test H+ concentration calculation from pH."""
    # Test a few specific values
    assert compute_h_from_ph(7.0) == 1e-7
    assert compute_h_from_ph(0.0) == 1.0
    assert compute_h_from_ph(14.0) == 1e-14
    
    # Test a range of values
    for ph in np.linspace(0, 14, 15):
        h = compute_h_from_ph(ph)
        assert h == 10**(-ph)


def test_compute_oh():
    """Test OH- concentration calculation from H+."""
    # Test a few specific values
    assert compute_oh(1e-7) == pytest.approx(1e-7)   # At pH 7, [OH-] ≈ [H+] = 1e-7
    assert compute_oh(1.0) == pytest.approx(1e-14)    # At pH 0, [OH-] ≈ Kw/[H+]
    assert compute_oh(1e-14) == pytest.approx(1.0)    # At pH 14, [OH-] ≈ 1.0
    
    # Test with custom Kw
    assert compute_oh(1e-7, 1e-15) == pytest.approx(1e-8)  # With Kw = 1e-15


def test_compute_sulfate_fraction():
    """Test sulfate fraction f(H) calculation."""
    # At high [H+] (low pH), f(H) approaches 1
    assert compute_sulfate_fraction(1.0) == pytest.approx(1.0, rel=2e-2)
    
    # At low [H+] (high pH), f(H) approaches 2
    assert compute_sulfate_fraction(1e-12) == pytest.approx(2.0, rel=1e-2)
    
    # At [H+] = Ka2, f(H) should be (1 + 2) / (1 + 1) = 1.5
    assert compute_sulfate_fraction(K_A2) == pytest.approx(1.5, rel=1e-2)
    
    # Test with custom Ka2
    custom_ka2 = 1e-3
    assert compute_sulfate_fraction(custom_ka2, custom_ka2) == pytest.approx(1.5, rel=1e-2)


def test_time_to_base_volume():
    """Test conversion from time to base volume."""
    # Test with default pump rate (1.0 mL/min)
    assert time_to_base_volume(60, 1.0, "s") == 1.0  # 60s = 1min = 1mL at 1mL/min
    assert time_to_base_volume(120, 1.0, "s") == 2.0  # 120s = 2min = 2mL at 1mL/min
    
    # Test with custom pump rate
    assert time_to_base_volume(60, 2.0, "s") == 2.0  # 60s = 1min = 2mL at 2mL/min
    
    # Test with time in minutes
    assert time_to_base_volume(1, 1.0, "min") == 1.0  # 1min = 1mL at 1mL/min
    assert time_to_base_volume(2, 2.0, "min") == 4.0  # 2min = 4mL at 2mL/min


def test_compute_base_moles():
    """Test calculation of base moles from volume."""
    # Test with default concentration (0.1 mol/L)
    assert compute_base_moles(10.0) == 0.001  # 10mL * 0.1mol/L / 1000 = 0.001mol
    
    # Test with custom concentration
    assert compute_base_moles(10.0, 0.2) == 0.002  # 10mL * 0.2mol/L / 1000 = 0.002mol


def test_compute_normalized_base():
    """Test calculation of normalized base concentration."""
    # Test with default initial volume (100 mL)
    assert compute_normalized_base(0.001) == 0.01  # 0.001mol / (100mL/1000) = 0.01mol/L
    
    # Test with custom initial volume
    assert compute_normalized_base(0.001, 200.0) == 0.005  # 0.001mol / (200mL/1000) = 0.005mol/L


def test_compute_sodium_with_dilution():
    """Test calculation of sodium concentration with dilution."""
    # Test with various parameters
    assert compute_sodium_with_dilution(10.0, 0.1, 100.0) == pytest.approx(0.00909, rel=1e-3)
    # 0.1mol/L * 10mL / (100mL + 10mL) = 0.00909mol/L
    
    assert compute_sodium_with_dilution(20.0, 0.2, 200.0) == pytest.approx(0.01818, rel=1e-3)
    # 0.2mol/L * 20mL / (200mL + 20mL) = 0.01818mol/L


def test_compute_h2so4_model():
    """Test H2SO4 model calculation."""
    # Test with various parameters
    h = 1e-3  # pH 3
    oh = 1e-11  # Kw/h
    c_a = 0.05  # Total sulfate concentration
    f_h = 1.1  # Sulfate fraction
    
    # Na_model = c_a * f_h + oh - h
    expected = 0.05 * 1.1 + 1e-11 - 1e-3
    assert compute_h2so4_model(h, oh, c_a, f_h) == pytest.approx(expected, rel=1e-3)


def test_conversion_functions_invert():
    """Test that normalized base <-> Na conversion functions invert properly."""
    # Test a range of values
    c_b = 0.1  # Base concentration
    
    for b_meas in [0.001, 0.01, 0.05, 0.1, 0.2]:
        # Convert normalized base to Na
        na = convert_normalized_base_to_na(b_meas, c_b)
        
        # Convert Na back to normalized base
        b_meas_back = convert_na_to_normalized_base(na, c_b)
        
        # Verify the conversion is invertible (within numerical precision)
        assert b_meas_back == pytest.approx(b_meas, rel=1e-10)


def test_estimate_c_a_synthetic():
    """Test C_A estimation with synthetic data."""
    # Generate synthetic pH values
    ph_values = np.linspace(2.0, 3.0, 10)
    
    # Assume a known C_A
    true_c_a = 0.05  # mol/L
    
    # Calculate h, oh, f(H) values
    h_values = [compute_h_from_ph(ph) for ph in ph_values]
    oh_values = [compute_oh(h) for h in h_values]
    f_h_values = [compute_sulfate_fraction(h) for h in h_values]
    
    # Calculate Na_model values using the H2SO4 model
    na_values = [compute_h2so4_model(h, oh, true_c_a, f_h) 
                for h, oh, f_h in zip(h_values, oh_values, f_h_values)]
    
    # Add small random noise to Na values to simulate measurement error
    np.random.seed(42)  # For reproducibility
    noise = np.random.normal(0, 0.0001, len(na_values))
    na_values_with_noise = [na + n for na, n in zip(na_values, noise)]
    
    # Estimate C_A from noisy data
    estimated_c_a = estimate_c_a(ph_values, na_values_with_noise, h_values, oh_values)
    
    # Verify the estimated C_A is close to the true value
    assert estimated_c_a == pytest.approx(true_c_a, rel=1e-2)


def test_estimate_c_a_with_outliers():
    """Test C_A estimation with outliers in the data."""
    # Generate synthetic pH values
    ph_values = np.linspace(2.0, 3.0, 10)
    
    # Assume a known C_A
    true_c_a = 0.05  # mol/L
    
    # Calculate h, oh, f(H) values
    h_values = [compute_h_from_ph(ph) for ph in ph_values]
    oh_values = [compute_oh(h) for h in h_values]
    f_h_values = [compute_sulfate_fraction(h) for h in h_values]
    
    # Calculate Na_model values using the H2SO4 model
    na_values = [compute_h2so4_model(h, oh, true_c_a, f_h) 
                for h, oh, f_h in zip(h_values, oh_values, f_h_values)]
    
    # Add outliers
    na_values[2] *= 2.0  # Double one value
    na_values[7] *= 0.5  # Halve another value
    
    # Estimate C_A from data with outliers
    estimated_c_a = estimate_c_a(ph_values, na_values, h_values, oh_values)
    
    # Verify the estimated C_A is still reasonably close to the true value
    # The median-based estimator should be robust to outliers
    assert estimated_c_a == pytest.approx(true_c_a, rel=0.1)


def test_process_row():
    """Test processing of a single data row."""
    # Test with default parameters
    row = process_row(ph=3.0, time=60.0, c_a=0.05)
    
    # Check that all expected keys are present
    expected_keys = ["time", "pH", "v_b", "n_b", "b_meas", "na", "h", "oh", "b_model", "delta_b"]
    for key in expected_keys:
        assert key in row
    
    # Check some specific values
    assert row["time"] == 60.0
    assert row["pH"] == 3.0
    assert row["v_b"] == 1.0  # 60s = 1min = 1mL at default 1mL/min
    assert row["h"] == 1e-3  # pH 3 -> [H+] = 10^-3
    
    # Test with custom parameters
    row = process_row(
        ph=4.0, 
        time=120.0, 
        c_b=0.2, 
        q=2.0, 
        v0=200.0, 
        time_unit="s", 
        c_a=0.1
    )
    
    # Check some specific values with custom parameters
    assert row["v_b"] == 4.0  # 120s = 2min = 4mL at 2mL/min
    assert row["n_b"] == 0.0008  # 4mL * 0.2mol/L / 1000 = 0.0008mol


def test_process_titration_data():
    """Test processing of complete titration dataset."""
    # Generate synthetic data
    ph_values = np.linspace(2.0, 6.0, 20)
    time_values = np.linspace(0, 1200, 20)  # 0 to 20 minutes in seconds
    
    # Process the data
    processed_rows, c_a = process_titration_data(
        ph_values=ph_values,
        time_values=time_values,
        c_b=0.1,
        q=1.0,
        v0=100.0,
        time_unit="s",
        start_index=0
    )
    
    # Check that we got the expected number of rows
    assert len(processed_rows) == 20
    
    # Check that each row has all expected fields
    for row in processed_rows:
        assert "time" in row
        assert "pH" in row
        assert "v_b" in row
        assert "n_b" in row
        assert "b_meas" in row
        assert "na" in row
        assert "b_model" in row
        assert "delta_b" in row
        assert "d_delta_b_d_ph" in row
    
    # Check that start_index is applied correctly
    start_index = 5
    processed_rows_with_start, _ = process_titration_data(
        ph_values=ph_values,
        time_values=time_values,
        start_index=start_index
    )
    
    assert len(processed_rows_with_start) == len(ph_values) - start_index
    assert processed_rows_with_start[0]["pH"] == ph_values[start_index]
    assert processed_rows_with_start[0]["time"] == time_values[start_index]
