import socket
import codecs


from sys import exit
from . import records
from .logs import Logg
from . import crc16

logger = Logg.create_logger("decoder")


class Connection:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.socket = socket.socket()

    def close(self):
        self.socket.close()

    def connect(self, timeout=5.0):
        """Connect to decoder with configurable timeout.

        Args:
            timeout: Socket timeout in seconds (default: 5.0)
        """
        try:
            self.socket.settimeout(timeout)
            self.socket.connect((self.ip, self.port))
        except ConnectionRefusedError as error:
            logger.error(
                "Can not connect to {}:{}. {}".format(self.ip, self.port, error)
            )
            exit(1)
        except (socket.timeout, socket.error) as error:
            logger.error(
                "Error occurred while trying to communicate with  {}:{}:{}".format(
                    self.ip, self.port, error
                )
            )
            exit(1)

    def split_records(self, data):
        """some times server send 2 records in one message
        concatenated, you can find those by '8f8e' EOR and SOR next to each other"""
        byte_array = bytearray(data)
        size = len(byte_array)
        split_data = [bytearray()]
        for index, byte in enumerate(byte_array):
            if index != size - 1 and byte == 143 and byte_array[index + 1] == 142:
                logger.debug("found delimeter byte 143,142 b'8f8e'")
                split_data[-1].append(byte)
                split_data.append(bytearray())
                logger.debug("start new record")
            else:
                split_data[-1].append(byte)
        return split_data

    def read(self, bufsize=10240):
        """Read data from socket with timeout handling.

        Args:
            bufsize: Buffer size for recv (default: 10240)

        Returns:
            List of bytearrays containing split records
        """
        try:
            data = self.socket.recv(bufsize)
        except socket.timeout:
            logger.debug("Socket timeout while reading, no data available")
            return []  # Return empty list on timeout
        except socket.error as e:
            logger.error(f"Error reading from socket: {e}")
            exit(1)

        if data == b"":
            msg = "No data received, it seems socket got closed"
            logger.info("{}".format(msg))
            self.socket.close()
            exit(1)
        return self.split_records(data)

    def write(self, data):
        try:
            data = self.socket.send(data)
        except socket.error:
            logger.error("Error write from socket")
            exit(1)
        except socket.timeout:
            logger.error("Socket closed while reading")


