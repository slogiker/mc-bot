import os
import pytest
import asyncio
import discord
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from contextlib import contextmanager
from datetime import datetime
from cogs.backup import BackupCog, BackupDownloadView
from cogs.admin import Admin

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.wait_until_ready = AsyncMock()
    bot.server = MagicMock()
    bot.get_channel = MagicMock()
    return bot

@pytest.fixture
def backup_cog(mock_bot):
    with patch('discord.ext.tasks.Loop.start') as mock_start:
        cog = BackupCog(mock_bot)
        cog.backup_loop = MagicMock()
        return cog

@pytest.fixture
def admin_cog(mock_bot):
    return Admin(mock_bot)

@pytest.fixture
def mock_interaction():
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.guild = MagicMock()
    return interaction

@pytest.mark.asyncio
async def test_admin_backup_now_success(admin_cog, mock_interaction):
    """Test /backup_now command success."""
    with patch('src.backup_manager.backup_manager.create_backup', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = (True, "backup_manual_123.zip", "/path/to/backup_manual_123.zip")
        
        await admin_cog.backup_now.callback(admin_cog, mock_interaction, name="test-backup")
        
        mock_create.assert_called_once_with(custom_name="test-backup", server=admin_cog.bot.server)
        mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
        assert mock_interaction.followup.send.call_count == 2
        mock_interaction.followup.send.assert_any_call("⏳ Starting backup...", ephemeral=True)
        mock_interaction.followup.send.assert_any_call("✅ Backup created: `backup_manual_123.zip`", ephemeral=True)

@pytest.mark.asyncio
async def test_admin_backup_now_failure(admin_cog, mock_interaction):
    """Test /backup_now command failure."""
    with patch('src.backup_manager.backup_manager.create_backup', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = (False, "Error message", None)
        
        await admin_cog.backup_now.callback(admin_cog, mock_interaction, name="test-backup")
        
        mock_interaction.followup.send.assert_any_call("❌ Backup failed: Error message", ephemeral=True)

@pytest.mark.asyncio
async def test_backup_command_success(backup_cog, mock_interaction):
    """Test /backup command success."""
    with patch('src.backup_manager.backup_manager.create_backup', new_callable=AsyncMock) as mock_create, \
         patch('cogs.backup.BackupDownloadView') as mock_view_class:
        mock_create.return_value = (True, "backup_manual_123.zip", "/path/to/backup_manual_123.zip")
        mock_view = MagicMock()
        mock_view_class.return_value = mock_view
        
        await backup_cog.backup.callback(backup_cog, mock_interaction, name="test-backup")
        
        mock_create.assert_called_once_with(custom_name="test-backup", server=backup_cog.bot.server)
        mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction.followup.send.assert_any_call("⏳ Starting backup... This might take a moment.")
        mock_interaction.followup.send.assert_any_call(
            "✅ Backup created successfully: `backup_manual_123.zip`",
            view=mock_view,
            ephemeral=True
        )

@pytest.mark.asyncio
async def test_backup_loop_trigger_success(backup_cog):
    """Test backup_loop triggers scheduled backup when time matches."""
    from src.config import config
    
    mock_channel = AsyncMock()
    backup_cog.bot.get_channel.return_value = mock_channel
    
    user_cfg = {"backup_time": "03:00"}
    bot_cfg = {"last_auto_backup": "2026-06-28"}
    
    mock_now = datetime(2026, 6, 29, 3, 0)
    
    @contextmanager
    def mock_update_bot_config():
        data = bot_cfg.copy()
        yield data
        bot_cfg.update(data)
        
    with patch('src.config.config.load_user_config', return_value=user_cfg), \
         patch('src.config.config.load_bot_config', return_value=bot_cfg), \
         patch('src.config.config.update_bot_config', side_effect=mock_update_bot_config), \
         patch('cogs.backup.datetime') as mock_datetime, \
         patch('src.backup_manager.backup_manager.create_backup', new_callable=AsyncMock) as mock_create:
        
        mock_datetime.now.return_value = mock_now
        mock_create.return_value = (True, "backup_auto_20260629.zip", "/path/to/backup")
        
        await BackupCog.backup_loop.coro(backup_cog)
        
        backup_cog.bot.wait_until_ready.assert_called_once()
        mock_create.assert_called_once_with(server=backup_cog.bot.server)
        mock_channel.send.assert_any_call("⏳ Starting scheduled backup...")
        mock_channel.send.assert_any_call("✅ Scheduled backup created: `backup_auto_20260629.zip`")
        assert bot_cfg["last_auto_backup"] == "2026-06-29"

@pytest.mark.asyncio
async def test_backup_loop_already_done_today(backup_cog):
    """Test backup_loop does not run backup if already done today."""
    mock_channel = AsyncMock()
    backup_cog.bot.get_channel.return_value = mock_channel
    
    user_cfg = {"backup_time": "03:00"}
    bot_cfg = {"last_auto_backup": "2026-06-29"}
    mock_now = datetime(2026, 6, 29, 3, 0)
    
    with patch('src.config.config.load_user_config', return_value=user_cfg), \
         patch('src.config.config.load_bot_config', return_value=bot_cfg), \
         patch('cogs.backup.datetime') as mock_datetime, \
         patch('src.backup_manager.backup_manager.create_backup', new_callable=AsyncMock) as mock_create:
        
        mock_datetime.now.return_value = mock_now
        
        await BackupCog.backup_loop.coro(backup_cog)
        
        mock_create.assert_not_called()
        mock_channel.send.assert_not_called()

@pytest.mark.asyncio
async def test_backup_loop_time_not_matched(backup_cog):
    """Test backup_loop does not run backup if time does not match."""
    mock_channel = AsyncMock()
    backup_cog.bot.get_channel.return_value = mock_channel
    
    user_cfg = {"backup_time": "03:00"}
    bot_cfg = {"last_auto_backup": "2026-06-28"}
    mock_now = datetime(2026, 6, 29, 3, 1)
    
    with patch('src.config.config.load_user_config', return_value=user_cfg), \
         patch('src.config.config.load_bot_config', return_value=bot_cfg), \
         patch('cogs.backup.datetime') as mock_datetime, \
         patch('src.backup_manager.backup_manager.create_backup', new_callable=AsyncMock) as mock_create:
        
        mock_datetime.now.return_value = mock_now
        
        await BackupCog.backup_loop.coro(backup_cog)
        
        mock_create.assert_not_called()

@pytest.mark.asyncio
async def test_backup_list(backup_cog, mock_interaction):
    """Test /backup_list command."""
    with patch('cogs.backup.backup_manager') as mock_bm, \
         patch('os.path.exists', return_value=True), \
         patch('os.listdir') as mock_listdir:
        
        mock_bm.auto_dir = "/fake/auto"
        mock_bm.custom_dir = "/fake/custom"
        
        mock_listdir.side_effect = [
            ["backup_auto_2.zip", "backup_auto_1.zip"],
            ["backup_custom_2.zip", "backup_custom_1.zip"]
        ]
        
        await backup_cog.backup_list.callback(backup_cog, mock_interaction)
        
        mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "backup_auto_1.zip" in msg
        assert "backup_custom_1.zip" in msg

@pytest.mark.asyncio
async def test_backup_download_found(backup_cog, mock_interaction):
    """Test /backup_download command when file is found."""
    with patch('cogs.backup.backup_manager') as mock_bm, \
         patch('os.path.exists') as mock_exists, \
         patch('discord.File') as mock_file_class:
        
        mock_bm.custom_dir = "/fake/custom"
        mock_bm.auto_dir = "/fake/auto"
        
        mock_exists.side_effect = lambda path: "custom" in path
        
        mock_file = MagicMock()
        mock_file_class.return_value = mock_file
        
        await backup_cog.backup_download.callback(backup_cog, mock_interaction, "my_backup.zip")
        
        mock_exists.assert_any_call("/fake/custom/my_backup.zip")
        mock_file_class.assert_called_once_with("/fake/custom/my_backup.zip")
        mock_interaction.followup.send.assert_any_call("⏳ Preparing download...", ephemeral=True)
        mock_interaction.followup.send.assert_any_call(file=mock_file, ephemeral=True)

@pytest.mark.asyncio
async def test_backup_download_not_found(backup_cog, mock_interaction):
    """Test /backup_download command when file is not found."""
    with patch('cogs.backup.backup_manager') as mock_bm, \
         patch('os.path.exists', return_value=False):
        
        mock_bm.custom_dir = "/fake/custom"
        mock_bm.auto_dir = "/fake/auto"
        
        await backup_cog.backup_download.callback(backup_cog, mock_interaction, "missing.zip")
        
        mock_interaction.followup.send.assert_called_once_with("❌ Backup `missing.zip` not found.", ephemeral=True)

@pytest.mark.asyncio
async def test_backup_download_autocomplete(backup_cog, mock_interaction):
    """Test autocomplete for backup downloads."""
    with patch('cogs.backup.backup_manager') as mock_bm, \
         patch('os.listdir') as mock_listdir:
        
        mock_bm.custom_dir = "/fake/custom"
        mock_bm.auto_dir = "/fake/auto"
        
        mock_listdir.side_effect = [
            ["custom1.zip", "custom2.zip"],
            ["auto1.zip", "auto2.zip"]
        ]
        
        choices = await backup_cog.backup_download_autocomplete(mock_interaction, "custom")
        
        assert len(choices) == 2
        assert choices[0].name == "custom2.zip"
        assert choices[1].name == "custom1.zip"

@pytest.mark.asyncio
async def test_backup_download_view(mock_interaction):
    """Test BackupDownloadView button click."""
    view = BackupDownloadView("/path/to/backup.zip")
    button = MagicMock(spec=discord.ui.Button)
    
    with patch('discord.File') as mock_file_class:
        mock_file = MagicMock()
        mock_file_class.return_value = mock_file
        
        await view.download_button.callback(mock_interaction)
        
        mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
        mock_file_class.assert_called_once_with("/path/to/backup.zip")
        mock_interaction.followup.send.assert_called_once_with(file=mock_file, ephemeral=True)
        assert view.uploaded is True
        assert view.download_button.disabled is True
        mock_interaction.edit_original_response.assert_called_once_with(view=view)
