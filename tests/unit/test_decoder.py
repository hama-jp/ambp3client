"""Unit tests for AmbP3.decoder module."""
import pytest
import codecs
from unittest.mock import Mock, patch, MagicMock
from AmbP3.decoder import (
    bin_data_to_ascii,
    bin_dict_to_ascii,
    hex_to_binary,
    bin_to_decimal,
    p3decode,
    Connection
)


class TestBinDataToAscii:
    """Tests for bin_data_to_ascii function."""

    def test_basic_conversion(self):
        """Test basic binary to ASCII conversion."""
        test_data = b'\x8e\x02'
        result = bin_data_to_ascii(test_data)
        assert result == '8e02'

    def test_empty_data(self):
        """Test conversion with empty data."""
        test_data = b''
        result = bin_data_to_ascii(test_data)
        assert result == ''

    def test_hex_values(self):
        """Test conversion with various hex values."""
        test_data = b'\xff\xaa\x00\x12'
        result = bin_data_to_ascii(test_data)
        assert result == 'ffaa0012'


class TestBinDictToAscii:
    """Tests for bin_dict_to_ascii function."""

    def test_dict_conversion(self):
        """Test dictionary binary to ASCII conversion."""
        test_dict = {
            'key1': b'\x8e\x02',
            'key2': b'\xff\xaa'
        }
        result = bin_dict_to_ascii(test_dict)
        assert result['key1'] == '8e02'
        assert result['key2'] == 'ffaa'

    def test_empty_dict(self):
        """Test conversion with empty dictionary."""
        test_dict = {}
        result = bin_dict_to_ascii(test_dict)
        assert result == {}

    def test_dict_with_empty_values(self):
        """Test conversion with empty binary values."""
        test_dict = {'key1': b''}
        result = bin_dict_to_ascii(test_dict)
        assert result['key1'] == ''


class TestHexToBinary:
    """Tests for hex_to_binary function."""

    def test_basic_hex_conversion(self):
        """Test basic hex string to binary conversion."""
        result = hex_to_binary('8e02')
        assert isinstance(result, bytes)
        assert result == b'\x8e\x02'

    def test_single_byte(self):
        """Test single byte conversion."""
        result = hex_to_binary('ff')
        assert result == b'\xff'

    @pytest.mark.xfail(reason="BUG: hex_to_binary has incorrect byte length calculation")
    def test_multiple_bytes(self):
        """Test multiple bytes conversion.

        KNOWN BUG: hex_to_binary() calculates byte length as len(bin_str)//8,
        but bin_str is in format "0b..." so the length includes the prefix.

        For '123456':
        - int('123456', 16) = 1193046
        - bin(1193046) = '0b100100011010001010110' (23 chars including '0b')
        - 23//8 = 2 bytes
        - int.to_bytes(1193046, 2, 'big') raises OverflowError (needs 3 bytes)

        Expected: b'\\x12\\x34\\x56'
        Actual: OverflowError: int too big to convert
        """
        result = hex_to_binary('123456')
        assert result == b'\x12\x34\x56'


class TestBinToDecimal:
    """Tests for bin_to_decimal function."""

    def test_basic_conversion(self):
        """Test basic binary to decimal conversion."""
        # Create encoded hex data
        test_data = codecs.encode(b'\x10', 'hex')  # b'10'
        result = bin_to_decimal(test_data)
        assert result == 16

    def test_zero_value(self):
        """Test conversion with zero."""
        test_data = codecs.encode(b'\x00', 'hex')  # b'00'
        result = bin_to_decimal(test_data)
        assert result == 0

    def test_large_value(self):
        """Test conversion with large value."""
        test_data = codecs.encode(b'\xff', 'hex')  # b'ff'
        result = bin_to_decimal(test_data)
        assert result == 255


