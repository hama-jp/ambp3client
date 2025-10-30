"""Unit tests for AmbP3.config module."""

import pytest
import tempfile
import yaml
from unittest.mock import Mock, patch, mock_open
from argparse import Namespace
from AmbP3.config import (
    Config,
    get_args,
    DefaultConfig,
    DEFAULT_IP,
    DEFAULT_PORT,
    DEFAULT_CONFIG_FILE,
)


class TestDefaultConfig:
    """Tests for default configuration values."""

    def test_default_config_structure(self):
        """Test that DefaultConfig has expected structure."""
        assert "ip" in DefaultConfig
        assert "port" in DefaultConfig
        assert "file" in DefaultConfig
        assert "debug_file" in DefaultConfig
        assert "mysql_backend" in DefaultConfig
        assert "mysql_host" in DefaultConfig
        assert "mysql_port" in DefaultConfig

    def test_default_values(self):
        """Test default configuration values."""
        assert DefaultConfig["ip"] == DEFAULT_IP
        assert DefaultConfig["port"] == DEFAULT_PORT
        assert DefaultConfig["file"] is False
        assert DefaultConfig["debug_file"] is False
        assert DefaultConfig["mysql_backend"] is False
        assert DefaultConfig["mysql_host"] == "127.0.0.1"
        assert DefaultConfig["mysql_port"] == 3306


