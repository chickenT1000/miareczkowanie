"""
Tests for CSV import and parsing utilities in io_csv.py.
"""
import io
import pytest
from io_csv import parse_csv_file, parse_uploaded_csv, parse_generic_csv, detect_separators, extract_seconds


def test_parse_csv_file_with_instrument_format():
    """Test parsing a CSV file with instrument format (MODULE_A header)."""
    # Sample CSV content mimicking the instrument format
    csv_content = """"","
"Date / Time","2025-09-03 15:31:32"
"Sample ID","1"
"Comment"," ---"
"Result status","OK"
"Instrument ID","SevenDirect SD20"
"Measurement type","pH"
"Temperature","26.4 °C(ATC)"
"MODULE_A","","pH","°C"
"60 seconds","A","0.45","24.3"
"120 seconds","A","0.49","24.3"
"180 seconds","A","0.52","24.3"
"240 seconds","A","0.54","24.3"
"""
    
    # Parse the CSV content
    result = parse_csv_file(csv_content.encode('utf-8'))
    
    # Check that the result has the expected structure
    assert "columns" in result
    assert "rows" in result
    assert "time_unit" in result
    assert "decimal_separator" in result
    assert "column_separator" in result
    
    # Check that rows were parsed
    assert len(result["rows"]) == 4
    
    # Check that the first row has the expected keys and values
    first_row = result["rows"][0]
    assert "time" in first_row
    assert "pH" in first_row
    assert "temperature" in first_row
    
    # Check that time is numeric and in seconds
    assert isinstance(first_row["time"], float)
    assert first_row["time"] == 60.0
    
    # Check that pH is numeric
    assert isinstance(first_row["pH"], float)
    assert first_row["pH"] == 0.45
    
    # Check that temperature is numeric
    assert isinstance(first_row["temperature"], float)
    assert first_row["temperature"] == 24.3


def test_parse_csv_file_with_decimal_comma():
    """Test parsing a CSV file with decimal comma."""
    # Sample CSV content with decimal comma
    csv_content = """"","
"Date / Time","2025-09-03 15:31:32"
"MODULE_A","","pH","°C"
"60 seconds","A","0,45","24,3"
"120 seconds","A","0,49","24,3"
"""
    
    # Parse the CSV content
    result = parse_csv_file(csv_content.encode('utf-8'))
    
    # Check that decimal separator was detected correctly
    assert result["decimal_separator"] == ","
    
    # Check that values were converted correctly
    first_row = result["rows"][0]
    assert first_row["pH"] == 0.45
    assert first_row["temperature"] == 24.3


def test_parse_csv_file_with_minutes():
    """Test parsing a CSV file with time in minutes."""
    # Sample CSV content with time in minutes
    csv_content = """"","
"Date / Time","2025-09-03 15:31:32"
"MODULE_A","","pH","°C"
"1 min","A","0.45","24.3"
"2 min","A","0.49","24.3"
"""
    
    # Parse the CSV content
    result = parse_csv_file(csv_content.encode('utf-8'))
    
    # Check that time unit was detected correctly
    assert result["time_unit"] == "min"
    
    # Check that time was converted to seconds
    first_row = result["rows"][0]
    assert first_row["time"] == 60.0  # 1 min = 60 seconds
    
    second_row = result["rows"][1]
    assert second_row["time"] == 120.0  # 2 min = 120 seconds


def test_parse_csv_file_empty():
    """Test parsing an empty CSV file."""
    # Empty CSV content
    csv_content = ""
    
    # Parse the CSV content
    result = parse_csv_file(csv_content.encode('utf-8'))
    
    # Check that no rows were parsed
    assert len(result["rows"]) == 0


def test_parse_csv_file_no_data_rows():
    """Test parsing a CSV file with headers but no data rows."""
    # CSV content with headers but no data
    csv_content = """"","
"Date / Time","2025-09-03 15:31:32"
"MODULE_A","","pH","°C"
"""
    
    # Parse the CSV content
    result = parse_csv_file(csv_content.encode('utf-8'))
    
    # Check that no rows were parsed
    assert len(result["rows"]) == 0


def test_detect_separators():
    """Test detection of decimal and column separators."""
    # CSV with comma as decimal separator
    csv_comma = "time,pH,temp\n60,0,45,24,3".encode('utf-8')
    dec_sep, col_sep = detect_separators(csv_comma)
    assert dec_sep == ","
    assert col_sep == ","
    
    # CSV with dot as decimal separator and semicolon as column separator
    csv_semicolon = "time;pH;temp\n60;0.45;24.3".encode('utf-8')
    dec_sep, col_sep = detect_separators(csv_semicolon)
    assert dec_sep == "."
    assert col_sep == ";"


def test_extract_seconds():
    """Test extraction of seconds from time strings."""
    # Test seconds
    seconds, unit = extract_seconds("60 seconds")
    assert seconds == 60.0
    assert unit == "s"
    
    # Test minutes
    seconds, unit = extract_seconds("2 min")
    assert seconds == 120.0
    assert unit == "min"
    
    # Test decimal
    seconds, unit = extract_seconds("1.5 min")
    assert seconds == 90.0
    assert unit == "min"
    
    # Test decimal comma
    seconds, unit = extract_seconds("1,5 min")
    assert seconds == 90.0
    assert unit == "min"


def test_parse_generic_csv():
    """Test parsing a generic CSV file with headers in the first row."""
    # Sample generic CSV content
    csv_content = """time,pH,temperature
60,2.56,22.9
120,2.56,22.8
180,2.56,22.8
"""
    
    # Parse the CSV content
    result = parse_generic_csv(csv_content.encode('utf-8'))
    
    # Check that the result has the expected structure
    assert "columns" in result
    assert "rows" in result
    
    # Check that columns were detected correctly
    assert result["columns"] == ["time", "pH", "temperature"]
    
    # Check that rows were parsed
    assert len(result["rows"]) == 3
    
    # Check that values were converted correctly
    first_row = result["rows"][0]
    assert first_row["time"] == 60.0
    assert first_row["pH"] == 2.56
    assert first_row["temperature"] == 22.9
