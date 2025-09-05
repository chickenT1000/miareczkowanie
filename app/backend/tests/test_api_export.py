"""
API tests for the export endpoint.

These tests verify that the /api/export endpoint:
1. Returns data in the correct format (CSV/JSON)
2. Includes all required fields
3. Handles errors appropriately
"""
import csv
import io
import json
from typing import Dict, List

import pytest
from fastapi.testclient import TestClient

from main import app
from schemas import ComputeSettings, ColumnMapping, ExportFormat, DataType


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def minimal_compute_request():
    """Create a minimal compute request with synthetic data."""
    # Create simple pH and time data
    rows = [
        {"pH": 2.0, "time": 0.0},
        {"pH": 2.5, "time": 60.0},
        {"pH": 3.0, "time": 120.0},
        {"pH": 3.5, "time": 180.0},
        {"pH": 4.0, "time": 240.0},
    ]
    
    # Create column mapping
    column_mapping = ColumnMapping(
        ph="pH",
        time="time"
    )
    
    # Create compute settings
    return ComputeSettings(
        c_b=0.1,
        q=1.0,
        v0=100.0,
        t=25.0,
        ph_cutoff=6.5,
        start_index=0,
        column_mapping=column_mapping,
        rows=rows
    )


@pytest.fixture
def computed_state(client, minimal_compute_request):
    """Call compute endpoint to populate app state."""
    response = client.post("/api/compute", json=minimal_compute_request.model_dump())
    assert response.status_code == 200, "Compute request failed"
    return response.json()


def test_export_before_compute(client):
    """Test that export returns 400 when called before compute."""
    # Reset app state
    app.state.last_processed = None
    app.state.last_model = None
    app.state.last_peaks = None
    app.state.last_c_a = None
    
    # Try to export
    response = client.post(
        "/api/export", 
        json={"format": "csv", "data_type": "processed"}
    )
    
    # Should return 400
    assert response.status_code == 400
    assert "No computation data available" in response.json()["detail"]


def test_export_processed_csv(client, computed_state):
    """Test export of processed data in CSV format."""
    response = client.post(
        "/api/export", 
        json={"format": "csv", "data_type": "processed"}
    )
    
    # Check response
    assert response.status_code == 200
    
    # Check response structure
    data = response.json()
    assert "filename" in data
    assert "content_type" in data
    assert "data" in data
    
    # Check content type
    assert data["content_type"] == "text/csv"
    assert data["filename"].endswith(".csv")
    
    # Check CSV content
    csv_content = data["data"]
    csv_reader = csv.reader(io.StringIO(csv_content))
    
    # Check header
    header = next(csv_reader)
    expected_headers = [
        "time", "pH", "v_b", "n_b", "b_meas", 
        "na", "b_model", "delta_b", "d_delta_b_d_ph"
    ]
    assert all(h in header for h in expected_headers)
    
    # Check that we have rows
    rows = list(csv_reader)
    assert len(rows) > 0


def test_export_processed_json(client, computed_state):
    """Test export of processed data in JSON format."""
    response = client.post(
        "/api/export", 
        json={"format": "json", "data_type": "processed"}
    )
    
    # Check response
    assert response.status_code == 200
    
    # Check response structure
    data = response.json()
    assert "filename" in data
    assert "content_type" in data
    assert "data" in data
    
    # Check content type
    assert data["content_type"] == "application/json"
    assert data["filename"].endswith(".json")
    
    # Check JSON content
    json_content = data["data"]
    assert isinstance(json_content, list)
    assert len(json_content) > 0
    
    # Check first row structure
    first_row = json_content[0]
    expected_fields = [
        "time", "ph", "v_b", "n_b", "b_meas", 
        "na", "b_model", "delta_b", "d_delta_b_d_ph"
    ]
    assert all(field in first_row for field in expected_fields)


def test_export_peaks_csv(client, computed_state):
    """Test export of peaks data in CSV format."""
    response = client.post(
        "/api/export", 
        json={"format": "csv", "data_type": "peaks"}
    )
    
    # Check response
    assert response.status_code == 200
    
    # Check response structure
    data = response.json()
    assert "filename" in data
    assert "content_type" in data
    assert "data" in data
    
    # Check content type
    assert data["content_type"] == "text/csv"
    assert data["filename"].endswith(".csv")
    
    # Check CSV content
    csv_content = data["data"]
    csv_reader = csv.reader(io.StringIO(csv_content))
    
    # Check header
    header = next(csv_reader)
    expected_headers = ["peak_id", "ph_start", "ph_apex", "ph_end", "delta_b_step"]
    assert all(h in header for h in expected_headers)


def test_export_peaks_json(client, computed_state):
    """Test export of peaks data in JSON format."""
    response = client.post(
        "/api/export", 
        json={"format": "json", "data_type": "peaks"}
    )
    
    # Check response
    assert response.status_code == 200
    
    # Check response structure
    data = response.json()
    assert "filename" in data
    assert "content_type" in data
    assert "data" in data
    
    # Check content type
    assert data["content_type"] == "application/json"
    assert data["filename"].endswith(".json")
    
    # Check JSON content
    json_content = data["data"]
    assert isinstance(json_content, list)
    
    # Even if no peaks were detected, we should get an empty list, not an error
    if json_content:
        # Check first peak structure
        first_peak = json_content[0]
        expected_fields = ["peak_id", "ph_start", "ph_apex", "ph_end", "delta_b_step"]
        assert all(field in first_peak for field in expected_fields)


def test_export_session_json(client, computed_state):
    """Test export of session data in JSON format."""
    response = client.post(
        "/api/export", 
        json={"format": "json", "data_type": "session"}
    )
    
    # Check response
    assert response.status_code == 200
    
    # Check response structure
    data = response.json()
    assert "filename" in data
    assert "content_type" in data
    assert "data" in data
    
    # Check content type
    assert data["content_type"] == "application/json"
    assert data["filename"].endswith(".json")
    
    # Check JSON content
    json_content = data["data"]
    assert isinstance(json_content, dict)
    
    # Check session structure
    expected_fields = ["settings", "processed_table", "model_data", "peaks", "c_a", "version"]
    assert all(field in json_content for field in expected_fields)


def test_export_session_csv_not_supported(client, computed_state):
    """Test that session export in CSV format returns 400."""
    response = client.post(
        "/api/export", 
        json={"format": "csv", "data_type": "session"}
    )
    
    # Should return 400
    assert response.status_code == 400
    assert "only supported in JSON format" in response.json()["detail"]