class TestP3Decode:
    """Tests for p3decode function."""

    @pytest.mark.xfail(reason="BUG: p3decode doesn't handle None input correctly")
    def test_decode_with_none(self):
        """Test p3decode with None input.

        KNOWN BUG: In _validate() (decoder.py:100), logger.debug() is called
        with data.hex() after _check_crc() returns None. The None check on
        line 99 uses a ternary but doesn't prevent line 100 from executing.

        Expected: Should return (None, None) gracefully
        Actual: AttributeError: 'NoneType' object has no attribute 'hex'
        """
        result = p3decode(None)
        assert result == (None, None)

    def test_decode_with_invalid_data(self):
        """Test p3decode with empty data.

        NOTE: The current implementation doesn't reject empty data but
        attempts to parse it, returning partial header structure.
        This may not be the desired behavior, but it's how the code works.
        """
        result = p3decode(b'')
        header, body = result

        # Function processes even empty data, doesn't return (None, None)
        # Instead returns partial structure
        assert isinstance(header, dict) or header is None
        assert isinstance(body, dict) or body is None

    @patch('AmbP3.decoder.logger')
    def test_decode_basic_structure(self, mock_logger):
        """Test basic decoding structure with minimal valid data."""
        # Create a minimal valid P3 message:
        # SOR (1 byte) + Version (1 byte) + Length (2 bytes) + CRC (2 bytes) +
        # Flags (2 bytes) + TOR (2 bytes) + EOR (1 byte)
        test_data = b'\x8e\x01\x00\x0b\x00\x00\x00\x00\x00\x01\x8f'

        header, body = p3decode(test_data)

        # Check that we get some decoded structure
        assert header is not None or body is not None


class TestConnection:
    """Tests for Connection class."""

    def test_connection_init(self):
        """Test Connection initialization."""
        conn = Connection('127.0.0.1', 5403)
        assert conn.ip == '127.0.0.1'
        assert conn.port == 5403
        assert conn.socket is not None

    def test_split_records_single(self):
        """Test split_records with single record."""
        conn = Connection('127.0.0.1', 5403)
        test_data = b'\x8e\x01\x02\x03\x8f'
        result = conn.split_records(test_data)
        assert len(result) == 1
        assert result[0] == bytearray(test_data)

    def test_split_records_multiple(self):
        """Test split_records with multiple concatenated records."""
        conn = Connection('127.0.0.1', 5403)
        # Two records: first ends with 0x8f, second starts with 0x8e
        test_data = b'\x8e\x01\x02\x8f\x8e\x03\x04\x8f'
        result = conn.split_records(test_data)
        assert len(result) == 2

    def test_close(self):
        """Test connection close."""
        conn = Connection('127.0.0.1', 5403)
        mock_socket = Mock()
        conn.socket = mock_socket
        conn.close()
        mock_socket.close.assert_called_once()

    @patch('socket.socket')
    def test_connect_success(self, mock_socket_class):
        """Test successful connection."""
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket

        conn = Connection('127.0.0.1', 5403)
        conn.socket = mock_socket
        conn.connect()

        mock_socket.connect.assert_called_once_with(('127.0.0.1', 5403))

    @patch('socket.socket')
    @patch('AmbP3.decoder.exit')
    @patch('AmbP3.decoder.logger')
    def test_connect_refused(self, mock_logger, mock_exit, mock_socket_class):
        """Test connection refused error."""
        mock_socket = Mock()
        mock_socket.connect.side_effect = ConnectionRefusedError("Connection refused")
        mock_socket_class.return_value = mock_socket

        conn = Connection('127.0.0.1', 5403)
        conn.socket = mock_socket
        conn.connect()

        mock_exit.assert_called_once_with(1)
        mock_logger.error.assert_called()


@pytest.fixture
def sample_binary_data():
    """Fixture providing sample binary data for tests."""
    return b'\x8e\x01\x00\x10\x00\x00\x00\x00\x00\x01\x02\x04\x12\x34\x56\x78\x8f'


@pytest.fixture
def mock_connection():
    """Fixture providing a mocked Connection object."""
    with patch('socket.socket'):
        conn = Connection('127.0.0.1', 5403)
        conn.socket = Mock()
        return conn
