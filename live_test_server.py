#!/usr/bin/env python3
"""
Live AMB P3 Decoder Simulator

Simulates a realistic AMB decoder with dynamic timestamp generation,
multi-transponder race scenarios, and realistic signal characteristics.

This is a Phase 1 implementation with:
- Dynamic timestamp generation (RTC_TIME/UTC_TIME)
- Multi-transponder simulation with realistic lap time variance
- Signal quality simulation (STRENGTH/HITS based on distance/speed)
- Periodic STATUS messages (1s interval matching real decoder behavior)
- Command-line argument support
"""

import socket
import threading
import time
import random
import logging
from argparse import ArgumentParser
from dataclasses import dataclass
from typing import List, Optional
from AmbP3 import crc16

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("live_test_server")

# Protocol constants
SOR = 0x8E  # Start of Record
EOR = 0x8F  # End of Record
ESC = 0x8D  # Escape character
VERSION = 0x02  # Protocol version

# Default decoder configuration
DEFAULT_DECODER_ID = 0x04131804
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 12001
DEFAULT_DURATION = 480  # 8 minutes
DEFAULT_STATUS_INTERVAL = 1.0  # 1 second


@dataclass
class TransponderConfig:
    """Configuration for a single transponder."""
    transponder_id: int
    avg_lap_time: float  # Average lap time in seconds
    variance: float  # Lap time variance in seconds (std deviation)
    start_delay: float = 0.0  # Delay before first lap in seconds


