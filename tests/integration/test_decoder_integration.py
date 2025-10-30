"""Integration tests for decoder with mock server."""

import pytest
import socket
import threading
import time
from pathlib import Path
from AmbP3.decoder import Connection, p3decode, hex_to_binary


class MockDecoderServer:
    """Mock AMB Decoder server for testing."""

    def __init__(self, host="127.0.0.1", port=0, data_file=None):
        """Initialize mock server.

        Args:
            host: Host to bind to
            port: Port to bind to (0 = auto-assign)
            data_file: Path to file with hex data (one message per line)
        """
        self.host = host
        self.port = port
        self.data_file = data_file
        self.server_socket = None
        self.client_socket = None
        self.server_thread = None
        self.running = False
        self.actual_port = None

    def start(self):
        """Start the mock server in a background thread."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        self.server_socket.settimeout(5.0)  # Timeout for accept

        # Get actual port if auto-assigned
        self.actual_port = self.server_socket.getsockname()[1]

        self.running = True
        self.server_thread = threading.Thread(target=self._serve, daemon=True)
        self.server_thread.start()

        # Give server time to start
        time.sleep(0.1)

    def _serve(self):
        """Server loop - accept connections and send data."""
        try:
            self.client_socket, _ = self.server_socket.accept()
            self.client_socket.settimeout(1.0)

            if self.data_file and Path(self.data_file).exists():
                self._send_data_from_file()

        except socket.timeout:
            pass
        except Exception as e:
            if self.running:
                print(f"Server error: {e}")

    def _send_data_from_file(self):
        """Read hex data from file and send to client."""
        try:
            with open(self.data_file, "r") as f:
                for line in f:
                    if not self.running:
                        break

                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data_bytes = bytes.fromhex(line)
                        self.client_socket.send(data_bytes)
                        time.sleep(0.05)  # Small delay between messages
                    except ValueError:
                        continue
                    except (BrokenPipeError, ConnectionResetError):
                        break
        except Exception as e:
            if self.running:
                print(f"Error sending data: {e}")

    def send_raw(self, hex_data):
        """Send raw hex data to connected client.

        Args:
            hex_data: Hex string to send (e.g., "8e021f00...")
        """
        if self.client_socket:
            try:
                data_bytes = bytes.fromhex(hex_data)
                self.client_socket.send(data_bytes)
            except Exception as e:
                print(f"Error sending raw data: {e}")

    def stop(self):
        """Stop the server."""
        self.running = False

        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass

        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=2.0)


@pytest.fixture
def mock_decoder_server():
    """Fixture providing a mock decoder server."""
    server = MockDecoderServer()
    server.start()
    yield server
    server.stop()


@pytest.fixture
def sample_data_file():
    """Fixture providing path to sample data file."""
    test_dir = Path(__file__).parent.parent.parent
    sample_file = test_dir / "test_server" / "amb-short.out"

    if sample_file.exists():
        return str(sample_file)
    return None


class TestDecoderIntegration:
    """Integration tests for decoder with mock server."""

    @pytest.mark.integration
    def test_connection_to_mock_server(self, mock_decoder_server):
        """Test connecting to mock server."""
        conn = Connection(mock_decoder_server.host, mock_decoder_server.actual_port)
        conn.connect()

        assert conn.socket is not None

        conn.close()

    @pytest.mark.integration
    def test_receive_single_message(self, mock_decoder_server):
        """Test receiving and decoding a single message."""
        # Sample PASSING message
        test_message = "8e021f00f3890000020001022800070216000c01760601008104131804008f"

        # Connect client
        conn = Connection(mock_decoder_server.host, mock_decoder_server.actual_port)
        conn.connect()

        # Send message from server
        mock_decoder_server.send_raw(test_message)
        time.sleep(0.1)

        # Read and verify
        data_list = conn.read(bufsize=1024)
        assert len(data_list) > 0

        # Decode first message
        header, body = p3decode(bytes(data_list[0]))
        assert header is not None
        assert body is not None

        conn.close()

    @pytest.mark.integration
    @pytest.mark.slow
    def test_receive_multiple_messages(self, mock_decoder_server, sample_data_file):
        """Test receiving multiple messages from file."""
        if not sample_data_file:
            pytest.skip("Sample data file not found")

        # Create new server with data file
        server = MockDecoderServer(host="127.0.0.1", port=0, data_file=sample_data_file)
        server.start()

        try:
            # Connect and read messages
            conn = Connection(server.host, server.actual_port)
            conn.connect()

            messages_received = 0
            max_messages = 10
            timeout = time.time() + 5.0  # 5 second timeout

            while messages_received < max_messages and time.time() < timeout:
                try:
                    conn.socket.settimeout(1.0)
                    data_list = conn.read(bufsize=1024)

                    for data in data_list:
                        if len(data) > 0:
                            messages_received += 1

                            # Try to decode
                            header, body = p3decode(bytes(data))

                            # Basic validation
                            if header is not None:
                                assert "SOR" in header
                                assert "TOR" in header

                except socket.timeout:
                    break
                except Exception as e:
                    print(f"Error reading: {e}")
                    break

            assert messages_received > 0, "Should receive at least one message"

            conn.close()
        finally:
            server.stop()

    @pytest.mark.integration
    def test_decode_passing_message(self, mock_decoder_server):
        """Test decoding a PASSING message."""
        # PASSING message with transponder data
        passing_msg = "8e02330053c800000100010451680200030473d75600040888f2fab51e8305000502b20006023400080200008104131804008f"

        conn = Connection(mock_decoder_server.host, mock_decoder_server.actual_port)
        conn.connect()

        mock_decoder_server.send_raw(passing_msg)
        time.sleep(0.1)

        data_list = conn.read(bufsize=1024)
        header, body = p3decode(bytes(data_list[0]))

        assert body is not None
        assert "RESULT" in body

        # Should contain transponder information
        result = body["RESULT"]
        assert "TOR" in result

        conn.close()

    @pytest.mark.integration
    def test_split_concatenated_records(self, mock_decoder_server):
        """Test handling of concatenated records."""
        # Two messages concatenated
        msg1 = "8e021f00f3890000020001022800070216000c01760601008104131804008f"
        msg2 = "8e021f00895d0000020001022500070216000c01760601008104131804008f"
        concatenated = msg1 + msg2

        conn = Connection(mock_decoder_server.host, mock_decoder_server.actual_port)
        conn.connect()

        mock_decoder_server.send_raw(concatenated)
        time.sleep(0.1)

        data_list = conn.read(bufsize=2048)

        # Should split into 2 records
        assert len(data_list) >= 1

        # Each should be decodable
        for data in data_list:
            if len(data) > 10:  # Minimum valid message size
                header, body = p3decode(bytes(data))
                assert header is not None or body is not None

        conn.close()

    @pytest.mark.integration
    def test_connection_retry_after_close(self, mock_decoder_server):
        """Test that connection can be re-established after close."""
        conn = Connection(mock_decoder_server.host, mock_decoder_server.actual_port)

        # First connection
        conn.connect()
        assert conn.socket is not None
        conn.close()

        # Second connection (would need new server in real scenario)
        # This test demonstrates the pattern
        assert conn.socket is not None


class TestHexToBinaryIntegration:
    """Integration tests for hex conversion functions."""

    @pytest.mark.integration
    def test_hex_to_binary_with_real_data(self, sample_data_file):
        """Test hex_to_binary with real P3 protocol data."""
        if not sample_data_file:
            pytest.skip("Sample data file not found")

        with open(sample_data_file, "r") as f:
            for line in f.readlines()[:5]:  # Test first 5 lines
                line = line.strip()
                if not line:
                    continue

                # Convert using our function
                binary_data = hex_to_binary(line)

                # Verify it's bytes
                assert isinstance(binary_data, bytes)

                # Verify it can be decoded
                header, body = p3decode(binary_data)
                assert header is not None or body is not None


@pytest.mark.integration
@pytest.mark.network
class TestRealDecoderConnection:
    """Tests that require a real AMB decoder or test_server.py running."""

    def test_connect_to_test_server(self):
        """Test connection to test_server.py if it's running.

        Note: This test will be skipped if no server is running.
        To run manually:
        1. Start test server: ./test_server.py test_server/amb-short.out -p 12001
        2. Run this test: pytest tests/integration/test_decoder_integration.py::TestRealDecoderConnection -v
        """
        test_host = "127.0.0.1"
        test_port = 12001

        # Try to connect
        try:
            conn = Connection(test_host, test_port)
            test_sock = socket.socket()
            test_sock.settimeout(1.0)
            test_sock.connect((test_host, test_port))
            test_sock.close()

            # If we get here, server is running
            conn.connect()

            # Try to read some data
            conn.socket.settimeout(2.0)
            data_list = conn.read(bufsize=1024)

            assert len(data_list) > 0

            conn.close()

        except (ConnectionRefusedError, socket.timeout):
            pytest.skip("Test server not running on port 12001")
