"""
Chemistry calculations for titration analysis.

This module implements the core chemistry model for acid-base titrations:
1. H+ and OH- concentrations from pH
2. Sulfate speciation fraction f(H)
3. Base volume and moles from time
4. Dilution corrections
5. H₂SO₄-only model based on electroneutrality
6. Robust C_A estimation

All concentrations are in mol/L unless otherwise specified.
"""
from typing import Dict, List, Optional, Tuple, Union, Sequence
import numpy as np
from scipy import stats
from scipy import optimize

# Import constants from models.py
from models import K_A2, K_W


def compute_h_from_ph(ph: float) -> float:
    """
    Calculate H+ concentration from pH.
    
    Args:
        ph: pH value
        
    Returns:
        H+ concentration in mol/L
    """
    return 10 ** (-ph)


def compute_oh(h: float, k_w: float = K_W) -> float:
    """
    Calculate OH- concentration from H+ using water dissociation constant.
    
    Args:
        h: H+ concentration in mol/L
        k_w: Water dissociation constant (default from models.K_W)
        
    Returns:
        OH- concentration in mol/L
    """
    return k_w / h


def compute_sulfate_fraction(h: float, k_a2: float = K_A2) -> float:
    """
    Calculate the fraction f(H) for sulfate speciation.
    
    f(H) = (H + 2*K_a2)/(H + K_a2)
    
    This represents the average charge per sulfate molecule and is used
    in the electroneutrality equation.
    
    Args:
        h: H+ concentration in mol/L
        k_a2: Second dissociation constant of H2SO4 (default from models.K_A2)
        
    Returns:
        Sulfate fraction f(H)
    """
    return (h + 2 * k_a2) / (h + k_a2)


def time_to_base_volume(
    time: float, 
    q: float = 1.0, 
    time_unit: str = "s"
) -> float:
    """
    Convert time to delivered base volume.
    
    Args:
        time: Time value
        q: Pump rate in mL/min (default 1.0)
        time_unit: Time unit, 's' for seconds or 'min' for minutes (default 's')
        
    Returns:
        Base volume in mL
    """
    # If time is in seconds, convert to minutes first
    if time_unit == "s":
        time_min = time / 60
    else:
        time_min = time
    
    return q * time_min


def compute_base_moles(
    v_b: float, 
    c_b: float = 0.1
) -> float:
    """
    Calculate moles of base delivered.
    
    Args:
        v_b: Base volume in mL
        c_b: Base concentration in mol/L (default 0.1)
        
    Returns:
        Base moles in mol
    """
    return c_b * v_b / 1000  # Convert mL to L


def compute_normalized_base(
    n_b: float, 
    v0: float = 100.0
) -> float:
    """
    Calculate normalized base concentration (B_meas).
    
    B_meas = n_b / (V₀/1000)  [mol/L "per initial volume"]
    
    Args:
        n_b: Base moles in mol
        v0: Initial sample volume in mL (default 100.0)
        
    Returns:
        Normalized base concentration in mol/L
    """
    return n_b / (v0 / 1000)


def compute_sodium_with_dilution(
    v_b: float, 
    c_b: float, 
    v0: float
) -> float:
    """
    Calculate instantaneous sodium concentration with dilution.
    
    Na = (C_b * V_b/1000) / ((V₀ + V_b)/1000) = C_b * V_b / (V₀ + V_b)  [mol/L]
    
    Args:
        v_b: Base volume in mL
        c_b: Base concentration in mol/L
        v0: Initial sample volume in mL
        
    Returns:
        Sodium concentration with dilution in mol/L
    """
    return c_b * v_b / (v0 + v_b)


def compute_h2so4_model(
    h: float, 
    oh: float, 
    c_a: float, 
    sulfate_fraction: float
) -> float:
    """
    Calculate sodium concentration based on H₂SO₄-only model (electroneutrality).
    
    Na_model = C_A * f(H) + OH - H
    
    Args:
        h: H+ concentration in mol/L
        oh: OH- concentration in mol/L
        c_a: Total sulfate concentration in mol/L
        sulfate_fraction: Sulfate fraction f(H)
        
    Returns:
        Model sodium concentration in mol/L
    """
    return c_a * sulfate_fraction + oh - h


