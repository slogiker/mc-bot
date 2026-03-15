import pytest
import os
import json
import asyncio
from src.mc_link_manager import MCLinkManager

TEST_DB_PATH = "data/test_mc_links.json"

@pytest.fixture
def manager():
    # Setup
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    mgr = MCLinkManager(data_file=TEST_DB_PATH)
    yield mgr
    # Teardown
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

@pytest.mark.asyncio
async def test_link_account(manager):
    await manager.link_account(12345, "playerOne", True)
    
    link = await manager.get_link_by_discord(12345)
    assert link is not None
    assert link["mc_username"] == "playerOne"
    assert link["is_premium"] is True
    
    by_mc = await manager.get_link_by_mc("playerOne")
    assert by_mc is not None
    assert by_mc["discord_id"] == 12345

@pytest.mark.asyncio
async def test_unlink_account(manager):
    await manager.link_account(12345, "playerOne", True)
    success = await manager.unlink_account(12345)
    assert success is True
    
    link = await manager.get_link_by_discord(12345)
    assert link is None

@pytest.mark.asyncio
async def test_replace_link(manager):
    await manager.link_account(12345, "playerOne", False)
    # Same discord ID, new MC name
    await manager.link_account(12345, "playerTwo", True)
    
    link = await manager.get_link_by_discord(12345)
    assert link["mc_username"] == "playerTwo"
    assert link["is_premium"] is True
    
    old_link = await manager.get_link_by_mc("playerOne")
    assert old_link is None

@pytest.mark.asyncio
async def test_stealing_link(manager):
    # Discord user 1 links an account
    await manager.link_account(111, "playerOne", False)
    # Discord user 2 links the SAME account
    await manager.link_account(222, "playerOne", True)
    
    # First user should lose the link
    link1 = await manager.get_link_by_discord(111)
    assert link1 is None
    
    link2 = await manager.get_link_by_discord(222)
    assert link2["mc_username"] == "playerOne"
