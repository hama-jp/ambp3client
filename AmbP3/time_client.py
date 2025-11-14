#!/usr/bin/python
from time import sleep
import threading
import socket
from AmbP3.time_server import TIME_PORT
from AmbP3.time_server import TIME_IP
from AmbP3.time_server import DecoderTime
from .logs import Logg

logger = Logg.create_logger("time_client")

# Time client configuration
CONNECTION_RETRY_INTERVAL = 0.5  # Interval between connection attempts in seconds
READ_POLL_INTERVAL = 0.5  # Interval for polling time updates in seconds


class TCPClient:
    """TCP client for connecting to time server."""

    def __init__(self, dt, address, port, interval, retry_connect=30):
        """Initialize TCP client.

        Args:
            dt: DecoderTime instance to update with received time
            address: Server IP address
            port: Server port number
            interval: Update interval in seconds
            retry_connect: Maximum number of connection retry attempts
        """
        self.dt = dt
        self.interval = interval
        self.server_address = (address, port)
        self.retry_connect = retry_connect
        self.connected = False

    def connect(self):
        """Establish connection to time server with retry logic."""
        self.connected = False
        retry = self.retry_connect
        while retry > 1:
            sleep(CONNECTION_RETRY_INTERVAL)
            try:
                logger.info(f"connecting, retry left {retry}")
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect(self.server_address)
                self.connected = True
                retry -= 1
                break
            except (socket.error, socket.timeout) as e:
                logger.error(f"connect failed: {e}")
                self.connected = False
                retry -= 1
        else:
            logger.error("Can not connect, exiting")
            exit(1)

    def read(self):
        """Read data from time server with retry logic.

        Returns:
            Data received from server, or False on failure
        """
        retry = self.retry_connect
        data = False
        while retry > 1:
            try:
                data = self.socket.recv(2048)
                self.connected = True
                retry -= 1
                break
            except (socket.error, socket.timeout) as e:
                logger.error(f"read failed, reconnecting: {e}")
                self.connected = False
                retry -= 1
                self.connect()
        return data


class TimeClient(object):
    """Time client that continuously synchronizes decoder time from time server."""

    def __init__(self, dt, ADDR=TIME_IP, PORT=TIME_PORT, interval=1, retry_connect=30):
        """Initialize time client and start background thread.

        Args:
            dt: DecoderTime instance to update with received time
            ADDR: Server IP address (default: TIME_IP)
            PORT: Server port (default: TIME_PORT)
            interval: Update interval in seconds
            retry_connect: Maximum connection retry attempts
        """
        self.dt = dt
        self.ADDR = ADDR
        self.PORT = PORT
        self.retry_connect = retry_connect
        self.interval = interval
        self.tcpclient = TCPClient(
            self.dt, ADDR, PORT, interval, retry_connect=self.retry_connect
        )
        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True
        thread.start()

    def run(self):
        """Background thread main loop for continuous time synchronization."""
        while True:
            if not self.tcpclient.connected:
                self.tcpclient.connect()
            else:
                try:
                    data = int(self.tcpclient.read().split()[-1])
                    self.dt.decoder_time = data
                except (ValueError, IndexError) as e:
                    self.dt.decoder_time = 0
                    logger.error(f"Failed to read data: {e}")
                    logger.info(f"reconnecting")
                    self.tcpclient.connected = False
            sleep(READ_POLL_INTERVAL)


if __name__ == "__main__":
    dt = DecoderTime(1)
    bg = TimeClient(dt)
    while True:
        logger.debug("Doing stuff")
        sleep(1)