class TestConfig:
    """Tests for Config class."""

    def test_config_with_missing_file(self):
        """Test Config initialization with missing config file."""
        cli_args = Namespace(
            config_file="nonexistent.yaml", ip=None, port=None, file=None
        )

        config = Config(cli_args)

        # Should fall back to defaults
        assert config.ip == DEFAULT_IP
        assert config.port == DEFAULT_PORT
        assert config.file is False

    def test_config_with_valid_yaml(self):
        """Test Config initialization with valid YAML file."""
        # Create a temporary YAML file
        yaml_content = {
            "ip": "192.168.1.100",
            "port": 6000,
            "mysql_host": "db.example.com",
            "mysql_port": 3307,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(yaml_content, f)
            temp_file = f.name

        try:
            cli_args = Namespace(config_file=temp_file, ip=None, port=None, file=None)

            config = Config(cli_args)

            # Values from YAML should be loaded
            assert config.conf["mysql_host"] == "db.example.com"
            assert config.conf["mysql_port"] == 3307
        finally:
            import os

            os.unlink(temp_file)

    def test_config_cli_args_override(self):
        """Test that CLI args override config file values."""
        yaml_content = {"ip": "192.168.1.100", "port": 6000}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(yaml_content, f)
            temp_file = f.name

        try:
            cli_args = Namespace(
                config_file=temp_file,
                ip="10.0.0.1",  # Override YAML value
                port=7000,  # Override YAML value
                file="/tmp/test.log",
            )

            config = Config(cli_args)

            # CLI args should take precedence
            assert config.ip == "10.0.0.1"
            assert config.port == 7000
            assert config.file == "/tmp/test.log"
        finally:
            import os

            os.unlink(temp_file)

    def test_config_none_values_removed(self):
        """Test that None values from CLI args don't override config."""
        yaml_content = {"ip": "192.168.1.100", "port": 6000}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(yaml_content, f)
            temp_file = f.name

        try:
            cli_args = Namespace(
                config_file=temp_file,
                ip=None,  # Should not override
                port=None,  # Should not override
                file=None,
            )

            config = Config(cli_args)

            # YAML values should remain since CLI args are None
            assert config.ip == "192.168.1.100"
            assert config.port == 6000
        finally:
            import os

            os.unlink(temp_file)

    @pytest.mark.xfail(
        reason="BUG: Config doesn't set attributes when YAML is empty/None"
    )
    def test_config_with_empty_yaml(self):
        """Test Config with empty YAML file.

        KNOWN BUG: When YAML file is empty (yaml.safe_load returns None),
        isinstance(config_from_file, dict) is False, so the code in the
        if block (lines 32-35 in config.py) is never executed. This means
        self.ip, self.port, self.file, and self.debug_file are never set,
        causing AttributeError.

        Expected behavior: Should fall back to defaults.
        Actual behavior: Attributes are not set at all.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            temp_file = f.name

        try:
            cli_args = Namespace(config_file=temp_file, ip=None, port=None, file=None)

            config = Config(cli_args)

            # This will fail with AttributeError until bug is fixed
            assert config.ip == DEFAULT_IP
            assert config.port == DEFAULT_PORT
        finally:
            import os

            os.unlink(temp_file)

    @pytest.mark.xfail(
        reason="BUG: Config doesn't set attributes when YAML is not a dict"
    )
    def test_config_with_invalid_yaml_structure(self):
        """Test Config when YAML doesn't parse to a dict.

        KNOWN BUG: When YAML parses to a list or other non-dict type,
        isinstance(config_from_file, dict) is False, causing the same
        bug as test_config_with_empty_yaml.

        Expected behavior: Should fall back to defaults or raise error.
        Actual behavior: Attributes are not set, causing AttributeError.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Write a YAML list instead of dict
            f.write("- item1\n- item2\n")
            temp_file = f.name

        try:
            cli_args = Namespace(config_file=temp_file, ip=None, port=None, file=None)

            config = Config(cli_args)

            # This will fail with AttributeError until bug is fixed
            assert config.ip == DEFAULT_IP
            assert config.port == DEFAULT_PORT
        finally:
            import os

            os.unlink(temp_file)


class TestGetArgs:
    """Tests for get_args function."""

    @patch("sys.argv", ["test_prog", "-f", "nonexistent.yaml"])
    def test_get_args_defaults(self):
        """Test get_args with no CLI arguments (using non-existent config).

        Note: We use a non-existent config file to avoid reading the actual
        conf.yaml in the project which may have different values.
        """
        config = get_args()

        # Should use defaults when config file doesn't exist
        assert config.ip == DEFAULT_IP
        assert config.port == DEFAULT_PORT
        assert config.file is False

    @patch(
        "sys.argv",
        ["test_prog", "-f", "nonexistent.yaml", "-i", "10.0.0.1", "-p", "8000"],
    )
    def test_get_args_with_ip_and_port(self):
        """Test get_args with IP and port arguments."""
        config = get_args()

        assert config.ip == "10.0.0.1"
        assert config.port == 8000

    @patch("sys.argv", ["test_prog", "-f", "nonexistent.yaml", "-l", "/tmp/test.log"])
    def test_get_args_with_log_file(self):
        """Test get_args with log file argument."""
        config = get_args()

        assert config.file == "/tmp/test.log"

    @patch("sys.argv", ["test_prog", "-f", "nonexistent_custom.yaml"])
    def test_get_args_with_config_file(self):
        """Test get_args with custom config file.

        Note: The config_file parameter is used to load the config,
        but it's not stored in the final config.conf dict. It's only
        in the original cli_args Namespace object.
        """
        config = get_args()

        # Config should be loaded (or use defaults if file doesn't exist)
        assert config.conf is not None
        assert "ip" in config.conf
        assert "port" in config.conf

        # The config itself should have the expected structure
        assert config.ip == DEFAULT_IP
        assert config.port == DEFAULT_PORT


@pytest.fixture
def sample_yaml_config():
    """Fixture providing a sample YAML configuration."""
    return {
        "ip": "192.168.1.100",
        "port": 5403,
        "mysql_host": "localhost",
        "mysql_user": "testuser",
        "mysql_db": "testdb",
        "mysql_password": "testpass",
    }


@pytest.fixture
def temp_config_file(sample_yaml_config):
    """Fixture creating a temporary config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(sample_yaml_config, f)
        temp_file = f.name

    yield temp_file

    # Cleanup
    import os

    os.unlink(temp_file)