def convert_na_to_normalized_base(
    na_model: float, 
    c_b: float
) -> float:
    """
    Convert sodium concentration to normalized base (B_model).
    
    B_model = Na_model / (1 - Na_model / C_b)
    
    This inverts the dilution relation to get back to the normalized-dose axis.
    
    Args:
        na_model: Sodium concentration from model in mol/L
        c_b: Base concentration in mol/L
        
    Returns:
        Model base in mol/L (normalized to initial volume)
    """
    return na_model / (1 - na_model / c_b)


def convert_normalized_base_to_na(
    b_meas: float, 
    c_b: float
) -> float:
    """
    Convert normalized base to sodium concentration.
    
    Na_meas = B_meas / (1 + B_meas/C_b)
    
    Args:
        b_meas: Normalized base in mol/L
        c_b: Base concentration in mol/L
        
    Returns:
        Sodium concentration in mol/L
    """
    return b_meas / (1 + b_meas / c_b)


# --------------------------------------------------------------------------- #
#  New helpers: standalone model curve generation                             #
# --------------------------------------------------------------------------- #

def solve_h(c_a_mix: float, na: float) -> float:
    """
    Solve for H⁺ given Na and diluted acid concentration using electroneutrality.

    Equation:  g(h) = c_a_mix * f(h) + K_W / h - h - na = 0

    Args:
        c_a_mix: Diluted acid concentration (mol/L)
        na: Sodium concentration (mol/L)

    Returns:
        H⁺ concentration (mol/L)

    Raises:
        ValueError if root not bracketed even after expanding search range.
    """
    def g(h: float) -> float:
        f_h = compute_sulfate_fraction(h)
        return c_a_mix * f_h + K_W / h - h - na

    # Initial conservative bracket in acidic domain up to 1 M
    lower, upper = 1e-14, 1.0

    # If g(lower) and g(upper) have same sign, expand the bracket
    if np.sign(g(lower)) == np.sign(g(upper)):
        lower, upper = 1e-16, 10.0  # broaden search

    if np.sign(g(lower)) == np.sign(g(upper)):
        raise ValueError("Root not bracketed for h; check parameters.")

    return optimize.brentq(g, lower, upper, maxiter=100, xtol=1e-14)


def build_model_curve(
    c_a: float,
    c_b: float,
    num_points: int = 200,
    target_ph: float = 7.0,
) -> Tuple[List[float], List[float]]:
    """
    Generate a standalone H₂SO₄ model curve (pH vs B) up to target pH.

    Args:
        c_a: Total sulfate concentration (mol/L)
        c_b: Base concentration (mol/L)
        num_points: Number of points for the curve
        target_ph: Target pH to reach (default 7.0)

    Returns:
        Tuple (ph_list, b_list) with length up to `num_points`
    """
    # Adaptive upper bound for B
    b_max = 2.5 * c_a
    max_iterations = 8
    
    ph_list: List[float] = []
    b_list: List[float] = []
    
    for iteration in range(max_iterations):
        b_grid = np.linspace(0.0, b_max, num_points)
        
        # Clear previous results if retrying with higher b_max
        if iteration > 0:
            ph_list = []
            b_list = []
        
        for b in b_grid:
            try:
                # Convert B to Na
                na = convert_normalized_base_to_na(float(b), c_b)
                
                # Calculate diluted acid concentration
                c_a_mix = c_a / (1 + b / c_b)
                
                # Solve for H+ and calculate pH
                h = solve_h(c_a_mix, na)
                ph_val = -np.log10(h)
                
                ph_list.append(ph_val)
                b_list.append(float(b))
                
            except ValueError:
                # Skip if solver fails (should be rare near bounds)
                continue
        
        # Check if we reached target pH
        if not ph_list or ph_list[-1] < target_ph:
            b_max *= 2  # Double the upper bound and try again
        else:
            break  # We reached the target pH
    
    return ph_list, b_list


