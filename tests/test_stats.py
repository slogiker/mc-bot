import os
import json
import pytest
import asyncio
import discord
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from cogs.stats import StatsCog

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    return bot

@pytest.fixture
def stats_cog(mock_bot):
    return StatsCog(mock_bot)

@pytest.fixture
def mock_interaction():
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = 11111
    interaction.user.name = "CommandUser"
    return interaction

@pytest.mark.asyncio
async def test_get_uuid_online_success(stats_cog):
    """Test get_uuid_online when Mojang API returns 200."""
    mock_json = {"id": "1234567890", "name": "MojangPlayer"}
    
    class MockResponse:
        def __init__(self, status, json_data):
            self.status = status
            self._json_data = json_data
        async def json(self):
            return self._json_data
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockSession:
        def __init__(self, *args, **kwargs):
            pass
        def get(self, url, *args, **kwargs):
            return MockResponse(200, mock_json)
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch('aiohttp.ClientSession', new=MockSession):
        uuid, name = await stats_cog.get_uuid_online("MojangPlayer")
        assert uuid == "1234567890"
        assert name == "MojangPlayer"

@pytest.mark.asyncio
async def test_get_uuid_online_failure(stats_cog):
    """Test get_uuid_online when Mojang API fails or returns non-200."""
    class MockResponse:
        def __init__(self, status):
            self.status = status
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockSession:
        def __init__(self, *args, **kwargs):
            pass
        def get(self, url, *args, **kwargs):
            return MockResponse(404)
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch('aiohttp.ClientSession', new=MockSession):
        uuid, name = await stats_cog.get_uuid_online("NonExistent")
        assert uuid is None
        assert name is None

@pytest.mark.asyncio
async def test_get_offline_uuid(stats_cog):
    """Test get_offline_uuid generates a v3 offline UUID."""
    uuid_str, name = await stats_cog.get_offline_uuid("OfflinePlayer")
    assert name == "OfflinePlayer"
    assert len(uuid_str) == 32

def test_get_stats_from_nbt(stats_cog, tmp_path):
    """Test get_stats_from_nbt parses json and NBT files correctly."""
    world_dir = tmp_path / "world"
    stats_dir = world_dir / "stats"
    playerdata_dir = world_dir / "playerdata"
    stats_dir.mkdir(parents=True)
    playerdata_dir.mkdir(parents=True)

    uuid_hex = "12345678123456781234567812345678"
    uuid_formatted = "12345678-1234-5678-1234-567812345678"

    stats_json_file = stats_dir / f"{uuid_formatted}.json"
    stats_content = {
        "stats": {
            "minecraft:custom": {
                "minecraft:play_time": 72000,
                "minecraft:deaths": 5
            }
        }
    }
    stats_json_file.write_text(json.dumps(stats_content))
    (playerdata_dir / f"{uuid_formatted}.dat").touch()

    with patch('nbtlib.load') as mock_nbt_load, \
         patch('src.config.Config.WORLD_FOLDER', new_callable=PropertyMock) as mock_world:
        mock_world.return_value = "world"
        
        mock_nbt_file = MagicMock()
        mock_nbt_file.root = {"Inventory": []}
        mock_nbt_load.return_value = mock_nbt_file

        stats, nbt = stats_cog.get_stats_from_nbt(uuid_hex, str(tmp_path))
        
        assert stats == stats_content
        assert nbt == {"Inventory": []}
        mock_nbt_load.assert_called_once_with(os.path.join(playerdata_dir, f"{uuid_formatted}.dat"))

@pytest.mark.asyncio
async def test_stats_command_no_args_not_linked(stats_cog, mock_interaction):
    """Test stats command when no args are provided and the caller is not linked."""
    with patch('cogs.stats.MCLinkManager') as mock_link_class:
        mock_lm = mock_link_class.return_value
        mock_lm.get_link_by_discord = AsyncMock(return_value=None)
        
        await stats_cog.stats.callback(stats_cog, mock_interaction)
        
        mock_lm.get_link_by_discord.assert_called_once_with(mock_interaction.user.id)
        mock_interaction.followup.send.assert_called_once_with("❌ This user is not linked to a Minecraft player.")

