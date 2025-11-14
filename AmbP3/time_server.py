#!/usr/bin/python
from time import sleep
import threading
import time
import socketserver
from .logs import Logg

logger = Logg.create_logger("time_server")

# Time server configuration
TIME_PORT = 9999
TIME_IP = "127.0.0.1"
DEFAULT_INTERVAL = 0.5  # Default interval for TCP server updates in seconds


class RefreshTime:
    """Background task to periodically request decoder time."""

    def __init__(self, connection, refresh_interval=30):
        """Initialize and start refresh time thread.

        Args:
            connection: Connection instance to the decoder
            refresh_interval: Interval in seconds between time requests
        """
        self.refresh_interval = refresh_interval
        self.connection = connection
        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True
        thread.start()

    def run(self):
        """Send periodic time request to decoder."""
        logger.info("Requesting Decoder Time")
        get_time_msg = bytes.fromhex("8E0000005BEB000024000100040005008F")
        self.connection.write(get_time_msg)
        sleep(self.refresh_interval)


class TCPServer(socketserver.BaseRequestHandler):
    """TCP server request handler for broadcasting decoder time."""

    def __init__(self, dt, interval):
        """Initialize server handler.

        Args:
            dt: DecoderTime instance containing current time
            interval: Update interval in seconds
        """
        self.dt = dt
        self.interval = interval

    def __call__(self, request, client_address, server):
        """Make handler callable for socketserver.

        Args:
            request: Client request
            client_address: Client address tuple
            server: Server instance
        """
        h = TCPServer(self.dt, self.interval)
        socketserver.BaseRequestHandler.__init__(h, request, client_address, server)

    def handle(self):
        """Handle client connection and broadcast time updates.

        Accepts RTC timestamp (e.g. 1592148824541000) and sends incremented
        timestamp every interval seconds based on monotonic clock.
        """
        # while True:
        #     ts_send = self.dt.decoder_time + (round(time.monotonic() * 1000000) - self.dt.monotonic_ts)
        #     msg = f"{ts_send}\n"
        #     self.data = msg.encode()
        #     self.request.sendall(self.data)
        #     sleep(self.interval)
        while True:
            try:
                ts_send = self.dt.decoder_time + (
                    round(time.monotonic() * 1000000) - self.dt.monotonic_ts
                )
                msg = f"{ts_send}\n"
                self.data = msg.encode()
                self.request.sendall(self.data)
                sleep(self.interval)
            except (ConnectionResetError, BrokenPipeError) as error:
                logger.error("socket connection error: {}".format(error))
                break
            except (KeyboardInterrupt, TypeError) as error:
                logger.info("closing socket, connection: {}".format(error))
                break


class DecoderTime:
    """Manages decoder time synchronized with monotonic clock."""

    def __init__(self, decoder_time):
        """Initialize with decoder RTC time.

        Args:
            decoder_time: Initial decoder RTC timestamp in microseconds
        """
        self.decoder_time = decoder_time
        self.monotonic_ts = round(time.monotonic() * 1000000)

    def set_decoder_time(self, decoder_time):
        """Update decoder time and reset monotonic reference.

        Args:
            decoder_time: New decoder RTC timestamp in microseconds
        """
        self.decoder_time = decoder_time
        self.monotonic_ts = round(time.monotonic() * 1000000)


class TimeServer(object):
    """TCP server that broadcasts decoder time to connected clients."""

    def __init__(self, dt, ADDR="127.0.0.1", PORT=9999, interval=1):
        """Initialize and start time server in background thread.

        Args:
            dt: DecoderTime instance to broadcast
            ADDR: Server bind address (default: "127.0.0.1")
            PORT: Server port (default: 9999)
            interval: Update interval in seconds
        """
        self.dt = dt
        self.ADDR = ADDR
        self.PORT = PORT
        self.interval = interval
        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True
        thread.start()

    def run(self):
        """Start the TCP server main loop."""
        TCPServer.dt = self.dt
        TCPServer.interval = self.interval
        socketserver.TCPServer.allow_reuse_address = True
        self.server = socketserver.TCPServer(
            (self.ADDR, self.PORT), TCPServer(self.dt, DEFAULT_INTERVAL)
        )
        self.server.serve_forever()

    def shutdown(self):
        """Shutdown the server gracefully."""
        self.server.shutdown()

    def stop(self):
        """Close the server socket."""
        self.server.server_close()


if __name__ == "__main__":
    bg = TimeServer(3)
    while True:
        logger.debug("Doing stuff")
        sleep(1)
