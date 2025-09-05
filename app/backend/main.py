"""
Main FastAPI application for the titration analysis app.
Defines API endpoints for CSV import, data processing, and result export.
"""
import os
from typing import Dict, List, Optional, Union

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from models import get_constants as _get_constants_data
from schemas import (
    Constants,
    ImportResponse,
    ComputeSettings,
    ComputeResponse,
    ExportRequest,
)
from io_csv import parse_csv_file  # CSV parser integration

# Environment configuration
APP_ENV = os.getenv("APP_ENV", "dev")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
ORIGIN = os.getenv("ORIGIN", "http://localhost:5173")

# Initialize FastAPI app
app = FastAPI(
    title="Miareczkowanie API",
    description="API for titration data analysis",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API endpoints
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": app.version}

@app.get("/api/constants", response_model=Constants)
async def get_constants():
    """Return chemical constants and metal data."""
    # Delegate to models.get_constants for authoritative data
    return _get_constants_data()

@app.post("/api/import", response_model=ImportResponse)
async def import_csv(file: UploadFile = File(...)):
    """
    Parse uploaded CSV file and return detected columns and sample rows.
    
    Handles flexible column mapping, decimal formats, and separators.
    """
    if not file.filename or not file.filename.lower().endswith(('.csv', '.txt')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    
    # Check file size (limit to MAX_UPLOAD_MB)
    file_size_mb = 0
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    await file.seek(0)
    
    if file_size_mb > MAX_UPLOAD_MB:
        raise HTTPException(
            status_code=400, 
            detail=f"File too large. Maximum size is {MAX_UPLOAD_MB} MB."
        )
    # Parse CSV content using dedicated parser
    try:
        result = parse_csv_file(content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CSV parsing failed: {exc}") from exc

    return result

@app.post("/api/compute", response_model=ComputeResponse)
async def compute_data(settings: ComputeSettings):
    """
    Process titration data with the provided settings.
    
    Computes the H₂SO₄ model, excess base, and detects peaks.
    """
    # Placeholder - actual computation will be implemented in chem.py and peaks.py
    return {
        "processed_table": [],
        "model_data": {"pH": [], "B_model": []},
        "peaks": [],
        "c_a": 0.0,
    }

@app.post("/api/export")
async def export_data(request: ExportRequest):
    """
    Export processed data in the requested format.
    
    Supports CSV and JSON formats for processed data and peaks.
    """
    # Placeholder - actual export will be implemented later
    return {
        "filename": f"titration_data.{request.format}",
        "content_type": "text/csv" if request.format == "csv" else "application/json",
        "data": "time,pH,V_b\n60,2.56,1.0\n120,2.57,2.0",
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
