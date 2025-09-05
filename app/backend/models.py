"""
Chemical constants and metal data for titration analysis.

This module provides access to:
1. Chemical constants (K_a2, K_w)
2. Metal data (name, molar mass, stoichiometry)
3. Helper functions to fetch this data as pydantic models
"""
from typing import Dict

from schemas import Constants, Metal, MetalData


# Metal data: name, molar mass (g/mol), and stoichiometry (OH⁻/mol metal)
METALS_DATA: Dict[Metal, MetalData] = {
    Metal.FE3: MetalData(
        name="Iron(III)",
        molar_mass=55.845,
        stoichiometry=3
    ),
    Metal.FE2: MetalData(
        name="Iron(II)",
        molar_mass=55.845,
        stoichiometry=2
    ),
    Metal.AL3: MetalData(
        name="Aluminum",
        molar_mass=26.982,
        stoichiometry=3
    ),
    Metal.NI2: MetalData(
        name="Nickel",
        molar_mass=58.693,
        stoichiometry=2
    ),
    Metal.CO2: MetalData(
        name="Cobalt",
        molar_mass=58.933,
        stoichiometry=2
    ),
    Metal.MN2: MetalData(
        name="Manganese",
        molar_mass=54.938,
        stoichiometry=2
    ),
}

# Chemical constants
K_A2 = 1.2e-2  # HSO₄⁻ ⇌ H⁺ + SO₄²⁻ at 25°C
K_W = 1.0e-14  # Water dissociation constant at 25°C


def get_constants() -> Constants:
    """
    Return chemical constants and metal data as a pydantic model.
    
    This function is used by the /api/constants endpoint.
    
    Returns:
        Constants: A pydantic model containing K_a2, K_w, and metals data
    """
    return Constants(
        k_a2=K_A2,
        k_w=K_W,
        metals=METALS_DATA
    )