def hex_to_binary(data):
    bin_str = bin(int(data, 16))
    byte_str = int(bin_str, 2).to_bytes((len(bin_str) // 8), "big")
    return byte_str


def bin_to_decimal(bin_data):
    return int(bin_data.decode(), 16)


def bin_data_to_ascii(bin_data):
    "Converts binary input HEX data into ascii"
    data = codecs.encode(bin_data, "hex")
    decoded_data = data.decode("ascii")
    return "{}".format(decoded_data)


def bin_dict_to_ascii(dict):
    "takes as input Dict with Binary values, converts into ascii, returns converted dict"
    for key, value in dict.items():
        dict[key] = bin_data_to_ascii(value)
    return dict


def p3decode(data):
    def _validate(data):
        "perform validation checks and return ready to process data or None"
        data = _check_crc(data) if data is not None else None
        logger.debug("P3decode function decoding: {}".format(data.hex()))
        data = _unescape(data) if data is not None else None
        data = _check_length(data) if data is not None else None
        return data

    def _check_crc(data):
        """Check CRC integrity of the packet.

        CRC is computed on the entire packet (including SOR and EOR bytes)
        with CRC bytes set to 0x00, as per AMB P3 protocol specification.

        Args:
            data: Raw packet data as bytes

        Returns:
            data if CRC is valid, None if CRC check fails
        """
        if len(data) < 6:
            logger.warning("Packet too short for CRC check")
            return None

        # Extract CRC from header (bytes 4-6, little-endian)
        packet_crc_bytes = data[4:6]
        packet_crc = int.from_bytes(packet_crc_bytes, byteorder='little')

        # Create a copy of the data with CRC bytes zeroed out
        data_for_crc = bytearray(data)
        data_for_crc[4:6] = b'\x00\x00'

        # Calculate CRC using the existing crc16 module
        crc_table = crc16.table()
        calculated_crc = crc16.calc(data_for_crc.hex(), crc_table)

        if calculated_crc != packet_crc:
            logger.error(
                f"CRC check failed: packet CRC={hex(packet_crc)}, "
                f"calculated CRC={hex(calculated_crc)}"
            )
            return None

        logger.debug(f"CRC check passed: {hex(packet_crc)}")
        return data

    def _unescape(data):
        "If the value is 0x8d, 0x8e or 0x8f and it's not the first or last byte of the message,\
         the value is prefixed/escaped by 0x8D followed by the byte value plus 0x20."
        new_data = bytearray(data)[
            1:-1
        ]  # first and last character should not be escaped
        escaped_data = bytearray()
        escape_next = False
        for byte in new_data:
            if escape_next:
                escaped_data.append(byte - 32)
                escape_next = False
                continue
            if byte in [141, 141, 142]:
                escape_next = True
            else:
                escaped_data.append(byte)
        escaped_data.insert(0, 142)  # INSERT THE SOR Start of Record
        escaped_data.append(143)  # INSERT THE EOR End of Record
        return bytes(escaped_data)

    def _check_length(data):
        "check if data is of correct length"
        return data

    def _get_header(data):
        str_header = data[0:10]
        header = {
            "SOR": str_header[0:1],
            "Version": str_header[1:2],
            "Length": str_header[2:4][::-1],  # [::-1] invert the hex ...
            "CRC": str_header[4:6][::-1],
            "Flags": str_header[6:8][::-1],
            "TOR": str_header[8:10][::-1],
        }
        return header

    def _decode_record(tor, tor_body):
        """record type is always followed by 1 byte representing the record length"""
        hex_tor = codecs.encode(tor, "hex")
        logger.info("tor:{} converted to hex_tor: {}".format(tor, hex_tor))
        if hex_tor in records.type_of_records:
            tor_name = records.type_of_records[hex_tor]["tor_name"]
            tor_fields = records.type_of_records[hex_tor]["tor_fields"]
            DECODED = {"TOR": tor_name}
        else:
            logger.error("{} record_type unknown".format(hex_tor))
            return {"undecoded_tor_body": tor_body}

        general_fields = records.GENERAL
        tor_fields = {**general_fields, **tor_fields}
        tor_body = bytearray(tor_body)
        while len(tor_body) > 0:
            """continuously read the MSG
            1) take first byte and check if it exists in TOR FIELDS
            2) if exists capture record_attr
            3) capture record_attr_length ( length is always next byte after record_attr
            4) capture record_attr_value ( this is after record_attr_length )
            5) truncate the TOR by decoded info
            """
            one_byte = tor_body[0:1]
            one_byte_hex = codecs.encode(one_byte, "hex")
            if one_byte_hex in tor_fields:
                record_attr = tor_fields[one_byte_hex]
            elif one_byte_hex == b"8f":  # records always end in 8f
                tor_body = []  # null tor_body and continue so we can exit the loop
                continue
            else:
                hex_tor = codecs.encode(tor, "hex")
                hex_tor_body = tor_body.hex()
                logger.error(
                    "DECODE FAILED. TOR: {}, TOR_BODY: {}".format(hex_tor, hex_tor_body)
                )
                record_attr = "UNDECODED_" + one_byte_hex.decode()

            """record type is always followed by 1 byte representing the record length"""
            record_attr_length = int(codecs.encode(tor_body[1:2], "hex"))
            record_attr_value = codecs.encode(
                tor_body[2 : 2 + record_attr_length][::-1], "hex"
            )
            del tor_body[: 2 + record_attr_length]
            DECODED[record_attr] = (
                record_attr_value if len(record_attr_value) > 0 else ""
            )
        return DECODED

    def _decode_body(tor, data):
        tor_body = _get_tor_body(data)
        try:
            result = _decode_record(tor, tor_body)
            return {"RESULT": result}
        except ValueError:
            hex_tor = codecs.encode(tor, "hex")
            hex_tor_body = tor_body.hex()
            logger.error(
                "DECODE FAILED. TOR: {}, TOR_BODY: {}".format(hex_tor, hex_tor_body)
            )
            return {"RESULT": {}}

    def _get_tor_body(data):
        tor_body = data[10:]
        return tor_body

    data = _validate(data)
    if data is not None:
        decoded_header = _get_header(data)
        tor = decoded_header["TOR"]
        decoded_body = _decode_body(tor, data)
        return decoded_header, decoded_body
    else:
        return data, data
