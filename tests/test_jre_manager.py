import pytest
from src.jre_manager import jre_manager

def test_get_required_java_version():
    # Older versions (Java 8)
    assert jre_manager.get_required_java_version("1.16.5") == 8
    assert jre_manager.get_required_java_version("1.12.2") == 8
    
    # Mid-range versions (Java 17)
    assert jre_manager.get_required_java_version("1.17") == 17
    assert jre_manager.get_required_java_version("1.17.1") == 17
    assert jre_manager.get_required_java_version("1.18.2") == 17
    assert jre_manager.get_required_java_version("1.20.1") == 17
    assert jre_manager.get_required_java_version("1.20.4") == 17
    
    # Modern versions (Java 21)
    assert jre_manager.get_required_java_version("1.20.5") == 21
    assert jre_manager.get_required_java_version("1.20.6") == 21
    assert jre_manager.get_required_java_version("1.21") == 21
    assert jre_manager.get_required_java_version("1.21.1") == 21
    
    # Future/Simulated versions (Java 25)
    assert jre_manager.get_required_java_version("1.22") == 25
    assert jre_manager.get_required_java_version("1.25.3") == 25
    assert jre_manager.get_required_java_version("26.2") == 25
    assert jre_manager.get_required_java_version("26.1.2") == 25
    
    # Fallback cases
    assert jre_manager.get_required_java_version(None) == 21
    assert jre_manager.get_required_java_version("unknown") == 21
    assert jre_manager.get_required_java_version("") == 21
    assert jre_manager.get_required_java_version("invalid-version") == 21
