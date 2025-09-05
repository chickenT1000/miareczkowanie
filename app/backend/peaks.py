"""
Peak detection and quantification for titration analysis.

This module implements:
1. Smoothing of ΔB(pH) with Savitzky-Golay filter
2. Derivative calculation
3. Peak finding in the derivative curve
4. Peak boundary detection via zero-crossings
5. Step size calculation and metal quantification
"""
from typing import Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
from scipy import signal


def smooth_data(
    y: Sequence[float],
    window_length: int = 9,
    polyorder: int = 3
) -> np.ndarray:
    """
    Apply Savitzky-Golay filter to smooth data.
    
    Args:
        y: Data to smooth
        window_length: Window length for filter (must be odd, default 9)
        polyorder: Polynomial order (default 3)
        
    Returns:
        Smoothed data as numpy array
    """
    # Ensure window length is odd
    if window_length % 2 == 0:
        window_length += 1
    
    # Ensure window length is less than data length
    if len(y) < window_length:
        # Fall back to smaller window or no smoothing for short data
        if len(y) > 3:
            window_length = min(len(y) - 2, 5)
            polyorder = min(polyorder, window_length - 1)
            return signal.savgol_filter(y, window_length, polyorder)
        else:
            return np.array(y)
    
    return signal.savgol_filter(y, window_length, polyorder)


def compute_derivative(
    x: Sequence[float], 
    y: Sequence[float]
) -> np.ndarray:
    """
    Compute central difference derivative dy/dx.
    
    Args:
        x: x-values (e.g., pH)
        y: y-values (e.g., delta_b)
        
    Returns:
        Derivative values as numpy array
    """
    if len(x) <= 1:
        return np.zeros(len(x))
    
    # Convert to numpy arrays
    x_arr = np.array(x)
    y_arr = np.array(y)
    
    # Central difference for interior points
    dy = np.zeros_like(y_arr)
    
    # Forward difference for first point
    dy[0] = (y_arr[1] - y_arr[0]) / (x_arr[1] - x_arr[0]) if x_arr[1] != x_arr[0] else 0
    
    # Central difference for interior points
    for i in range(1, len(x) - 1):
        dy[i] = (y_arr[i+1] - y_arr[i-1]) / (x_arr[i+1] - x_arr[i-1]) if x_arr[i+1] != x_arr[i-1] else 0
    
    # Backward difference for last point
    dy[-1] = (y_arr[-1] - y_arr[-2]) / (x_arr[-1] - x_arr[-2]) if x_arr[-1] != x_arr[-2] else 0
    
    return dy


def find_zero_crossings(
    x: Sequence[float],
    y: Sequence[float]
) -> List[int]:
    """
    Find indices where the data crosses zero.
    
    Args:
        x: x-values (e.g., pH)
        y: y-values (e.g., derivative)
        
    Returns:
        List of indices where zero crossings occur
    """
    # Convert to numpy arrays
    y_arr = np.array(y)
    
    # Find sign changes
    sign_changes = np.where(np.diff(np.signbit(y_arr)))[0]
    
    # Return as list of indices
    return list(sign_changes)


def find_peaks_in_derivative(
    x: Sequence[float],
    y: Sequence[float],
    height: Optional[float] = None,
    prominence: Optional[float] = None,
    width: Optional[float] = None,
    ph_cutoff: Optional[float] = 6.5
) -> Tuple[List[int], Dict[str, np.ndarray]]:
    """
    Find peaks in the derivative curve using SciPy's find_peaks.
    
    Args:
        x: x-values (pH)
        y: y-values (derivative)
        height: Minimum peak height
        prominence: Minimum peak prominence
        width: Minimum peak width
        ph_cutoff: pH cutoff for peak detection (default 6.5)
        
    Returns:
        Tuple of (peak indices, peak properties)
    """
    # Apply pH cutoff if provided
    if ph_cutoff is not None:
        cutoff_idx = next((i for i, ph in enumerate(x) if ph > ph_cutoff), len(x))
        if cutoff_idx == 0:
            return [], {}
        
        x = x[:cutoff_idx]
        y = y[:cutoff_idx]
    
    if not x or len(x) < 3:
        return [], {}
    
    # Find peaks using SciPy
    peak_indices, peak_props = signal.find_peaks(
        y,
        height=height,
        prominence=prominence,
        width=width
    )
    
    return list(peak_indices), peak_props


