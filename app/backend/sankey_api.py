"""
FastAPI router for Sankey diagram functionality.
Provides endpoints for graph management and scaling.
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Union, Literal

from fastapi import APIRouter, Request, HTTPException, Body
from pydantic import BaseModel

from sankey_models import Graph, Meta, Node, Link, scale_graph_global, normalize_graph

# Create router
router = APIRouter(tags=["sankey"])

# Default graph path
DEFAULT_GRAPH_PATH = Path(__file__).parent / "data" / "sankey_default.json"

class ScaleRequest(BaseModel):
    """Request model for scaling a graph"""
    batch_target_kg: float
    strategy: Literal["global", "per-node"] = "global"

def load_default_graph() -> Graph:
    """Load default graph from JSON file if it exists"""
    if not DEFAULT_GRAPH_PATH.exists():
        # Return empty graph if default doesn't exist
        return Graph(
            meta=Meta(batch_target_kg=300.0),
            nodes=[],
            links=[],
            sources=[],
            sinks=[]
        )
    
    try:
        with open(DEFAULT_GRAPH_PATH, "r") as f:
            data = json.load(f)
            return Graph.model_validate(data)
    except Exception as e:
        # Return empty graph on error
        print(f"Error loading default graph: {e}")
        return Graph(
            meta=Meta(batch_target_kg=300.0),
            nodes=[],
            links=[],
            sources=[],
            sinks=[]
        )

@router.get("/graph", response_model=Graph)
async def get_graph(request: Request) -> Graph:
    """
    Get the current Sankey graph.
    
    If no graph exists in app state, load the default graph.
    """
    # Check if graph exists in app state
    if not hasattr(request.app.state, "sankey_graph"):
        # Load default graph
        request.app.state.sankey_graph = load_default_graph()
    
    return request.app.state.sankey_graph

@router.post("/graph", response_model=Graph)
async def set_graph(request: Request, graph: Graph) -> Graph:
    """
    Set the current Sankey graph.
    
    Normalizes the graph before storing.
    """
    # Normalize graph
    normalized_graph = normalize_graph(graph)
    
    # Store in app state
    request.app.state.sankey_graph = normalized_graph
    
    return normalized_graph

@router.post("/scale", response_model=Graph)
async def scale_graph(
    request: Request, 
    scale_request: ScaleRequest = Body(...)
) -> Graph:
    """
    Scale the current graph based on target batch size.
    
    Does not modify the stored graph.
    """
    # Get current graph
    if not hasattr(request.app.state, "sankey_graph"):
        request.app.state.sankey_graph = load_default_graph()
    
    current_graph = request.app.state.sankey_graph
    
    # Scale graph based on strategy
    if scale_request.strategy == "global":
        scaled_graph = scale_graph_global(
            current_graph, 
            batch_target_kg=scale_request.batch_target_kg
        )
    elif scale_request.strategy == "per-node":
        # Not implemented yet, fall back to global
        # TODO: Implement per-node scaling
        scaled_graph = scale_graph_global(
            current_graph, 
            batch_target_kg=scale_request.batch_target_kg
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported scaling strategy: {scale_request.strategy}"
        )
    
    # Return scaled graph without modifying stored graph
    return scaled_graph

@router.post("/import", response_model=Graph)
async def import_data(
    request: Request,
    file_content: str = Body(..., embed=True),
    file_type: Literal["json", "csv"] = Body("json", embed=True)
) -> Graph:
    """
    Import graph data from JSON or CSV.
    
    Currently only supports JSON import.
    """
    if file_type == "json":
        try:
            data = json.loads(file_content)
            graph = Graph.model_validate(data)
            normalized_graph = normalize_graph(graph)
            request.app.state.sankey_graph = normalized_graph
            return normalized_graph
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid JSON format: {str(e)}"
            )
    elif file_type == "csv":
        # Not implemented yet
        raise HTTPException(
            status_code=501,
            detail="CSV import not implemented yet"
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_type}"
        )
