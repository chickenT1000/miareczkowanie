"""
CSV import and parsing utilities.

This module handles:
1. Parsing CSV files from pH meters with various formats
2. Detecting decimal and column separators
3. Extracting time and pH data from instrument logs
4. Normalizing data for further processing
"""
import csv
import io
import re
from typing import Dict, List, Tuple, Union, Optional, Any


def detect_separators(content: bytes) -> Tuple[str, str]:
    """
    Detect decimal and column separators in CSV content.
    
    Args:
        content: Raw CSV content as bytes
    
    Returns:
        Tuple of (decimal_separator, column_separator)
    """
    # Default separators
    decimal_sep = "."
    column_sep = ","
    
    # Convert first chunk to string for analysis
    sample = content[:min(5000, len(content))].decode('utf-8', errors='ignore')
    
    # Check for semicolons as column separators
    if ";" in sample:
        column_sep = ";"
    
    # Look for numeric patterns with comma as decimal
    # Simple pattern like 1,23  or 0,5  (avoid 1,000 by limiting decimals to max 3)
    decimal_comma_pattern = re.compile(r"\d+,\d{1,3}")
    if decimal_comma_pattern.search(sample):
        decimal_sep = ","
    
    return decimal_sep, column_sep


def extract_seconds(time_str: str) -> Tuple[float, str]:
    """
    Extract seconds from time string like "60 seconds".
    
    Args:
        time_str: Time string (e.g., "60 seconds", "2 min")
    
    Returns:
        Tuple of (seconds as float, time unit as string)
    """
    # Default values
    seconds = 0.0
    unit = "s"
    
    # Clean up the string
    time_str = time_str.strip().lower()
    
    # Extract numeric part
    match = re.search(r'(\d+(?:[.,]\d+)?)', time_str)
    if match:
        # Get the number and handle comma as decimal
        num_str = match.group(1).replace(',', '.')
        try:
            value = float(num_str)
            
            # Determine unit and convert to seconds
            if "min" in time_str:
                seconds = value * 60
                unit = "min"
            else:
                seconds = value
                unit = "s"
        except ValueError:
            pass
    
    return seconds, unit


def normalize_value(value: str, decimal_sep: str = ".") -> Union[float, str]:
    """
    Try to convert a string to a float, handling different decimal separators.
    
    Args:
        value: String value to convert
        decimal_sep: Decimal separator to use
    
    Returns:
        Float if conversion successful, otherwise the original string
    """
    if not value or not isinstance(value, str):
        return value
    
    # Replace decimal separator with dot for float conversion
    if decimal_sep == ",":
        value = value.replace(",", ".")
    
    # Try to convert to float
    try:
        return float(value)
    except ValueError:
        return value


def find_data_section(reader: csv.reader) -> Tuple[List[str], int]:
    """
    Find the data section in the CSV by looking for the MODULE_A header.
    
    Args:
        reader: CSV reader object
    
    Returns:
        Tuple of (column names, row index where data starts)
    """
    for i, row in enumerate(reader):
        # Clean row values
        cleaned_row = [cell.strip().strip('"').strip() for cell in row if cell.strip()]
        # Case-insensitive search for MODULE_A in any cell
        if any("module_a" in cell.lower() for cell in cleaned_row):
            # Attempt to use next row as headers
            try:
                header_row = next(reader)
                header_row = [h.strip().strip('"') for h in header_row]
                # data start is the line right after the header we just consumed
                return header_row, i + 1
            except StopIteration:
                # Header exists but no data
                return ["time", "module", "pH", "temperature"], i + 2
    
    # If we didn't find the header, use default column names
    return ["time", "module", "pH", "temperature"], 0