class P3MessageBuilder:
    """Build AMB P3 protocol messages with proper CRC and escape sequences."""

    @staticmethod
    def build_passing(passing_number: int, transponder_id: int, rtc_time: int,
                     strength: int, hits: int, flags: int, utc_time: int,
                     decoder_id: int) -> bytes:
        """Build PASSING (0x0001) message.

        Args:
            passing_number: Sequential passing number
            transponder_id: Transponder ID (4 bytes)
            rtc_time: RTC timestamp in microseconds (8 bytes)
            strength: Signal strength 0-1023 (2 bytes)
            hits: Number of hits 1-6 (2 bytes)
            flags: Flags field (2 bytes)
            utc_time: UTC timestamp in seconds (8 bytes)
            decoder_id: Decoder ID (4 bytes)

        Returns:
            Complete P3 PASSING message as bytes
        """
        body = bytearray()

        # TOR (Type of Record) - 0x0001 for PASSING
        body.extend((0x01, 0x00))

        # PASSING_NUMBER (Field ID 0x01, Length 4)
        body.extend([0x01, 0x04])
        body.extend(passing_number.to_bytes(4, 'little'))

        # TRANSPONDER (Field ID 0x03, Length 4)
        body.extend([0x03, 0x04])
        body.extend(transponder_id.to_bytes(4, 'little'))

        # RTC_TIME (Field ID 0x04, Length 8)
        body.extend([0x04, 0x08])
        body.extend(rtc_time.to_bytes(8, 'little'))

        # STRENGTH (Field ID 0x05, Length 2)
        body.extend([0x05, 0x02])
        body.extend(strength.to_bytes(2, 'little'))

        # HITS (Field ID 0x06, Length 2)
        body.extend([0x06, 0x02])
        body.extend(hits.to_bytes(2, 'little'))

        # FLAGS (Field ID 0x08, Length 2)
        body.extend([0x08, 0x02])
        body.extend(flags.to_bytes(2, 'little'))

        # UTC_TIME (Field ID 0x10, Length 8) - optional but included
        body.extend([0x10, 0x08])
        body.extend(utc_time.to_bytes(8, 'little'))

        # DECODER_ID (Field ID 0x81, Length 4) - General field
        body.extend([0x81, 0x04])
        body.extend(decoder_id.to_bytes(4, 'little'))

        return P3MessageBuilder._build_message(body)

    @staticmethod
    def build_status(noise: int, gps: int, temperature: int, voltage: int,
                    loop_triggers: int, decoder_id: int) -> bytes:
        """Build STATUS (0x0002) message.

        Args:
            noise: Noise level 0-100 (2 bytes)
            gps: GPS status 0-1 (1 byte)
            temperature: Temperature in °C (2 bytes)
            voltage: Input voltage (1 byte, e.g., 120 = 12.0V)
            loop_triggers: Loop trigger count (2 bytes)
            decoder_id: Decoder ID (4 bytes)

        Returns:
            Complete P3 STATUS message as bytes
        """
        body = bytearray()

        # TOR - 0x0002 for STATUS
        body.extend((0x02, 0x00))

        # NOISE (Field ID 0x01, Length 2)
        body.extend([0x01, 0x02])
        body.extend(noise.to_bytes(2, 'little'))

        # GPS (Field ID 0x06, Length 1)
        body.extend([0x06, 0x01])
        body.extend([gps])

        # TEMPERATURE (Field ID 0x07, Length 2)
        body.extend([0x07, 0x02])
        body.extend(temperature.to_bytes(2, 'little'))

        # INPUT_VOLTAGE (Field ID 0x0c, Length 1)
        body.extend([0x0c, 0x01])
        body.extend([voltage])

        # LOOP_TRIGGERS (Field ID 0x0b, Length 2)
        body.extend([0x0b, 0x02])
        body.extend(loop_triggers.to_bytes(2, 'little'))

        # DECODER_ID (Field ID 0x81, Length 4)
        body.extend([0x81, 0x04])
        body.extend(decoder_id.to_bytes(4, 'little'))

        return P3MessageBuilder._build_message(body)

    @staticmethod
    def build_get_time_response(rtc_time: int, decoder_id: int) -> bytes:
        """Build GET_TIME (0x0024) response message.

        Note: Field lengths for GET_TIME are not fully documented.
        This implementation uses minimal fields based on records.py comments.

        Args:
            rtc_time: RTC timestamp in microseconds
            decoder_id: Decoder ID (4 bytes)

        Returns:
            Complete P3 GET_TIME message as bytes
        """
        body = bytearray()

        # TOR - 0x0024 for GET_TIME
        body.extend((0x24, 0x00))

        # RTC_TIME (Field ID 0x01, Length 4 per records.py comment)
        # Note: PASSING uses 8 bytes, but GET_TIME might use 4
        body.extend([0x01, 0x04])
        body.extend((rtc_time & 0xFFFFFFFF).to_bytes(4, 'little'))

        # DECODER_ID (Field ID 0x81, Length 4)
        body.extend([0x81, 0x04])
        body.extend(decoder_id.to_bytes(4, 'little'))

        return P3MessageBuilder._build_message(body)

    @staticmethod
    def _build_message(body: bytearray) -> bytes:
        """Build complete P3 message with header, CRC, and escape sequences.

        Args:
            body: Message body including TOR and fields

        Returns:
            Complete escaped P3 message
        """
        message = bytearray()

        # SOR
        message.append(SOR)

        # Version
        message.append(VERSION)

        # Flags (always 0x0000 for now)
        flags = 0x0000

        # Length (SOR to EOR inclusive)
        # Structure: SOR(1) + VER(1) + LEN(2) + CRC(2) + FLAGS(2) + BODY + EOR(1)
        length = 1 + 1 + 2 + 2 + 2 + len(body) + 1
        message.extend(length.to_bytes(2, 'little'))

        # CRC placeholder (will be filled later)
        crc_pos = len(message)
        message.extend([0x00, 0x00])

        # Flags
        message.extend(flags.to_bytes(2, 'little'))

        # Body
        message.extend(body)

        # EOR
        message.append(EOR)

        # Calculate CRC with CRC field zeroed
        message_for_crc = bytearray(message)
        message_for_crc[crc_pos:crc_pos+2] = [0x00, 0x00]

        crc_table = crc16.table()
        calculated_crc = crc16.calc(message_for_crc.hex(), crc_table)

        # Insert CRC in big-endian format
        message[crc_pos:crc_pos+2] = calculated_crc.to_bytes(2, 'big')

        # Apply escape sequences
        return P3MessageBuilder._escape(bytes(message))

    @staticmethod
    def _escape(data: bytes) -> bytes:
        """Apply P3 escape sequences.

        Bytes 0x8D, 0x8E, 0x8F in the message body (not SOR/EOR) are escaped
        by prefixing with 0x8D and adding 0x20 to the byte value.

        Args:
            data: Unescaped message

        Returns:
            Escaped message
        """
        escaped = bytearray()
        escaped.append(data[0])  # SOR - never escaped

        # Escape middle bytes
        for byte in data[1:-1]:
            if byte in [ESC, SOR, EOR]:
                escaped.append(ESC)
                escaped.append(byte + 0x20)
            else:
                escaped.append(byte)

        escaped.append(data[-1])  # EOR - never escaped
        return bytes(escaped)


