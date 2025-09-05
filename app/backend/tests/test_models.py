"""
Tests for the chemical constants and metal data in models.py.
"""
import pytest
from models import get_constants, K_A2, K_W
from schemas import Metal


def test_get_constants_returns_expected_values():
    """Test that get_constants returns the expected values for K_A2 and K_W."""
    constants = get_constants()
    
    # Check K_A2 value
    assert constants.k_a2 == K_A2
    assert constants.k_a2 == 1.2e-2
    
    # Check K_W value
    assert constants.k_w == K_W
    assert constants.k_w == 1.0e-14


def test_get_constants_includes_required_metals():
    """Test that get_constants includes required metals with correct stoichiometries."""
    constants = get_constants()
    
    # Check that metals data is present
    assert constants.metals is not None
    
    # Check Fe3+ (Iron III)
    assert Metal.FE3 in constants.metals
    assert constants.metals[Metal.FE3].name == "Iron(III)"
    assert constants.metals[Metal.FE3].molar_mass == 55.845
    assert constants.metals[Metal.FE3].stoichiometry == 3
    
    # Check Ni2+ (Nickel)
    assert Metal.NI2 in constants.metals
    assert constants.metals[Metal.NI2].name == "Nickel"
    assert constants.metals[Metal.NI2].molar_mass == 58.693
    assert constants.metals[Metal.NI2].stoichiometry == 2


def test_all_metals_have_required_fields():
    """Test that all metals have the required fields with appropriate values."""
    constants = get_constants()
    
    for metal, data in constants.metals.items():
        # Check that each metal has the required fields
        assert hasattr(data, "name")
        assert hasattr(data, "molar_mass")
        assert hasattr(data, "stoichiometry")
        
        # Check that values are of the correct type
        assert isinstance(data.name, str)
        assert isinstance(data.molar_mass, float)
        assert isinstance(data.stoichiometry, int)
        
        # Check that values are in reasonable ranges
        assert len(data.name) > 0
        assert 1.0 < data.molar_mass < 300.0  # Reasonable range for element molar masses
        assert 1 <= data.stoichiometry <= 3    # Reasonable range for metal stoichiometries
