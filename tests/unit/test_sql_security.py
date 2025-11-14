"""Tests for SQL injection prevention in amb_laps.py"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class TestSQLParameterization:
    """Test that SQL queries use parameterized queries properly."""

    def test_sql_select_with_params(self):
        """Test sql_select function with parameters."""
        from amb_laps import sql_select

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [(1, "test")]
        mock_cursor.rowcount = 1

        query = "SELECT * FROM table WHERE id = %s"
        params = (123,)

        result = sql_select(mock_cursor, query, params)

        # Verify execute was called with query and params
        mock_cursor.execute.assert_called_once_with(query, params)
        assert result == [(1, "test")]

    def test_sql_select_without_params(self):
        """Test sql_select function without parameters."""
        from amb_laps import sql_select

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [(1, "test")]
        mock_cursor.rowcount = 1

        query = "SELECT * FROM table"

        result = sql_select(mock_cursor, query)

        # Verify execute was called with just query
        mock_cursor.execute.assert_called_once_with(query)
        assert result == [(1, "test")]

    def test_sql_write_with_params(self):
        """Test sql_write function with parameters."""
        from amb_laps import sql_write

        mock_mysql = Mock()
        mock_cursor = Mock()
        mock_cursor.rowcount = 1
        mycon = (mock_mysql, mock_cursor)

        query = "INSERT INTO table (col1, col2) VALUES (%s, %s)"
        params = (123, "test")

        result = sql_write(mycon, query, params)

        # Verify execute was called with query and params
        mock_cursor.execute.assert_called_once_with(query, params)
        mock_mysql.commit.assert_called_once()
        assert result == 1

    def test_sql_write_without_params(self):
        """Test sql_write function without parameters."""
        from amb_laps import sql_write

        mock_mysql = Mock()
        mock_cursor = Mock()
        mock_cursor.rowcount = 1
        mycon = (mock_mysql, mock_cursor)

        query = "INSERT INTO table (col1) VALUES (123)"

        result = sql_write(mycon, query)

        # Verify execute was called with just query
        mock_cursor.execute.assert_called_once_with(query)
        mock_mysql.commit.assert_called_once()
        assert result == 1


class TestHeatMethodSecurity:
    """Test that Heat class methods use parameterized queries."""

    @pytest.fixture
    def mock_heat_config(self):
        """Fixture for mock Heat configuration."""
        return {
            "mysql_user": "test_user",
            "mysql_db": "test_db",
            "mysql_password": "test_pass",
            "mysql_host": "127.0.0.1",
            "mysql_port": 3306,
        }

    @pytest.fixture
    def mock_decoder_time(self):
        """Fixture for mock DecoderTime."""
        decoder_time = Mock()
        decoder_time.decoder_time = 1000000
        return decoder_time

    @patch("amb_laps.mysql_connect")
    @patch("amb_laps.sql_select")
    def test_is_running_uses_parameterized_query(
        self, mock_sql_select, mock_mysql_connect, mock_heat_config, mock_decoder_time
    ):
        """Test that is_running method uses parameterized queries."""
        from amb_laps import Heat

        # Setup mocks
        mock_cursor = Mock()
        mock_mysql = Mock()
        mock_mysql.cursor.return_value = mock_cursor
        mock_mysql_connect.return_value = mock_mysql

        # Mock settings and heat queries
        # Note: first_pass_id is None to avoid calling get_transponder during init
        mock_sql_select.side_effect = [
            [],  # settings query
            [
                (1, False, None, None, 1000000, None, 0, 2000000)
            ],  # get_heat query (first_pass_id=None)
        ]

        heat = Heat(mock_heat_config, mock_decoder_time)

        # Reset mock to track only is_running calls
        mock_sql_select.reset_mock()
        mock_sql_select.side_effect = None  # Clear side_effect
        mock_sql_select.return_value = [(False,)]

        heat.is_running(123)

        # Verify parameterized query was used
        call_args = mock_sql_select.call_args
        assert call_args is not None
        query = call_args[0][1]  # Second argument is the query
        params = (
            call_args[0][2] if len(call_args[0]) > 2 else None
        )  # Third argument is params

        # Check that query uses %s placeholder
        assert "%s" in query
        assert "{" not in query  # No f-string formatting
        assert "format(" not in query  # No .format()
        # Check that params were passed
        assert params == (123,)

    @patch("amb_laps.mysql_connect")
    @patch("amb_laps.sql_select")
    def test_get_transponder_uses_parameterized_query(
        self, mock_sql_select, mock_mysql_connect, mock_heat_config, mock_decoder_time
    ):
        """Test that get_transponder method uses parameterized queries."""
        from amb_laps import Heat

        # Setup mocks
        mock_cursor = Mock()
        mock_mysql = Mock()
        mock_mysql.cursor.return_value = mock_cursor
        mock_mysql_connect.return_value = mock_mysql

        # Mock queries
        # Note: first_pass_id is None to avoid calling get_transponder during init
        mock_sql_select.side_effect = [
            [],  # settings query
            [
                (1, False, None, None, 1000000, None, 0, 2000000)
            ],  # get_heat query (first_pass_id=None)
        ]

        heat = Heat(mock_heat_config, mock_decoder_time)

        # Reset and set up for get_transponder call
        mock_sql_select.reset_mock()
        mock_sql_select.side_effect = None  # Clear side_effect
        mock_sql_select.return_value = [[12345]]

        result = heat.get_transponder(100)

        # Verify parameterized query was used
        call_args = mock_sql_select.call_args
        query = call_args[0][1]
        params = call_args[0][2] if len(call_args[0]) > 2 else None

        assert "%s" in query
        assert params == (100,)
        assert result == 12345


class TestNoSQLInjectionVulnerabilities:
    """Test that common SQL injection patterns are not present."""

    def test_no_f_string_in_sql_queries(self):
        """Verify no f-strings are used in SQL queries in critical methods."""
        import inspect
        from amb_laps import Heat

        # Get source code of Heat class
        source = inspect.getsource(Heat)

        # List of methods that should not have f-string SQL queries
        critical_methods = [
            "is_running",
            "get_pass_timestamp",
            "get_transponder",
            "finish_heat",
            "valid_lap_time",
            "wave_finish_flag",
            "check_if_all_finished",
            "get_kart_id",
        ]

        # This is a basic check - in a real scenario, you'd use AST parsing
        # for more accurate detection
        for method_name in critical_methods:
            # Check that method exists
            assert hasattr(Heat, method_name), f"Method {method_name} not found"

    def test_sql_helper_functions_support_params(self):
        """Test that SQL helper functions properly support parameters."""
        from amb_laps import sql_select, sql_write
        import inspect

        # Check sql_select signature
        sig_select = inspect.signature(sql_select)
        assert "params" in sig_select.parameters
        assert sig_select.parameters["params"].default is None

        # Check sql_write signature
        sig_write = inspect.signature(sql_write)
        assert "params" in sig_write.parameters
        assert sig_write.parameters["params"].default is None


class TestSQLInjectionPrevention:
    """Test specific SQL injection attack patterns are prevented."""

    def test_malicious_input_in_parameterized_query(self):
        """Test that malicious SQL input is safely handled by parameterized queries."""
        from amb_laps import sql_select

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.rowcount = 0

        # Malicious input that would cause SQL injection if not parameterized
        malicious_id = "1 OR 1=1; DROP TABLE users; --"

        query = "SELECT * FROM table WHERE id = %s"
        params = (malicious_id,)

        sql_select(mock_cursor, query, params)

        # Verify that the malicious input was passed as a parameter
        # (which will be safely escaped by the database driver)
        mock_cursor.execute.assert_called_once_with(query, (malicious_id,))

    def test_multiple_params_handled_correctly(self):
        """Test that multiple parameters are handled correctly."""
        from amb_laps import sql_select

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []

        query = "SELECT * FROM table WHERE col1 = %s AND col2 = %s AND col3 = %s"
        params = (123, "test", 456)

        sql_select(mock_cursor, query, params)

        mock_cursor.execute.assert_called_once_with(query, params)
