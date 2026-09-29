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

    # Platform-prefixed versions
    assert jre_manager.get_required_java_version("paper-1.16.5") == 8
    assert jre_manager.get_required_java_version("paper-1.20.4") == 17
    assert jre_manager.get_required_java_version("fabric-1.21.1") == 21
    assert jre_manager.get_required_java_version("vanilla-1.22") == 25


@pytest.mark.asyncio
async def test_upgrade_java_if_needed():
    # Test upgrading from 1.20.4 (Java 17) to 1.21.1 (Java 21)
    status_messages = []
    async def callback(msg):
        status_messages.append(msg)

    target_java, changed, exe = await jre_manager.upgrade_java_if_needed(
        new_mc_version="1.21.1",
        old_mc_version="1.20.4",
        progress_callback=callback
    )
    assert target_java == 21
    assert changed is True
    assert len(status_messages) > 0
    assert "Java 17" in status_messages[0] and "Java 21" in status_messages[0]

    # Test updating within same Java generation (1.21.1 to 1.21.4 -> both Java 21)
    status_messages.clear()
    target_java, changed, exe = await jre_manager.upgrade_java_if_needed(
        new_mc_version="1.21.4",
        old_mc_version="1.21.1",
        progress_callback=callback
    )
    assert target_java == 21
    assert changed is False
    assert len(status_messages) == 0

