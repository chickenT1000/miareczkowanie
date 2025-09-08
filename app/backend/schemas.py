"""
Pydantic models for API request/response schemas.
"""
from enum import Enum
from typing import Dict, List, Optional, Union, Literal

from pydantic import BaseModel, Field, ConfigDict


class ColumnMapping(BaseModel):
    """Maps CSV columns to expected fields."""
    
    ph: str = Field(..., description="Column name for pH values")
    time: str = Field(..., description="Column name for time values")
    pump_flow: Optional[str] = Field(None, description="Optional column for pump flow (mL/min)")
    naoh_conc: Optional[str] = Field(None, description="Optional column for NaOH concentration")


class Row(BaseModel):
    """Represents a raw data row from imported CSV."""
    
    model_config = ConfigDict(extra="allow")
    
    # We allow any fields here since they come from CSV mapping
    # Core fields will be accessed via the mapping


class ProcessedRow(BaseModel):
    """Represents a processed data row after calculations."""
    
    time: float = Field(..., description="Time (s)")
    ph: float = Field(..., description="pH value")
    v_b: float = Field(..., description="Base volume (mL)")
    n_b: float = Field(..., description="Base moles (mol)")
    b_meas: float = Field(..., description="Measured base (mol/L, normalized to V₀)")
    na: float = Field(..., description="Sodium concentration with dilution (mol/L)")
    b_model: float = Field(..., description="Model base (mol/L)")
    delta_b: float = Field(..., description="Excess base: B_meas - B_model (mol/L)")
    d_delta_b_d_ph: float = Field(..., description="Derivative of excess base with respect to pH")


class Metal(str, Enum):
    """Available metals for peak assignment."""
    
    FE3 = "Fe3+"
    FE2 = "Fe2+"
    AL3 = "Al3+"
    NI2 = "Ni2+"
    CO2 = "Co2+"
    MN2 = "Mn2+"


class MetalData(BaseModel):
    """Metal properties."""
    
    name: str = Field(..., description="Display name")
    molar_mass: float = Field(..., description="Molar mass (g/mol)")
    stoichiometry: int = Field(..., description="Stoichiometry (OH⁻/mol metal)")


class Peak(BaseModel):
    """Detected peak data."""
    
    peak_id: int = Field(..., description="Unique peak identifier")
    ph_start: float = Field(..., description="pH at peak start")
    ph_apex: float = Field(..., description="pH at peak apex")
    ph_end: float = Field(..., description="pH at peak end")
    delta_b_step: float = Field(..., description="Step size in excess base (mol/L)")
    metal: Optional[Metal] = Field(None, description="Assigned metal")
    stoichiometry: Optional[int] = Field(None, description="Stoichiometry (OH⁻/mol metal)")
    c_metal: Optional[float] = Field(None, description="Metal concentration (mol/L)")
    mg_l: Optional[float] = Field(None, description="Metal concentration (mg/L)")
    notes: Optional[str] = Field(None, description="User notes")


class ImportResponse(BaseModel):
    """Response for CSV import endpoint."""
    
    columns: List[str] = Field(..., description="Detected column names")
    rows: List[Dict[str, Union[float, str]]] = Field(..., description="Parsed data rows")
    time_unit: str = Field("s", description="Detected time unit (s or min)")
    decimal_separator: str = Field(".", description="Detected decimal separator (. or ,)")
    column_separator: str = Field(",", description="Detected column separator (, or ;)")


