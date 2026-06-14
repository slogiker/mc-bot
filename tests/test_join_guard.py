import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from src.join_guard import JoinGuard

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.get_user = MagicMock()
    bot.fetch_user = AsyncMock()
    return bot

@pytest.fixture
def join_guard(mock_bot):
    with patch('src.join_guard.MCLinkManager') as mock_link_manager:
        jg = JoinGuard(mock_bot)
        # Mock methods on link_manager as needed
        jg.link_manager.get_link_by_mc = AsyncMock()
        jg.link_manager.is_within_grace = AsyncMock(return_value=False)
        jg.link_manager.record_verified = AsyncMock()
        return jg

@pytest.mark.asyncio
async def test_handle_player_login_premium_no_link(join_guard):
    """Test that a premium player with no link is allowed to join."""
    join_guard.link_manager.get_link_by_mc.return_value = None
    
    with patch('src.join_guard.verify_premium_mc_account', new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = True
        join_guard._kick = AsyncMock()
        
        await join_guard.handle_player_login("PremiumPlayer", "uuid-123")
        
        # Check that it was called (ignoring session argument which is mocked)
        assert mock_verify.called
        assert mock_verify.call_args[0][0] == "PremiumPlayer"
        join_guard._kick.assert_not_called()

@pytest.mark.asyncio
async def test_handle_player_login_cracked_no_link_kicked(join_guard):
    """Test that a cracked player with no link is kicked."""
    join_guard.link_manager.get_link_by_mc.return_value = None
    
    with patch('src.join_guard.verify_premium_mc_account', new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = False
        join_guard._kick = AsyncMock()
        
        await join_guard.handle_player_login("CrackedPlayer", "uuid-456")
        
        join_guard._kick.assert_called_once()
        args, _ = join_guard._kick.call_args
        assert args[0] == "CrackedPlayer"
        assert "ni povezan z Discordom" in args[1]

@pytest.mark.asyncio
async def test_handle_player_login_premium_link_allowed(join_guard):
    """Test that a player who is premium (from Mojang API) is allowed regardless of link."""
    # Note: In the new JoinGuard, it checks verify_premium_mc_account FIRST.
    with patch('src.join_guard.verify_premium_mc_account', new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = True
        join_guard._kick = AsyncMock()
        
        await join_guard.handle_player_login("PremiumLinked", "uuid-789")
        
        join_guard._kick.assert_not_called()

@pytest.mark.asyncio
async def test_handle_player_login_cracked_link_grace_period(join_guard):
    """Test that a cracked player within grace period is allowed."""
    join_guard.link_manager.get_link_by_mc.return_value = {
        "discord_id": 123,
        "mc_username": "CrackedLinked",
        "is_premium": False
    }
    join_guard.link_manager.is_within_grace.return_value = True
    join_guard._kick = AsyncMock()
    
    with patch('src.join_guard.verify_premium_mc_account', new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = False
        await join_guard.handle_player_login("CrackedLinked", "uuid-abc")
        join_guard._kick.assert_not_called()

@pytest.mark.asyncio
async def test_handle_player_login_cracked_link_issue_challenge(join_guard):
    """Test that a cracked player outside grace period is challenged (kicked with code)."""
    join_guard.link_manager.get_link_by_mc.return_value = {
        "discord_id": 123,
        "mc_username": "CrackedLinked",
        "is_premium": False
    }
    join_guard.link_manager.is_within_grace.return_value = False
    join_guard._kick = AsyncMock()
    
    with patch('src.join_guard.verify_premium_mc_account', new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = False
        await join_guard.handle_player_login("CrackedLinked", "uuid-abc")
        
        # In new JoinGuard, issuing challenge means kicking with a code
        join_guard._kick.assert_called_once()
        assert "Koda:" in join_guard._kick.call_args[0][1]
        assert "crackedlinked" in join_guard.active_challenges

@pytest.mark.asyncio
async def test_verify_code_success(join_guard):
    """Test successful code verification."""
    join_guard.active_challenges["playerone"] = {
        "discord_id": 123,
        "code": "SECRET",
        "expires_at": time.time() + 300
    }
    
    success, message = await join_guard.verify_code(123, "SECRET")
    
    assert success is True
    assert "potrjena" in message
    assert "playerone" not in join_guard.active_challenges
    join_guard.link_manager.record_verified.assert_called_with("playerone")

@pytest.mark.asyncio
async def test_verify_code_wrong(join_guard):
    """Test incorrect code verification."""
    join_guard.active_challenges["playerone"] = {
        "discord_id": 123,
        "code": "SECRET",
        "expires_at": time.time() + 300
    }
    
    success, message = await join_guard.verify_code(123, "WRONG")
    
    assert success is False
    assert "Napacna koda" in message
    assert "playerone" in join_guard.active_challenges