@pytest.mark.asyncio
async def test_stats_command_user_linked_no_data(stats_cog, mock_interaction):
    """Test stats command when looking up a linked user but no server data exists."""
    linked_member = MagicMock(spec=discord.Member)
    linked_member.id = 22222
    linked_member.name = "LinkedUser"

    with patch('cogs.stats.MCLinkManager') as mock_link_class, \
         patch('cogs.stats.get_uuid', new_callable=AsyncMock) as mock_get_uuid:
        mock_lm = mock_link_class.return_value
        mock_lm.get_link_by_discord = AsyncMock(return_value={
            "discord_id": 22222,
            "mc_username": "LinkedPlayer",
            "is_premium": True
        })
        mock_get_uuid.return_value = "cached-uuid-123"
        
        stats_cog.get_stats_from_nbt = MagicMock(return_value=({}, {}))
        
        await stats_cog.stats.callback(stats_cog, mock_interaction, user=linked_member)
        
        mock_lm.get_link_by_discord.assert_called_once_with(22222)
        mock_get_uuid.assert_called_once_with("LinkedPlayer")
        mock_interaction.followup.send.assert_called_once_with(
            "❌ No data found for player 'LinkedPlayer'. Has this player joined the server?"
        )

@pytest.mark.asyncio
async def test_stats_command_player_specified_premium_with_data(stats_cog, mock_interaction):
    """Test stats command with player name, premium, with data."""
    with patch('cogs.stats.MCLinkManager') as mock_link_class, \
         patch('cogs.stats.get_uuid', new_callable=AsyncMock) as mock_get_uuid:
        mock_lm = mock_link_class.return_value
        mock_lm.get_link_by_mc = AsyncMock(return_value=None)
        
        stats_cog.get_uuid_online = AsyncMock(side_effect=[
            ("premium-uuid-456", "PremiumPlayer"),
            ("premium-uuid-456", "PremiumPlayer")
        ])
        
        mock_get_uuid.return_value = "premium-uuid-456"
        
        stats_data = {
            "stats": {
                "minecraft:custom": {
                    "minecraft:play_time": 72000,
                    "minecraft:deaths": 2,
                    "minecraft:player_kills": 1,
                    "minecraft:mob_kills": 10
                }
            }
        }
        stats_cog.get_stats_from_nbt = MagicMock(return_value=(stats_data, {}))
        
        await stats_cog.stats.callback(stats_cog, mock_interaction, player="PremiumPlayer")
        
        mock_lm.get_link_by_mc.assert_called_once_with("PremiumPlayer")
        assert stats_cog.get_uuid_online.call_count == 2
        
        mock_interaction.followup.send.assert_called_once()
        _, kwargs = mock_interaction.followup.send.call_args
        assert "embed" in kwargs
        embed = kwargs["embed"]
        assert embed.title == "Stats for PremiumPlayer"
        assert embed.fields[0].value == "1.00 hours"
        assert embed.fields[1].value == "2"
        assert embed.fields[2].value == "1"
        assert embed.fields[3].value == "10"
        assert embed.thumbnail.url == "https://crafatar.com/avatars/premium-uuid-456?overlay"
        assert embed.footer.text == "Account Type: Premium"

@pytest.mark.asyncio
async def test_stats_command_player_specified_cracked_with_data(stats_cog, mock_interaction):
    """Test stats command with player name, cracked, with data."""
    with patch('cogs.stats.MCLinkManager') as mock_link_class, \
         patch('cogs.stats.get_uuid', new_callable=AsyncMock) as mock_get_uuid:
        mock_lm = mock_link_class.return_value
        mock_lm.get_link_by_mc = AsyncMock(return_value=None)
        
        stats_cog.get_uuid_online = AsyncMock(return_value=(None, None))
        
        mock_get_uuid.return_value = None
        stats_cog.get_offline_uuid = AsyncMock(return_value=("offline-uuid-789", "CrackedPlayer"))
        
        stats_data = {
            "stats": {
                "minecraft:custom": {
                    "minecraft:play_time": 144000,
                    "minecraft:deaths": 0,
                    "minecraft:player_kills": 0,
                    "minecraft:mob_kills": 0
                }
            }
        }
        stats_cog.get_stats_from_nbt = MagicMock(return_value=(stats_data, {}))
        
        await stats_cog.stats.callback(stats_cog, mock_interaction, player="CrackedPlayer")
        
        mock_lm.get_link_by_mc.assert_called_once_with("CrackedPlayer")
        stats_cog.get_uuid_online.assert_called_once_with("CrackedPlayer")
        stats_cog.get_offline_uuid.assert_called_once_with("CrackedPlayer")
        
        mock_interaction.followup.send.assert_called_once()
        _, kwargs = mock_interaction.followup.send.call_args
        assert "embed" in kwargs
        embed = kwargs["embed"]
        assert embed.title == "Stats for CrackedPlayer"
        assert embed.fields[0].value == "2.00 hours"
        assert embed.thumbnail.url == "https://minecraft-heads.com/avatar/Steve/64"
        assert embed.footer.text == "Account Type: Cracked / Offline"