class TransponderSimulator:
    """Simulate a single transponder's movement through a race."""

    def __init__(self, config: TransponderConfig, track_length: float = 100.0):
        """Initialize transponder simulator.

        Args:
            config: Transponder configuration
            track_length: Track length in meters (for speed calculation)
        """
        self.config = config
        self.track_length = track_length
        self.lap_count = 0
        self.race_start_time: Optional[float] = None
        self.next_lap_time: Optional[float] = None

    def start_race(self, start_time: float):
        """Start the race for this transponder.

        Args:
            start_time: Race start timestamp
        """
        self.race_start_time = start_time
        self.lap_count = 0
        # First lap happens after start_delay + first lap time
        self.next_lap_time = start_time + self.config.start_delay + self._generate_lap_time()
        logger.debug(f"Transponder {self.config.transponder_id} starting, "
                    f"first lap at {self.next_lap_time:.2f}s")

    def update(self, current_time: float) -> Optional[dict]:
        """Update transponder state and return passing event if lap completed.

        Args:
            current_time: Current timestamp

        Returns:
            Passing event dict or None
        """
        if self.next_lap_time is None or current_time < self.next_lap_time:
            return None

        # Lap completed!
        self.lap_count += 1
        passing_time = self.next_lap_time

        # Calculate realistic signal parameters
        lap_time = self._generate_lap_time()
        speed = self.track_length / lap_time  # m/s
        strength = self._calculate_strength()
        hits = self._calculate_hits(speed)

        event = {
            "transponder_id": self.config.transponder_id,
            "time": passing_time,
            "lap": self.lap_count,
            "strength": strength,
            "hits": hits,
            "flags": 0x0000,
        }

        # Schedule next lap
        self.next_lap_time = passing_time + lap_time

        logger.debug(f"Transponder {self.config.transponder_id} lap {self.lap_count} "
                    f"at {passing_time:.2f}s, speed={speed:.1f}m/s, "
                    f"strength={strength}, hits={hits}")

        return event

    def _generate_lap_time(self) -> float:
        """Generate a lap time with realistic variance.

        Returns:
            Lap time in seconds
        """
        # Use Gaussian distribution for natural variance
        lap_time = random.gauss(self.config.avg_lap_time, self.config.variance)
        # Ensure lap time is always positive and reasonable
        return max(self.config.avg_lap_time * 0.5, lap_time)

    def _calculate_strength(self) -> int:
        """Calculate signal strength.

        Simulates distance from antenna with some randomness.

        Returns:
            Signal strength 0-1023
        """
        # Simulate distance variation (0.0m to 2.0m from antenna)
        distance = random.uniform(0.0, 2.0)
        max_strength = 1023
        min_strength = 200
        max_distance = 2.0

        if distance >= max_distance:
            return min_strength

        # Linear decay with distance (could use inverse square for more realism)
        ratio = 1.0 - (distance / max_distance)
        strength = int(min_strength + (max_strength - min_strength) * ratio)

        # Add noise (±5%)
        noise = random.randint(-50, 50)
        return max(min_strength, min(max_strength, strength + noise))

    def _calculate_hits(self, speed: float) -> int:
        """Calculate number of hits based on passing speed.

        Slower speeds = more hits as transponder is in antenna field longer.

        Args:
            speed: Speed in m/s

        Returns:
            Number of hits 1-6
        """
        # Speed ranges for hits (slower = more hits)
        if speed <= 2.0:
            return 6
        elif speed <= 3.0:
            return 5
        elif speed <= 4.0:
            return 4
        elif speed <= 5.0:
            return 3
        elif speed <= 6.0:
            return 2
        else:
            return 1