def estimate_c_a(
    ph_values: Sequence[float],
    na_values: Sequence[float],
    h_values: Optional[Sequence[float]] = None,
    oh_values: Optional[Sequence[float]] = None,
    k_a2: float = K_A2,
    k_w: float = K_W
) -> float:
    """
    Estimate total sulfate concentration (C_A) from baseline window.
    
    For rows in the user-selected baseline window:
    C_A,j = (Na_meas,j + H_j - OH_j)/f(H_j)
    
    Uses robust median with MAD outlier rejection.
    
    Args:
        ph_values: pH values in baseline window
        na_values: Measured sodium values with dilution
        h_values: Optional pre-computed H+ values (if None, calculated from pH)
        oh_values: Optional pre-computed OH- values (if None, calculated from H+)
        k_a2: Second dissociation constant of H2SO4
        k_w: Water dissociation constant
        
    Returns:
        Estimated total sulfate concentration in mol/L
    """
    if len(ph_values) == 0:
        return 0.0
    
    # Calculate H+ if not provided
    if h_values is None:
        h_values = [compute_h_from_ph(ph) for ph in ph_values]
    
    # Calculate OH- if not provided
    if oh_values is None:
        oh_values = [compute_oh(h, k_w) for h in h_values]
    
    # Calculate sulfate fractions
    f_h_values = [compute_sulfate_fraction(h, k_a2) for h in h_values]
    
    # Calculate individual C_A estimates
    c_a_estimates = [
        (na + h - oh) / f_h 
        for na, h, oh, f_h in zip(na_values, h_values, oh_values, f_h_values)
    ]
    
    # Robust estimator: median with MAD-based outlier rejection
    c_a_arr = np.asarray(c_a_estimates, dtype=float)
    median_val = np.median(c_a_arr)

    # Median absolute deviation
    mad = np.median(np.abs(c_a_arr - median_val))

    if mad == 0:  # all points identical or too few points
        return float(median_val)

    # Scale factor 1.4826 converts MAD to std-dev equivalent for normal dist.
    threshold = 3.0 * 1.4826 * mad
    inlier_mask = np.abs(c_a_arr - median_val) <= threshold

    inliers = c_a_arr[inlier_mask]

    # Fallback to overall median if no inliers (should be rare)
    if inliers.size == 0:
        return float(median_val)

    return float(np.median(inliers))


def process_row(
    ph: float,
    time: float,
    c_b: float = 0.1,
    q: float = 1.0,
    v0: float = 100.0,
    time_unit: str = "s",
    c_a: Optional[float] = None,
    k_a2: float = K_A2,
    k_w: float = K_W
) -> Dict[str, float]:
    """
    Process a single data row with all calculations.
    
    Args:
        ph: pH value
        time: Time value
        c_b: Base concentration in mol/L
        q: Pump rate in mL/min
        v0: Initial sample volume in mL
        time_unit: Time unit ('s' or 'min')
        c_a: Total sulfate concentration (if None, no model calculations)
        k_a2: Second dissociation constant of H2SO4
        k_w: Water dissociation constant
        
    Returns:
        Dictionary with all calculated values
    """
    # TODO: Implement full row processing
    # This is a placeholder that will chain all the calculations
    
    # Calculate H+ and OH-
    h = compute_h_from_ph(ph)
    oh = compute_oh(h, k_w)
    
    # Calculate base volume and moles
    v_b = time_to_base_volume(time, q, time_unit)
    n_b = compute_base_moles(v_b, c_b)
    
    # Calculate normalized base and sodium with dilution
    b_meas = compute_normalized_base(n_b, v0)
    na_meas = compute_sodium_with_dilution(v_b, c_b, v0)
    
    # Initialize model values
    b_model = 0.0
    delta_b = 0.0
    
    # Calculate model if C_A is provided
    if c_a is not None:
        sulfate_fraction = compute_sulfate_fraction(h, k_a2)
        na_model = compute_h2so4_model(h, oh, c_a, sulfate_fraction)
        b_model = convert_na_to_normalized_base(na_model, c_b)
        delta_b = b_meas - b_model
    
    # Return all calculated values
    return {
        "time": time,
        "pH": ph,
        "v_b": v_b,
        "n_b": n_b,
        "b_meas": b_meas,
        "na": na_meas,
        "h": h,
        "oh": oh,
        "b_model": b_model,
        "delta_b": delta_b,
        # d_delta_b_d_ph will be calculated separately after smoothing
    }


def compute_derivative(
    x: Sequence[float], 
    y: Sequence[float]
) -> List[float]:
    """
    Compute central difference derivative dy/dx.
    
    Args:
        x: x-values (e.g., pH)
        y: y-values (e.g., delta_b)
        
    Returns:
        List of derivative values
    """
    # TODO: Implement central difference derivative
    # This is a placeholder for a proper implementation
    
    if len(x) <= 1:
        return [0.0] * len(x)
    
    # Simple central difference for interior points
    # Forward/backward difference for endpoints
    derivatives = []
    for i in range(len(x)):
        if i == 0:
            # Forward difference for first point
            dx = x[1] - x[0]
            dy = y[1] - y[0]
        elif i == len(x) - 1:
            # Backward difference for last point
            dx = x[i] - x[i-1]
            dy = y[i] - y[i-1]
        else:
            # Central difference for interior points
            dx = x[i+1] - x[i-1]
            dy = y[i+1] - y[i-1]
        
        if dx != 0:
            derivatives.append(dy / dx)
        else:
            derivatives.append(0.0)
    
    return derivatives


