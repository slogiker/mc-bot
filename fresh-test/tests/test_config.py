"""
Tests for src/config.py — validate_user_config()
"""
from src.config import validate_user_config


class TestValidateUserConfig:
    """Tests for the validate_user_config function."""

    def test_valid_config_passes(self, valid_user_config):
        valid, errors = validate_user_config(valid_user_config)
        assert valid is True
        assert errors == []

    def test_missing_java_ram_min(self, valid_user_config):
        del valid_user_config["java_ram_min"]
        valid, errors = validate_user_config(valid_user_config)
        assert valid is False
        assert any("java_ram_min" in e for e in errors)

    def test_missing_java_ram_max(self, valid_user_config):
        del valid_user_config["java_ram_max"]
        valid, errors = validate_user_config(valid_user_config)
        assert valid is False
        assert any("java_ram_max" in e for e in errors)

    def test_invalid_ram_format(self, valid_user_config):
        valid_user_config["java_ram_max"] = "4X"
        valid, errors = validate_user_config(valid_user_config)
        assert valid is False
        assert any("4G" in e or "2048M" in e for e in errors)

    def test_ram_min_greater_than_max(self, valid_user_config):
        valid_user_config["java_ram_min"] = "8G"
        valid_user_config["java_ram_max"] = "2G"
        valid, errors = validate_user_config(valid_user_config)
        assert valid is False
        assert any("java_ram_min" in e and "<=" in e for e in errors)

    def test_ram_min_equals_max_ok(self, valid_user_config):
        valid_user_config["java_ram_min"] = "4G"
        valid_user_config["java_ram_max"] = "4G"
        valid, errors = validate_user_config(valid_user_config)
        assert valid is True

    def test_ram_mixed_units(self, valid_user_config):
        valid_user_config["java_ram_min"] = "512M"
        valid_user_config["java_ram_max"] = "4G"
        valid, errors = validate_user_config(valid_user_config)
        assert valid is True

    def test_invalid_backup_time(self, valid_user_config):
        valid_user_config["backup_time"] = "25:99"
        valid, errors = validate_user_config(valid_user_config)
        assert valid is False
        assert any("backup_time" in e for e in errors)

    def test_invalid_restart_time(self, valid_user_config):
        valid_user_config["restart_time"] = "not-a-time"
        valid, errors = validate_user_config(valid_user_config)
        assert valid is False
        assert any("restart_time" in e for e in errors)

    def test_missing_backup_time(self, valid_user_config):
        del valid_user_config["backup_time"]
        valid, errors = validate_user_config(valid_user_config)
        assert valid is False
        assert any("backup_time" in e for e in errors)

    def test_backup_keep_days_zero(self, valid_user_config):
        valid_user_config["backup_keep_days"] = 0
        valid, errors = validate_user_config(valid_user_config)
        assert valid is False
        assert any("backup_keep_days" in e for e in errors)

    def test_backup_keep_days_too_high(self, valid_user_config):
        valid_user_config["backup_keep_days"] = 999
        valid, errors = validate_user_config(valid_user_config)
        assert valid is False

    def test_backup_keep_days_string(self, valid_user_config):
        valid_user_config["backup_keep_days"] = "seven"
        valid, errors = validate_user_config(valid_user_config)
        assert valid is False

    def test_missing_timezone(self, valid_user_config):
        del valid_user_config["timezone"]
        valid, errors = validate_user_config(valid_user_config)
        assert valid is False
        assert any("timezone" in e for e in errors)

    def test_missing_permissions(self, valid_user_config):
        del valid_user_config["permissions"]
        valid, errors = validate_user_config(valid_user_config)
        assert valid is False
        assert any("permissions" in e for e in errors)

    def test_permissions_not_dict(self, valid_user_config):
        valid_user_config["permissions"] = "not-a-dict"
        valid, errors = validate_user_config(valid_user_config)
        assert valid is False
        assert any("permissions" in e for e in errors)

    def test_empty_config(self):
        valid, errors = validate_user_config({})
        assert valid is False
        assert len(errors) >= 5  # All required fields missing

    def test_boundary_keep_days_1(self, valid_user_config):
        valid_user_config["backup_keep_days"] = 1
        valid, errors = validate_user_config(valid_user_config)
        assert valid is True

    def test_boundary_keep_days_365(self, valid_user_config):
        valid_user_config["backup_keep_days"] = 365
        valid, errors = validate_user_config(valid_user_config)
        assert valid is True