def calculate_peak_step(
    ph_values: Sequence[float],
    delta_b_values: Sequence[float],
    peak_start_idx: int,
    peak_end_idx: int
) -> float:
    """
    Calculate the step size (ΔB_step) for a peak.
    
    ΔB_step = ΔB(pH_end) - ΔB(pH_start)
    
    Args:
        ph_values: pH values
        delta_b_values: ΔB values
        peak_start_idx: Index of peak start
        peak_end_idx: Index of peak end
        
    Returns:
        Step size in mol/L
    """
    # Ensure indices are within bounds
    start_idx = max(0, min(peak_start_idx, len(delta_b_values) - 1))
    end_idx = max(0, min(peak_end_idx, len(delta_b_values) - 1))
    
    # Calculate step size
    delta_b_step = delta_b_values[end_idx] - delta_b_values[start_idx]
    
    return delta_b_step


def calculate_metal_concentration(
    delta_b_step: float,
    stoichiometry: int
) -> float:
    """
    Calculate metal concentration from step size and stoichiometry.
    
    c_metal = ΔB_step / ν
    
    Args:
        delta_b_step: Step size in mol/L
        stoichiometry: Stoichiometry (OH⁻/mol metal)
        
    Returns:
        Metal concentration in mol/L
    """
    if stoichiometry <= 0:
        return 0.0
    
    return delta_b_step / stoichiometry


def detect_and_quantify_peaks(
    ph_values: Sequence[float],
    delta_b_values: Sequence[float],
    derivative_values: Optional[Sequence[float]] = None,
    window_length: int = 9,
    polyorder: int = 3,
    height: Optional[float] = None,
    prominence: Optional[float] = 0.001,
    width: Optional[float] = None,
    ph_cutoff: float = 6.5
) -> List[Dict[str, Union[int, float]]]:
    """
    Detect and quantify peaks in titration data.
    
    Args:
        ph_values: pH values
        delta_b_values: ΔB values (excess base)
        derivative_values: Optional pre-computed derivative values
        window_length: Window length for Savitzky-Golay filter
        polyorder: Polynomial order for Savitzky-Golay filter
        height: Minimum peak height for detection
        prominence: Minimum peak prominence for detection
        width: Minimum peak width for detection
        ph_cutoff: pH cutoff for peak detection
        
    Returns:
        List of peak data dictionaries with keys:
            - peak_id: Unique peak identifier
            - ph_start: pH at peak start
            - ph_apex: pH at peak apex
            - ph_end: pH at peak end
            - delta_b_step: Step size in excess base (mol/L)
    """
    # Convert inputs to numpy arrays
    ph_arr = np.array(ph_values)
    delta_b_arr = np.array(delta_b_values)
    
    # Smooth delta_b data
    smoothed_delta_b = smooth_data(delta_b_arr, window_length, polyorder)
    
    # Compute derivative if not provided
    if derivative_values is None:
        derivative = compute_derivative(ph_arr, smoothed_delta_b)
    else:
        derivative = np.array(derivative_values)
    
    # Find peaks in derivative
    peak_indices, peak_props = find_peaks_in_derivative(
        ph_arr,
        derivative,
        height=height,
        prominence=prominence,
        width=width,
        ph_cutoff=ph_cutoff
    )
    
    # Find zero crossings in derivative for peak boundaries
    zero_crossings = find_zero_crossings(ph_arr, derivative)
    
    # Process each peak
    peaks = []
    for i, peak_idx in enumerate(peak_indices):
        # Find nearest zero crossing before peak
        start_crossings = [idx for idx in zero_crossings if idx < peak_idx]
        start_idx = max(start_crossings) if start_crossings else 0
        
        # Find nearest zero crossing after peak
        end_crossings = [idx for idx in zero_crossings if idx > peak_idx]
        end_idx = min(end_crossings) if end_crossings else len(ph_arr) - 1
        
        # Calculate step size
        delta_b_step = calculate_peak_step(ph_arr, smoothed_delta_b, start_idx, end_idx)
        
        # Create peak data
        peak = {
            "peak_id": i + 1,
            "ph_start": float(ph_arr[start_idx]),
            "ph_apex": float(ph_arr[peak_idx]),
            "ph_end": float(ph_arr[end_idx]),
            "delta_b_step": float(delta_b_step)
        }
        
        peaks.append(peak)
    
    return peaks