def parse_uploaded_csv(content: bytes) -> Dict[str, Any]:
    """
    Parse uploaded CSV file from pH meter.
    
    Args:
        content: Raw CSV content as bytes
    
    Returns:
        Dict with keys:
            - columns: List of column names
            - rows: List of parsed data rows
            - time_unit: Detected time unit (s or min)
            - decimal_separator: Detected decimal separator (. or ,)
            - column_separator: Detected column separator (, or ;)
    """
    # Detect separators
    decimal_sep, column_sep = detect_separators(content)
    
    # Decode content
    text = content.decode('utf-8', errors='ignore')
    
    # Create CSV reader
    f = io.StringIO(text)
    reader = csv.reader(f, delimiter=column_sep)
    
    # Find data section
    column_names, data_start_idx = find_data_section(reader)
    # Track whether we recognised the instrument format
    instrument_found: bool = data_start_idx > 0
    
    # If we didn't find the data section, reset and try again with a simpler approach
    if data_start_idx == 0:
        f.seek(0)
        reader = csv.reader(f, delimiter=column_sep)
        
        # Skip metadata rows until we find a row that looks like time data
        for i, row in enumerate(reader):
            if len(row) >= 3 and re.search(r'\d+\s*(seconds?|sec|s|min|m)', row[0].lower()):
                data_start_idx = i
                column_names = ["time", "module", "pH", "temperature"]
                break
    
    # Reset file position if we found data
    if data_start_idx > 0:
        f.seek(0)
        reader = csv.reader(f, delimiter=column_sep)
        # Skip to data start
        for _ in range(data_start_idx):
            try:
                next(reader)
            except StopIteration:
                # Reached EOF before expected; no data rows present
                break
    
    # Parse data rows
    rows = []
    time_unit = "s"  # Default
    
    for row in reader:
        # Skip empty rows
        if not row or not any(cell.strip() for cell in row):
            continue
        
        # Ensure row has enough columns
        if len(row) < 3:
            continue
        
        # Extract time, module, pH, and temperature
        time_label = row[0].strip()
        module = row[1].strip() if len(row) > 1 else ""
        ph_value = row[2].strip() if len(row) > 2 else ""
        temp_value = row[3].strip() if len(row) > 3 else ""
        
        # Skip rows that don't look like data
        if not re.search(r'\d+\s*(seconds?|sec|s|min|m)', time_label):
            continue
        
        # Extract seconds and time unit
        seconds, detected_unit = extract_seconds(time_label)
        # Keep track of last non-seconds unit to report overall time_unit
        if detected_unit != "s":
            time_unit = detected_unit
        
        # Normalize pH and temperature
        ph = normalize_value(ph_value, decimal_sep)
        temperature = normalize_value(temp_value, decimal_sep)
        
        # Create normalized row
        normalized_row = {
            "time": seconds,
            "time_label": time_label,
            "module": module,
            "pH": ph,
            "temperature": temperature
        }
        
        rows.append(normalized_row)
    
    # Prepare column mapping for frontend
    # Put the numeric “time” first so the frontend auto-selects it,
    # followed by the main numeric columns, then the textual label/module.
    frontend_columns = ["time", "pH", "temperature", "time_label", "module"]
    
    return {
        "columns": frontend_columns,
        "rows": rows,
        "time_unit": time_unit,
        "decimal_separator": decimal_sep,
        "column_separator": column_sep,
        "instrument": instrument_found,
    }


def parse_generic_csv(content: bytes) -> Dict[str, Any]:
    """
    Parse a generic CSV file with headers in the first row.
    
    Args:
        content: Raw CSV content as bytes
    
    Returns:
        Dict with keys:
            - columns: List of column names
            - rows: List of parsed data rows
            - time_unit: Detected time unit (s or min)
            - decimal_separator: Detected decimal separator (. or ,)
            - column_separator: Detected column separator (, or ;)
    """
    # Detect separators
    decimal_sep, column_sep = detect_separators(content)
    
    # Decode content
    text = content.decode('utf-8', errors='ignore')
    
    # Create CSV reader
    f = io.StringIO(text)
    reader = csv.reader(f, delimiter=column_sep)
    
    # Try to read header row
    try:
        headers = next(reader)
        # Clean up header names
        headers = [h.strip() for h in headers]
    except StopIteration:
        headers = []
    
    # Parse data rows
    rows = []
    time_unit = "s"  # Default
    
    for row in reader:
        # Skip empty rows
        if not row or not any(cell.strip() for cell in row):
            continue
        
        # Create a dictionary for this row
        row_dict = {}
        for i, value in enumerate(row):
            if i < len(headers):
                key = headers[i]
                # Try to convert to float if possible
                row_dict[key] = normalize_value(value, decimal_sep)
            else:
                # Handle extra columns
                row_dict[f"column_{i}"] = normalize_value(value, decimal_sep)
        
        rows.append(row_dict)
    
    return {
        "columns": headers,
        "rows": rows,
        "time_unit": time_unit,
        "decimal_separator": decimal_sep,
        "column_separator": column_sep
    }


def parse_csv_file(content: bytes) -> Dict[str, Any]:
    """
    Parse a CSV file, trying different strategies.
    
    First tries to parse as an instrument CSV, then falls back to generic CSV parsing.
    
    Args:
        content: Raw CSV content as bytes
    
    Returns:
        Dict with parsed data
    """
    # Try instrument-specific parser first
    result = parse_uploaded_csv(content)
    
    # If we got no rows, try generic parser
    if (not result["rows"]) and (result.get("instrument") is False):
        result = parse_generic_csv(content)
    
    return result
