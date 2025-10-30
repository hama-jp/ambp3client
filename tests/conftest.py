"""Pytest configuration and shared fixtures."""
import pytest
import tempfile
import yaml
from pathlib import Path


@pytest.fixture(scope="session")
def test_data_dir():
    """Fixture providing the test data directory path."""
    return Path(__file__).parent.parent / "test_server"


@pytest.fixture(scope="session")
def sample_amb_data_file(test_data_dir):
    """Fixture providing path to sample AMB data file."""
    amb_short = test_data_dir / "amb-short.out"
    if amb_short.exists():
        return str(amb_short)
    return None


@pytest.fixture(scope="session")
def sample_amb_data_full(test_data_dir):
    """Fixture providing path to full AMB data file."""
    amb_full = test_data_dir / "amb.out"
    if amb_full.exists():
        return str(amb_full)
    return None


@pytest.fixture
def temp_config_file():
    """Fixture creating a temporary config file."""
    config_data = {
        'ip': '127.0.0.1',
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

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_file = f.name

    yield temp_file

    # Cleanup
    import os
    try:
        os.unlink(temp_file)
    except:
        pass


@pytest.fixture
def temp_log_file():
    """Fixture creating a temporary log file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        temp_file = f.name

    yield temp_file

    # Cleanup
    import os
    try:
        os.unlink(temp_file)
    except:
        pass


@pytest.fixture
def sample_p3_messages():
    """Fixture providing sample P3 protocol messages."""
    return {
        'get_time': "8e021000000000000000000000008f",
        'passing_1': "8e021f00f3890000020001022800070216000c01760601008104131804008f",
        'passing_2': "8e021f00895d0000020001022500070216000c01760601008104131804008f",
        'passing_with_transponder': "8e02330053c800000100010451680200030473d75600040888f2fab51e8305000502b20006023400080200008104131804008f",
        'heartbeat': "8e021f006e970000020001022700070216000c01770601008104131804008f",
    }


@pytest.fixture
def sample_decoded_data():
    """Fixture providing sample decoded P3 data."""
    return {
        'header': {
            'SOR': b'\x8e',
            'Version': b'\x02',
            'Length': b'\x00\x1f',
            'CRC': b'\x00\xf3',
            'Flags': b'\x89\x00',
            'TOR': b'\x00\x00'
        },
        'body': {
            'RESULT': {
                'TOR': 'PASSING',
                'RTC_TIME': '12345678',
                'TRANSPONDER': '1234'
            }
        }
    }


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "network: mark test as requiring network access"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically apply markers based on test location."""
    for item in items:
        # Mark all tests in integration directory
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Mark tests that might be slow
        if "slow" in item.name or "multiple" in item.name:
            item.add_marker(pytest.mark.slow)
