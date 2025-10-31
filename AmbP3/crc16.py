#!/usr/bin/python

from sys import argv
from sys import exit
from .logs import Logg

logger = Logg.create_logger("crc16")

POLY = 0x1021
START = 0xFFFF


def table():
    crctable = []
    for i in range(256):
        crc = i << 8
        for j in range(8):
            crc = (
                (0xFFFF & crc << 1) ^ (POLY if ((crc & 0x8000) != 0) else 0)
            ) & 0xFFFF
        crctable.append(crc)
    return crctable


def calc(msg, tbl):
    try:
        ba = bytearray.fromhex(msg)
    except ValueError:
        logger.error(f"msg: {msg} can not be evaluated as hex")

    crc = START
    for b in ba:
        crc = 0xFFFF & (tbl[(crc >> 8) & 0xFF] ^ (0xFFFF & crc << 8) ^ b)
    return (crc << 8 & 0xFFFF) | (crc >> 8)


if __name__ == "__main__":
    if len(argv) < 2:
        logger.error("provide argument string represenation of a hex msg")
        exit(1)
    else:
        msg = argv[1]
        result = hex(calc(msg, table()))
        logger.info(f"msg: {msg}\nresult:{result}")
