"""
Pydantic models for Sankey diagram data structures.
Includes scaling and normalization helpers.
"""
from typing import Dict, List, Optional, Union, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

class Meta(BaseModel):
    """Metadata for Sankey graph"""
    version: int = 2
    units: Dict[str, str] = Field(default_factory=lambda: {"mass": "kg"})
    notes: Optional[str] = None
    batch_target_kg: Optional[float] = 300.0

class Node(BaseModel):
    """Node in Sankey diagram (machine, stream, or product)"""
    id: str
    label: str
    type: Literal["machine", "stream", "product"]
    tags: Optional[List[str]] = None
    
    @field_validator('id')
    @classmethod
    def id_must_be_valid(cls, v: str) -> str:
        """Ensure ID is valid for Plotly Sankey"""
        if not v:
            raise ValueError("Node ID cannot be empty")
        return v

class Link(BaseModel):
    """Link between nodes with optional measured and scaled masses"""
    id: str
    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")
    measured_kg: Optional[float] = None
    scaled_kg: Optional[float] = None
    percent_of_parent: Optional[float] = None
    trial_id: Optional[str] = None
    notes: Optional[str] = None
    
    class Config:
        populate_by_name = True

class Graph(BaseModel):
    """Complete Sankey graph with nodes, links, and metadata"""
    meta: Meta = Field(default_factory=Meta)
    nodes: List[Node] = Field(default_factory=list)
    links: List[Link] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    sinks: List[str] = Field(default_factory=list)
    
    @model_validator(mode='after')
    def validate_node_references(self) -> 'Graph':
        """Ensure all node references in links exist"""
        node_ids = {node.id for node in self.nodes}
        for link in self.links:
            if link.from_node not in node_ids:
                raise ValueError(f"Link {link.id} references non-existent from_node: {link.from_node}")
            if link.to_node not in node_ids:
                raise ValueError(f"Link {link.id} references non-existent to_node: {link.to_node}")
        return self

def compute_total_input(graph: Graph) -> float:
    """Calculate total input mass from source nodes"""
    total = 0.0
    
    # If sources defined, use those
    if graph.sources:
        for source_id in graph.sources:
            for link in graph.links:
                if link.from_node == source_id and link.measured_kg is not None:
                    total += link.measured_kg
    # Otherwise, find nodes with no incoming links
    else:
        # Find nodes with no incoming links
        incoming_nodes = {link.to_node for link in graph.links}
        potential_sources = {node.id for node in graph.nodes} - incoming_nodes
        
        # Sum outgoing measured_kg from these nodes
        for source_id in potential_sources:
            for link in graph.links:
                if link.from_node == source_id and link.measured_kg is not None:
                    total += link.measured_kg
    
    return total

def scale_graph_global(graph: Graph, batch_target_kg: Optional[float] = None) -> Graph:
    """Scale all measured_kg values by a global factor"""
    # Use target from graph.meta if not specified
    target = batch_target_kg or graph.meta.batch_target_kg
    if not target:
        raise ValueError("Batch target must be specified")
    
    # Calculate total input
    total_input = compute_total_input(graph)
    if total_input <= 0:
        raise ValueError("Total input mass must be positive")
    
    # Calculate scale factor
    scale_factor = target / total_input
    
    # Create new graph with scaled values
    new_graph = graph.model_copy(deep=True)
    
    # Scale all measured_kg values
    for link in new_graph.links:
        if link.measured_kg is not None:
            link.scaled_kg = link.measured_kg * scale_factor
    
    return new_graph

def normalize_graph(graph: Graph) -> Graph:
    """Ensure graph has all required fields and normalize data"""
    new_graph = graph.model_copy(deep=True)
    
    # Ensure meta exists
    if new_graph.meta is None:
        new_graph.meta = Meta()
    
    # Ensure sources and sinks exist
    if not new_graph.sources:
        # Find nodes with no incoming links
        incoming_nodes = {link.to_node for link in new_graph.links}
        new_graph.sources = [
            node.id for node in new_graph.nodes 
            if node.id not in incoming_nodes
        ]
    
    if not new_graph.sinks:
        # Find nodes with no outgoing links
        outgoing_nodes = {link.from_node for link in new_graph.links}
        new_graph.sinks = [
            node.id for node in new_graph.nodes 
            if node.id not in outgoing_nodes
        ]
    
    # Compute percentages if not present
    node_totals = {}
    for link in new_graph.links:
        if link.from_node not in node_totals:
            node_totals[link.from_node] = 0.0
        
        if link.measured_kg is not None:
            node_totals[link.from_node] += link.measured_kg
    
    for link in new_graph.links:
        if (link.measured_kg is not None and 
            node_totals.get(link.from_node, 0) > 0 and 
            link.percent_of_parent is None):
            link.percent_of_parent = link.measured_kg / node_totals[link.from_node] * 100
    
    return new_graph