def process_titration_data(
    ph_values: Sequence[float],
    time_values: Sequence[float],
    c_b: float = 0.1,
    q: float = 1.0,
    v0: float = 100.0,
    time_unit: str = "s",
    start_index: int = 0,
    baseline_end_index: Optional[int] = None
) -> Tuple[List[Dict[str, float]], float]:
    """
    Process complete titration dataset.
    
    Args:
        ph_values: List of pH values
        time_values: List of time values
        c_b: Base concentration in mol/L
        q: Pump rate in mL/min
        v0: Initial sample volume in mL
        time_unit: Time unit ('s' or 'min')
        start_index: Index to start calculations from
        baseline_end_index: End index for baseline window (for C_A estimation)
        
    Returns:
        Tuple of (processed rows, estimated C_A)
    """
    # TODO: Implement full dataset processing
    # This is a placeholder for the complete implementation
    
    # Apply start index
    ph_values = ph_values[start_index:]
    time_values = time_values[start_index:]
    
    # Process each row without model first to get Na values for C_A estimation
    initial_processed = []
    for ph, time in zip(ph_values, time_values):
        row = process_row(ph, time, c_b, q, v0, time_unit)
        initial_processed.append(row)
    
    # Determine baseline window for C_A estimation
    if baseline_end_index is None:
        # Default to first 20% of data points if not specified
        baseline_end_index = max(3, int(len(initial_processed) * 0.2))
    
    # Extract values for C_A estimation
    baseline_ph = [row["pH"] for row in initial_processed[:baseline_end_index]]
    baseline_na = [row["na"] for row in initial_processed[:baseline_end_index]]
    baseline_h = [row["h"] for row in initial_processed[:baseline_end_index]]
    baseline_oh = [row["oh"] for row in initial_processed[:baseline_end_index]]
    
    # Estimate C_A from baseline
    c_a = estimate_c_a(baseline_ph, baseline_na, baseline_h, baseline_oh)
    
    # ------------------------------------------------------------------ #
    # Reprocess with model using estimated C_A
    # ------------------------------------------------------------------ #
    final_processed = []
    for ph, time in zip(ph_values, time_values):
        row = process_row(ph, time, c_b, q, v0, time_unit, c_a)
        final_processed.append(row)
    
    # ------------------------------------------------------------------ #
    # Build physically-constrained model in the Na domain
    # ------------------------------------------------------------------ #
    if final_processed:
        # 1. Raw Na_model based on electroneutrality with dilution
        na_model_raw = []
        for row in final_processed:
            # Calculate diluted acid concentration
            c_a_mix = c_a * (v0 / (v0 + row["v_b"]))
            f_h = compute_sulfate_fraction(row["h"])
            na_m = compute_h2so4_model(row["h"], row["oh"], c_a_mix, f_h)
            na_model_raw.append(na_m)

        # 2. Anchor to measured Na at first point
        na_offset = na_model_raw[0] - final_processed[0]["na"]
        na_model_shifted = [na_m - na_offset for na_m in na_model_raw]

        # 3. Clamp to physical bounds and enforce monotonicity
        na_model_clamped: List[float] = []
        prev_val = 0.0
        upper_bound = 0.999 * c_b  # avoid division singularity
        for na_m in na_model_shifted:
            na_m = max(0.0, min(upper_bound, na_m))       # clamp
            na_m = max(prev_val, na_m)                    # monotone non-decreasing
            na_model_clamped.append(na_m)
            prev_val = na_m

        # 4. Convert back to B_model and update rows
        for row, na_m in zip(final_processed, na_model_clamped):
            b_model = convert_na_to_normalized_base(na_m, c_b)
            row["b_model"] = b_model
            row["delta_b"] = row["b_meas"] - b_model

    # Extract delta_b and pH for derivative calculation
    delta_b_values = [row["delta_b"] for row in final_processed]
    ph_for_deriv = [row["pH"] for row in final_processed]
    
    # Calculate derivatives
    derivatives = compute_derivative(ph_for_deriv, delta_b_values)
    
    # Add derivatives to processed rows
    for i, deriv in enumerate(derivatives):
        final_processed[i]["d_delta_b_d_ph"] = deriv
    
    return final_processed, c_a