class ComputeSettings(BaseModel):
    """Settings for computation endpoint."""
    
    c_b: float = Field(0.1, description="Base concentration (mol/L)")
    q: float = Field(1.0, description="Pump rate (mL/min)")
    v0: float = Field(100.0, description="Initial sample volume (mL)")
    t: float = Field(25.0, description="Temperature (°C)")
    ph_cutoff: float = Field(6.5, description="pH cutoff for peak detection")
    start_index: int = Field(0, description="Start index for calculations")
    # ---------------------------- New options ----------------------------- #
    c_a_known: Optional[float] = Field(
        None,
        description=(
            "If provided, use this fixed total sulfate concentration (mol/L) "
            "instead of estimating it from the baseline window."
        ),
    )
    ph_ignore_below: Optional[float] = Field(
        None,
        description=(
            "Rows with pH below this value are ignored when estimating "
            "C_A (only applies if c_a_known is not provided)."
        ),
    )
    column_mapping: ColumnMapping = Field(..., description="Column mapping")
    rows: List[Dict[str, Union[float, str]]] = Field(..., description="Data rows")


class ModelData(BaseModel):
    """H₂SO₄ model data."""
    
    ph: List[float] = Field(..., description="pH values")
    b_model: List[float] = Field(..., description="Model base values (mol/L)")
    # Extended pure model curve (independent of measured sample points)
    ph_model: Optional[List[float]] = Field(
        None,
        description="Calculated pH values for the standalone model curve (e.g., sweep until pH 7)",
    )
    b_model_curve: Optional[List[float]] = Field(
        None,
        description="Corresponding model base values for the standalone curve (mol/L)",
    )
    # --------------------- pH-registered subtraction ---------------------- #
    b_model_ph_aligned: Optional[List[float]] = Field(
        None,
        description="Model base values evaluated at the same pH as each measurement",
    )
    delta_b_ph_aligned: Optional[List[float]] = Field(
        None,
        description="Excess base ΔB computed with pH-aligned model values",
    )


class ComputeResponse(BaseModel):
    """Response for compute endpoint."""
    
    processed_table: List[ProcessedRow] = Field(..., description="Processed data rows")
    model_data: ModelData = Field(..., description="H₂SO₄ model data")
    peaks: List[Peak] = Field(..., description="Detected peaks")
    c_a: float = Field(..., description="Estimated total sulfate concentration (mol/L)")


class Constants(BaseModel):
    """Chemical constants and metal data."""
    
    k_a2: float = Field(1.2e-2, description="HSO₄⁻ ⇌ H⁺ + SO₄²⁻ at 25°C")
    k_w: float = Field(1.0e-14, description="Water dissociation constant at 25°C")
    metals: Dict[Metal, MetalData] = Field(..., description="Metal data with molar mass and stoichiometry")


class ExportFormat(str, Enum):
    """Export format options."""
    
    CSV = "csv"
    JSON = "json"


class DataType(str, Enum):
    """Data type options for export."""
    
    PROCESSED = "processed"
    PEAKS = "peaks"
    SESSION = "session"


class ExportRequest(BaseModel):
    """Request for export endpoint."""
    
    format: ExportFormat = Field(ExportFormat.CSV, description="Export format")
    data_type: DataType = Field(DataType.PROCESSED, description="Data type to export")
    include_plots: bool = Field(False, description="Include plot data in export")


class SessionData(BaseModel):
    """Session data for save/load functionality."""
    
    settings: ComputeSettings = Field(..., description="Computation settings")
    processed_table: Optional[List[ProcessedRow]] = Field(None, description="Processed data")
    model_data: Optional[ModelData] = Field(None, description="Model data")
    peaks: Optional[List[Peak]] = Field(None, description="Detected peaks")
    c_a: Optional[float] = Field(None, description="Estimated sulfate concentration")
    version: str = Field("0.1.0", description="Session data format version")

# --------------------------------------------------------------------------- #
#  New models for peak → metal assignment                                     #
# --------------------------------------------------------------------------- #


class PeakAssignment(BaseModel):
    """Single peak-to-metal assignment coming from the UI."""

    peak_id: int = Field(..., description="ID of the peak to assign")
    metal: Metal = Field(..., description="Selected metal for this peak")


class AssignPeaksRequest(BaseModel):
    """Request payload for /api/assign_peaks endpoint."""

    assignments: List[PeakAssignment] = Field(
        ..., description="List of peak→metal assignments"
    )