class ScenarioManager:
    """Manage multiple transponders in a race scenario."""

    def __init__(self, transponder_configs: List[TransponderConfig],
                 track_length: float = 100.0):
        """Initialize scenario manager.

        Args:
            transponder_configs: List of transponder configurations
            track_length: Track length in meters
        """
        self.transponders = [
            TransponderSimulator(config, track_length)
            for config in transponder_configs
        ]
        self.start_time: Optional[float] = None
        self.track_length = track_length

    def start(self):
        """Start the race scenario."""
        self.start_time = time.time()
        for transponder in self.transponders:
            transponder.start_race(self.start_time)
        logger.info(f"Race started with {len(self.transponders)} transponders")

    def get_pending_events(self, current_time: float) -> List[dict]:
        """Get all pending passing events up to current time.

        Args:
            current_time: Current timestamp

        Returns:
            List of passing events sorted by time
        """
        events = []
        for transponder in self.transponders:
            while True:
                event = transponder.update(current_time)
                if event is None:
                    break
                events.append(event)

        # Sort by time
        events.sort(key=lambda e: e["time"])
        return events


class LiveDecoderServer:
    """Live AMB P3 decoder simulator server."""

    def __init__(self, host: str, port: int, scenario_manager: ScenarioManager,
                 decoder_id: int = DEFAULT_DECODER_ID,
                 status_interval: float = DEFAULT_STATUS_INTERVAL):
        """Initialize live decoder server.

        Args:
            host: Host to bind to
            port: Port to bind to
            scenario_manager: Race scenario manager
            decoder_id: Decoder ID
            status_interval: STATUS message interval in seconds
        """
        self.host = host
        self.port = port
        self.scenario_manager = scenario_manager
        self.decoder_id = decoder_id
        self.status_interval = status_interval
        self.running = False
        self.conn: Optional[socket.socket] = None
        self.passing_number = 0
        self.message_builder = P3MessageBuilder()

    def start(self):
        """Start the server and begin simulation."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(1)

        logger.info(f"Live decoder server listening on {self.host}:{self.port}")
        logger.info("Waiting for client connection...")

        self.conn, addr = server_socket.accept()
        logger.info(f"Client connected: {addr}")

        self.running = True

        # Start STATUS message thread
        status_thread = threading.Thread(target=self._status_loop, daemon=True)
        status_thread.start()

        # Start race
        self.scenario_manager.start()

        # Send initial GET_TIME response (simulating decoder behavior)
        self._send_get_time()

        # Main PASSING message loop
        try:
            self._passing_loop()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error in passing loop: {e}")
        finally:
            self.running = False
            if self.conn:
                self.conn.close()
            server_socket.close()

    def _send_get_time(self):
        """Send GET_TIME message to client."""
        current_time = time.time()
        rtc_time = int(current_time * 1_000_000)  # microseconds

        msg = self.message_builder.build_get_time_response(
            rtc_time=rtc_time,
            decoder_id=self.decoder_id
        )

        try:
            self.conn.send(msg)
            logger.info(f"Sent GET_TIME: RTC={rtc_time}")
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            logger.error(f"Failed to send GET_TIME: {e}")

    def _passing_loop(self):
        """Main loop for sending PASSING messages."""
        last_check_time = time.time()

        while self.running:
            current_time = time.time()

            # Get all pending events
            events = self.scenario_manager.get_pending_events(current_time)

            for event in events:
                self.passing_number += 1

                # Convert event time to microseconds for RTC_TIME
                rtc_time = int(event["time"] * 1_000_000)
                utc_time = int(event["time"])

                msg = self.message_builder.build_passing(
                    passing_number=self.passing_number,
                    transponder_id=event["transponder_id"],
                    rtc_time=rtc_time,
                    strength=event["strength"],
                    hits=event["hits"],
                    flags=event["flags"],
                    utc_time=utc_time,
                    decoder_id=self.decoder_id
                )

                try:
                    self.conn.send(msg)
                    logger.info(
                        f"PASSING #{self.passing_number}: "
                        f"Transponder {event['transponder_id']}, "
                        f"Lap {event['lap']}, "
                        f"Strength {event['strength']}, "
                        f"Hits {event['hits']}"
                    )
                except (BrokenPipeError, ConnectionResetError, OSError) as e:
                    logger.error(f"Connection lost: {e}")
                    self.running = False
                    break

            # Sleep briefly to avoid busy-waiting
            time.sleep(0.01)  # 10ms

    def _status_loop(self):
        """Background loop for sending STATUS messages."""
        while self.running:
            msg = self.message_builder.build_status(
                noise=random.randint(20, 50),
                gps=1,  # Always GPS locked in simulation
                temperature=random.randint(25, 45),
                voltage=random.randint(115, 125),  # 11.5V - 12.5V
                loop_triggers=random.randint(0, 10),
                decoder_id=self.decoder_id
            )

            try:
                if self.conn:
                    self.conn.send(msg)
                    logger.debug("Sent STATUS message")
            except (BrokenPipeError, ConnectionResetError, OSError):
                # Connection lost, exit loop
                break

            time.sleep(self.status_interval)


def create_default_scenario() -> List[TransponderConfig]:
    """Create a default 3-transponder race scenario.

    Returns:
        List of transponder configurations
    """
    return [
        TransponderConfig(
            transponder_id=123456,
            avg_lap_time=25.5,
            variance=0.3,
            start_delay=0.0
        ),
        TransponderConfig(
            transponder_id=234567,
            avg_lap_time=27.2,
            variance=0.5,
            start_delay=0.2
        ),
        TransponderConfig(
            transponder_id=345678,
            avg_lap_time=29.8,
            variance=0.8,
            start_delay=0.5
        ),
    ]


def get_args():
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = ArgumentParser(description="Live AMB P3 Decoder Simulator")
    parser.add_argument(
        "-l", "--listen-address",
        help="IP address to bind on",
        default=DEFAULT_HOST,
        dest="host"
    )
    parser.add_argument(
        "-p", "--listen-port",
        help="Port to bind on",
        default=DEFAULT_PORT,
        dest="port",
        type=int
    )
    parser.add_argument(
        "-d", "--duration",
        help="Race duration in seconds (for reference, not enforced)",
        default=DEFAULT_DURATION,
        dest="duration",
        type=int
    )
    parser.add_argument(
        "--status-interval",
        help="STATUS message interval in seconds",
        default=DEFAULT_STATUS_INTERVAL,
        dest="status_interval",
        type=float
    )
    parser.add_argument(
        "--decoder-id",
        help="Decoder ID (hex)",
        default=hex(DEFAULT_DECODER_ID),
        dest="decoder_id",
        type=lambda x: int(x, 16)
    )
    parser.add_argument(
        "-v", "--verbose",
        help="Enable verbose (debug) logging",
        action="store_true",
        dest="verbose"
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = get_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info("Live AMB P3 Decoder Simulator - Phase 1")
    logger.info("=" * 60)
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    logger.info(f"Decoder ID: {hex(args.decoder_id)}")
    logger.info(f"STATUS interval: {args.status_interval}s")
    logger.info(f"Race duration (reference): {args.duration}s")
    logger.info("=" * 60)

    # Create default scenario
    transponder_configs = create_default_scenario()
    logger.info("Default scenario: 3 transponders")
    for config in transponder_configs:
        logger.info(f"  - ID {config.transponder_id}: "
                   f"avg lap {config.avg_lap_time:.1f}s ± {config.variance:.1f}s, "
                   f"start delay {config.start_delay:.1f}s")

    scenario_manager = ScenarioManager(transponder_configs, track_length=100.0)

    server = LiveDecoderServer(
        host=args.host,
        port=args.port,
        scenario_manager=scenario_manager,
        decoder_id=args.decoder_id,
        status_interval=args.status_interval
    )

    server.start()


if __name__ == "__main__":
    main()
