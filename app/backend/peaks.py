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

    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)

    # Use gradient with edge_order=2 for better endpoint behavior
    return np.gradient(y_arr, x_arr, edge_order=2)


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
    y_arr = np.asarray(y, dtype=float)

    if y_arr.size == 0:
        return []

    # Compute sign array: -1, 0, 1
    signs = np.sign(y_arr)

    # Replace zeros with previous sign to avoid ambiguous sign flips
    for i in range(1, len(signs)):
        if signs[i] == 0:
            signs[i] = signs[i - 1]

    # Include indices where original value is exactly zero
    zero_indices = np.where(y_arr == 0)[0]

    # Sign changes occur where sign diff is non-zero
    change_indices = np.where(np.diff(signs) != 0)[0]

    crossings = np.unique(np.concatenate((zero_indices, change_indices))).tolist()
    crossings.sort()
    return crossings


def find_peaks_in_derivative(
    x: Sequence[float],
    y: Sequence[float],
    height: Optional[float] = None,
    prominence: Optional[float] = None,
    width: Optional[float] = None,
    distance: Optional[int] = None,
    ph_cutoff: Optional[float] = None
) -> Tuple[List[int], Dict[str, np.ndarray]]:
    """
    Find peaks in the derivative curve using SciPy's find_peaks.
    
    Args:
        x: x-values (pH)
        y: y-values (derivative)
        height: Minimum peak height
        prominence: Minimum peak prominence
        width: Minimum peak width
        distance: Minimum distance between peaks
        ph_cutoff: If provided, ignore data with pH values **below** this cutoff
        
    Returns:
        Tuple of (peak indices, peak properties)
    """
    # Ensure numpy arrays for downstream operations
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    # Dual–interpretation of pH-cutoff --------------------------------------
    # 1) Try *upper-bound* slice  (keep x <= ph_cutoff). If peaks found we are done.
    # 2) If none found and the cutoff lies in the upper 70 % of the range,
    #    fall back to *lower-bound* slice (keep x >= ph_cutoff).
    if ph_cutoff is not None:
        # --- upper-bound slice ---
        end_idx = next((i for i, ph_val in enumerate(x) if ph_val > ph_cutoff), len(x))
        x_upper = x[:end_idx]
        y_upper = y[:end_idx]

        if len(x_upper) >= 3:
            pk_idx_u, pk_props_u = signal.find_peaks(
                y_upper,
                height=height,
                prominence=prominence,
                width=width,
                distance=distance
            )
            if len(pk_idx_u) > 0:
                return list(pk_idx_u), pk_props_u

        # --- decide whether we should attempt lower-bound slice ---
        data_min = float(np.min(x))
        data_max = float(np.max(x))
        if ph_cutoff > data_min + 0.3 * (data_max - data_min):
            start_idx = next(
                (i for i, ph_val in enumerate(x) if ph_val >= ph_cutoff),
                len(x)
            )
            if start_idx < len(x):
                x_lower = x[start_idx:]
                y_lower = y[start_idx:]
                if len(x_lower) >= 3:
                    pk_idx_l, pk_props_l = signal.find_peaks(
                        y_lower,
                        height=height,
                        prominence=prominence,
                        width=width,
                        distance=distance
                    )
                    return list(pk_idx_l), pk_props_l

        # If we reach here, no peaks found under cutoff rules
        return [], {}

    if len(x) < 3:
        return [], {}
    
    # Find peaks using SciPy
    peak_indices, peak_props = signal.find_peaks(
        y,
        height=height,
        prominence=prominence,
        width=width,
        distance=distance
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
    window_length: int = 19,
    polyorder: int = 3,
    height: Optional[float] = None,
    prominence: Optional[float] = 0.001,
    width: Optional[float] = None,
    ph_cutoff: Optional[float] = 6.5
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
    
    # Compute derivative from smoothed data
    derivative = compute_derivative(ph_arr, smoothed_delta_b)
    
    # If derivative_values were provided, smooth them too
    if derivative_values is not None:
        derivative = smooth_data(derivative_values, window_length, polyorder)
    
    # Compute robust noise estimate using MAD
    derivative_median = np.median(derivative)
    derivative_mad = np.median(np.abs(derivative - derivative_median))
    # Scale factor 1.4826 converts MAD to std-dev equivalent for normal distribution
    sigma = 1.4826 * derivative_mad

    # ------------------------------------------------------------------
    # Robust minimum step threshold (mol/L) to filter negligible steps.
    # ------------------------------------------------------------------
    if len(smoothed_delta_b) > 2:
        step_sigma = 1.4826 * np.median(np.abs(np.diff(smoothed_delta_b)))
    else:
        step_sigma = 0.0
    step_min = max(5 * step_sigma, 1e-4)
    
    # Set minimum prominence based on noise level
    min_prominence = max(prominence or 0, 6 * sigma)
    
    # Set minimum distance between peaks based on data length
    min_distance = max(5, len(ph_arr) // 50)
    
    # Find zero crossings to define segments
    zero_crossings = find_zero_crossings(ph_arr, derivative)
    
    # Add start and end points to zero crossings if not present
    if 0 not in zero_crossings:
        zero_crossings.insert(0, 0)
    if len(ph_arr) - 1 not in zero_crossings:
        zero_crossings.append(len(ph_arr) - 1)
    
    # Define segments between zero crossings
    segments = []
    for i in range(len(zero_crossings) - 1):
        start_idx = zero_crossings[i]
        end_idx = zero_crossings[i+1]
        if end_idx - start_idx > 1:  # Skip segments that are too small
            # Calculate segment properties
            segment_derivative = derivative[start_idx:end_idx]
            segment_ph = ph_arr[start_idx:end_idx]
            
            # Find max absolute derivative in segment
            max_abs_idx = np.argmax(np.abs(segment_derivative)) + start_idx
            max_abs_value = np.abs(derivative[max_abs_idx])
            segment_sign = np.sign(derivative[max_abs_idx])
            
            segments.append({
                "start_idx": start_idx,
                "end_idx": end_idx,
                "max_abs_idx": max_abs_idx,
                "max_abs_value": max_abs_value,
                "sign": segment_sign,
                "ph_start": ph_arr[start_idx],
                "ph_end": ph_arr[end_idx],
                "ph_apex": ph_arr[max_abs_idx]
            })
    
    # Group adjacent segments with opposite signs into events
    events = []
    i = 0
    while i < len(segments):
        current_segment = segments[i]
        
        # Check if this segment is significant enough to be considered
        if current_segment["max_abs_value"] < min_prominence:
            i += 1
            continue
        
        # Start a new event with this segment
        event = {
            "start_idx": current_segment["start_idx"],
            "end_idx": current_segment["end_idx"],
            "max_abs_idx": current_segment["max_abs_idx"],
            "max_abs_value": current_segment["max_abs_value"],
            "ph_start": current_segment["ph_start"],
            "ph_end": current_segment["ph_end"],
            "ph_apex": current_segment["ph_apex"]
        }
        
        # Look ahead for an adjacent segment with opposite sign
        if i + 1 < len(segments):
            next_segment = segments[i + 1]
            if (current_segment["sign"] * next_segment["sign"] < 0 and 
                next_segment["max_abs_value"] >= min_prominence * 0.5):
                # Extend event to include the next segment
                event["end_idx"] = next_segment["end_idx"]
                event["ph_end"] = next_segment["ph_end"]
                
                # Use the segment with larger absolute value for apex
                if next_segment["max_abs_value"] > current_segment["max_abs_value"]:
                    event["max_abs_idx"] = next_segment["max_abs_idx"]
                    event["max_abs_value"] = next_segment["max_abs_value"]
                    event["ph_apex"] = next_segment["ph_apex"]
                
                i += 2  # Skip the next segment since we've included it
            else:
                i += 1
        else:
            i += 1
        
        # Apply pH cutoff
        if ph_cutoff is not None and event["ph_apex"] > ph_cutoff:
            continue
            
        events.append(event)
    
    # ------------------------------------------------------------------
    # Merge neighbouring events whose apex pH values are very close.
    # This reduces spurious double-detections originating from derivative
    # lobes on either side of a single titration step.
    # ------------------------------------------------------------------
    if events:
        # Sort by apex pH
        events.sort(key=lambda e: e["ph_apex"])
        # Estimate typical pH spacing
        if len(ph_arr) > 1:
            median_spacing = float(np.median(np.diff(np.sort(ph_arr))))
        else:
            median_spacing = 0.05
        merge_tol = max(0.15, 3 * median_spacing)
        gap_tol = max(0.05, 1.5 * median_spacing)

        merged_events = []
        current = events[0]

        for nxt in events[1:]:
            # Merge if apexes close OR physical gap between events is tiny
            if (abs(nxt["ph_apex"] - current["ph_apex"]) < merge_tol or
                (nxt["ph_start"] - current["ph_end"]) < gap_tol):
                # Merge nxt into current
                current["start_idx"] = min(current["start_idx"], nxt["start_idx"])
                current["end_idx"] = max(current["end_idx"], nxt["end_idx"])
                current["ph_start"] = min(current["ph_start"], nxt["ph_start"])
                current["ph_end"] = max(current["ph_end"], nxt["ph_end"])
                # Pick apex of larger absolute value
                if nxt["max_abs_value"] > current["max_abs_value"]:
                    current["max_abs_idx"] = nxt["max_abs_idx"]
                    current["max_abs_value"] = nxt["max_abs_value"]
                    current["ph_apex"] = nxt["ph_apex"]
            else:
                merged_events.append(current)
                current = nxt
        merged_events.append(current)
    else:
        merged_events = []
    
    # Calculate step sizes and create peak data from merged events
    peaks = []
    for i, event in enumerate(merged_events):
        # Calculate step size
        delta_b_step = calculate_peak_step(
            ph_arr, 
            smoothed_delta_b, 
            event["start_idx"], 
            event["end_idx"]
        )
        
        # Skip negligible or negative (within tolerance) steps
        if (abs(delta_b_step) >= step_min) and (delta_b_step >= -0.5 * step_min):
            peak = {
                "peak_id": i + 1,
                "ph_start": float(event["ph_start"]),
                "ph_apex": float(event["ph_apex"]),
                "ph_end": float(event["ph_end"]),
                "delta_b_step": float(delta_b_step)
            }
            peaks.append(peak)
    
    # Sort peaks by pH
    peaks.sort(key=lambda p: p["ph_apex"])
    
    # Reassign peak IDs after sorting
    for i, peak in enumerate(peaks):
        peak["peak_id"] = i + 1
    
    return peaks
