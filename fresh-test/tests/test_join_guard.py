import pytest
import asyncio
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
        jg.link_manager = mock_link_manager.return_value
        return jg

@pytest.mark.asyncio
async def test_handle_player_login_premium_no_link(join_guard):
    """Test that a premium player with no link is allowed to join."""
    join_guard.link_manager.get_link_by_mc = AsyncMock(return_value=None)
    
    with patch('src.join_guard.verify_premium_mc_account', new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = True
        
        # We don't want to actually kick
        join_guard._kick_player = AsyncMock()
        
        await join_guard.handle_player_login("PremiumPlayer", "uuid-123")
        
        join_guard.link_manager.get_link_by_mc.assert_called_with("PremiumPlayer")
        mock_verify.assert_called_with("PremiumPlayer")
        join_guard._kick_player.assert_not_called()

@pytest.mark.asyncio
async def test_handle_player_login_cracked_no_link_kicked(join_guard):
    """Test that a cracked player with no link is kicked."""
    join_guard.link_manager.get_link_by_mc = AsyncMock(return_value=None)
    
    with patch('src.join_guard.verify_premium_mc_account', new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = False
        join_guard._kick_player = AsyncMock()
        
        await join_guard.handle_player_login("CrackedPlayer", "uuid-456")
        
        join_guard._kick_player.assert_called_once()
        args, _ = join_guard._kick_player.call_args
        assert args[0] == "CrackedPlayer"
        assert "must link your Discord" in args[1]

@pytest.mark.asyncio
async def test_handle_player_login_premium_link_allowed(join_guard):
    """Test that a player with a premium link is allowed."""
    join_guard.link_manager.get_link_by_mc = AsyncMock(return_value={
        "discord_id": 123,
        "mc_username": "PremiumLinked",
        "is_premium": True
    })
    join_guard._kick_player = AsyncMock()
    
    await join_guard.handle_player_login("PremiumLinked", "uuid-789")
    
    join_guard._kick_player.assert_not_called()

@pytest.mark.asyncio
async def test_handle_player_login_cracked_link_grace_period(join_guard):
    """Test that a cracked player within grace period is allowed."""
    join_guard.link_manager.get_link_by_mc = AsyncMock(return_value={
        "discord_id": 123,
        "mc_username": "CrackedLinked",
        "is_premium": False
    })
    join_guard._kick_player = AsyncMock()
    
    # Set grace period
    join_guard.recently_disconnected["crackedlinked"] = asyncio.get_event_loop().time() + 1000 # Future but it uses time.time()
    
    # Mock time.time()
    with patch('time.time', return_value=10000):
        join_guard.recently_disconnected["crackedlinked"] = 9500 # 500s ago, within 1800s grace
        
        await join_guard.handle_player_login("CrackedLinked", "uuid-abc")
        
        join_guard._kick_player.assert_not_called()
        assert "crackedlinked" not in join_guard.recently_disconnected

@pytest.mark.asyncio
async def test_handle_player_login_cracked_link_issue_challenge(join_guard):
    """Test that a cracked player outside grace period is challenged."""
    join_guard.link_manager.get_link_by_mc = AsyncMock(return_value={
        "discord_id": 123,
        "mc_username": "CrackedLinked",
        "is_premium": False
    })
    join_guard._kick_player = AsyncMock()
    join_guard._issue_challenge = AsyncMock()
    
    # No entry in recently_disconnected
    
    await join_guard.handle_player_login("CrackedLinked", "uuid-abc")
    
    join_guard._issue_challenge.assert_called_once_with("CrackedLinked", 123)

@pytest.mark.asyncio
async def test_verify_code_success(join_guard):
    """Test successful code verification."""
    join_guard.active_challenges["PlayerOne"] = {
        "discord_id": 123,
        "code": "SECRET",
        "timeout_task": MagicMock()
    }
    
    success, message = await join_guard.verify_code(123, "SECRET")
    
    assert success is True
    assert "successful" in message
    assert "PlayerOne" not in join_guard.active_challenges
    assert "playerone" in join_guard.recently_disconnected

@pytest.mark.asyncio
async def test_verify_code_wrong(join_guard):
    """Test incorrect code verification."""
    join_guard.active_challenges["PlayerOne"] = {
        "discord_id": 123,
        "code": "SECRET",
        "timeout_task": MagicMock()
    }
    
    success, message = await join_guard.verify_code(123, "WRONG")
    
    assert success is False
    assert "Incorrect" in message
    assert "PlayerOne" in join_guard.active_challenges
