"""
Tests for src/utils.py — pure utility functions
"""
import os
import pytest
from src.utils import parse_server_version


class TestParseServerVersion:
    @pytest.mark.asyncio
    async def test_extracts_version(self, mock_server_log):
        """Parses version from a valid latest.log."""
        from unittest.mock import patch
        with patch("src.utils.config") as mock_cfg:
            mock_cfg.SERVER_DIR = str(mock_server_log)
            version = await parse_server_version()
            assert version == "1.21.4"

    @pytest.mark.asyncio
    async def test_missing_log_returns_unknown(self):
        """Returns 'Unknown' when log doesn't exist."""
        from unittest.mock import patch
        with patch("src.utils.config") as mock_cfg:
            mock_cfg.SERVER_DIR = "/nonexistent/path"
            version = await parse_server_version()
            assert version == "Unknown"

    @pytest.mark.asyncio
    async def test_no_version_line(self, tmp_path):
        """Returns 'Unknown' when log has no version line."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "latest.log").write_text(
            "[12:00:00] [Server thread/INFO]: Loading properties\n"
        )
        from unittest.mock import patch
        with patch("src.utils.config") as mock_cfg:
            mock_cfg.SERVER_DIR = str(tmp_path)
            version = await parse_server_version()
            assert version == "Unknown"
