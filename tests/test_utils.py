"""
Tests for src/utils.py — pure utility functions
"""
import os
import pytest
from src.utils import map_key, display_key, parse_server_version


class TestMapKey:
    def test_basic(self):
        assert map_key("diamonds") == "minecraft:diamonds"

    def test_uppercase_lowered(self):
        assert map_key("DIAMONDS") == "minecraft:diamonds"

    def test_mixed_case(self):
        assert map_key("DiAmOnDs") == "minecraft:diamonds"

    def test_already_prefixed(self):
        # Should double-prefix — map_key just prepends blindly
        result = map_key("minecraft:diamonds")
        assert result == "minecraft:minecraft:diamonds"

    def test_empty_string(self):
        assert map_key("") == "minecraft:"


class TestDisplayKey:
    def test_removes_prefix(self):
        assert display_key("minecraft:diamonds") == "diamonds"

    def test_no_prefix(self):
        assert display_key("diamonds") == "diamonds"

    def test_partial_prefix(self):
        assert display_key("mine:diamonds") == "mine:diamonds"

    def test_empty_string(self):
        assert display_key("") == ""

    def test_only_prefix(self):
        assert display_key("minecraft:") == ""


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
