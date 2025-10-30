"""Test fixtures and sample data for testing."""
import pytest


# Sample P3 protocol data
SAMPLE_P3_MESSAGES = {
    'get_time': b'\x8e\x01\x00\x10\x00\x00\x00\x00\x00\x01\x02\x04\x12\x34\x56\x78\x8f',
    'passing': b'\x8e\x01\x00\x15\x00\x00\x00\x00\x00\x02\x03\x06\x11\x22\x33\x44\x55\x66\x8f',
    'heartbeat': b'\x8e\x01\x00\x0b\x00\x00\x00\x00\x00\x03\x8f',
}

# Sample escaped data
SAMPLE_ESCAPED_DATA = {
    'simple': b'\x8e\x01\x02\x03\x8f',
    'with_escape': b'\x8e\x01\x8d\xad\x03\x8f',  # 0x8d followed by escaped byte
}

# Sample database records
SAMPLE_PASSES = [
    {
        'pass_id': 1,
        'transponder_id': 12345,
        'rtc_time': 1234567890,
        'timestamp': '2025-10-30 10:00:00'
    },
    {
        'pass_id': 2,
        'transponder_id': 12346,
        'rtc_time': 1234567900,
        'timestamp': '2025-10-30 10:00:10'
    },
    {
        'pass_id': 3,
        'transponder_id': 12345,
        'rtc_time': 1234567920,
        'timestamp': '2025-10-30 10:00:30'
    },
]

SAMPLE_HEATS = [
    {
        'heat_id': 1,
        'heat_started': '2025-10-30 10:00:00',
        'heat_finished': 0,
        'first_pass_id': 1,
        'last_pass_id': None
    },
    {
        'heat_id': 2,
        'heat_started': '2025-10-30 11:00:00',
        'heat_finished': 1,
        'first_pass_id': 10,
        'last_pass_id': 25
    },
]

SAMPLE_LAPS = [
    {
        'lap_id': 1,
        'heat_id': 1,
        'pass_id': 1,
        'transponder_id': 12345,
        'lap_time': 45.123,
        'rtc_time': 1234567890
    },
    {
        'lap_id': 2,
        'heat_id': 1,
        'pass_id': 3,
        'transponder_id': 12345,
        'lap_time': 46.789,
        'rtc_time': 1234567920
    },
]

# Sample configuration
SAMPLE_CONFIG = {
    'ip': '192.168.1.100',
    'port': 5403,
    'mysql_host': 'localhost',
    'mysql_port': 3306,
    'mysql_user': 'testuser',
    'mysql_db': 'testdb',
    'mysql_password': 'testpass',
    'file': '/tmp/test.log',
    'debug_file': '/tmp/debug.log',
    'mysql_backend': True
}

# Sample YAML config content
SAMPLE_YAML_CONFIG = """
ip: 192.168.1.100
port: 5403
mysql_host: localhost
mysql_port: 3306
mysql_user: testuser
mysql_db: testdb
mysql_password: testpass
file: /tmp/test.log
debug_file: /tmp/debug.log
mysql_backend: true
"""

# Sample connection parameters
SAMPLE_CONNECTION_PARAMS = {
    'valid': {
        'ip': '127.0.0.1',
        'port': 5403
    },
    'invalid_ip': {
        'ip': '999.999.999.999',
        'port': 5403
    },
    'invalid_port': {
        'ip': '127.0.0.1',
        'port': 99999
    }
}

# Sample decoder responses
SAMPLE_DECODER_RESPONSES = {
    'get_time_response': {
        'header': {
            'SOR': b'\x8e',
            'Version': b'\x01',
            'Length': b'\x00\x10',
            'CRC': b'\x00\x00',
            'Flags': b'\x00\x00',
            'TOR': b'\x00\x01'
        },
        'body': {
            'RESULT': {
                'TOR': 'GET_TIME',
                'RTC_TIME': b'12345678'
            }
        }
    },
    'passing_response': {
        'header': {
            'SOR': b'\x8e',
            'Version': b'\x01',
            'Length': b'\x00\x15',
            'CRC': b'\x00\x00',
            'Flags': b'\x00\x00',
            'TOR': b'\x00\x02'
        },
        'body': {
            'RESULT': {
                'TOR': 'PASSING',
                'TRANSPONDER': b'3039',
                'RTC_TIME': b'12345678'
            }
        }
    }
}


@pytest.fixture
def sample_p3_message():
    """Fixture providing a sample P3 protocol message."""
    return SAMPLE_P3_MESSAGES['get_time']


@pytest.fixture
def sample_config():
    """Fixture providing a sample configuration dictionary."""
    return SAMPLE_CONFIG.copy()


@pytest.fixture
def sample_passes():
    """Fixture providing sample passing records."""
    return [pass_record.copy() for pass_record in SAMPLE_PASSES]


@pytest.fixture
def sample_heats():
    """Fixture providing sample heat records."""
    return [heat.copy() for heat in SAMPLE_HEATS]


@pytest.fixture
def sample_laps():
    """Fixture providing sample lap records."""
    return [lap.copy() for lap in SAMPLE_LAPS]


@pytest.fixture
def sample_connection_params():
    """Fixture providing sample connection parameters."""
    return SAMPLE_CONNECTION_PARAMS.copy()
