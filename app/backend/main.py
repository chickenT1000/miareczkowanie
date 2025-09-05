"""
Main FastAPI application for the titration analysis app.
Defines API endpoints for CSV import, data processing, and result export.
"""
import os
from typing import Dict, List, Optional, Union, Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from models import get_constants as _get_constants_data
from schemas import (
    Constants,
    ImportResponse,
    ComputeSettings,
    ComputeResponse,
    ProcessedRow,
    Peak,
    ModelData,
    ExportRequest,
    ExportFormat,
    DataType,
    SessionData,
    Metal,
)
from io_csv import parse_csv_file
import chem
import peaks

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

# --------------------------------------------------------------------------- #
# Initialise shared state to keep the most recent compute result
# --------------------------------------------------------------------------- #
app.state.last_settings: Optional[ComputeSettings] = None
app.state.last_processed: Optional[List[ProcessedRow]] = None
app.state.last_model: Optional[ModelData] = None
app.state.last_peaks: Optional[List[Peak]] = None
app.state.last_c_a: Optional[float] = None

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
    try:
        # Extract pH and time arrays using column mapping
        ph_values = []
        time_values = []
        
        for row in settings.rows:
            # Get pH and time values using the column mapping
            ph_key = settings.column_mapping.ph
            time_key = settings.column_mapping.time
            
            if ph_key not in row or time_key not in row:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required columns in data. Check column mapping."
                )
            
            # Extract values and ensure they're numeric
            ph = row.get(ph_key)
            time = row.get(time_key)
            
            if not isinstance(ph, (int, float)) or not isinstance(time, (int, float)):
                raise HTTPException(
                    status_code=400,
                    detail=f"Non-numeric values found in pH or time columns."
                )
            
            ph_values.append(ph)
            time_values.append(time)
        
        # Process titration data using chem module
        processed_rows, c_a = chem.process_titration_data(
            ph_values=ph_values,
            time_values=time_values,
            c_b=settings.c_b,
            q=settings.q,
            v0=settings.v0,
            time_unit="s",  # Assuming time is in seconds from CSV parser
            start_index=settings.start_index,
        )
        
        # Convert processed rows to ProcessedRow model
        processed_table = [
            ProcessedRow(
                time=row["time"],
                ph=row["pH"],
                v_b=row["v_b"],
                n_b=row["n_b"],
                b_meas=row["b_meas"],
                na=row["na"],
                b_model=row["b_model"],
                delta_b=row["delta_b"],
                d_delta_b_d_ph=row["d_delta_b_d_ph"]
            )
            for row in processed_rows
        ]
        
        # Extract pH and delta_b for peak detection
        ph_for_peaks = [row["pH"] for row in processed_rows]
        delta_b_for_peaks = [row["delta_b"] for row in processed_rows]
        
        # Detect and quantify peaks
        detected_peaks = peaks.detect_and_quantify_peaks(
            ph_values=ph_for_peaks,
            delta_b_values=delta_b_for_peaks,
            ph_cutoff=settings.ph_cutoff
        )
        
        # Convert detected peaks to Peak model
        peak_models = [
            Peak(
                peak_id=peak["peak_id"],
                ph_start=peak["ph_start"],
                ph_apex=peak["ph_apex"],
                ph_end=peak["ph_end"],
                delta_b_step=peak["delta_b_step"],
                metal=None,  # Default to None as per instructions
                stoichiometry=None,  # Default to None as per instructions
                c_metal=None,
                mg_l=None,
                notes=None
            )
            for peak in detected_peaks
        ]
        
        # Build model data
        model_data = ModelData(
            ph=[row["pH"] for row in processed_rows],
            b_model=[row["b_model"] for row in processed_rows]
        )
        
        # Return compute response
        response = ComputeResponse(
            processed_table=processed_table,
            model_data=model_data,
            peaks=peak_models,
            c_a=c_a
        )

        # Persist result in app state for later export
        app.state.last_settings = settings
        app.state.last_processed = processed_table
        app.state.last_model = model_data
        app.state.last_peaks = peak_models
        app.state.last_c_a = c_a

        return response
    
    except Exception as exc:
        # Handle any unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Computation failed: {str(exc)}"
        ) from exc

@app.post("/api/export")
async def export_data(request: ExportRequest):
    """
    Export processed data in the requested format.
    
    Supports CSV and JSON formats for processed data and peaks.
    """
    # Ensure we have a previous compute
    if app.state.last_processed is None:
        raise HTTPException(status_code=400, detail="No computation data available to export.")

    # Helper functions ----------------------------------------------------- #
    def processed_to_csv(rows: List[ProcessedRow]) -> str:
        header = (
            "time,pH,v_b,n_b,b_meas,na,b_model,delta_b,d_delta_b_d_ph"
        )
        lines = [header]
        for r in rows:
            lines.append(
                f"{r.time},{r.ph},{r.v_b},{r.n_b},{r.b_meas},"
                f"{r.na},{r.b_model},{r.delta_b},{r.d_delta_b_d_ph}"
            )
        return "\n".join(lines)

    def peaks_to_csv(peaks_list: List[Peak]) -> str:
        header = "peak_id,ph_start,ph_apex,ph_end,delta_b_step"
        lines = [header]
        for p in peaks_list:
            lines.append(f"{p.peak_id},{p.ph_start},{p.ph_apex},{p.ph_end},{p.delta_b_step}")
        return "\n".join(lines)

    # Build data based on request ----------------------------------------- #
    filename_base = "titration"
    content_type: str
    data_payload: Any

    if request.data_type == DataType.PROCESSED:
        if request.format == ExportFormat.CSV:
            content_type = "text/csv"
            data_payload = processed_to_csv(app.state.last_processed)
            filename = f"{filename_base}_processed.csv"
        else:
            content_type = "application/json"
            data_payload = (
                # Pydantic models have .model_dump_json in v2; retain simple repr
                [r.model_dump() for r in app.state.last_processed]
            )
            filename = f"{filename_base}_processed.json"

    elif request.data_type == DataType.PEAKS:
        if request.format == ExportFormat.CSV:
            content_type = "text/csv"
            data_payload = peaks_to_csv(app.state.last_peaks)
            filename = f"{filename_base}_peaks.csv"
        else:
            content_type = "application/json"
            data_payload = [p.model_dump() for p in app.state.last_peaks]
            filename = f"{filename_base}_peaks.json"

    elif request.data_type == DataType.SESSION:
        # Session must be JSON for portability
        if request.format != ExportFormat.JSON:
            raise HTTPException(status_code=400, detail="Session export only supported in JSON format.")
        content_type = "application/json"
        session = SessionData(
            settings=app.state.last_settings,
            processed_table=app.state.last_processed,
            model_data=app.state.last_model,
            peaks=app.state.last_peaks,
            c_a=app.state.last_c_a,
        )
        data_payload = session.model_dump()
        filename = f"{filename_base}_session.json"
    else:
        # Should not reach here due to enum validation
        raise HTTPException(status_code=400, detail="Unsupported data type.")

    return {
        "filename": filename,
        "content_type": content_type,
        "data": data_payload,
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
