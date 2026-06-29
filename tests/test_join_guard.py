import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from src.join_guard import JoinGuard

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.get_user = MagicMock()
    bot.fetch_user = AsyncMock()
    return bot

@pytest.fixture
def join_guard(mock_bot):
    with patch('src.join_guard.MCLinkManager') as mock_link_manager, \
         patch('src.config.Config.ONLINE_MODE', new_callable=PropertyMock) as mock_online:
        mock_online.return_value = False
        jg = JoinGuard(mock_bot)
        # Mock methods on link_manager as needed
        jg.link_manager.get_link_by_mc = AsyncMock()
        jg.link_manager.is_within_grace = AsyncMock(return_value=False)
        jg.link_manager.record_verified = AsyncMock()
        yield jg

@pytest.mark.asyncio
async def test_handle_player_login_premium_no_link_kicked(join_guard):
    """Test that a premium player with no link is kicked (no premium bypass in offline mode)."""
    join_guard.link_manager.get_link_by_mc.return_value = None
    join_guard._kick = AsyncMock()
    
    await join_guard.handle_player_login("PremiumPlayer", "uuid-123")
    
    join_guard._kick.assert_called_once()
    args, _ = join_guard._kick.call_args
    assert args[0] == "PremiumPlayer"
    assert "ni povezan z Discordom" in args[1]

@pytest.mark.asyncio
async def test_handle_player_login_premium_link_challenged(join_guard):
    """Test that a premium player with a link who is outside grace period is challenged (kicked with code)."""
    join_guard.link_manager.get_link_by_mc.return_value = {
        "discord_id": 123,
        "mc_username": "PremiumLinked",
        "is_premium": True
    }
    join_guard.link_manager.is_within_grace.return_value = False
    join_guard._kick = AsyncMock()
    
    await join_guard.handle_player_login("PremiumLinked", "uuid-789")
    
    join_guard._kick.assert_called_once()
    assert "Koda:" in join_guard._kick.call_args[0][1]
    assert "premiumlinked" in join_guard.active_challenges

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


@pytest.mark.asyncio
async def test_handle_player_login_online_mode_bypassed(mock_bot):
    """Test that when the server is in online-mode, JoinGuard is bypassed."""
    with patch('src.join_guard.MCLinkManager'), \
         patch('src.config.Config.ONLINE_MODE', new_callable=PropertyMock) as mock_online:
        mock_online.return_value = True
        jg = JoinGuard(mock_bot)
        jg._kick = AsyncMock()
        
        # Should return immediately and not kick or do anything
        await jg.handle_player_login("AnyPlayer", "uuid-123")
        jg._kick.assert_not_called()


@pytest.mark.asyncio
async def test_handle_player_quit_normal(join_guard):
    """Test that handle_player_quit records disconnect in normal mode."""
    join_guard.link_manager.record_disconnect = AsyncMock()
    join_guard.handle_player_quit("PlayerOne")
    # It runs as a background task, so we yield control to the event loop.
    await asyncio.sleep(0.01)
    join_guard.link_manager.record_disconnect.assert_called_once_with("PlayerOne")


@pytest.mark.asyncio
async def test_handle_player_quit_online_mode(mock_bot):
    """Test that handle_player_quit is bypassed in online-mode."""
    with patch('src.join_guard.MCLinkManager') as mock_link_class, \
         patch('src.config.Config.ONLINE_MODE', new_callable=PropertyMock) as mock_online:
        mock_online.return_value = True
        mock_lm = mock_link_class.return_value
        mock_lm.record_disconnect = AsyncMock()
        
        jg = JoinGuard(mock_bot)
        jg.handle_player_quit("PlayerOne")
        
        await asyncio.sleep(0.01)
        mock_lm.record_disconnect.assert_not_called()


@pytest.mark.asyncio
async def test_handle_collision_normal_linked(join_guard, mock_bot):
    """Test that handle_collision grants emergency grace and sends DM if player is linked."""
    join_guard.link_manager.grant_emergency_grace = AsyncMock()
    join_guard.link_manager.get_link_by_mc.return_value = {
        "discord_id": 12345,
        "mc_username": "PlayerOne"
    }
    
    mock_user = AsyncMock()
    mock_bot.get_user.return_value = mock_user
    
    await join_guard.handle_collision("PlayerOne")
    
    join_guard.link_manager.grant_emergency_grace.assert_called_once_with("PlayerOne")
    join_guard.link_manager.get_link_by_mc.assert_called_once_with("PlayerOne")
    mock_bot.get_user.assert_called_once_with(12345)
    mock_user.send.assert_called_once()
    
    # Check that embed is sent
    _, kwargs = mock_user.send.call_args
    assert "embed" in kwargs
    assert kwargs["embed"].title == "Poskus laznega predstavljanja!"


@pytest.mark.asyncio
async def test_handle_collision_normal_not_linked(join_guard, mock_bot):
    """Test that handle_collision grants emergency grace but does not send DM if not linked."""
    join_guard.link_manager.grant_emergency_grace = AsyncMock()
    join_guard.link_manager.get_link_by_mc.return_value = None
    
    await join_guard.handle_collision("PlayerOne")
    
    join_guard.link_manager.grant_emergency_grace.assert_called_once_with("PlayerOne")
    join_guard.link_manager.get_link_by_mc.assert_called_once_with("PlayerOne")
    mock_bot.get_user.assert_not_called()


@pytest.mark.asyncio
async def test_handle_collision_online_mode(mock_bot):
    """Test that handle_collision is bypassed in online-mode."""
    with patch('src.join_guard.MCLinkManager') as mock_link_class, \
         patch('src.config.Config.ONLINE_MODE', new_callable=PropertyMock) as mock_online:
        mock_online.return_value = True
        mock_lm = mock_link_class.return_value
        mock_lm.grant_emergency_grace = AsyncMock()
        
        jg = JoinGuard(mock_bot)
        await jg.handle_collision("PlayerOne")
        
        mock_lm.grant_emergency_grace.assert_not_called()
