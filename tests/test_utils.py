"""Utility functions for testing."""

import socket
import time
from contextlib import contextmanager


def is_port_available(host, port, timeout=1.0):
    """Check if a port is available (not in use).

    Args:
        host: Host to check
        port: Port to check
        timeout: Connection timeout in seconds

    Returns:
        True if port is available, False if in use
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex((host, port))
        sock.close()
        return result != 0
    except socket.error:
        return True


def wait_for_port(host, port, timeout=5.0, interval=0.1):
    """Wait for a port to become available (server to start).

    Args:
        host: Host to check
        port: Port to check
        timeout: Maximum time to wait in seconds
        interval: Check interval in seconds

    Returns:
        True if port became available, False if timeout

    Raises:
        TimeoutError: If port doesn't become available within timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not is_port_available(host, port):
            return True
        time.sleep(interval)
    raise TimeoutError(f"Port {port} did not become available within {timeout}s")


def find_free_port(host="127.0.0.1", start_port=10000, max_tries=100):
    """Find a free port on the host.

    Args:
        host: Host to check
        start_port: Starting port number
        max_tries: Maximum number of ports to try

    Returns:
        Free port number

    Raises:
        RuntimeError: If no free port found
    """
    for port in range(start_port, start_port + max_tries):
        if is_port_available(host, port):
            return port
    raise RuntimeError(
        f"Could not find free port in range {start_port}-{start_port + max_tries}"
    )


@contextmanager
def temporary_socket_server(host="127.0.0.1", port=0):
    """Context manager for a temporary socket server.

    Args:
        host: Host to bind to
        port: Port to bind to (0 = auto-assign)

    Yields:
        tuple: (socket, actual_port)
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    actual_port = sock.getsockname()[1]
    sock.listen(1)

    try:
        yield sock, actual_port
    finally:
        try:
            sock.close()
        except:
            pass


def read_hex_data_file(file_path, max_lines=None):
    """Read hex data from a file.

    Args:
        file_path: Path to the file
        max_lines: Maximum number of lines to read (None = all)

    Returns:
        List of hex strings
    """
    hex_data = []
    try:
        with open(file_path, "r") as f:
            for i, line in enumerate(f):
                if max_lines and i >= max_lines:
                    break

                line = line.strip()
                if line:
                    hex_data.append(line)
    except FileNotFoundError:
        return []

    return hex_data


def hex_to_bytes(hex_string):
    """Convert hex string to bytes.

    Args:
        hex_string: Hex string (e.g., "8e021f00...")

    Returns:
        bytes object

    Raises:
        ValueError: If hex string is invalid
    """
    try:
        return bytes.fromhex(hex_string)
    except ValueError as e:
        raise ValueError(f"Invalid hex string: {hex_string}") from e


def bytes_to_hex(data):
    """Convert bytes to hex string.

    Args:
        data: bytes object

    Returns:
        Hex string (lowercase)
    """
    return data.hex()


def validate_p3_message(data):
    """Validate basic P3 message structure.

    Args:
        data: bytes object or hex string

    Returns:
        True if valid basic structure, False otherwise
    """
    if isinstance(data, str):
        try:
            data = bytes.fromhex(data)
        except ValueError:
            return False

    if len(data) < 11:  # Minimum P3 message size
        return False

    # Check SOR (Start of Record) - should be 0x8e
    if data[0] != 0x8E:
        return False

    # Check EOR (End of Record) - should be 0x8f
    if data[-1] != 0x8F:
        return False

    return True


class TestTimer:
    """Simple timer for measuring test execution time."""

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        """Start the timer."""
        self.start_time = time.time()

    def stop(self):
        """Stop the timer."""
        self.end_time = time.time()

    def elapsed(self):
        """Get elapsed time in seconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()


def assert_similar_dicts(dict1, dict2, ignore_keys=None):
    """Assert two dictionaries are similar, optionally ignoring some keys.

    Args:
        dict1: First dictionary
        dict2: Second dictionary
        ignore_keys: Set of keys to ignore in comparison

    Raises:
        AssertionError: If dictionaries differ in non-ignored keys
    """
    ignore_keys = ignore_keys or set()

    keys1 = set(dict1.keys()) - ignore_keys
    keys2 = set(dict2.keys()) - ignore_keys

    assert keys1 == keys2, f"Key mismatch: {keys1} vs {keys2}"

    for key in keys1:
        assert (
            dict1[key] == dict2[key]
        ), f"Value mismatch for key '{key}': {dict1[key]} vs {dict2[key]}"
